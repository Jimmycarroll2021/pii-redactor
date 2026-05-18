"""Detection orchestrator.

Takes raw text, returns deduplicated PIISpans with original values attached.
The flow:

    text → chunks → LLM(prompt + grammar) → parsed entities
         → locate each value in source text → PIISpans
         → run Australian validators to filter false positives
         → merge overlapping spans
         → return

Chunking is character-based with overlap. Token-aware chunking would be
better but adds a tokenizer dependency; 4000-char chunks comfortably fit
inside Llama-3 8B's context window for any sensible prompt.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterable, Optional

from .grammar import build_grammar
from .llm_client import LLMClient
from .models import PIICategory, PIISpan
from .prompts import build_prompt
from .validators import get_validator, regex_first_pass

logger = logging.getLogger(__name__)


class PIIExtractionError(RuntimeError):
    """Raised when fail-closed PII extraction cannot trust the LLM response."""


class PIIDetector:
    def __init__(
        self,
        llm_client: LLMClient,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        categories: Optional[list[PIICategory]] = None,
        use_grammar: bool = True,
        use_regex_prepass: bool = True,
        fail_on_llm_error: bool = False,
    ):
        self.llm = llm_client
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.categories = categories or list(PIICategory)
        self.grammar = build_grammar(self.categories) if use_grammar else None
        self._use_regex_prepass = use_regex_prepass
        self._fail_on_llm_error = fail_on_llm_error

    # ------------------------------------------------------------------ public

    def detect(self, text: str) -> list[PIISpan]:
        """Detect PII in `text`. Returns merged, deduplicated spans."""
        all_spans: list[PIISpan] = []
        if self._use_regex_prepass:
            all_spans.extend(self._regex_detect(text))
        for chunk_text, chunk_offset in self._chunk(text):
            entities = self._extract_entities(chunk_text)
            for category, value in entities:
                for span in self._locate_in_source(text, value, category, chunk_offset):
                    all_spans.append(span)
        validated = self._apply_validators(all_spans)
        return self._merge(validated)

    def _regex_detect(self, text: str) -> list[PIISpan]:
        """Run regex patterns as a fast first pass for structured identifiers."""
        return [
            PIISpan(category=cat, start=start, end=end, value=value)
            for cat, start, end, value in regex_first_pass(text)
        ]

    # ----------------------------------------------------------------- helpers

    def _chunk(self, text: str) -> Iterable[tuple[str, int]]:
        """Yield (chunk_text, offset_in_source) tuples."""
        if len(text) <= self.chunk_size:
            yield text, 0
            return
        step = self.chunk_size - self.chunk_overlap
        i = 0
        while i < len(text):
            yield text[i : i + self.chunk_size], i
            i += step

    def _extract_entities(self, chunk_text: str) -> list[tuple[PIICategory, str]]:
        """Call the LLM, parse the JSON response, return (category, value) tuples."""
        cat_strs = [c.value for c in self.categories]
        system, user = build_prompt(chunk_text, cat_strs)
        parse_attempts = 2 if self._fail_on_llm_error else 1
        last_error: Exception | None = None
        for attempt in range(1, parse_attempts + 1):
            try:
                raw = self.llm.complete(
                    system_prompt=system,
                    user_prompt=user,
                    grammar=self.grammar,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM call failed: %s", exc)
                if self._fail_on_llm_error:
                    raise PIIExtractionError("LLM extraction failed") from exc
                return []

            try:
                return self._parse_response(
                    raw,
                    fail_on_parse_error=self._fail_on_llm_error,
                )
            except PIIExtractionError as exc:
                last_error = exc
                if attempt < parse_attempts:
                    logger.warning("LLM response schema invalid; retrying extraction once")
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < parse_attempts:
                    logger.warning("Could not parse LLM response; retrying extraction once")
                    continue
                if self._fail_on_llm_error:
                    raise PIIExtractionError("LLM response parsing failed") from exc
                logger.warning("Could not parse LLM response: %s", exc)
                return []
        if self._fail_on_llm_error:
            raise PIIExtractionError("LLM response parsing failed after retry") from last_error
        return []

    @staticmethod
    def _parse_response(
        raw: str,
        fail_on_parse_error: bool = False,
    ) -> list[tuple[PIICategory, str]]:
        """Defensive JSON parsing.

        Even with a grammar, we parse defensively for the case where the
        backend doesn't enforce one (HF Inference, mock, etc).
        """
        # Strip common LLM artefacts: markdown fences, leading prose
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        # Support both {"pii": [...]} and bare [...] array responses
        if cleaned.startswith("["):
            first, last = 0, len(cleaned)
            try:
                entities_raw = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                logger.warning("Could not parse LLM response as JSON: %s", exc)
                if fail_on_parse_error:
                    raise PIIExtractionError("LLM response is not valid JSON") from exc
                return []
        else:
            first = cleaned.find("{")
            last = cleaned.rfind("}")
            if first == -1 or last == -1:
                if fail_on_parse_error:
                    raise PIIExtractionError("LLM response did not contain a JSON object")
                return []
            try:
                data = json.loads(cleaned[first : last + 1])
            except json.JSONDecodeError as exc:
                logger.warning("Could not parse LLM response as JSON: %s", exc)
                if fail_on_parse_error:
                    raise PIIExtractionError("LLM response is not valid JSON") from exc
                return []
            entities_raw = PIIDetector._coerce_entity_payload(data)
            if entities_raw is None:
                if fail_on_parse_error:
                    raise PIIExtractionError(
                        "LLM response JSON did not contain a supported PII entity payload"
                    )
                return []

        out: list[tuple[PIICategory, str]] = []
        for entity in entities_raw:
            if not isinstance(entity, dict):
                continue
            cat_str = (
                entity.get("category")
                or entity.get("type")
                or entity.get("entity_type")
                or entity.get("label")
            )
            value = (
                entity.get("value")
                or entity.get("text")
                or entity.get("entity")
                or entity.get("detected_text")
            )
            if not cat_str or not value:
                continue
            # Normalise enum repr: "PIICategory.NAME" -> "name"
            if "." in cat_str:
                cat_str = cat_str.split(".")[-1].lower()
            try:
                cat = PIICategory(cat_str)
            except ValueError:
                logger.debug("Unknown category from LLM: %s", cat_str)
                continue
            out.append((cat, value))
        return out

    @staticmethod
    def _coerce_entity_payload(data) -> list[dict] | None:
        """Normalize common LLM JSON schemas into a list of entity objects."""
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return None
        if not data:
            return []
        if any(key in data for key in ("category", "type", "entity_type", "label")) and any(
            key in data for key in ("value", "text", "entity", "detected_text")
        ):
            return [data]
        for key in (
            "pii",
            "entities",
            "pii_entities",
            "personal_information",
            "redactions",
            "items",
            "results",
        ):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = PIIDetector._coerce_entity_payload(value)
                if nested is not None:
                    return nested
        nested_data = data.get("data")
        if isinstance(nested_data, (dict, list)):
            nested = PIIDetector._coerce_entity_payload(nested_data)
            if nested is not None:
                return nested
        grouped: list[dict] = []
        category_values = {category.value for category in PIICategory}
        for key, value in data.items():
            normalized_key = str(key).lower()
            if normalized_key not in category_values:
                continue
            if isinstance(value, str):
                grouped.append({"category": normalized_key, "value": value})
            elif isinstance(value, list):
                grouped.extend(
                    {"category": normalized_key, "value": item}
                    for item in value
                    if isinstance(item, str)
                )
        return grouped if grouped else None

    @staticmethod
    def _locate_in_source(
        text: str, value: str, category: PIICategory, search_from: int
    ) -> list[PIISpan]:
        """Find all occurrences of `value` in `text` at or after `search_from`.

        Returns a list because the LLM reports each entity once but the value
        may appear multiple times in the source.
        """
        spans: list[PIISpan] = []
        if not value:
            return spans
        # Search the entire text from the chunk start, since chunks overlap
        idx = search_from
        while True:
            pos = text.find(value, idx)
            if pos == -1:
                break
            spans.append(
                PIISpan(
                    category=category,
                    start=pos,
                    end=pos + len(value),
                    value=value,
                )
            )
            idx = pos + len(value)
        return spans

    @staticmethod
    def _apply_validators(spans: list[PIISpan]) -> list[PIISpan]:
        """Run category-specific validators. Drop spans that fail."""
        out: list[PIISpan] = []
        for span in spans:
            validator = get_validator(span.category)
            if validator is None:
                span.validator_passed = None
                out.append(span)
                continue
            if validator(span.value or ""):
                span.validator_passed = True
                out.append(span)
            else:
                span.validator_passed = False
                logger.debug(
                    "Dropped %s span '%s' — failed checksum",
                    span.category.value,
                    span.value,
                )
        return out

    @staticmethod
    def _merge(spans: list[PIISpan]) -> list[PIISpan]:
        """Sort and deduplicate. When two spans overlap, prefer the longer
        one; if equal length, prefer the one with a passing validator."""
        if not spans:
            return []
        # Deduplicate exact duplicates first
        seen: set[tuple[int, int, str]] = set()
        unique: list[PIISpan] = []
        for s in spans:
            key = (s.start, s.end, s.category.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)

        # Sort by start, then by length descending
        unique.sort(key=lambda s: (s.start, -(s.end - s.start)))

        merged: list[PIISpan] = []
        for span in unique:
            if not merged:
                merged.append(span)
                continue
            last = merged[-1]
            if span.overlaps(last):
                # Prefer longer; on tie prefer validated
                if len(span) > len(last):
                    merged[-1] = span
                elif len(span) == len(last) and (
                    span.validator_passed and not last.validator_passed
                ):
                    merged[-1] = span
                # otherwise drop the new span
            else:
                merged.append(span)
        return merged
