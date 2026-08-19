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
from ..models import PIISpan
from ..pipeline import Pipeline
from ..redactor import Redactor
from .au_org_loc import supplement_org_loc
from .au_resolver import resolve_account_numbers
from .llama_pass import LlamaNERPass
from .openai_backend import OpenAIPrivacyFilter
from .regex_supplement import supplement_with_regex
from .vllm_pass import VLLMNERPass, select_llama_backend


def _select_openai_backend(
    backend: str | None = None,
    adapter_path: str | None = None,
) -> OpenAIPrivacyFilter:
    """Pick OpenAI/Privacy-Filter backend variant based on ``PIIR_BACKEND``.

    Returns:
      - ``FinetunedOpenAIBackend(adapter_path=...)`` if backend == ``transformers_au_finetuned``
      - ``OpenAIPrivacyFilter()`` otherwise (the base / "transformers_au" path)

    The finetuned path soft-falls back to the base if the adapter dir is
    missing — preserves liveness so a misconfigured deployment still works.
    """
    requested = (backend or os.environ.get("PIIR_BACKEND", "")).lower()
    if requested == "transformers_au_gliner":
        # License-clean Apache-2.0 GLiNER substrate (bake-off winner). Distinct
        # architecture from the HF token-classification path, so it ships its own
        # backend; the AU moat + regex floor + merge + fail-closed sit on top.
        from .gliner_backend import GlinerBackend  # noqa: PLC0415

        return GlinerBackend()
    if requested == "transformers_au_finetuned":
        from .finetuned_backend import FinetunedOpenAIBackend  # noqa: PLC0415

        try:
            return FinetunedOpenAIBackend(adapter_path=adapter_path)
        except FileNotFoundError as exc:
            logger.warning(
                "LoRA adapter unavailable (%s); falling back to base openai/privacy-filter",
                exc,
            )
            return OpenAIPrivacyFilter()
    return OpenAIPrivacyFilter()


logger = logging.getLogger(__name__)


# Phase 2.y gate defaults. Tuned against Gretel-100 + Medical-50 — the
# narrative cue list matches the clinical/legal language that the openai
# head systematically under-extracts on.
GATE_MODE_CONFIDENCE = "confidence"
GATE_MODE_ALWAYS = "always"
GATE_MODE_NEVER = "never"
VALID_GATE_MODES = frozenset({GATE_MODE_CONFIDENCE, GATE_MODE_ALWAYS, GATE_MODE_NEVER})

DEFAULT_GATE_MODE = GATE_MODE_CONFIDENCE
# Tuned for: zero Gretel leak regression + Medical 100% + max llama-skip rate.
# Score threshold 0.7 (not 0.85) — only spans the openai head is *genuinely*
# hedging on flip the gate. 0.85 turned out to fire on almost every doc.
DEFAULT_GATE_MIN_SCORE = 0.70
# Token floor 200 (not 50) — short structured form docs (the bulk of
# Gretel-100) get the v0.2.0 fast path; only longer narrative docs invoke
# the llama pass.
DEFAULT_GATE_MIN_TOKENS = 200

# Narrative cues — substrings (case-insensitive). Deliberately CLINICAL-
# and LEGAL-ONLY: words / phrases that almost never appear in structured
# financial / form data but always appear in casework narrative. Generic
# verbs like "born on", "located at", titles like "Mr.", "Ms.", "Dr."
# were tested and over-fired — they appear in every Gretel-100 fixture
# doc and would defeat the gate entirely.
_NARRATIVE_CUE_PATTERN = re.compile(
    r"\b("
    r"the patient|the client(?!'s account)|the resident|"
    r"patient\s+[A-Z][a-z]+|the deceased|the defendant|the plaintiff|"
    r"diagnosed with|presenting with|presented with|"
    r"admitted (to|with|for|after)|discharged from|"
    r"clinician|physician|psychiatrist|outpatient|inpatient|"
    r"medical history|chief complaint|assessment and plan|"
    r"a/prof\.?\s+[A-Z][a-z]+|prof\.?\s+[A-Z][a-z]+|"
    r"dr\.?\s+[A-Z][a-z]+|"
    r"\bmrn[-:]\s*[A-Z0-9]"
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
    # 1. Narrative cues are the strongest signal — clinical/legal text
    #    where the calibrated head consistently under-recalls names + DOBs.
    if _has_narrative_cue(text):
        return True, "narrative_cue"
    # 2. Long documents — narrative PII tends to live in longer text.
    n_tokens = _token_count(text)
    if n_tokens >= min_tokens:
        return True, f"tokens={n_tokens}>={min_tokens}"
    # 3. Multi-span low confidence — at least two spans below the floor
    #    suggests systematic hedging (one is noise, two is signal).
    if openai_scores:
        below = [s for s in openai_scores if s < min_score]
        if len(below) >= 2:
            return True, (f"openai_low_conf={len(below)}<{min_score:.2f}")
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
        llama_pass: LlamaNERPass | VLLMNERPass | None = None,
        use_llama_pass: bool | None = None,
        gate_mode: str | None = None,
        gate_min_score: float | None = None,
        gate_min_tokens: int | None = None,
        llama_backend: str | None = None,
        backend: str | None = None,
        lora_adapter_path: str | None = None,
    ):
        # v0.4.0: pick FinetunedOpenAIBackend when backend=transformers_au_finetuned
        self.openai = openai_backend or _select_openai_backend(
            backend=backend, adapter_path=lora_adapter_path
        )
        self.use_regex_supplement = use_regex_supplement
        if use_llama_pass is None:
            use_llama_pass = _env_truthy("PIIR_LLAMA_ENABLED", True)
        self.use_llama_pass = use_llama_pass
        # v0.4.0: short-circuit when llama_backend == "disabled" AND no
        # explicit llama_pass was injected. Skips the health check and any
        # HTTP traffic — important because the default config no longer
        # ships with a llama endpoint reachable. Explicit injection (e.g.
        # for tests or custom deployments) takes precedence.
        effective_llama_backend = llama_backend or os.environ.get("PIIR_LLAMA_BACKEND", "disabled")
        if llama_pass is None and effective_llama_backend == "disabled":
            self.use_llama_pass = False
            self.llama = None
            self.llama_backend_name = "disabled"
            self._configure_gate(gate_mode, gate_min_score, gate_min_tokens)
            self._gate_invocations = 0
            self._gate_skips = 0
            return
        # Phase 2.z: select the llama narrative backend (vLLM / Ollama).
        # Explicit injection still wins so tests can pass in fakes; otherwise
        # respect PIIR_LLAMA_BACKEND (default: auto-detect vLLM, fall back).
        if self.use_llama_pass:
            if llama_pass is not None:
                self.llama = llama_pass
                # Best-effort identification of an injected pass for /info.
                self.llama_backend_name = (
                    "vllm"
                    if isinstance(llama_pass, VLLMNERPass)
                    else "ollama"
                    if isinstance(llama_pass, LlamaNERPass)
                    else "custom"
                )
            else:
                self.llama_backend_name, self.llama = select_llama_backend(llama_backend)
                if self.llama is None:
                    self.use_llama_pass = False
        else:
            self.llama = None
            self.llama_backend_name = "disabled"
        # Phase 2.y gate config (factored so v0.4.0 disabled-short-circuit reuses it)
        self._configure_gate(gate_mode, gate_min_score, gate_min_tokens)
        # Lightweight runtime stats for observability — incremented per
        # .detect() call. Surfaced via .gate_stats() and (in the FastAPI
        # layer) the /health response.
        self._gate_invocations = 0
        self._gate_skips = 0

    def _configure_gate(
        self,
        gate_mode: str | None,
        gate_min_score: float | None,
        gate_min_tokens: int | None,
    ) -> None:
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

    # The interface PIIDetector exposes is .detect(text) -> list[PIISpan].
    # We mirror that exactly so HybridDetector slots into Pipeline unchanged.

    def detect(self, text: str) -> list[PIISpan]:
        if not text:
            return []

        # 1a. Calibrated NER pass (GPU substrate). Use the score-bearing variant
        # so the gate can inspect per-span confidence. Fall back to plain
        # predict() (score=1.0) for backends that don't implement the scored API.
        # Wrapped: a substrate failure (cold model, OOM, unrecognised checkpoint
        # architecture) must NOT abort detection and pass raw text through —
        # audit 2026-06-26 caught exactly that fail-open. On failure we continue
        # to the unconditional regex floor below, which keeps the stack >= mock.
        raw_spans: list[tuple[str, int, int, str]] = []
        openai_scores: list[float] = []
        try:
            scored_fn = getattr(self.openai, "predict_with_scores", None)
            if callable(scored_fn):
                scored = scored_fn(text)
                raw_spans = [(c, s, e, v) for (c, s, e, v, _sc) in scored]
                openai_scores = [sc for (_c, _s, _e, _v, sc) in scored]
            else:
                raw_spans = list(self.openai.predict(text))
                openai_scores = [1.0] * len(raw_spans)
        except Exception as exc:  # noqa: BLE001
            logger.warning("substrate NER pass failed (regex floor only): %s", exc)

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

        # 3b. v0.4.1 — supplement with AU organisation + location
        # recognisers. Phase 5 closes the org (3-29%) and location (<60%)
        # recall gaps on the sector bench without retraining.
        if self.use_regex_supplement:
            spans.extend(supplement_org_loc(text, spans))

        # 3c. Unconditional regex floor — email/phone/AU IDs (validator-gated)
        # from the same regex_first_pass the mock backend uses. This is the
        # safety net that guarantees the hybrid stack is never WORSE than mock,
        # even when the substrate model is cold/failed (audit 2026-06-26
        # fail-open fix). The merge below dedupes any overlap with model spans.
        if self.use_regex_supplement:
            spans.extend(self._regex_floor(text))

        # 4. Merge / dedupe overlapping spans. Among equally-sized overlaps,
        # spans with a passing validator and AU-specific categories win.
        return self._merge_with_au_priority(spans, text)

    @staticmethod
    def _regex_floor(text: str) -> list[PIISpan]:
        """Validator-gated regex spans (email/phone/AU IDs) as an always-on floor.

        Applies the same validator + fail-closed ``needs_review`` logic the
        stock ``PIIDetector`` uses (DEFECT #3 fix): an AU ID-shaped token whose
        checksum fails is retained, flagged ``validator_passed=False`` /
        ``needs_review=True`` so the substrate path keeps mock's review signal.
        """
        from ..detector import PIIDetector
        from ..validators import regex_first_pass

        floor = [
            PIISpan(category=cat, start=start, end=end, value=value)
            for cat, start, end, value in regex_first_pass(text)
        ]
        return PIIDetector._apply_validators(floor)

    @staticmethod
    def _merge_with_au_priority(spans: list[PIISpan], text: str = "") -> list[PIISpan]:
        """Variant of PIIDetector._merge that prefers AU-specific categories
        on ties, so e.g. a regex USERNAME hit beats an OpenAI NAME hit at
        the same span.

        ``text`` is the source document; it is used only to confirm that a
        validated AU span which is shorter than an overlapping generic span
        leaves no PII (alphanumeric) characters uncovered before letting the AU
        span win (DEFECT #2 coverage guard).
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
            PIICategory.ADDRESS: 60,
            PIICategory.ORGANISATION: 55,  # v0.4.1
            PIICategory.LOCATION: 55,  # v0.4.1
            PIICategory.NAME: 50,
            PIICategory.GENERIC_ID: 10,
        }

        # DEFECT #2: validated AU-specific structured IDs must not lose to a
        # merely-LONGER generic substrate span. piiranha emits a `generic_id`
        # span that runs ~1 char wider than the AU regex floor (it eats
        # trailing punctuation); the old unconditional "prefer longer" let that
        # generic span clobber a checksum-validated medicare/passport/acn span.
        # These are the AU IDs whose category carries a checksum/structural
        # validation signal worth protecting.
        AU_SPECIFIC: frozenset[PIICategory] = frozenset(
            {
                PIICategory.TFN,
                PIICategory.ABN,
                PIICategory.ACN,
                PIICategory.MEDICARE,
                PIICategory.BSB_ACCOUNT,
                PIICategory.PASSPORT,
                PIICategory.DRIVER_LICENCE,
                PIICategory.CRN,
                PIICategory.HEALTHCARE_IDENTIFIER,
                PIICategory.MEDICAL_RECORD_NUMBER,
            }
        )
        # Generic substrate categories that should yield to a validated AU
        # span even when they happen to span one extra (punctuation) char.
        GENERIC_LOSERS: frozenset[PIICategory] = frozenset(
            {
                PIICategory.GENERIC_ID,
                PIICategory.NAME,
                PIICategory.USERNAME,
            }
        )

        def _overhang_is_punctuation(a: PIISpan, b: PIISpan) -> bool:
            """True if every char of `b` lying OUTSIDE `a`'s range is non-PII
            (not alphanumeric) — i.e. `b` is just `a` plus trailing/leading
            punctuation or whitespace. Conservative: if we have no source text,
            require full coverage instead (return False on any overhang)."""
            lead = text[b.start : a.start] if b.start < a.start else ""
            tail = text[a.end : b.end] if b.end > a.end else ""
            overhang = lead + tail
            if not text:
                return overhang == ""
            return not any(c.isalnum() for c in overhang)

        def _au_validated_beats_generic(a: PIISpan, b: PIISpan) -> bool:
            """True if span `a` is a validated AU-specific ID and `b` is a
            merely-generic span — `a` then wins even when `b` is longer.

            COVERAGE GUARD (fail-closed): the flip is allowed ONLY when `b`'s
            extent beyond `a` is pure punctuation/whitespace (piiranha's generic
            span eating a trailing period). A validated-but-SHORTER AU span whose
            generic neighbour covers REAL extra digits (e.g. a 6-digit BSB prefix
            of a longer failed TFN run) must NOT win — this merge keeps the
            winner's own offsets (no union), so stripping the longer span would
            leak the uncovered digits into cleartext.
            """
            return (
                a.category in AU_SPECIFIC
                and a.validator_passed is True
                and b.category in GENERIC_LOSERS
                and _overhang_is_punctuation(a, b)
            )

        def _same_range_rank(s: PIISpan) -> tuple[int, int, int]:
            """Tie-break key for spans occupying the SAME range; higher wins.

            DEFECT #2: at the same range piiranha's generic span and the AU
            regex floor collide. A span whose checksum PASSED must beat one
            whose checksum FAILED (acn-passed vs tfn-failed), and an AU-specific
            structured ID must beat a USERNAME/GENERIC_ID shape it happens to
            also match (passport vs username). SPECIFICITY breaks remaining
            ties (keeps the original USERNAME-over-NAME behaviour intact).
            """
            return (
                1 if s.validator_passed is True else 0,
                1 if s.category in AU_SPECIFIC else 0,
                SPECIFICITY.get(s.category, 0),
            )

        if not spans:
            return []
        # Deduplicate exact (start,end,category) collisions. The SAME AU ID is
        # emitted by both the regex supplement (validator_passed=None) and the
        # regex floor (validator_passed + needs_review applied). DEFECT #3:
        # collapse them onto the first-seen span but fold in the fail-closed
        # review flag and any definite validator verdict from the duplicate,
        # so the floor's needs_review can't be silently dropped here.
        seen: dict[tuple[int, int, str], PIISpan] = {}
        unique: list[PIISpan] = []
        for s in spans:
            key = (s.start, s.end, s.category.value)
            kept = seen.get(key)
            if kept is not None:
                kept.needs_review = kept.needs_review or s.needs_review
                if kept.validator_passed is None and s.validator_passed is not None:
                    kept.validator_passed = s.validator_passed
                    kept.confidence = min(kept.confidence, s.confidence)
                continue
            seen[key] = s
            unique.append(s)
        unique.sort(key=lambda s: (s.start, -(s.end - s.start)))

        merged: list[PIISpan] = []
        for span in unique:
            if not merged:
                merged.append(span)
                continue
            last = merged[-1]
            if span.overlaps(last):
                same_range = span.start == last.start and span.end == last.end
                if same_range:
                    # Pick by validated-first, AU-specific, then specificity.
                    # The winner keeps its OWN needs_review — a different-category
                    # interpretation of the SAME digits that failed its checksum
                    # (e.g. a tfn-reading of a valid acn) must not stamp review
                    # onto a span that validated cleanly (mirrors stock _merge,
                    # which only propagates review when bounds actually grow).
                    if _same_range_rank(span) > _same_range_rank(last):
                        merged[-1] = span
                    continue
                # DEFECT #3: on a DIFFERENT-sized overlap the longer span can
                # absorb a shorter flagged one (losing its coverage). The
                # fail-closed review flag must survive that absorption, so
                # OR-propagate it across the kept span. This is the substrate
                # analogue of stock _merge's `keep.needs_review |= other...`.
                review = span.needs_review or last.needs_review
                # DEFECT #2: a validated AU-specific ID must NOT lose to a
                # merely-longer generic span. The generic substrate span runs
                # ~1 char wider (it eats trailing punctuation); without this
                # guard "prefer longer" mislabels the AU ID and widens past the
                # validated token. Prefer the AU span and its tighter offsets.
                if _au_validated_beats_generic(span, last):
                    merged[-1] = span
                elif _au_validated_beats_generic(last, span):
                    pass  # keep `last` (the validated AU span)
                # Otherwise keep the original "prefer longer" behaviour — the
                # correct rule for real multi-token entities (ADDRESS, NAME,
                # ORGANISATION) where the longer span is genuinely right.
                elif len(span) > len(last):
                    merged[-1] = span
                elif len(span) == len(last) and (
                    span.validator_passed and not last.validator_passed
                ):
                    merged[-1] = span
                merged[-1].needs_review = review
            else:
                merged.append(span)
        return merged

    @property
    def name(self) -> str:
        if self.llama is not None:
            return f"hybrid({self.openai.name}+{self.llama.name},gate={self.gate_mode})"
        return f"hybrid({self.openai.name})"

    def gate_stats(self) -> dict:
        """Return cumulative gate invocation stats for /health + bench logs."""
        total = self._gate_invocations + self._gate_skips
        stats: dict = {
            "mode": self.gate_mode,
            "min_score": self.gate_min_score,
            "min_tokens": self.gate_min_tokens,
            "llama_invocations": self._gate_invocations,
            "llama_skips": self._gate_skips,
            "llama_invoke_rate": (self._gate_invocations / total if total > 0 else 0.0),
            "documents_processed": total,
        }
        backend = getattr(self, "llama_backend_name", None)
        if backend:
            stats["llama_backend"] = backend
            llama_obj = self.llama
            if isinstance(llama_obj, VLLMNERPass):
                stats["vllm_model"] = llama_obj.model
                stats["vllm_quant"] = llama_obj.quant
                stats["vllm_base_url"] = llama_obj.base_url
            elif isinstance(llama_obj, LlamaNERPass):
                stats["ollama_model"] = llama_obj.model
                stats["ollama_base_url"] = llama_obj.base_url
        return stats

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
    llama_pass: LlamaNERPass | VLLMNERPass | None = None,
    use_llama_pass: bool | None = None,
    gate_mode: str | None = None,
    gate_min_score: float | None = None,
    gate_min_tokens: int | None = None,
    llama_backend: str | None = None,
) -> Pipeline:
    """Construct a Pipeline that uses the hybrid detector.

    The resulting Pipeline has the same interface as the LLM-backed one and
    is drop-in-compatible with the FastAPI service.
    """
    cfg = config or Config.from_env()
    # v0.4.0: backend selection routed through the detector so the finetuned
    # path is picked up automatically when PIIR_BACKEND=transformers_au_finetuned.
    backend = openai_backend or _select_openai_backend(
        backend=cfg.backend, adapter_path=cfg.lora_adapter_path
    )
    detector = HybridDetector(
        openai_backend=backend,
        use_regex_supplement=use_regex_supplement,
        llama_pass=llama_pass,
        use_llama_pass=use_llama_pass,
        gate_mode=gate_mode,
        gate_min_score=gate_min_score,
        gate_min_tokens=gate_min_tokens,
        llama_backend=llama_backend,
        backend=cfg.backend,
        lora_adapter_path=cfg.lora_adapter_path,
    )
    if warmup:
        try:
            detector.warmup()
        except Exception as exc:  # noqa: BLE001
            # Fail-closed switch (audit 2026-06-26): a substrate that won't load
            # previously "continued cold" and silently emitted unredacted output
            # for generic PII. With PIIR_REQUIRE_SUBSTRATE set, refuse to serve a
            # degraded redactor — fail the deploy loudly instead.
            if _env_truthy("PIIR_REQUIRE_SUBSTRATE", default=False):
                raise RuntimeError(
                    "substrate warmup failed and PIIR_REQUIRE_SUBSTRATE is set; "
                    f"refusing to serve a cold/degraded redactor: {exc}"
                ) from exc
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
