"""Hybrid OpenAI + AU validator pipeline.

Drop-in replacement for the `PIIDetector` that runs:

    text → openai/privacy-filter (GPU)
         → [optional llama3.1:8b narrative pass — gated]
         → AU resolver (account_number/secret → TFN/ABN/MRN/etc + checksum)
         → regex supplement (username, AU phone/address, missed structured)
         → merge spans (same merge logic as the stock detector)
         → return PIISpan list

Phase 2.y adds a confidence gate so the llama narrative pass only runs
when it's likely to add coverage. The cheap openai head runs on every
document (~110 ms on RTX); the 2.5-4 s/doc llama call is reserved for
narrative-heavy or low-confidence documents. Gate modes:

- ``confidence`` (default): invoke llama when the document looks
  narrative-heavy (>= MIN_TOKENS tokens) OR any openai span score is
  below MIN_SCORE OR the text contains clinical/legal narrative cues
  (titles, "the patient", "diagnosed with", etc.).
- ``always``: invoke llama on every document (v0.3.0 behaviour).
- ``never``: skip llama unconditionally (v0.2.0 behaviour).

The result plugs into the existing Pipeline class so the
audit + redactor layers stay identical.
"""
from __future__ import annotations

import logging
import os
import re

from ..audit import AuditLog
from ..config import Config
from ..detector import PIIDetector
from ..models import PIISpan
from ..pipeline import Pipeline
from ..redactor import Redactor
from .au_resolver import resolve_account_numbers
from .llama_pass import LlamaNERPass
from .openai_backend import OpenAIPrivacyFilter
from .regex_supplement import supplement_with_regex

logger = logging.getLogger(__name__)


# Phase 2.y gate defaults. Tuned against Gretel-100 + Medical-50 — the
# narrative cue list matches the clinical/legal language that the openai
# head systematically under-extracts on.
GATE_MODE_CONFIDENCE = "confidence"
GATE_MODE_ALWAYS = "always"
GATE_MODE_NEVER = "never"
VALID_GATE_MODES = frozenset({GATE_MODE_CONFIDENCE, GATE_MODE_ALWAYS, GATE_MODE_NEVER})

DEFAULT_GATE_MODE = GATE_MODE_CONFIDENCE
DEFAULT_GATE_MIN_SCORE = 0.85
DEFAULT_GATE_MIN_TOKENS = 50

# Narrative cues — substrings (case-insensitive). The presence of any one
# of these is a strong signal the document is a clinical/legal/casework
# narrative where the openai head systematically under-recalls names,
# addresses, and DOBs that llama's prompt-driven pass recovers.
_NARRATIVE_CUE_PATTERN = re.compile(
    r"\b("
    r"the patient|the client|the customer|the resident|"
    r"patient\s+[A-Z]|client\s+[A-Z]|resident\s+[A-Z]|"
    r"diagnosed with|presenting with|admitted (to|with|for)|"
    r"discharged|located at|residing at|born on|date of birth|"
    r"\bdob\b|"
    r"named|known as|"
    r"dr\.?\s+[A-Z]|mr\.?\s+[A-Z]|mrs\.?\s+[A-Z]|ms\.?\s+[A-Z]|"
    r"prof\.?\s+[A-Z]|a/prof\.?\s+[A-Z]|"
    r"clinician|physician|psychiatrist|"
    r"the deceased|the defendant|the plaintiff|the applicant|"
    r"mrn[-:]"
    r")",
    re.IGNORECASE,
)


def _env_truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() or default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _token_count(text: str) -> int:
    """Cheap whitespace-token count. Fast on a 1k-char doc (~10 us)."""
    if not text:
        return 0
    return len(text.split())


def _has_narrative_cue(text: str) -> bool:
    """True if the document contains any clinical/legal narrative cue."""
    if not text:
        return False
    return bool(_NARRATIVE_CUE_PATTERN.search(text))


def should_invoke_llama(
    text: str,
    openai_scores: list[float],
    *,
    mode: str = DEFAULT_GATE_MODE,
    min_score: float = DEFAULT_GATE_MIN_SCORE,
    min_tokens: int = DEFAULT_GATE_MIN_TOKENS,
) -> tuple[bool, str]:
    """Phase 2.y gate predicate. Returns (invoke?, reason).

    The reason string is suitable for logging at DEBUG. Pure function —
    no IO, no env reads — so it's straightforward to unit-test.

    Decision tree (confidence mode):

    1. If openai had any below-MIN_SCORE span → invoke (calibrated head
       is hedging, llama may recover the right span).
    2. If text contains a narrative cue → invoke.
    3. If token count >= MIN_TOKENS → invoke (long-form doc, likely has
       narrative PII the openai head missed).
    4. Otherwise skip — structured/short doc, openai + regex + resolver
       have it covered.
    """
    if mode == GATE_MODE_ALWAYS:
        return True, "mode=always"
    if mode == GATE_MODE_NEVER:
        return False, "mode=never"
    # confidence mode
    if openai_scores:
        lo = min(openai_scores)
        if lo < min_score:
            return True, f"openai_min_score={lo:.3f}<{min_score:.3f}"
    if _has_narrative_cue(text):
        return True, "narrative_cue"
    n_tokens = _token_count(text)
    if n_tokens >= min_tokens:
        return True, f"tokens={n_tokens}>={min_tokens}"
    return False, f"skip(tokens={n_tokens},spans={len(openai_scores)})"


class HybridDetector:
    """End-to-end PII detector using OpenAI Privacy Filter + AU validators.

    Phase 2.x: optional parallel llama3.1:8b narrative NER pass. Both NERs
    run on the GPU; the union of their spans flows through the AU
    resolver so any narrative PII (names, addresses, DOBs) the calibrated
    OpenAI head missed is recovered from llama's prompt-driven extraction.
    """

    def __init__(
        self,
        openai_backend: OpenAIPrivacyFilter | None = None,
        use_regex_supplement: bool = True,
        llama_pass: LlamaNERPass | None = None,
        use_llama_pass: bool | None = None,
        gate_mode: str | None = None,
        gate_min_score: float | None = None,
        gate_min_tokens: int | None = None,
    ):
        self.openai = openai_backend or OpenAIPrivacyFilter()
        self.use_regex_supplement = use_regex_supplement
        if use_llama_pass is None:
            use_llama_pass = _env_truthy("PIIR_LLAMA_ENABLED", True)
        self.use_llama_pass = use_llama_pass
        if self.use_llama_pass:
            self.llama = llama_pass or LlamaNERPass()
        else:
            self.llama = None
        # Phase 2.y gate config — env knobs take effect at __init__ time so
        # the gate state is observable via /info on the FastAPI service.
        if gate_mode is None:
            gate_mode = _env_str("PIIR_LLAMA_GATE", DEFAULT_GATE_MODE)
        if gate_mode not in VALID_GATE_MODES:
            logger.warning(
                "Unknown PIIR_LLAMA_GATE=%r, falling back to %r",
                gate_mode,
                DEFAULT_GATE_MODE,
            )
            gate_mode = DEFAULT_GATE_MODE
        self.gate_mode = gate_mode
        self.gate_min_score = (
            gate_min_score
            if gate_min_score is not None
            else _env_float("PIIR_LLAMA_GATE_MIN_SCORE", DEFAULT_GATE_MIN_SCORE)
        )
        self.gate_min_tokens = (
            gate_min_tokens
            if gate_min_tokens is not None
            else _env_int("PIIR_LLAMA_GATE_MIN_TOKENS", DEFAULT_GATE_MIN_TOKENS)
        )
        # Lightweight runtime stats for observability — incremented per
        # .detect() call. Surfaced via .gate_stats() and (in the FastAPI
        # layer) the /health response.
        self._gate_invocations = 0
        self._gate_skips = 0

    # The interface PIIDetector exposes is .detect(text) -> list[PIISpan].
    # We mirror that exactly so HybridDetector slots into Pipeline unchanged.

    def detect(self, text: str) -> list[PIISpan]:
        if not text:
            return []

        # 1a. Calibrated NER pass (GPU, openai/privacy-filter). Use the
        # score-bearing variant so the gate can inspect per-span confidence.
        # Fall back to plain predict() (score=1.0) for backends that don't
        # implement the scored API — keeps test doubles + custom backends
        # working unchanged.
        scored_fn = getattr(self.openai, "predict_with_scores", None)
        if callable(scored_fn):
            scored = scored_fn(text)
            raw_spans: list[tuple[str, int, int, str]] = [
                (c, s, e, v) for (c, s, e, v, _sc) in scored
            ]
            openai_scores = [sc for (_c, _s, _e, _v, sc) in scored]
        else:
            raw_spans = list(self.openai.predict(text))
            openai_scores = [1.0] * len(raw_spans)

        # 1b. Narrative NER pass (GPU, llama3.1:8b via Ollama). Gated —
        # only invoked when the gate predicate says so. Soft-fails to
        # empty list when Ollama is unreachable.
        if self.llama is not None:
            invoke, reason = should_invoke_llama(
                text,
                openai_scores,
                mode=self.gate_mode,
                min_score=self.gate_min_score,
                min_tokens=self.gate_min_tokens,
            )
            if invoke:
                self._gate_invocations += 1
                logger.debug("llama gate: invoke (%s)", reason)
                try:
                    raw_spans.extend(self.llama.predict(text))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("llama narrative pass failed: %s", exc)
            else:
                self._gate_skips += 1
                logger.debug("llama gate: skip (%s)", reason)

        # 2. Resolve OpenAI's account_number / secret into precise AU
        # sub-categories using checksum validators where applicable.
        spans = resolve_account_numbers(raw_spans, text)

        # 3. Supplement with the AU regex layer for username + AU patterns.
        # The supplement function knows when to override OpenAI's category
        # (currently: username override of name) — it emits a regex span
        # that competes against the OpenAI span in the merge step below.
        if self.use_regex_supplement:
            spans.extend(supplement_with_regex(text, spans))

        # 4. Merge / dedupe overlapping spans. Among equally-sized overlaps,
        # spans with a passing validator and AU-specific categories win.
        return self._merge_with_au_priority(spans)

    @staticmethod
    def _merge_with_au_priority(spans: list[PIISpan]) -> list[PIISpan]:
        """Variant of PIIDetector._merge that prefers AU-specific categories
        on ties, so e.g. a regex USERNAME hit beats an OpenAI NAME hit at
        the same span.
        """
        from ..models import PIICategory

        # Score: higher = more specific
        SPECIFICITY: dict[PIICategory, int] = {
            PIICategory.USERNAME: 100,
            PIICategory.TFN: 100,
            PIICategory.ABN: 100,
            PIICategory.ACN: 100,
            PIICategory.MEDICARE: 100,
            PIICategory.HEALTHCARE_IDENTIFIER: 100,
            PIICategory.MEDICAL_RECORD_NUMBER: 100,
            PIICategory.PASSPORT: 90,
            PIICategory.DRIVER_LICENCE: 90,
            PIICategory.CRN: 90,
            PIICategory.BSB_ACCOUNT: 80,
            PIICategory.NAME: 50,
            PIICategory.GENERIC_ID: 10,
        }
        if not spans:
            return []
        seen: set[tuple[int, int, str]] = set()
        unique: list[PIISpan] = []
        for s in spans:
            key = (s.start, s.end, s.category.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
        unique.sort(key=lambda s: (s.start, -(s.end - s.start)))

        merged: list[PIISpan] = []
        for span in unique:
            if not merged:
                merged.append(span)
                continue
            last = merged[-1]
            if span.overlaps(last):
                same_range = (span.start == last.start and span.end == last.end)
                if same_range:
                    # Pick the more specific category
                    if SPECIFICITY.get(span.category, 0) > SPECIFICITY.get(
                        last.category, 0
                    ):
                        merged[-1] = span
                    continue
                # Different sized overlap: keep the original "prefer longer"
                if len(span) > len(last):
                    merged[-1] = span
                elif len(span) == len(last) and (
                    span.validator_passed and not last.validator_passed
                ):
                    merged[-1] = span
            else:
                merged.append(span)
        return merged

    @property
    def name(self) -> str:
        if self.llama is not None:
            return (
                f"hybrid({self.openai.name}+{self.llama.name}"
                f",gate={self.gate_mode})"
            )
        return f"hybrid({self.openai.name})"

    def gate_stats(self) -> dict:
        """Return cumulative gate invocation stats for /health + bench logs."""
        total = self._gate_invocations + self._gate_skips
        return {
            "mode": self.gate_mode,
            "min_score": self.gate_min_score,
            "min_tokens": self.gate_min_tokens,
            "llama_invocations": self._gate_invocations,
            "llama_skips": self._gate_skips,
            "llama_invoke_rate": (
                self._gate_invocations / total if total > 0 else 0.0
            ),
            "documents_processed": total,
        }

    def warmup(self) -> None:
        self.openai.warmup()
        if self.llama is not None:
            try:
                self.llama.warmup()
            except Exception as exc:  # noqa: BLE001
                logger.warning("llama narrative pass warmup failed: %s", exc)


def build_hybrid_pipeline(
    config: Config | None = None,
    openai_backend: OpenAIPrivacyFilter | None = None,
    use_regex_supplement: bool = True,
    warmup: bool = True,
    llama_pass: LlamaNERPass | None = None,
    use_llama_pass: bool | None = None,
    gate_mode: str | None = None,
    gate_min_score: float | None = None,
    gate_min_tokens: int | None = None,
) -> Pipeline:
    """Construct a Pipeline that uses the hybrid detector.

    The resulting Pipeline has the same interface as the LLM-backed one and
    is drop-in-compatible with the FastAPI service.
    """
    cfg = config or Config.from_env()
    backend = openai_backend or OpenAIPrivacyFilter()
    detector = HybridDetector(
        openai_backend=backend,
        use_regex_supplement=use_regex_supplement,
        llama_pass=llama_pass,
        use_llama_pass=use_llama_pass,
        gate_mode=gate_mode,
        gate_min_score=gate_min_score,
        gate_min_tokens=gate_min_tokens,
    )
    if warmup:
        try:
            detector.warmup()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Hybrid detector warmup failed (continuing cold): %s", exc)

    redactor = Redactor(style=cfg.placeholder_style)
    audit = AuditLog(
        path=cfg.audit_log_path,
        encryption_key=cfg.audit_encryption_key,
        enabled=cfg.audit_enabled,
    )
    return Pipeline(
        detector=detector,  # type: ignore[arg-type]
        redactor=redactor,
        audit=audit,
        model_name=detector.name,
    )
