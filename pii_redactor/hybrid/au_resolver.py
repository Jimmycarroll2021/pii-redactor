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


# ---------------------------------------------------------------------------
# v0.4.3 — `private_address` vs `location` disambiguation
# ---------------------------------------------------------------------------
# openai/privacy-filter emits a single `private_address` label for BOTH
# postal addresses (street + suburb + postcode) AND standalone references
# to suburbs / regions / states. Phase 4 sector bench showed this collapse
# bottoms out the per-category `location` recall at ~0% even when the model
# is recovering the spans.
#
# This module post-processes any span tagged `address` (the AU primary
# mapping of `private_address`) and re-tags it as `location` when the
# span has no street-number / street-keyword / postcode component. Pure
# rule layer — no model change.

# Street-suffix vocabulary used for the structural check. Lower-cased
# for case-insensitive matching.
_AU_STREET_SUFFIX_RE = re.compile(
    r"\b("
    r"street|st|road|rd|avenue|ave|lane|ln|drive|dr|"
    r"crescent|cres|court|ct|place|pl|way|highway|hwy|"
    r"parade|pde|boulevard|blvd|terrace|tce|close|cl|"
    r"circuit|cct|esplanade|esp|square|sq|mews|walk|"
    r"track|trail|loop|rise|view|vista|grove|gardens|gdns"
    r")\b",
    re.IGNORECASE,
)

# 4-digit AU postcode pattern. AU postcodes are 4 digits, 0200-9999 (0xxx
# = ACT, 8xxx = NT/SA variants). The structural check uses presence /
# absence of any 4-digit run inside the span value.
_AU_POSTCODE_RE = re.compile(r"\b\d{4}\b")

# Leading digit run (street number) — "23 Collins Street" or "1/45 Park Rd".
_STREET_NUMBER_RE = re.compile(r"^\s*(?:\d+\s*[/\\-]?\s*)?\d+\b")

# AU state full names / abbreviations — used to spot trailing
# "Suburb STATE Postcode" pattern even when there's no street keyword.
_STATE_TOKEN_RE = re.compile(
    r"\b(NSW|VIC|QLD|WA|SA|TAS|NT|ACT|"
    r"New\s+South\s+Wales|Victoria|Queensland|Western\s+Australia|"
    r"South\s+Australia|Tasmania|Northern\s+Territory|"
    r"Australian\s+Capital\s+Territory)\b",
    re.IGNORECASE,
)

# PO Box / GPO Box / Locked Bag — explicit non-street address forms that
# still resolve to ADDRESS (mail address), not LOCATION.
_POSTAL_BOX_RE = re.compile(
    r"\b(?:P\.?O\.?\s*Box|GPO\s*Box|Locked\s+Bag|Private\s+Bag)\s*\d+",
    re.IGNORECASE,
)


def _disambiguate_address_vs_location(span_text: str) -> str:
    """Return ``"address"`` or ``"location"`` for an OpenAI `private_address`
    span, using structural heuristics on the span text only.

    Rules (first match wins):

    1. PO Box / GPO Box / Locked Bag → address (postal address).
    2. Has a 4-digit AU postcode AND (street suffix OR leading digit) →
       address.
    3. Has a leading digit run + a street-suffix keyword → address.
    4. Has a 4-digit AU postcode (alone) → address. AU postcodes are
       4-digit and rarely appear in pure location references.
    5. Has a street-suffix keyword (no postcode/digit) → address. Pure
       "Collins Street" is still an address fragment, not a location.
    6. Otherwise → location. Pure suburb / region / state references
       like "Melbourne", "NSW", "Greater Sydney", "the Yarra Valley".

    The function takes only the span text — context is intentionally not
    used here, because the caller (``resolve_account_numbers`` /
    ``resolve_one``) already has access to the full source text via
    other code paths if needed. Span-local rules give predictable
    behaviour and are cheap to unit-test.
    """
    if not span_text:
        return "location"
    text = span_text.strip()
    if not text:
        return "location"

    # 1. PO Box variants always resolve to address.
    if _POSTAL_BOX_RE.search(text):
        return "address"

    has_street = bool(_AU_STREET_SUFFIX_RE.search(text))
    has_postcode = bool(_AU_POSTCODE_RE.search(text))
    has_street_number = bool(_STREET_NUMBER_RE.search(text))
    has_state = bool(_STATE_TOKEN_RE.search(text))

    # 2./3. Strong street-address signal: digits + street keyword OR
    # digits + postcode. Both combinations are unambiguously address.
    if has_street_number and (has_street or has_postcode):
        return "address"

    # 4. Has a 4-digit postcode — almost always address. A bare suburb
    # name with no postcode would be tagged location; "Melbourne 3000"
    # is more likely "postcode-bound suburb" which downstream policy
    # still wants as ADDRESS so it stays redacted.
    if has_postcode:
        return "address"

    # 5. Has a street-suffix keyword — address fragment. "Collins Street"
    # alone is still a street name (address), not a location.
    if has_street:
        return "address"

    # 6. Pure suburb / state / region / "Greater X" / "the Yarra Valley".
    # If it's only a state token, definitely location.
    if has_state and not has_street_number:
        return "location"

    return "location"


def _looks_like_postal_address(span_text: str) -> bool:
    """Convenience helper for callers that want a boolean address signal."""
    return _disambiguate_address_vs_location(span_text) == "address"


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


# MRN-shaped digit run that lives downstream of an MRN/URN-style label.
# Accepts optional single leading letter (e.g. "A123456") + 4-10 digits.
_MRN_SHAPE_RE = re.compile(r"^[A-Z]?\d{4,10}$", re.IGNORECASE)

# When the label uses these specific MRN/URN keywords, the `-` and `: `
# between the label and the digit run is part of the binding, not a break.
_MRN_LABEL_KEYWORDS_RE = re.compile(
    r"\b(?:mrn|medical\s+record\s+number|hospital\s+ur(?:n)?|urn)\b",
    re.IGNORECASE,
)


def _label_prior(text: str, start: int, end: int, window: int = 40) -> PIICategory | None:
    """Look at the ~40 chars immediately before the span for a label like 'TFN:'.

    We require the label to be the *nearest* one to the value — comma /
    semicolon / newline / period-space characters between the label and the
    value break the binding so we don't, e.g., bind a TFN label to a
    subsequent ABN.

    Special MRN handling (Phase 2.x widening): when the candidate value is
    MRN-shaped (digit run, optional single leading letter) AND the chars
    sitting between the label and the value include ``-`` or ``: ``, that
    separator is treated as PART of the binding. This recovers the
    substantial MRN-recall loss observed when OpenAI's NER returns just
    the digits while the ``MRN-`` label sits immediately to the left.
    The widening applies only when the label keyword itself is MRN-shaped
    (mrn / medical record number / hospital urn) — TFN / ABN / Medicare /
    BSB bindings are unaffected.
    """
    left = max(0, start - window)
    snippet = text[left:start]
    span_value = text[start:end].strip()
    value_is_mrn_shaped = bool(_MRN_SHAPE_RE.match(span_value))

    # Legacy behaviour: cut on the standard hard separators (newline / `;` /
    # `,` / `. `). We intentionally do NOT add `:` / `-` as hard separators,
    # because labels routinely use `Label: value` and `MRN-value` patterns —
    # cutting on those would discard the label and lose the binding.
    base_separators = ("\n", ";", ",", ". ")
    for separator in base_separators:
        sep_idx = snippet.rfind(separator)
        if sep_idx != -1:
            snippet = snippet[sep_idx + len(separator):]

    # Phase 2.x widening: when the value is MRN-shaped AND the snippet
    # contains an MRN keyword, force MEDICAL_RECORD_NUMBER even if a
    # different label appears closer — because the snippet up to the MRN
    # token already passed the hard-separator cut, the binding is intact.
    # This is a no-op for non-MRN-shaped values, so TFN/ABN/Medicare
    # bindings remain unchanged.
    if value_is_mrn_shaped and _MRN_LABEL_KEYWORDS_RE.search(snippet):
        return PIICategory.MEDICAL_RECORD_NUMBER

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


def _try_explicit_prefix_structural(value: str) -> PIICategory | None:
    """Match structurally-tagged identifiers whose prefix is unambiguous.

    These are values where the prefix word/letters carry the category
    without further checksum work — they MUST be tried before the
    checksum dispatch, because the trailing digit run can satisfy a
    weaker checksum (e.g. ``MRN-686040`` → 6-digit BSB shape).
    """
    stripped = value.strip()
    # MRN with explicit prefix: "MRN-12345", "MRN_4567", "MRN:9999"
    if re.match(r"^MRN[-_:]\s?\w", stripped, re.IGNORECASE):
        return PIICategory.MEDICAL_RECORD_NUMBER
    # URN with explicit prefix
    if re.match(r"^UR[N]?[-_:]\s?\w", stripped, re.IGNORECASE):
        return PIICategory.MEDICAL_RECORD_NUMBER
    return None


def _try_structural_matchers(value: str) -> PIICategory | None:
    """Match shape-only (non-checksum) AU identifiers."""
    stripped = value.strip()
    if _IHI_RE.match(stripped):
        return PIICategory.HEALTHCARE_IDENTIFIER
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

    # 2a. Explicit-prefix structural identifiers — must precede the checksum
    # pass because the digit-only suffix of, say, "MRN-686040" could otherwise
    # be claimed by the BSB format validator (6 digits = BSB shape).
    explicit_struct = _try_explicit_prefix_structural(value)
    if explicit_struct is not None:
        return explicit_struct, None

    # 2b. Checksum-validated AU identifiers
    checksum_hit = _try_checksum_validators(value)
    if checksum_hit is not None:
        return checksum_hit

    # 3. Remaining structural-only AU identifiers (no explicit prefix)
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
            # v0.4.3 — disambiguate `private_address` → address vs location.
            # openai/privacy-filter collapses both into the same label; the
            # span-local heuristic re-tags pure suburb/region/state spans
            # as LOCATION while keeping street-bearing spans as ADDRESS.
            if openai_cat == "private_address":
                primary = _disambiguate_address_vs_location(value)
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
