"""Hybrid OpenAI + AU validator pipeline.

Drop-in replacement for the `PIIDetector` that runs:

    text → openai/privacy-filter (GPU)
         → AU resolver (account_number/secret → TFN/ABN/MRN/etc + checksum)
         → regex supplement (username, AU phone/address, missed structured)
         → merge spans (same merge logic as the stock detector)
         → return PIISpan list

The result plugs into the existing Pipeline class so the
audit + redactor layers stay identical.
"""
from __future__ import annotations

import logging

from ..audit import AuditLog
from ..config import Config
from ..detector import PIIDetector
from ..models import PIISpan
from ..pipeline import Pipeline
from ..redactor import Redactor
from .au_resolver import resolve_account_numbers
from .openai_backend import OpenAIPrivacyFilter
from .regex_supplement import supplement_with_regex

logger = logging.getLogger(__name__)


class HybridDetector:
    """End-to-end PII detector using OpenAI Privacy Filter + AU validators."""

    def __init__(
        self,
        openai_backend: OpenAIPrivacyFilter | None = None,
        use_regex_supplement: bool = True,
    ):
        self.openai = openai_backend or OpenAIPrivacyFilter()
        self.use_regex_supplement = use_regex_supplement

    # The interface PIIDetector exposes is .detect(text) -> list[PIISpan].
    # We mirror that exactly so HybridDetector slots into Pipeline unchanged.

    def detect(self, text: str) -> list[PIISpan]:
        if not text:
            return []

        # 1. First-pass NER on GPU
        raw_spans = self.openai.predict(text)

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
        return f"hybrid({self.openai.name})"

    def warmup(self) -> None:
        self.openai.warmup()


def build_hybrid_pipeline(
    config: Config | None = None,
    openai_backend: OpenAIPrivacyFilter | None = None,
    use_regex_supplement: bool = True,
    warmup: bool = True,
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
