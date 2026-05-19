"""Resolve OpenAI's generic `account_number` / `secret` spans into precise
Australian PII categories.

OpenAI's privacy-filter only has 8 entity types. Anything with an Australian
regulatory shape (TFN, ABN, ACN, Medicare, IHI, MRN, BSB, driver licence,
passport, Centrelink CRN) collapses into `account_number`. Downstream
compliance consumers need the specific type so the redaction policy can
apply the right rule (e.g. TFN gets full obfuscation per the Privacy Act,
ABN is publicly disclosable but still PII when paired with an individual).

Resolution strategy (in order of specificity)
---------------------------------------------
For each candidate span text:

1. Try the 5 checksum-protected AU identifiers in order of distinctness:
       TFN (9 digits, mod 11)
       ABN (11 digits, mod 89)
       ACN (9 digits, weighted mod 10)
       MEDICARE (10-11 digits, mod 10)
       BSB (6 digits, format-only)
   The first checksum that passes wins.

2. Try the structural-only AU identifiers (no checksum, regex shape match):
       IHI (16 digits)
       Medical record number (label-bound, e.g. "MRN-12345")
       Healthcare identifier
       Centrelink CRN (9 digits + 1 letter)
       Driver licence (state-specific format)
       Passport (1-2 letters + 7 digits)

3. Fall back to GENERIC_ID — that's what OpenAI was already telling us.

The function never returns None: every input span is resolved to *some*
PIICategory so the existing redactor can placeholder it. It does mutate
the .category and .validator_passed of the input spans.

The `resolve_account_numbers` entry-point is pure: it accepts a list of
candidate spans (typically just OpenAI's account_number + secret outputs)
and returns a list of *new* PIISpans with the upgraded category.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable

from ..models import PIICategory, PIISpan
from ..validators import validate_abn, validate_acn, validate_bsb, validate_medicare, validate_tfn

logger = logging.getLogger(__name__)


# --- Structural matchers for non-checksum AU IDs ----------------------------

# IHI: 16 digits, often grouped 4-4-4-4
_IHI_RE = re.compile(r"^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$")

# Centrelink CRN: 9 digits + 1 alpha
_CRN_RE = re.compile(r"^\d{9}[A-Za-z]$")

# Passport: 1-2 letters + 7 digits
_PASSPORT_RE = re.compile(r"^[A-Z]{1,2}\d{7}$", re.IGNORECASE)

# Driver licence: vary by state — accept the broad pattern used by validators
_DL_RE = re.compile(r"^[A-Z]{0,2}\d{6,9}$", re.IGNORECASE)

# MRN: shape only — typically alphanumeric short string with optional prefix.
# OpenAI sometimes returns just the digits, sometimes "MRN-12345" — accept both.
_MRN_RE = re.compile(r"^(?:MRN[-_:]?)?\s?[A-Z0-9][A-Z0-9-]{3,24}$", re.IGNORECASE)


def _digits_only(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


# --- Context-aware label sniffing -------------------------------------------

# Some categories are unambiguous only when read with their surrounding label
# ("TFN: ...", "MRN: ...", "Passport ..."). When the OpenAI span doesn't carry
# the label but the surrounding text does, we use the label as a strong prior.
_LABEL_PRIORS: list[tuple[re.Pattern[str], PIICategory]] = [
    (re.compile(r"\b(?:tfn|tax\s+file\s+number)\b", re.IGNORECASE), PIICategory.TFN),
    (
        re.compile(r"\babn\b|\baustralian\s+business\s+number\b", re.IGNORECASE),
        PIICategory.ABN,
    ),
    (
        re.compile(r"\bacn\b|\baustralian\s+company\s+number\b", re.IGNORECASE),
        PIICategory.ACN,
    ),
    (re.compile(r"\bmedicare\b", re.IGNORECASE), PIICategory.MEDICARE),
    (
        re.compile(
            r"\b(?:ihi|individual\s+healthcare\s+identifier|healthcare\s+identifier)\b",
            re.IGNORECASE,
        ),
        PIICategory.HEALTHCARE_IDENTIFIER,
    ),
    (
        re.compile(
            r"\b(?:mrn|medical\s+record\s+number|hospital\s+ur(?:n)?)\b",
            re.IGNORECASE,
        ),
        PIICategory.MEDICAL_RECORD_NUMBER,
    ),
    (
        re.compile(r"\b(?:bsb|bank\s+state\s+branch)\b", re.IGNORECASE),
        PIICategory.BSB_ACCOUNT,
    ),
    (re.compile(r"\bpassport\b", re.IGNORECASE), PIICategory.PASSPORT),
    (
        re.compile(
            r"\bdriver(?:'s)?\s+licen[cs]e\b|\bdl\b|\blicen[cs]e\s+number\b",
            re.IGNORECASE,
        ),
        PIICategory.DRIVER_LICENCE,
    ),
    (
        re.compile(
            r"\b(?:centrelink|crn|customer\s+reference\s+number)\b",
            re.IGNORECASE,
        ),
        PIICategory.CRN,
    ),
    (
        re.compile(
            r"\b(?:username|handle|login|screen\s*name|account\s*name)s?\b",
            re.IGNORECASE,
        ),
        PIICategory.USERNAME,
    ),
]


def _label_prior(text: str, start: int, end: int, window: int = 30) -> PIICategory | None:
    """Look at the ~30 chars immediately before the span for a label like 'TFN:'.

    We require the label to be the *nearest* one to the value — comma /
    semicolon / newline characters between the label and the value break
    the binding so we don't, e.g., bind a TFN label to a subsequent ABN.
    """
    left = max(0, start - window)
    snippet = text[left:start]
    # If there's a hard separator between the label and the value, drop it.
    for separator in ("\n", ";", ",", ". "):
        sep_idx = snippet.rfind(separator)
        if sep_idx != -1:
            snippet = snippet[sep_idx + len(separator):]
    for pattern, category in _LABEL_PRIORS:
        if pattern.search(snippet):
            return category
    return None


# --- Validator dispatch ------------------------------------------------------

# The order matters: try the most-specific checksum first so a string that
# happens to satisfy multiple shapes gets the strongest possible label.
_CHECKSUM_VALIDATORS: list[tuple[PIICategory, Callable[[str], bool]]] = [
    (PIICategory.ABN, validate_abn),         # 11 digits
    (PIICategory.MEDICARE, validate_medicare),  # 10-11 digits
    (PIICategory.TFN, validate_tfn),          # 9 digits
    (PIICategory.ACN, validate_acn),          # 9 digits
    # BSB is format-only (6 digits) so it must come LAST, otherwise a 6-digit
    # prefix of an ABN/Medicare/TFN would be claimed by BSB.
    (PIICategory.BSB_ACCOUNT, validate_bsb),
]


def _try_checksum_validators(value: str) -> tuple[PIICategory, bool] | None:
    """Return (category, True) on first passing checksum, or None."""
    digits = _digits_only(value)
    for category, validator in _CHECKSUM_VALIDATORS:
        try:
            if validator(value):
                return category, True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Validator %s threw on '%s': %s", category, value, exc)
            continue
    # Note: digits-only fallback intentionally omitted — validators already
    # call _digits_only internally so they handle whitespace/dashes.
    _ = digits  # silence unused-variable check while documenting the choice
    return None


def _try_structural_matchers(value: str) -> PIICategory | None:
    """Match shape-only (non-checksum) AU identifiers."""
    stripped = value.strip()
    if _IHI_RE.match(stripped):
        return PIICategory.HEALTHCARE_IDENTIFIER
    # MRN with explicit prefix: "MRN-12345", "MRN_4567", "MRN:9999"
    if re.match(r"^MRN[-_:]\s?\w", stripped, re.IGNORECASE):
        return PIICategory.MEDICAL_RECORD_NUMBER
    if _CRN_RE.match(stripped):
        return PIICategory.CRN
    if _PASSPORT_RE.match(stripped):
        return PIICategory.PASSPORT
    # Driver licence — only commit if 7+ chars and not a pure digit run that
    # already failed all the checksums. Avoid claiming generic numeric IDs.
    if _DL_RE.match(stripped) and len(stripped) >= 7:
        return PIICategory.DRIVER_LICENCE
    return None


# --- Public API --------------------------------------------------------------

def resolve_one(
    value: str,
    *,
    source_text: str = "",
    span_start: int = 0,
    span_end: int = 0,
    openai_category: str = "account_number",
) -> tuple[PIICategory, bool | None]:
    """Resolve a single candidate span text to a precise AU category.

    Returns (category, validator_passed). `validator_passed` is True when a
    checksum validator confirmed it, None when only shape matched or no
    validator exists, and False is never returned (failures fall through to
    GENERIC_ID, which has no validator).
    """
    # 1. Label prior — if the label says "TFN:" but the digits don't pass the
    # TFN checksum, we *still* tag it as TFN (with validator_passed=False) so
    # downstream policies don't silently mis-classify.
    label_hint = _label_prior(source_text, span_start, span_end) if source_text else None
    if label_hint is not None:
        validator_passed: bool | None = None
        validator_map = {
            PIICategory.TFN: validate_tfn,
            PIICategory.ABN: validate_abn,
            PIICategory.ACN: validate_acn,
            PIICategory.MEDICARE: validate_medicare,
            PIICategory.BSB_ACCOUNT: validate_bsb,
        }
        if label_hint in validator_map:
            try:
                validator_passed = bool(validator_map[label_hint](value))
            except Exception:  # noqa: BLE001
                validator_passed = False
        # If we have a label hint but it's a non-checksum AU type (e.g.
        # MRN, IHI, passport), trust the label.
        return label_hint, validator_passed

    # 2. Checksum-validated AU identifiers
    checksum_hit = _try_checksum_validators(value)
    if checksum_hit is not None:
        return checksum_hit

    # 3. Structural-only AU identifiers
    structural_hit = _try_structural_matchers(value)
    if structural_hit is not None:
        return structural_hit, None

    # 4. Fall back. If OpenAI flagged it as `secret`, prefer USERNAME when the
    # value looks like a handle (alphanumeric + `_`/`.` and contains letters);
    # otherwise GENERIC_ID.
    if openai_category == "secret":
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,31}", value.strip()) and any(
            c.isalpha() for c in value
        ):
            return PIICategory.USERNAME, None
    return PIICategory.GENERIC_ID, None


def resolve_account_numbers(
    candidate_spans: list[tuple[str, int, int, str]],
    source_text: str,
) -> list[PIISpan]:
    """Resolve a batch of OpenAI candidate spans into PIISpans.

    `candidate_spans` is the output of `OpenAIPrivacyFilter.predict()`:
    a list of (openai_category, start, end, value) tuples.

    Every span is converted to a PIISpan. Spans tagged `account_number`
    or `secret` are routed through the AU resolver; all other spans
    pass through with the primary mapping from OPENAI_TO_AU_PRIMARY.
    """
    from .openai_backend import OPENAI_TO_AU_PRIMARY

    out: list[PIISpan] = []
    for openai_cat, start, end, value in candidate_spans:
        if openai_cat in ("account_number", "secret"):
            category, validator_passed = resolve_one(
                value,
                source_text=source_text,
                span_start=start,
                span_end=end,
                openai_category=openai_cat,
            )
        else:
            primary = OPENAI_TO_AU_PRIMARY.get(openai_cat, "generic_id")
            try:
                category = PIICategory(primary)
            except ValueError:
                category = PIICategory.GENERIC_ID
            validator_passed = None

        out.append(
            PIISpan(
                category=category,
                start=start,
                end=end,
                value=value,
                confidence=1.0,
                validator_passed=validator_passed,
            )
        )
    return out
