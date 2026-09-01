"""Regression: label-anchored names must be detected by the regex-only path.

`validators.PATTERNS` had no `PIICategory.NAME` entry at all, so `MockClient`
- the library's zero-config default backend (`PIIR_BACKEND=mock`, used by
`Config.from_env()` and the Gradio demo's fallback) - never redacted names.
`Contact: Jamie Patel` from the library's own shipped demo fixture
(`app.py` EXAMPLES) leaked `Jamie Patel` verbatim through the full
pipeline. RUNTIME-01.

The fix is a high-precision, label-anchored regex (mirrors the existing
PATIENT_ID / MEDICAL_RECORD_NUMBER pattern style) - not general free-text
NER, which the regex-only path cannot do without unacceptable false
positives. Generic `Name:` fields stay out of the engine regex so the
workspace signature-context safety net can keep its dedicated
`SIGNATURE_NAME` placeholders.
"""

from __future__ import annotations

from pii_redactor.detector import PIIDetector
from pii_redactor.llm_client import MockClient
from pii_redactor.models import PIICategory
from pii_redactor.validators import PATTERNS


class TestNamePatternDirect:
    def test_contact_label_matches_name(self) -> None:
        match = PATTERNS[PIICategory.NAME].search("Contact: Jamie Patel, jpatel@example.com")
        assert match is not None
        assert match.group("value") == "Jamie Patel"

    def test_label_matching_remains_case_insensitive(self) -> None:
        cases = [
            ("contact: Jamie Patel", "Jamie Patel"),
            ("EMERGENCY CONTACT: Alex Nguyen", "Alex Nguyen"),
        ]
        for text, expected in cases:
            match = PATTERNS[PIICategory.NAME].search(text)
            assert match is not None, f"no match for {text!r}"
            assert match.group("value") == expected

    def test_various_labels_match(self) -> None:
        cases = [
            ("Patient: Mary-Anne O'Connor", "Mary-Anne O'Connor"),
            ("Client - David Lee", "David Lee"),
            ("Attn: Sarah Jane Wilson", "Sarah Jane Wilson"),
            ("Emergency contact: Alex Nguyen", "Alex Nguyen"),
        ]
        for text, expected in cases:
            match = PATTERNS[PIICategory.NAME].search(text)
            assert match is not None, f"no match for {text!r}"
            assert match.group("value") == expected

    def test_generic_name_label_not_matched(self) -> None:
        assert PATTERNS[PIICategory.NAME].search("Name: John Smith") is None

    def test_unlabelled_name_not_matched(self) -> None:
        # Confirms this stays a label-anchored backstop, not free-text NER -
        # a bare capitalised word pair with no label must not fire.
        assert (
            PATTERNS[PIICategory.NAME].search("Please update the case for Sarah Mitchell") is None
        )

    def test_common_capitalised_phrase_not_matched(self) -> None:
        # Guards against the label list swallowing ordinary prose.
        assert PATTERNS[PIICategory.NAME].search("Northbourne Avenue, Canberra") is None

    def test_lowercase_phrases_after_supported_labels_not_matched(self) -> None:
        cases = [
            "Contact: service timeout",
            "Customer: pending review",
            "Patient: follow up required",
        ]
        for text in cases:
            assert PATTERNS[PIICategory.NAME].search(text) is None, text


class TestJamiePatelLeakFixture:
    """Reproduces the exact leaked fixture from app.py EXAMPLES verbatim."""

    TEXT = (
        "Vendor onboarding for Acme Logistics Pty Ltd, ABN 33 051 775 556, "
        "ACN 051 775 556. Contact: Jamie Patel, jpatel@acmelogistics.com.au, "
        "(02) 6271 7000. Bank details: BSB 062-000, Account 12345678."
    )

    def test_mock_backend_detects_name_span(self) -> None:
        det = PIIDetector(llm_client=MockClient(), use_grammar=False)
        spans = det.detect(self.TEXT)
        name_spans = [s for s in spans if s.category == PIICategory.NAME]
        assert name_spans, "MockClient must detect the labelled name span"
        assert any(s.value == "Jamie Patel" for s in name_spans)

    def test_mock_backend_redacts_name_from_output(self, tmp_path) -> None:
        from pii_redactor import AuditLog, Pipeline, Redactor

        pipeline = Pipeline(
            detector=PIIDetector(llm_client=MockClient(), use_grammar=False),
            redactor=Redactor(style="numbered"),
            audit=AuditLog(path=str(tmp_path / "audit.jsonl"), enabled=True),
            model_name="mock",
        )
        result = pipeline.process_document(self.TEXT)
        assert "Jamie Patel" not in result.redacted_text
        assert "[REDACTED_NAME_001]" in result.redacted_text

    def test_mock_backend_ignores_lowercase_contact_phrase(self) -> None:
        det = PIIDetector(llm_client=MockClient(), use_grammar=False)
        spans = det.detect("Contact: service timeout")
        assert not [s for s in spans if s.category == PIICategory.NAME]
