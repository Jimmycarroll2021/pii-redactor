"""AU organisation + location recognisers (v0.4.1).

Phase 5 closes the two biggest Phase 4 gaps: organisation recall (3-29%
across sectors) and location recall (Tier 1 ‑43pp on federal/legal). Both
are pure rule + gazetteer — no model changes — and run inside the
regex_supplement layer.

Design:
    - Lazy load: gazetteers are read on first use, cached on the class.
    - Env knobs: ``PIIR_REGEX_ORGANISATION`` / ``PIIR_REGEX_LOCATION``
      (default true). Path overrides via ``PIIR_ORG_GAZETTEER_PATH`` /
      ``PIIR_LOC_GAZETTEER_PATH``.
    - Conservative emission: never tag a span that already overlaps an
      OpenAI / privacy-filter span tagged ``address`` or ``name`` (the
      pipeline merge step would discard the new tag anyway, but suppressing
      here saves CPU).

Sources used to build the bundled gazetteers:
    - data.gov.au — federal department list (composite gazetteer)
    - asic.gov.au — registered company / commission register
    - matthewproctor/australianpostcodes — CC0 postcode + suburb list

Files live under ``pii_redactor/data/gazetteers/`` (also mirrored at
``redact-au/data/gazetteers/`` for the company repo).
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from ..models import PIICategory, PIISpan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Env knobs
# ---------------------------------------------------------------------------
def _env_truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def organisation_enabled() -> bool:
    return _env_truthy("PIIR_REGEX_ORGANISATION", True)


def location_enabled() -> bool:
    return _env_truthy("PIIR_REGEX_LOCATION", True)


def _gazetteer_dir() -> Path:
    """Default gazetteer directory — packaged inside pii_redactor."""
    return Path(__file__).resolve().parent.parent / "data" / "gazetteers"


# ---------------------------------------------------------------------------
# Gazetteer loaders (cached)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_organisations() -> tuple[set[str], dict[str, str]]:
    """Return ``(canonical_names, acronyms)``.

    ``canonical_names`` is a case-sensitive set of full organisation names.
    ``acronyms`` maps ``ACRONYM`` → canonical expansion (for context-gated
    acronym detection).
    """
    path = Path(os.environ.get("PIIR_ORG_GAZETTEER_PATH") or
                _gazetteer_dir() / "au_organisations.txt")
    acro_path = (_gazetteer_dir() / "au_organisation_acronyms.txt")
    names: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            names.add(line)
    acronyms: dict[str, str] = {}
    if acro_path.exists():
        for line in acro_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                acronyms[parts[0]] = parts[1]
    logger.debug("Loaded %d AU organisations, %d acronyms",
                 len(names), len(acronyms))
    return names, acronyms


@lru_cache(maxsize=1)
def load_locations() -> tuple[dict[str, set[str]], dict[str, set[tuple[str, str]]]]:
    """Return ``(suburbs, postcodes)``.

    ``suburbs[name]`` → set of states (e.g. ``{'NSW', 'VIC'}``).
    ``postcodes[code]`` → set of ``(suburb, state)`` tuples.
    """
    sub_path = Path(os.environ.get("PIIR_LOC_GAZETTEER_PATH") or
                    _gazetteer_dir() / "au_suburbs.txt")
    pc_path = (_gazetteer_dir() / "au_postcodes.txt")
    suburbs: dict[str, set[str]] = {}
    if sub_path.exists():
        for line in sub_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                name, states = line.split("|", 1)
                suburbs[name] = set(s.strip() for s in states.split(",") if s.strip())
            else:
                suburbs[line] = set()
    postcodes: dict[str, set[tuple[str, str]]] = {}
    if pc_path.exists():
        for line in pc_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                code, entries = line.split("|", 1)
                for ent in entries.split(","):
                    if ":" in ent:
                        sub, st = ent.split(":", 1)
                        postcodes.setdefault(code, set()).add(
                            (sub.strip(), st.strip())
                        )
    logger.debug("Loaded %d suburbs, %d postcodes",
                 len(suburbs), len(postcodes))
    return suburbs, postcodes


def clear_gazetteer_cache() -> None:
    """Used by tests to force a reload after env overrides."""
    load_organisations.cache_clear()
    load_locations.cache_clear()


# ---------------------------------------------------------------------------
# AU state abbreviations (manual)
# ---------------------------------------------------------------------------
AU_STATES_FULL = {
    "New South Wales", "Victoria", "Queensland", "Western Australia",
    "South Australia", "Tasmania", "Northern Territory",
    "Australian Capital Territory",
}
AU_STATES_ABBREV = {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT"}
# Used to gate acronym matches and disambiguate state abbrevs from common words
AU_STATE_CONTEXT = (
    "australia", "australian", "sydney", "melbourne", "brisbane", "perth",
    "adelaide", "hobart", "darwin", "canberra", "newcastle", "wollongong",
    "geelong", "gold coast", "sunshine coast", "townsville", "cairns",
    "ballarat", "bendigo", "toowoomba",
)


# ---------------------------------------------------------------------------
# Organisation patterns (precompiled)
# ---------------------------------------------------------------------------
# Companies with corporate suffixes — high precision.
# v0.4.3: extend the suffix vocabulary to cover medical, legal, and community
# organisations the Phase 4 sector bench was missing (clinics, law firms,
# cooperatives, mutuals). The leading capitalised-token run requires the
# first token to start with a letter and contain at least one lowercase
# letter — this prevents identifier-like ALL-CAPS+digits tokens
# (e.g. "DEN0004340031") from being misread as the head of an org name.
_ORG_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"(?:[A-Z][a-z][\w&'\-]*(?:\s+(?:&\s+)?[A-Z][\w&'\-]*){0,5})"
    r"\s+"
    r"(?:Pty\s*\.?\s*Ltd\.?|Pty\s+Limited|Ltd\.?|Limited|LLP|"
    r"Corporation|Corp\.?|Inc\.?|Co\.?|"
    r"Group|Holdings|Industries|Associates|Partners|LLC|Australia|Australasia|"
    # v0.4.3 — medical
    r"Clinic|Medical\s+Centre|Health\s+Service|Health\s+Services|"
    # v0.4.3 — legal
    r"Lawyers|Legal|Solicitors|Barristers|Chambers|"
    # v0.4.3 — community / non-profit / financial mutuals
    r"Cooperative|Co-operative|Mutual|Society|Association|Foundation|Trust)"
    r")\b"
)

# `Practice` is too generic a suffix on its own — it collides with
# "Practice address:" labels in registration documents. Only emit when
# the leading capitalised-token run contains a clearly-medical
# qualifier ("Medical", "Dental", "General", "Specialist", "Family",
# "Group") so we tag "Eastern Suburbs Medical Practice" but NOT
# "DEN0004340031\nPractice".
_ORG_PRACTICE_PATTERN = re.compile(
    r"\b("
    r"(?:[A-Z][a-z][\w&'\-]*\s+){0,4}"
    r"(?:Medical|Dental|General|Specialist|Family|Group|Surgical|"
    r"Orthopaedic|Paediatric|Veterinary|Legal|Family\s+Law)"
    r"\s+Practice"
    r")\b"
)

# Compound legal-firm patterns like "Smith & Partners", "Brown, Black & Co",
# "Jones and Associates Solicitors". The leading run must look like a
# law-firm name (initial-cap surnames + ampersand / "and"). Conservative —
# the trailing keyword is required so we don't tag two-name phrases.
_ORG_LEGAL_PARTNERS_PATTERN = re.compile(
    r"\b("
    r"[A-Z][\w'\-]+"
    r"(?:\s*,\s*[A-Z][\w'\-]+)*"
    r"\s+(?:&|and)\s+"
    r"(?:Partners|Associates|Co\.?)"
    r"(?:\s+(?:Lawyers|Legal|Solicitors|Barristers|Chambers))?"
    r")\b"
)

# Government / department style names.
_ORG_DEPT_PATTERN = re.compile(
    r"\b("
    r"(?:Department|Ministry|Office|Bureau|Commission|Authority|"
    r"Service|Agency|Council|Board|Tribunal)"
    r"\s+(?:of|for|on)\s+"
    r"[A-Z][\w\-']*(?:\s+(?:and|of|for)?\s*[A-Z][\w\-']*){0,6}"
    r")\b"
)

# Hospitals
_ORG_HOSPITAL_PATTERN = re.compile(
    r"\b("
    r"(?:(?:Royal|St\.?|Saint|Mater|Mercy|Calvary|Westmead|Northern|Western|"
    r"Eastern|Southern|Sydney|Melbourne|Brisbane|Perth|Adelaide|Princess)\s+)+"
    r"(?:[A-Z][\w']*\s+)*"
    r"Hospital"
    r")\b"
)

# v0.4.3 — medical centres / clinics / health services without corporate
# suffix (e.g. "Bayside Medical Centre", "Northside GP Clinic"). Caps-noun
# prefix + medical-facility keyword. Distinct from the suffix pattern so
# 2-3-token names like "Bayside Medical Centre" match cleanly. The first
# token must contain a lowercase letter so identifier-like ALL-CAPS+digits
# tokens (e.g. "DEN0004340031") cannot anchor a false-positive org span.
_ORG_MEDICAL_FACILITY_PATTERN = re.compile(
    r"\b("
    r"(?:[A-Z][a-z][\w'\-]*\s+){1,4}"
    r"(?:Medical\s+Centre|Health\s+Service|Health\s+Services|"
    r"Health\s+Care|Healthcare|Aged\s+Care|GP\s+Clinic|"
    r"Day\s+Hospital|Day\s+Surgery|Specialist\s+Centre)"
    r")\b"
)

# Universities — both word orders.
_ORG_UNI_PATTERN = re.compile(
    r"\b("
    r"University\s+of\s+[A-Z][\w\-']*(?:\s+[A-Z][\w\-']*){0,3}"
    r"|"
    r"(?:[A-Z][\w\-']*\s+){1,3}University"
    r")\b"
)

# Plain acronym pattern — must be all-caps, 2-8 chars, surrounded by word
# boundaries. Filtering happens later (context check).
_ACRONYM_PATTERN = re.compile(r"\b([A-Z]{2,8})\b")

# Negative filter: common all-caps tokens that should NEVER be tagged as orgs.
_ACRONYM_BLOCKLIST = frozenset({
    "ID", "PIN", "URL", "HTTP", "HTTPS", "API", "PDF", "DOC", "XML", "JSON",
    "CSV", "TSV", "HTML", "CSS", "JS", "OK", "YES", "NO", "TRUE", "FALSE",
    "USA", "UK", "EU", "UN", "WHO", "WTO", "NATO",
    "AM", "PM", "AEST", "AEDT", "ACST", "ACDT", "AWST", "GMT", "UTC",
    "MR", "MRS", "MS", "DR", "PROF", "PHD",
    "GP", "GPS", "ICU", "ED", "PT", "RN",  # clinical — too generic alone
})


# ---------------------------------------------------------------------------
# Location patterns
# ---------------------------------------------------------------------------
_REGION_PATTERN = re.compile(
    r"\b("
    r"(?:Greater\s+|Inner\s+|Outer\s+|Central\s+|North(?:ern)?\s+|"
    r"South(?:ern)?\s+|East(?:ern)?\s+|West(?:ern)?\s+)"
    r"[A-Z][\w\-']*(?:\s+[A-Z][\w\-']*){0,2}"
    r")\b"
)

# v0.4.3 — informal Greater/Inner directional regions with explicit AU
# anchors (capital city or compass direction). Matches "Greater Sydney",
# "Inner West", "Inner East", "Northern Beaches", "Western Sydney", etc.
_INFORMAL_REGION_PATTERN = re.compile(
    r"\b("
    r"Greater\s+(?:Sydney|Melbourne|Brisbane|Perth|Adelaide|Canberra|"
    r"Hobart|Darwin|Newcastle|Wollongong|Geelong)"
    r"|"
    r"Inner\s+(?:West|East|North|South|City|Sydney|Melbourne|Brisbane)"
    r"|"
    r"Outer\s+(?:West|East|North|South|Sydney|Melbourne|Brisbane)"
    r"|"
    r"Northern\s+(?:Beaches|Suburbs|Rivers|Territory|Tablelands)"
    r"|"
    r"Southern\s+(?:Highlands|Tablelands|Suburbs|Cross)"
    r"|"
    r"Eastern\s+(?:Suburbs|Beaches|Freeway)"
    r"|"
    r"Western\s+(?:Suburbs|Sydney|Melbourne|Australia)"
    r"|"
    r"Mid[\s-]North\s+Coast"
    r"|"
    r"Far\s+North\s+(?:Queensland|Coast)"
    r")\b"
)

# v0.4.3 — well-known AU named regions and "the X" phrases. These are
# regional / topographical references with no street component so they
# resolve to LOCATION (not ADDRESS).
_NAMED_REGION_PATTERN = re.compile(
    r"\b(?:the\s+)?("
    r"Top\s+End|Outback|Goldfields|Pilbara|Kimberley|"
    r"Hunter\s+Valley|Yarra\s+Valley|Barossa\s+Valley|"
    r"Margaret\s+River|McLaren\s+Vale|Mornington\s+Peninsula|"
    r"Sunshine\s+Coast|Gold\s+Coast|Central\s+Coast|"
    r"Blue\s+Mountains|Snowy\s+Mountains|Great\s+Dividing\s+Range|"
    r"Daintree|Kakadu|Red\s+Centre|Atherton\s+Tableland"
    r")\b",
    re.IGNORECASE,
)

# v0.4.3 — "CBD" / "Central Business District" within AU city context.
_CBD_PATTERN = re.compile(
    r"\b("
    r"(?:Sydney|Melbourne|Brisbane|Perth|Adelaide|Canberra|"
    r"Hobart|Darwin|Newcastle|Wollongong|Geelong)\s+CBD"
    r"|"
    r"CBD\s+of\s+(?:Sydney|Melbourne|Brisbane|Perth|Adelaide|"
    r"Canberra|Hobart|Darwin)"
    r"|"
    r"(?:Sydney|Melbourne|Brisbane|Perth|Adelaide|Canberra|"
    r"Hobart|Darwin)\s+Central\s+Business\s+District"
    r")\b"
)

# Standalone 4-digit number candidates (for postcode resolution).
_FOUR_DIGITS = re.compile(r"\b(\d{4})\b")

# State abbreviation pattern.
_STATE_ABBREV_PATTERN = re.compile(
    r"\b(NSW|VIC|QLD|WA|SA|TAS|NT|ACT)\b"
)

# v0.4.3 — street-suffix keywords used by the address-vs-location
# disambiguator in au_resolver. Exposed at module scope so the resolver
# can import the canonical list.
AU_STREET_SUFFIXES = frozenset({
    "Street", "St", "Road", "Rd", "Avenue", "Ave", "Lane", "Ln",
    "Drive", "Dr", "Crescent", "Cres", "Court", "Ct", "Place", "Pl",
    "Way", "Highway", "Hwy", "Parade", "Pde", "Boulevard", "Blvd",
    "Terrace", "Tce", "Close", "Cl", "Circuit", "Cct", "Esplanade",
    "Esp", "Square", "Sq", "Mews", "Walk", "Track", "Trail", "Loop",
    "Rise", "View", "Vista", "Grove", "Gardens", "Gdns", "Park",
})


# ---------------------------------------------------------------------------
# Recogniser classes
# ---------------------------------------------------------------------------
class AUOrganisationRecogniser:
    """Rule + gazetteer recogniser for AU organisations.

    Returns ``list[PIISpan]`` with category ``ORGANISATION``. Spans never
    overlap each other; the merge step in the pipeline handles overlap
    with NER spans from openai/privacy-filter.
    """

    def __init__(self) -> None:
        self._names, self._acronyms = load_organisations()

    def recognise(self, text: str) -> list[PIISpan]:
        if not text:
            return []
        spans: list[tuple[int, int, str, bool]] = []  # (start, end, value, validated)
        text_lower = text.lower()

        # 1. Exact gazetteer hits — case-sensitive
        for name in self._names:
            if not name or len(name) < 3:
                continue
            # Word-boundary search; case-sensitive
            for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
                spans.append((m.start(), m.end(), m.group(0), True))

        # 2. Corporate suffix (Pty Ltd / Limited / Corp / etc.)
        for m in _ORG_SUFFIX_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 3. Department / Ministry / Authority …
        for m in _ORG_DEPT_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 4. Hospitals
        for m in _ORG_HOSPITAL_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 5. Universities
        for m in _ORG_UNI_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 5a. v0.4.3 — medical centres / clinics / day surgeries
        for m in _ORG_MEDICAL_FACILITY_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 5b. v0.4.3 — legal "& Partners / and Associates" compound names
        for m in _ORG_LEGAL_PARTNERS_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 5c. v0.4.3 — qualified medical "Practice" names
        for m in _ORG_PRACTICE_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), False))

        # 6. Acronyms — only if there's context (expansion present in doc OR
        #    expansion keyword within 200 chars).
        for m in _ACRONYM_PATTERN.finditer(text):
            tok = m.group(1)
            if tok in _ACRONYM_BLOCKLIST:
                continue
            if tok in AU_STATES_ABBREV:
                # States handled by location recogniser
                continue
            if tok not in self._acronyms:
                continue
            expansion = self._acronyms[tok].lower()
            window_lo = max(0, m.start() - 200)
            window_hi = min(len(text), m.end() + 200)
            window = text_lower[window_lo:window_hi]
            if expansion in window:
                spans.append((m.start(), m.end(), tok, True))
                continue
            # Fallback: any known context keyword. Acronyms file format:
            #   ACRONYM\tcanonical\tcontext1,context2,...
            # We didn't preserve the third column in the dict yet, so fall
            # back on the expansion's leading words as the context proxy.
            head = " ".join(expansion.split()[:2])
            if head and head in window:
                spans.append((m.start(), m.end(), tok, True))

        # Deduplicate / pick longest at each position
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged: list[tuple[int, int, str, bool]] = []
        last_end = -1
        for st, en, val, ok in spans:
            if st < last_end:
                continue
            merged.append((st, en, val, ok))
            last_end = en

        return [
            PIISpan(
                category=PIICategory.ORGANISATION,
                start=st,
                end=en,
                value=val,
                confidence=1.0 if ok else 0.85,
                validator_passed=ok if ok else None,
            )
            for st, en, val, ok in merged
        ]


class AULocationRecogniser:
    """Rule + gazetteer recogniser for AU locations.

    Tags suburbs (gazetteer-validated), state abbreviations, 4-digit
    postcodes in context, and region phrases ("Greater Sydney", "Inner
    West", etc.).
    """

    # Common false-positive suburb names — they're real suburbs but also
    # extremely common nouns. Only tag if a stronger anchor confirms.
    _AMBIGUOUS_SUBURBS = frozenset({
        "Hill", "Beach", "Park", "Bay", "Point", "Heights", "Vale",
        "Grove", "Springs", "Junction", "Heads", "Plains", "River",
        "Lake", "Creek", "Wood", "Forest", "Garden", "View", "Cross",
        "North", "South", "East", "West", "Central", "Town", "City",
        "Eight Mile Plains",  # also has 'Eight Mile' fragment
        "Industrial Estate", "Estate",
        "The Gap", "Top End", "Outback",
        "Mountain", "Valley", "Plateau",
        "Federation", "Newtown",  # too many homographs
    })

    def __init__(self) -> None:
        self._suburbs, self._postcodes = load_locations()
        # Pre-build a sorted list of suburb names (case-insensitive lookup
        # bucketed by length so we don't scan the whole gazetteer per doc).
        # The recogniser scans tokens, not the gazetteer.
        self._suburbs_ci = {name.lower(): name for name in self._suburbs}

    def recognise(self, text: str) -> list[PIISpan]:
        if not text:
            return []
        spans: list[tuple[int, int, str, bool]] = []
        text_lower = text.lower()

        # 1. State abbreviations — highest confidence
        for m in _STATE_ABBREV_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), True))

        # 2. State full names
        for full in AU_STATES_FULL:
            for m in re.finditer(r"\b" + re.escape(full) + r"\b", text):
                spans.append((m.start(), m.end(), m.group(0), True))

        # 3. Postcodes with context — 4-digit number that is in the
        #    gazetteer AND is preceded/followed by a state abbreviation OR
        #    a recognised suburb within 50 chars.
        for m in _FOUR_DIGITS.finditer(text):
            code = m.group(1)
            if code not in self._postcodes:
                continue
            window_lo = max(0, m.start() - 60)
            window_hi = min(len(text), m.end() + 60)
            window = text[window_lo:window_hi]
            window_lower = window.lower()
            # State abbreviation nearby?
            if _STATE_ABBREV_PATTERN.search(window):
                spans.append((m.start(), m.end(), code, True))
                continue
            # Suburb nearby (case-insensitive, against the postcode's own
            # known suburbs only, to avoid false positives).
            for sub, _st in self._postcodes[code]:
                if sub.lower() in window_lower:
                    spans.append((m.start(), m.end(), code, True))
                    break

        # 4. Suburb gazetteer matches. Scan capitalised word sequences
        #    (1-4 tokens) and check against the gazetteer. Skip ambiguous
        #    single-word suburbs unless they're capitalised AND the next
        #    char is a comma / state.
        for m in re.finditer(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text
        ):
            candidate = m.group(1)
            if candidate.lower() not in self._suburbs_ci:
                continue
            if candidate in self._AMBIGUOUS_SUBURBS:
                # Require state / postcode anchor within 30 chars
                window_hi = min(len(text), m.end() + 30)
                window = text[m.end():window_hi]
                if not (_STATE_ABBREV_PATTERN.search(window)
                        or _FOUR_DIGITS.search(window)):
                    continue
            spans.append((m.start(), m.end(), candidate, True))

        # 5. Region phrases ("Greater Sydney", "Inner West", "North Queensland")
        for m in _REGION_PATTERN.finditer(text):
            candidate = m.group(1)
            # Must include at least one capital noun beyond the directional
            # — guarded by the regex itself, but we re-check the suffix
            # against the suburb / state gazetteers OR a known capital city.
            tail = candidate.rsplit(maxsplit=1)[-1]
            if (tail.lower() in self._suburbs_ci
                    or tail.upper() in AU_STATES_ABBREV
                    or tail in {"Sydney", "Melbourne", "Brisbane", "Perth",
                                "Adelaide", "Hobart", "Darwin", "Canberra",
                                "Australia", "Queensland", "Victoria",
                                "Tasmania", "Territory"}):
                spans.append((m.start(), m.end(), candidate, True))

        # 6. v0.4.3 — informal Greater/Inner/Northern directional regions
        # ("Greater Sydney", "Inner West", "Northern Beaches"). High
        # precision — anchored on either capital city or compass direction.
        for m in _INFORMAL_REGION_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), True))

        # 7. v0.4.3 — named AU regions ("the Yarra Valley", "Pilbara",
        # "Hunter Valley", etc.). Capture group 1 is the bare name; the
        # span itself includes the optional "the " prefix if present.
        for m in _NAMED_REGION_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), True))

        # 8. v0.4.3 — "Sydney CBD" / "CBD of Melbourne" style references.
        for m in _CBD_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), True))

        # Deduplicate / pick longest at each position
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged: list[tuple[int, int, str, bool]] = []
        last_end = -1
        for st, en, val, ok in spans:
            if st < last_end:
                continue
            merged.append((st, en, val, ok))
            last_end = en

        return [
            PIISpan(
                category=PIICategory.LOCATION,
                start=st,
                end=en,
                value=val,
                confidence=1.0 if ok else 0.85,
                validator_passed=ok if ok else None,
            )
            for st, en, val, ok in merged
        ]


# ---------------------------------------------------------------------------
# Public helper: emit org + location spans that don't overlap existing spans
# ---------------------------------------------------------------------------
_SUPPRESSING_CATEGORIES: frozenset[PIICategory] = frozenset({
    PIICategory.ADDRESS,   # AU resolver / regex already tagged full address
    PIICategory.NAME,      # NER tagged a name overlapping a fragment
    PIICategory.EMAIL,
    PIICategory.URL,
})


def _overlap_categories(start: int, end: int, spans: Iterable[PIISpan]) -> set[PIICategory]:
    out: set[PIICategory] = set()
    for sp in spans:
        if not (end <= sp.start or sp.end <= start):
            out.add(sp.category)
    return out


def supplement_org_loc(text: str, existing_spans: list[PIISpan]) -> list[PIISpan]:
    """Run org + location recognisers, filter against existing spans.

    Honours env knobs ``PIIR_REGEX_ORGANISATION`` / ``PIIR_REGEX_LOCATION``.
    Suppresses candidates that overlap an existing high-confidence span
    (``address``, ``name``, ``email``, ``url``) — prevents double-tagging
    a span that the address recogniser already owns.
    """
    extra: list[PIISpan] = []
    if organisation_enabled():
        try:
            org = AUOrganisationRecogniser().recognise(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AU organisation recogniser failed: %s", exc)
            org = []
        for sp in org:
            overlap = _overlap_categories(sp.start, sp.end, existing_spans)
            if overlap & _SUPPRESSING_CATEGORIES:
                continue
            extra.append(sp)

    if location_enabled():
        try:
            loc = AULocationRecogniser().recognise(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AU location recogniser failed: %s", exc)
            loc = []
        for sp in loc:
            overlap = _overlap_categories(sp.start, sp.end,
                                          existing_spans + extra)
            if overlap & _SUPPRESSING_CATEGORIES:
                continue
            extra.append(sp)

    return extra
