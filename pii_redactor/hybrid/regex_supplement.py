"""Regex supplement layer.

OpenAI privacy-filter consistently misses three things on the Gretel-100
benchmark:

- usernames (0/7 hit rate)
- AU-formatted phones with extensions (15% recall drop)
- Multi-line / suburb-split AU addresses (18% recall drop)

The fix is cheap: re-run the existing regex_first_pass over the text and
add anything that doesn't already overlap an OpenAI span. The regex layer
runs in microseconds, so the throughput cost is negligible.

This module is intentionally NOT a fallback when OpenAI fails: it always
runs in parallel and unions its hits with OpenAI's. The merge layer in
HybridDetector deduplicates.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from ..models import PIICategory, PIISpan
from ..validators import regex_first_pass

logger = logging.getLogger(__name__)


# Categories the regex layer is *better* at than OpenAI on the Gretel corpus.
# Including everything risks reintroducing the FP noise that motivated the
# move away from regex-only. Keep this list tight.
_REGEX_HIGH_VALUE_CATEGORIES = frozenset(
    {
        PIICategory.USERNAME,
        PIICategory.PHONE,
        PIICategory.ADDRESS,
        PIICategory.EMAIL,
        PIICategory.URL,
        PIICategory.IP_ADDRESS,
        # All AU regulated identifiers — these never appear in OpenAI's
        # native categories and the regex layer enforces shape+checksum.
        PIICategory.TFN,
        PIICategory.ABN,
        PIICategory.ACN,
        PIICategory.MEDICARE,
        PIICategory.BSB_ACCOUNT,
        PIICategory.HEALTHCARE_IDENTIFIER,
        PIICategory.MEDICAL_RECORD_NUMBER,
        PIICategory.CRN,
        PIICategory.DRIVER_LICENCE,
        PIICategory.PASSPORT,
        PIICategory.PATIENT_ID,
    }
)


# When regex finds a USERNAME, allow it even if it overlaps a NAME span from
# OpenAI — openai/privacy-filter consistently labels handles (e.g. `tw_brian740`)
# as `private_person`. The merge step's "prefer longer span" rule lets the
# correct category win when the spans are identical, so emitting both is safe.
_OVERRIDE_OPENAI_CATEGORIES: dict[PIICategory, frozenset[PIICategory]] = {
    PIICategory.USERNAME: frozenset({PIICategory.NAME, PIICategory.GENERIC_ID}),
}


def _overlaps_any(start: int, end: int, existing: Iterable[tuple[int, int]]) -> bool:
    for ex_start, ex_end in existing:
        if not (end <= ex_start or ex_end <= start):
            return True
    return False


def _overlap_categories(
    start: int,
    end: int,
    spans: list[PIISpan],
) -> set[PIICategory]:
    """Return the categories of spans overlapping [start, end)."""
    out: set[PIICategory] = set()
    for span in spans:
        if not (end <= span.start or span.end <= start):
            out.add(span.category)
    return out


def supplement_with_regex(
    text: str,
    existing_spans: list[PIISpan],
    categories: frozenset[PIICategory] = _REGEX_HIGH_VALUE_CATEGORIES,
) -> list[PIISpan]:
    """Return regex-detected spans that don't overlap any existing span.

    The supplement is conservative: regex hits whose source-text range is
    already covered by an OpenAI span are discarded EXCEPT when the regex
    category is in `_OVERRIDE_OPENAI_CATEGORIES` and the overlapping OpenAI
    span uses a less-informative category (e.g. OpenAI labelled a handle as
    `private_person` → `name`). In that case the regex hit is emitted; the
    merge layer downstream picks the longer / more validated span.
    """
    if not text:
        return []
    existing_ranges = [(s.start, s.end) for s in existing_spans]
    extra: list[PIISpan] = []
    for category, start, end, value in regex_first_pass(text):
        if category not in categories:
            continue
        if _overlaps_any(start, end, existing_ranges):
            # Allow override for known OpenAI confusions
            overlap_cats = _overlap_categories(start, end, existing_spans)
            override_set = _OVERRIDE_OPENAI_CATEGORIES.get(category, frozenset())
            if not (overlap_cats & override_set):
                continue
        extra.append(
            PIISpan(
                category=category,
                start=start,
                end=end,
                value=value,
                confidence=1.0,
                validator_passed=None,  # regex_first_pass already filters by validator
            )
        )
    return extra
