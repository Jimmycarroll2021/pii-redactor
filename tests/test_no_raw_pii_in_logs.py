"""Regression tests for SEC-02 / VULN-05 / LOG-01 — raw PII must never be logged.

The Stage-1 hostile audit found that the values the detector declined to redact
on a failed checksum were the exact values it logged verbatim at DEBUG
(``detector.py``), and that ``au_resolver`` logged the raw candidate when a
validator raised. Logging at DEBUG (or any level) writes PII to an unprotected
sink (APP 11 breach).

The contract these tests pin: with logging captured at DEBUG, NO record emitted
during redaction may contain a raw PII value (the malformed-ID digit strings, a
person name, or an email). Only category + offsets + lengths are loggable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pii_redactor import AuditLog, PIIDetector, Pipeline, Redactor
from pii_redactor.hybrid import au_resolver
from pii_redactor.llm_client import MockClient

# Raw values that must never appear in any captured log message. Includes the
# malformed-ID fragments the audit saw leak and free-text PII.
RAW_PII = [
    "123 456 789",
    "789",
    "12 345 678 901",
    "678 901",
    "2950 04000 0",
    "bob@example.com",
    "Robert Smith",
]

SOURCE = (
    "TFN 123 456 789 and ABN 12 345 678 901 and Medicare 2950 04000 0; "
    "contact Robert Smith at bob@example.com."
)


def _pipeline(tmp_path: Path) -> Pipeline:
    return Pipeline(
        detector=PIIDetector(llm_client=MockClient(), use_grammar=False),
        redactor=Redactor(style="numbered"),
        audit=AuditLog(path=str(tmp_path / "audit.jsonl"), enabled=True),
        model_name="mock",
    )


def _assert_no_raw_pii(records: list[logging.LogRecord]) -> None:
    for record in records:
        message = record.getMessage()
        for raw in RAW_PII:
            assert raw not in message, (
                f"raw PII {raw!r} leaked into a {record.levelname} log from "
                f"{record.name}: {message!r}"
            )


def test_redaction_logs_no_raw_pii_at_debug(tmp_path, caplog):
    pipeline = _pipeline(tmp_path)
    with caplog.at_level(logging.DEBUG, logger="pii_redactor"):
        result = pipeline.process_document(SOURCE)
    # Sanity: the malformed IDs were actually exercised (fail-closed redaction).
    assert result.needs_review is True
    _assert_no_raw_pii(caplog.records)


def test_au_resolver_validator_exception_logs_no_raw_value(tmp_path, caplog, monkeypatch):
    """Force a validator to RAISE on a raw candidate and assert the exception path
    logs category + length only — never the candidate value (au_resolver.py)."""
    raw_value = "123 456 789"

    def boom(value: str) -> bool:
        # An exception whose message does NOT echo the value; the logging call
        # itself must also not interpolate the raw candidate.
        raise ValueError("synthetic validator failure")

    # Replace the checksum validators with one that raises, so the except branch
    # (the audit-flagged log line) is taken.
    monkeypatch.setattr(
        au_resolver,
        "_CHECKSUM_VALIDATORS",
        [(au_resolver._CHECKSUM_VALIDATORS[0][0], boom)],
    )
    with caplog.at_level(logging.DEBUG, logger="pii_redactor"):
        au_resolver._try_checksum_validators(raw_value)
    for record in caplog.records:
        assert raw_value not in record.getMessage()
        assert "789" not in record.getMessage()
