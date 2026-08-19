"""Redaction engine.

Takes detected spans and produces redacted text. Three placeholder
strategies are supported:

- "numbered": [REDACTED_NAME_001], [REDACTED_NAME_002], ...
  Preserves coreference within a document. Default. Best for downstream
  analytics where you want to know that two redacted spans referred to
  the same entity.

- "category": [REDACTED_NAME], [REDACTED_TFN], ...
  Lighter-weight, no coreference. Good for human-readable redacted output.

- "asterisk": ********
  Maximum opacity. Useful when even the category should be hidden.

The redactor mutates spans to record the placeholder used; the resulting
spans are safe to return in RedactionResult.
"""
from __future__ import annotations

from .models import PIISpan


class Redactor:
    def __init__(self, style: str = "numbered"):
        if style not in ("numbered", "category", "asterisk"):
            raise ValueError(
                f"Unknown placeholder style: {style}. "
                f"Use 'numbered', 'category', or 'asterisk'."
            )
        self.style = style

    def redact(self, text: str, spans: list[PIISpan]) -> tuple[str, list[PIISpan]]:
        """Apply redaction. Returns (redacted_text, updated_spans).

        Updated spans have their `placeholder` field set and their `value`
        field cleared (so they're safe to return downstream).
        """
        if not spans:
            return text, []

        # Sort by start ascending so we replace from start to end
        sorted_spans = sorted(spans, key=lambda s: s.start)

        # For "numbered" style, assign per-category counters keyed by value
        # so identical values within a document share a placeholder.
        value_to_placeholder: dict[tuple[str, str], str] = {}
        category_counters: dict[str, int] = {}

        # First pass: assign placeholders
        for span in sorted_spans:
            placeholder = self._placeholder_for(
                span, value_to_placeholder, category_counters
            )
            span.placeholder = placeholder

        # Second pass: build redacted text by walking spans in reverse so
        # offsets stay valid as we splice
        out = text
        for span in reversed(sorted_spans):
            out = out[: span.start] + (span.placeholder or "") + out[span.end :]

        # Clear original values before returning spans downstream
        safe_spans = []
        for s in sorted_spans:
            safe_spans.append(
                PIISpan(
                    category=s.category,
                    start=s.start,
                    end=s.end,
                    value=None,
                    confidence=s.confidence,
                    validator_passed=s.validator_passed,
                    placeholder=s.placeholder,
                    needs_review=s.needs_review,
                )
            )
        return out, safe_spans

    def _placeholder_for(
        self,
        span: PIISpan,
        value_map: dict[tuple[str, str], str],
        counters: dict[str, int],
    ) -> str:
        if self.style == "asterisk":
            return "*" * (span.end - span.start)

        if self.style == "category":
            return f"[REDACTED_{span.category.value.upper()}]"

        # numbered: stable per (category, value) within a single redaction call
        if span.value is None:
            return f"[REDACTED_{span.category.value.upper()}]"

        key = (span.category.value, span.value)
        if key not in value_map:
            counters[span.category.value] = counters.get(span.category.value, 0) + 1
            value_map[key] = (
                f"[REDACTED_{span.category.value.upper()}_"
                f"{counters[span.category.value]:03d}]"
            )
        return value_map[key]
