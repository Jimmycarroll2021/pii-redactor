"""Australian PII validators using checksum algorithms.

These validators are the second filter after LLM detection. The LLM is
optimised for recall (catch everything that looks like PII); the validators
add precision (confirm format-checksum match) for high-stakes identifiers.

A validator returning False filters out the detection. Returning True
confirms it. Returning None means no validator exists for that category,
and the LLM detection is trusted as-is.
"""

# References:
#   Australian Taxation Office (ATO) — Tax File Number (TFN) checksum.
#   Mod-11 weighted-sum with weight vector [1, 4, 3, 7, 5, 8, 6, 9, 10]
#   for the 9-digit format; supports both 8-digit (legacy) and 9-digit.
#   https://www.ato.gov.au/individuals-and-families/tax-file-number
#
#   Australian Business Register (ABR) — ABN Lookup + 11-digit ABN checksum
#   (mod-89 weighted-sum). Web service docs:
#   https://abr.business.gov.au/Tools/WebServices
#
#   Australian Securities & Investments Commission (ASIC) — ACN 9-digit
#   mod-10 weighted-sum checksum, used as the sanity check for the
#   business-component of the ABN.
#
#   Australian Digital Health Agency (ADHA, formerly NEHTA) — Individual
#   Healthcare Identifier (IHI) 16-digit specification + Luhn checksum.
#   https://www.digitalhealth.gov.au/healthcare-providers/individual-healthcare-identifiers-ihi
#
#   All four retrieved 2026-05-21.
#   See `docs/references/REFERENCES.md` (sections: ATO TFN, ABR ABN, ASIC ACN, IHI).

from __future__ import annotations

import os
import re
from collections.abc import Callable

from .models import PIICategory


def _digits_only(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def validate_tfn(value: str) -> bool:
    """Tax File Number checksum (ATO algorithm).

    Supports both the legacy 8-digit and current 9-digit formats.
    Reference: https://www.ato.gov.au/individuals-and-families/tax-file-number/about-tax-file-numbers
    """
    digits = _digits_only(value)
    if len(digits) == 9:
        weights = [1, 4, 3, 7, 5, 8, 6, 9, 10]
    elif len(digits) == 8:
        weights = [10, 7, 8, 4, 6, 3, 5, 1]
    else:
        return False
    if int(digits) == 0:  # reject trivial all-zero
        return False
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    return total % 11 == 0


def validate_abn(value: str) -> bool:
    """Australian Business Number checksum.

    Reference: https://abr.business.gov.au/Help/AbnFormat
    Algorithm: subtract 1 from leading digit, weighted sum mod 89 == 0.
    """
    digits = _digits_only(value)
    if len(digits) != 11:
        return False
    if int(digits) == 0:
        return False
    nums = [int(d) for d in digits]
    nums[0] -= 1
    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    total = sum(n * w for n, w in zip(nums, weights, strict=True))
    return total % 89 == 0


def validate_acn(value: str) -> bool:
    """Australian Company Number checksum (ASIC algorithm).

    Reference: https://asic.gov.au/for-business/registering-a-company/steps-to-register-a-company/australian-company-numbers/
    """
    digits = _digits_only(value)
    if len(digits) != 9:
        return False
    if int(digits) == 0:
        return False
    weights = [8, 7, 6, 5, 4, 3, 2, 1]
    total = sum(int(d) * w for d, w in zip(digits[:8], weights, strict=True))
    check = (10 - (total % 10)) % 10
    return check == int(digits[8])


def validate_medicare(value: str) -> bool:
    """Medicare card number checksum.

    Format: XXXX XXXXX X (10 digits) or XXXX XXXXX X-X (11 digits with IRN).
    First 8 digits are the customer number, 9th is check, 10th is issue,
    optional 11th is the individual reference number.
    """
    digits = _digits_only(value)
    if len(digits) not in (10, 11):
        return False
    if int(digits) == 0:
        return False
    weights = [1, 3, 7, 9, 1, 3, 7, 9]
    total = sum(int(d) * w for d, w in zip(digits[:8], weights, strict=True))
    check_digit = total % 10
    return check_digit == int(digits[8])


def validate_bsb(value: str) -> bool:
    """BSB number — 6 digits, first 2 indicate bank, no published checksum.

    Validates format only. Accepts XXX-XXX or XXXXXX.
    """
    digits = _digits_only(value)
    return len(digits) == 6


# High-recall regex patterns for first-pass screening.
# Ordered longest/most-specific first so the merge step's "prefer longer span"
# rule naturally resolves ambiguity (e.g. ABN before TFN before ACN before BSB).
PATTERNS: dict[PIICategory, re.Pattern[str]] = {
    # --- Structured numeric identifiers (longest first) ---
    # Use (?<!\d) / (?!\d) instead of \b so identifiers are detected even when
    # written directly after a label letter (e.g. "ABN33051775556").
    PIICategory.ABN: re.compile(r"(?<!\d)\d{2}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)"),
    PIICategory.TFN: re.compile(r"(?<!\d)\d{3}[\s-]?\d{3}[\s-]?\d{2,3}(?!\d)"),
    PIICategory.ACN: re.compile(r"(?<!\d)\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)"),
    PIICategory.MEDICARE: re.compile(r"(?<!\d)\d{4}[\s-]?\d{5}[\s-]?\d(?:[\s-]?\d)?(?!\d)"),
    PIICategory.BSB_ACCOUNT: re.compile(r"(?<!\d)\d{3}[\s-]?\d{3}(?!\d)"),
    # --- Medical / document identifiers ---
    # These are intentionally context-bound. A bare alphanumeric token is not
    # enough to call something a patient ID or MRN; the nearby label must say
    # so. The named "value" group lets regex_first_pass redact only the ID,
    # not the label text.
    PIICategory.PATIENT_ID: re.compile(
        r"\b(?:patient\s*(?:id|identifier|number|no\.?)|pt\s*id)\s*[:#-]?\s*"
        r"(?P<value>[A-Z0-9][A-Z0-9-]{4,24})\b",
        re.IGNORECASE,
    ),
    PIICategory.MEDICAL_RECORD_NUMBER: re.compile(
        r"\b(?:mrn|medical\s*record\s*(?:number|no\.?)|hospital\s*(?:urn|ur|number|no\.?))"
        r"\s*[:#-]?\s*(?P<value>[A-Z0-9][A-Z0-9-]{4,24})\b",
        re.IGNORECASE,
    ),
    PIICategory.HEALTHCARE_IDENTIFIER: re.compile(
        r"\b(?:ihi|individual\s*healthcare\s*identifier|healthcare\s*identifier)"
        r"\s*[:#-]?\s*(?P<value>\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})\b",
        re.IGNORECASE,
    ),
    # PASSPORT before DRIVER_LICENCE: both match e.g. "PA1234567" (2 letters + 7 digits);
    # PASSPORT is more specific so it takes priority when they tie on span length.
    PIICategory.PASSPORT: re.compile(r"\b[A-Z]{1,2}\d{7}\b"),
    PIICategory.DRIVER_LICENCE: re.compile(r"\b[A-Z]{0,2}\d{6,9}\b"),
    PIICategory.CRN: re.compile(r"\b\d{9}[A-Z]\b"),
    # --- Contact and network ---
    # Covers AU formats and common international forms with separators/extensions.
    # Kept after structured numeric identifiers so long AU IDs win overlaps.
    PIICategory.PHONE: re.compile(
        r"(?<!\d)(?:"
        # AU international: +61 or 0061 followed by valid AU prefix.
        r"(?:\+61|0061)[\s.-]?(?:[2-578][\s.-]?\d{4}[\s.-]?\d{4}|[45]\d{2}[\s.-]?\d{3}[\s.-]?\d{3})"
        # AU bracketed area code: (0X) XXXX XXXX (any separator).
        r"|\(0[2-578]\)[\s.-]?\d{4}[\s.-]?\d{4}"
        # AU landline: 0X XXXX XXXX with explicit dash/dot separator
        # OR space separator (bare 0X distinguishes AU phone from ABN/ACN).
        r"|0[2-578][\s.-]\d{4}[\s.-]?\d{4}"
        # AU mobile: 04XX XXX XXX.
        r"|04\d{2}[\s.-]?\d{3}[\s.-]?\d{3}"
        # Generic international with leading + and parens, with optional extension.
        r"|\+\d{1,3}[\s.-]?\(\d{2,4}\)[\s.-]?\d{3,5}[\s.-]?\d{3,4}(?:\s*(?:x|ext\.?|extension)\s*\d{1,6})?"
        # International trunk-prefix form: +CC(0)AREA LOCAL (e.g. +44(0)20 7496 0765).
        r"|\+\d{1,3}\(0\)[\s.-]?\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"
        # Generic international with leading + and dotted/dashed groups (e.g. +1 555-123-4567).
        r"|\+\d{1,3}[\s.-]?\d{3,5}[\s.-]\d{3,4}(?:[\s.-]\d{2,6})?(?:\s*(?:x|ext\.?|extension)\s*\d{1,6})?"
        # Broad international fallback: +CC then 2-4 separator-led groups of 2-5 digits
        # (e.g. +27 68 670 7513, +91-39941 98087). The leading + keeps FP risk low.
        r"|\+\d{1,3}(?:[\s.-]\d{2,5}){2,4}"
        # Leading country digit + bracketed area: 1 (XXX) XXX-XXXX.
        r"|\d[\s.-]?\(\d{2,4}\)[\s.-]?\d{3,5}[\s.-]?\d{3,4}(?:\s*(?:x|ext\.?|extension)\s*\d{1,6})?"
        # Bracketed area code with any separator: (XXX) XXX-XXXX or (XXXX) XXX XXXX, optional ext.
        r"|\(\d{2,4}\)[\s.-]?\d{3,5}[\s.-]?\d{3,4}(?:\s*(?:x|ext\.?|extension)\s*\d{1,6})?"
        # Dashed: XXX-XXX-XXXX or XXXX-XXXX.
        r"|\d{3}-\d{3}-\d{4}"
        # 8-digit local number, space/dot/dash grouped (e.g. 9423 5043, 9218.0642).
        r"|\d{4}[\s.-]\d{4}"
        # Dotted: XXX.XXX.XXXX.
        r"|\d{3}\.\d{3}\.\d{4}"
        # Leading-0 national, space/dot grouped: 3-4-4, 4-3-4 or 4-4-4
        # (e.g. 028 9018 0925, 0151 496 0156, 0701 369 4303).
        r"|0\d{2,4}[\s.]\d{3,4}[\s.]\d{3,4}"
        r")(?!\d)",
        re.IGNORECASE,
    ),
    # Require alphanumeric first/last char in local part; 2+ char TLD. Use
    # ASCII edge guards rather than \b so emails still match when immediately
    # followed by non-ASCII prose characters in synthetic corpora.
    PIICategory.EMAIL: re.compile(
        r"(?<![A-Za-z0-9_%+-])[A-Za-z0-9](?:[A-Za-z0-9_.+-]*[A-Za-z0-9])?"
        r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9])"
    ),
    PIICategory.URL: re.compile(
        r"(?:"
        r"\b(?:https?://|tps://|www\.)[\w./\-?=&%#:@]+"
        r"|(?<![@\w])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?\.)+[A-Za-z]{2,}(?:/[\w./\-?=&%#:@]*)?(?![A-Za-z0-9_-])"
        r")",
        re.IGNORECASE,
    ),
    PIICategory.ADDRESS: re.compile(
        r"\b\d{1,6}\s+"
        r"(?:[A-Za-z][A-Za-z'.-]*\s+){0,8}"
        r"(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|"
        r"Place|Pl|Terrace|Tce|Way|Close|Crescent|Cres|Highway|Hwy|Parade|Pde|"
        r"Square|Sq|Circuit|Cct|Track|Trail|Trl)\b"
        r"(?:,?\s+(?:[A-Za-z][A-Za-z'.-]*|NSW|VIC|QLD|WA|SA|TAS|ACT|NT|\d{4})){0,8}",
        re.IGNORECASE,
    ),
    PIICategory.USERNAME: re.compile(
        r"\b(?:username|handle|login|screen\s*name|account\s*name)s?\s*[:=]\s*(?P<context_value>[a-zA-Z0-9][a-zA-Z0-9._-]{2,31})\b"
        r"|(?<![\w@.])(?P<value>"
        r"@[a-zA-Z][a-zA-Z0-9._-]{2,31}"
        r"|(?=[a-zA-Z0-9._-]{3,32}(?![\w-]))(?=[a-zA-Z0-9._-]*[._-])(?=[a-zA-Z0-9._-]*[a-zA-Z])[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9_-]*)*"
        r"|(?=[a-zA-Z0-9._-]{5,32}(?![\w-]))(?=[a-zA-Z0-9._-]*\d)(?=[a-zA-Z0-9._-]*[a-zA-Z])[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9_-]*)*"
        r")(?![\w-])"
        r"|(?<=\.\.\.)(?P<ellipsis_value>"
        r"(?=[a-zA-Z0-9._-]{3,32}(?=\.\.\.))(?=[a-zA-Z0-9._-]*[._-])(?=[a-zA-Z0-9._-]*[a-zA-Z])[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9_-]*)*"
        r"|(?=[a-zA-Z0-9._-]{5,32}(?=\.\.\.))(?=[a-zA-Z0-9._-]*\d)(?=[a-zA-Z0-9._-]*[a-zA-Z])[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9_-]*)*"
        r")(?=\.\.\.)"
    ),
    PIICategory.GENERIC_ID: re.compile(
        r"(?:"
        r"\b(?:student|user|account|member|client|customer|case|pin|code|reference|ref|id(?:entifier)?|username)\s*(?:id|number|no\.?)?\s*[:#-]\s*(?P<labelled>[A-Z0-9][A-Z0-9._-]{2,32})\b"
        r"|(?<![A-Z0-9])(?P<codepair>[A-Z]{2,8}:[A-Z0-9]{5,18})(?![A-Z0-9])"
        r"|(?<!\d)(?P<ssn>\d{3}-\d{2}-\d{4})(?!\d)"
        r"|(?<![A-Z0-9])(?P<spacedid>[A-Z]{1,3}(?:\s+\d{2}){3,4}\s+[A-Z])(?![A-Z0-9])"
        r"|(?<![A-Z0-9])(?P<mixedid>(?-i:(?=[A-Z0-9]{6,18}\b)(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,18}))(?![A-Z0-9])"
        r"|(?<!\d)(?P<commaid>\d{1,2}(?:,\d{1,2}){2,5},?)(?!\d)"
        r"|(?<!\d)(?P<longnum>\d{10,16})(?!\d)"
        r")",
        re.IGNORECASE,
    ),
    PIICategory.DATE: re.compile(
        r"\b(?:"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|\d{1,2}:\d{2}(?::\d{2})?"
        r"|\d\s*[A-Za-z]\s*\d{2}"
        r"|\d{1,2}\s*[A-Za-z]\s*\d{2}"
        r"|(?:half past|quarter past|quarter to)\s+\d{1,2}"
        r"|\d{1,2}\s+o'clock"
        r"|[A-Za-z]{3,12}[/-]\d{1,4}"
        r"|[A-Za-z]{3,12}\s+\d{1,2}[A-Za-z]{0,3}\.?,?\s+\d{2,4}"
        r"|\d{1,2}[A-Za-z]{1,3}\s+[A-Za-z]{3,12}\s+\d{2,4}"
        r"|\d{1,2}\s+[A-Za-z]{3,12}\s+[A-Za-z]{3,12}\s+\d{1,2}"
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)[/-]\d{1,4}"
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)[/-]\d{1,2}"
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\.?,?\s+\d{2,4}"
        r"|\d{1,2}(?:st|nd|rd|th)?\.?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4}"
        r")(?!\d)",
        re.IGNORECASE,
    ),
    # Proper octet-range validation (0–255) instead of bare \d{1,3}.
    PIICategory.IP_ADDRESS: re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\b"
    ),
}


_VALIDATORS: dict[PIICategory, Callable[[str], bool]] = {
    PIICategory.TFN: validate_tfn,
    PIICategory.ABN: validate_abn,
    PIICategory.ACN: validate_acn,
    PIICategory.MEDICARE: validate_medicare,
    PIICategory.BSB_ACCOUNT: validate_bsb,
}


def get_validator(category: PIICategory) -> Callable[[str], bool] | None:
    """Return a validator function for the category, or None if none exists."""
    return _VALIDATORS.get(category)


_BENIGN_USERNAME_TOKEN_RE = re.compile(
    r"^(?:alpha|beta|gamma|omega|filler|batch|shard|build|train)\d{3,}$",
    re.IGNORECASE,
)


def _is_suppressed_regex_hit(
    category: PIICategory,
    value: str,
    value_group: str | None = None,
) -> bool:
    """Suppress obvious non-PII regex matches from technical corpora.

    These filters target reserved examples and synthetic filler tokens while
    preserving high-recall username handling for realistic names plus digits.
    """
    stripped = value.strip().rstrip(".,;:)")
    lowered = stripped.lower()
    if category == PIICategory.USERNAME:
        if (
            os.environ.get("PIIR_USERNAME_MODE", "high_recall").lower() == "strict"
            and value_group == "value"
            and not any(marker in stripped for marker in ("@", ".", "_", "-"))
        ):
            return True
        if _BENIGN_USERNAME_TOKEN_RE.match(stripped):
            return True
        suppress_tokens = {
            "snake_case_tokens", "markdown_headers", "service_timeout_ms",
            "retry_limit", "enable_cache", "log_level",
        }
        if lowered in suppress_tokens:
            return True
    if category == PIICategory.URL:
        if lowered in {"localhost"}:
            return True
        if lowered.endswith((".invalid", ".test", ".example")):
            return True
    if category == PIICategory.GENERIC_ID:
        if re.fullmatch(r"[A-Z]{4}\d{4}", stripped):
            return True
    return False


def regex_first_pass(text: str) -> list[tuple[PIICategory, int, int, str]]:
    """High-recall regex scan. Useful as a backstop when the LLM misses
    structured identifiers, or as the only detection layer in low-resource
    deployments where running a model isn't feasible.

    Returns list of (category, start, end, value) tuples.
    """
    hits: list[tuple[PIICategory, int, int, str]] = []
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value_group = None
            candidates = (
                "value", "context_value", "ellipsis_value", "labelled", "codepair",
                "ssn", "spacedid", "mixedid", "commaid", "longnum",
            )
            for candidate in candidates:
                if candidate in pattern.groupindex and match.group(candidate):
                    value_group = candidate
                    break
            if value_group:
                value = match.group(value_group)
                if _is_suppressed_regex_hit(category, value, value_group):
                    continue
                hits.append(
                    (
                        category,
                        match.start(value_group),
                        match.end(value_group),
                        value,
                    )
                )
            else:
                value = match.group()
                if _is_suppressed_regex_hit(category, value, None):
                    continue
                hits.append((category, match.start(), match.end(), value))
    return hits
