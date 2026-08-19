"""Regression: international / grouped phone formats must be detected.

These exact values leaked (`phone` category) through the deterministic
production gate on the `gretel-pii-masking-en-all` and
`user-pii-dataset-csv-all` fixtures before the phone-pattern broadening.
A leak here means the rules tier failed to redact a real phone number, so
each must be matched as a single PHONE span.

See: audit/stage1-hostile-2026-06-22 (phone-recall gap on non-AU formats).
"""

from __future__ import annotations

import pytest

from pii_redactor.models import PIICategory
from pii_redactor.validators import PATTERNS

# (value, why) — every entry was a confirmed gate leak.
LEAKED_PHONE_FORMATS = [
    "+27 68 670 7513",       # South Africa, 2-3-4 groups
    "+27 32 160 4356",
    "+91-39941 98087",       # India, dash then 5-5
    "+91-93973 49939",
    "+44(0)20 7496 0765",    # UK international trunk-prefix form
    "0151 496 0156",         # UK-style leading-0 4-3-4
    "0701 369 4303",
    "0186 704 2983",
    "0250 530 1581",
    "0115 496 0951",
    "0161 496 0234",
    "0117 496 0708",
    "9423 5043",             # 8-digit local, spaced
    "3090 5530",
    "9646 5929",
    "0037 0736",
    "9218.0642",             # 8-digit local, dotted
    "4383.1373",
    "0449.4191",
]


@pytest.mark.parametrize("value", LEAKED_PHONE_FORMATS)
def test_phone_format_is_fully_matched(value: str) -> None:
    match = PATTERNS[PIICategory.PHONE].search(value)
    assert match is not None, f"phone not detected at all: {value!r}"
    assert match.group(0).strip() == value, (
        f"phone only partially matched: {value!r} -> {match.group(0)!r}"
    )
