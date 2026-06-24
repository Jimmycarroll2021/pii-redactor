"""Regression tests for VULN-01 / SEC-01 — the checksum-drop fail-OPEN leak.

Before the fix, a malformed Australian identifier that failed its checksum was
silently dropped by the validator while a shorter overlapping regex match (e.g.
BSB = the first six digits) survived and redacted only part of the token,
leaving the discriminating tail in cleartext while the document was reported as
a clean pass.

The fail-closed contract these tests pin:
  1. No digit substring of a malformed ID-shaped token survives in the output.
  2. Such a redaction sets needs_review on the span and the result.
  3. Valid identifiers are unaffected (no spurious needs_review, still redacted).
"""
from pathlib import Path

from pii_redactor import AuditLog, PIIDetector, Pipeline, Redactor
from pii_redactor.llm_client import MockClient


def _pipeline(tmp_path: Path) -> Pipeline:
    return Pipeline(
        detector=PIIDetector(llm_client=MockClient(), use_grammar=False),
        redactor=Redactor(style="numbered"),
        audit=AuditLog(path=str(tmp_path / "audit.jsonl"), enabled=True),
        model_name="mock",
    )


# (label, malformed value that FAILS its checksum, raw substrings that must NOT leak)
MALFORMED = [
    ("TFN", "123 456 789", ["123 456 789", "789", "456"]),
    ("ABN", "12 345 678 901", ["12 345 678 901", "678 901", "901"]),
    ("ACN", "004 085 617", ["004 085 617", "617", "085"]),
    ("Medicare", "2950 04000 0", ["2950 04000 0", "2950 04000", "04000"]),
]


def test_malformed_ids_leave_no_cleartext_residue(tmp_path):
    pipeline = _pipeline(tmp_path)
    for label, value, must_not_leak in MALFORMED:
        text = f"Reference {label}: {value} end."
        result = pipeline.process_document(text)
        for fragment in must_not_leak:
            assert fragment not in result.redacted_text, (
                f"{label}: fragment {fragment!r} leaked into output: "
                f"{result.redacted_text!r}"
            )
        assert result.needs_review is True, f"{label}: expected needs_review"


def test_valid_ids_are_not_flagged_needs_review(tmp_path):
    # Valid TFN + valid ABN must redact cleanly without a spurious needs_review
    # (a spurious overlapping interpretation that fails its checksum must not
    # contaminate the validated span).
    pipeline = _pipeline(tmp_path)
    result = pipeline.process_document("TFN: 123 456 782 ABN: 33 051 775 556")
    assert "123 456 782" not in result.redacted_text
    assert "33 051 775 556" not in result.redacted_text
    assert result.needs_review is False


def test_no_partial_overlap_residue(tmp_path):
    # A malformed TFN immediately followed by a valid-looking BSB fragment must
    # not produce a half-redacted span. Belt-and-suspenders for the union merge.
    pipeline = _pipeline(tmp_path)
    result = pipeline.process_document("Bad TFN 999 999 999 here")
    assert "999" not in result.redacted_text
