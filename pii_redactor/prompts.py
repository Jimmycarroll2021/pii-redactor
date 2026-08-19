"""Prompt templates for PII extraction.

The default prompt follows the zero-shot pattern from Wiest et al.
(NEJM AI, 2024). The category list is extended with Australian
government identifiers. Output structure is enforced by the GBNF
grammar in `grammar.py` when using llama.cpp; for backends without
grammar support, the prompt instructs the model to return JSON only
and the response is parsed defensively.
"""
from __future__ import annotations

DEFAULT_SYSTEM_PROMPT = """You are a PII extraction assistant. Your only job \
is to identify personally identifiable information in the user's text and \
return it as structured JSON. You never explain, summarise, or refuse. You \
return JSON and nothing else."""


DEFAULT_USER_PROMPT = """Extract every piece of personally identifiable \
information (PII) from the text below. Return a single JSON object with one \
key, "pii", whose value is an array of objects. Each object must have:

- "category": one of {categories}
- "value": the exact substring as it appears in the text

Rules:
- Include every occurrence, even repeated values.
- Never invent categories outside the allowed category list. If the text contains
  an SSN/social-security-like value and "ssn" is not an allowed category, output
  it as "generic_id".
- Extract the exact PII substring only. Do not include surrounding punctuation,
  quotes, suffix letters, prose, or JSON syntax around the value.
- Use "name" for personal names of individuals (not organisation names). \
This INCLUDES clinical / professional titles in front of a name. Treat each \
of these patterns as ONE single "name" PII value, including the title and any \
trailing period: \
"Dr. Smith", "Prof. Williams", "A/Prof. Robinson", "Mr. Thomas", "Ms. Martinez", \
"Mrs. Jones", "Sir John Smith", "Dame Helen Mirren". Always extract the FULL \
"<title>. <surname>" or "<title> <given> <surname>" span as a single name — do \
NOT emit the title and the surname as separate entries.
- Use "address" for ANY string that identifies a location: postal addresses, \
street addresses, suburbs, localities, towns, cities, postcodes, and \
location-only descriptors. Specifically:
  * Full street addresses with a number, street name, and suburb/state/postcode \
    (e.g. "42 George Street, Surry Hills NSW 2010").
  * Compound addresses split across phrases (e.g. "located at Suite 378, \
    Yolanda Mountain, Burkeberg").
  * Bare suburb, town, locality, or city names whenever they appear in prose \
    that describes where something is located, even with no street component \
    (e.g. "Affected Area: Tiruvottiyur, Karnal" — extract "Tiruvottiyur" AND \
    "Karnal" as two separate addresses, OR the joined string "Tiruvottiyur, Karnal" \
    if they read as one locality phrase).
  * Postcodes alone whenever they appear under any address-like label such \
    as "Postcode:", "Zip:", "Address:", or stand alone in a postal context \
    (e.g. "Postcode: LN0Y 4PT" — extract "LN0Y 4PT" as address).
  * Street references without a leading number when context implies an \
    address (e.g. "the section of Cooper lane, Raymondhaven, will be closed" — \
    extract "Cooper lane, Raymondhaven" as address).
  When in doubt about whether a token is a location, prefer to extract it as \
  "address" over leaving it out. Address recall is critical; over-extraction \
  is acceptable. Capture the full span when multiple address components appear \
  together; do NOT truncate to just the street.
- Use "patient_id" for labelled patient identifiers that are not medical
  record numbers.
- Use "username" for usernames, handles, login names, screen names, or account names,
  even when they appear naturally inside prose or student essays.
- Use "generic_id" for labelled or obvious identifier numbers that are not covered
  by a more specific category, including student IDs, user IDs, account IDs, and
  long numeric IDs. SSN-style values such as 123-45-6789 are generic_id unless
  a more specific supported category applies.
- Use "url" for personal URLs, websites, profiles, social media links, and web handles
  written as http://, https://, www., or similar URL-like text.
- Use "medical_record_number" for MRN, URN, hospital number, or labelled
  medical-record identifiers.
- Use "healthcare_identifier" for IHI or other labelled healthcare identifiers.
- Use "date_of_birth" only when context confirms it is a birth date; \
otherwise use "date". If the surrounding text uses ambiguous labels like \
"reference", "DOB on file", "born on", or simply gives a date in YYYY-MM-DD or \
DD/MM/YYYY format inside a person-record, payment, or notice context, prefer \
"date_of_birth" over "date" when no other DoB candidate exists in the document. \
Either category counts as PII — always extract the value; only the label choice \
varies.
- Use "date" for times and date-like schedule markers too, including values like
  7:55, 07:55, 5:19, June 5th, 1987, and 31/07/1971 even when adjacent prose is
  malformed. For malformed text like "June 5th, 1987s", extract "June 5th, 1987".
- Australian-specific identifiers (TFN, Medicare, ABN, ACN, driver licence, \
passport, Centrelink CRN, BSB/account) must be tagged with their specific \
category, not generic.
- Detect PII across international examples too: non-Australian phone numbers, \
student names in essays, usernames, generic IDs, and personal URLs are PII.
- Return [] if nothing is found.
- Output JSON only. No prose, no explanation, no markdown fences.

Example 1 (full Australian residential address):

Text:
\"\"\"
Patient John Smith (DOB 14/03/1982, MRN HOSP-248813) was referred today at 7:55. TFN: 123 456 782. \
Contact: john.smith@example.com.au, 0412 345 678. \
Residence: 42 George Street, Surry Hills NSW 2010. External ID: 123-45-6789.
\"\"\"

Response:
{{"pii": [{{"category": "name", "value": "John Smith"}}, \
{{"category": "date_of_birth", "value": "14/03/1982"}}, \
{{"category": "medical_record_number", "value": "HOSP-248813"}}, \
{{"category": "date", "value": "7:55"}}, \
{{"category": "tfn", "value": "123 456 782"}}, \
{{"category": "email", "value": "john.smith@example.com.au"}}, \
{{"category": "phone", "value": "0412 345 678"}}, \
{{"category": "address", "value": "42 George Street, Surry Hills NSW 2010"}}, \
{{"category": "generic_id", "value": "123-45-6789"}}]}}

Example 2 (compound address with suite, locality and town across phrases):

Text:
\"\"\"
Transaction details: gasLimit set to 1000000 units by tw_brian740, \
contactable at +1-869-341-9301x7005, located at Suite 378, Yolanda Mountain, Burkeberg.
\"\"\"

Response:
{{"pii": [{{"category": "username", "value": "tw_brian740"}}, \
{{"category": "phone", "value": "+1-869-341-9301x7005"}}, \
{{"category": "address", "value": "Suite 378, Yolanda Mountain, Burkeberg"}}]}}

Example 3 (clinical titles + medical record + IHI):

Text:
\"\"\"
OUTPATIENT CLINIC NOTE — 16/03/2026
Reviewed Jackson Nguyen, DOB 01/06/1969, record MRN-153084 (clinician A/Prof. Robinson). \
Patient reachable on (03) 8268 5228. IHI 8003 1857 2352 5708.
\"\"\"

Response:
{{"pii": [{{"category": "date", "value": "16/03/2026"}}, \
{{"category": "name", "value": "Jackson Nguyen"}}, \
{{"category": "date_of_birth", "value": "01/06/1969"}}, \
{{"category": "medical_record_number", "value": "MRN-153084"}}, \
{{"category": "name", "value": "A/Prof. Robinson"}}, \
{{"category": "phone", "value": "(03) 8268 5228"}}, \
{{"category": "healthcare_identifier", "value": "8003 1857 2352 5708"}}]}}

Example 4 (bare suburb / labelled postcode / no-number street as addresses):

Text:
\"\"\"
**Power Outage Report**
**Affected Area:** Tiruvottiyur, Karnal
**Street Address:** 822 Sidhu Path, 053774, Karnal
**Postcode:** LN0Y 4PT
**Notice:** The section of Cooper lane, Raymondhaven, will be closed.
DOB on file: 1941-05-02.
\"\"\"

Response:
{{"pii": [{{"category": "address", "value": "Tiruvottiyur"}}, \
{{"category": "address", "value": "822 Sidhu Path, 053774, Karnal"}}, \
{{"category": "address", "value": "LN0Y 4PT"}}, \
{{"category": "address", "value": "Cooper lane, Raymondhaven"}}, \
{{"category": "date_of_birth", "value": "1941-05-02"}}]}}

Now extract from:

Text:
\"\"\"
{text}
\"\"\""""


def build_prompt(text: str, categories: list[str]) -> tuple[str, str]:
    """Render the system and user prompts for a chunk of text.

    Returns (system_prompt, user_prompt).
    """
    cat_list = ", ".join(f'"{c}"' for c in categories)
    return DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT.format(
        categories=cat_list, text=text
    )
