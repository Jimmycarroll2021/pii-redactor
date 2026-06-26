"""Regression: audit log is not a PII offset oracle (SEC-05 / VULN-07).

Cleartext audit rows must not disclose precise span offsets (which, with the
source document, re-localise every PII token). Offsets and the value live only
inside the encrypted token and are recoverable solely via reidentify().
"""

from __future__ import annotations

import json

import pytest

from pii_redactor.audit import AuditLog
from pii_redactor.models import PIICategory, PIISpan

Fernet = pytest.importorskip("cryptography.fernet").Fernet


def _spans() -> list[PIISpan]:
    # value/offsets mimic "TFN: 123 456 782" with the TFN at chars 5-16.
    return [
        PIISpan(
            category=PIICategory.TFN,
            start=5,
            end=16,
            value="123 456 782",
            placeholder="[REDACTED_TFN_001]",
        )
    ]


def test_cleartext_row_hides_offsets_and_value(tmp_path) -> None:
    key = Fernet.generate_key().decode()
    log = AuditLog(path=str(tmp_path / "audit.jsonl"), encryption_key=key, enabled=True)
    audit_id = log.write(document_id="doc1", spans=_spans(), model_used="mock")

    row = json.loads((tmp_path / "audit.jsonl").read_text().strip().splitlines()[0])
    # Offsets withheld in cleartext.
    assert row["span_start"] == -1
    assert row["span_end"] == -1
    # Raw value never present in cleartext (in any field but the encrypted token).
    for field, value in row.items():
        if field == "value_encrypted":
            continue
        assert "123 456 782" not in str(value)
    # Encrypted token is present and non-empty.
    assert row["value_encrypted"]
    assert audit_id


def test_reidentify_recovers_value_and_offsets(tmp_path) -> None:
    key = Fernet.generate_key().decode()
    log = AuditLog(path=str(tmp_path / "audit.jsonl"), encryption_key=key, enabled=True)
    audit_id = log.write(document_id="doc1", spans=_spans(), model_used="mock")

    recovered = log.reidentify(audit_id)
    assert len(recovered) == 1
    assert recovered[0]["value"] == "123 456 782"
    # Authorised path restores the real offsets from inside the token.
    assert recovered[0]["span_start"] == 5
    assert recovered[0]["span_end"] == 16


def test_unkeyed_audit_records_no_offsets(tmp_path) -> None:
    log = AuditLog(path=str(tmp_path / "audit.jsonl"), encryption_key=None, enabled=True)
    log.write(document_id="doc1", spans=_spans(), model_used="mock")
    row = json.loads((tmp_path / "audit.jsonl").read_text().strip().splitlines()[0])
    assert row["span_start"] == -1
    assert row["span_end"] == -1
    assert row["value_encrypted"] == ""
    assert "123 456 782" not in json.dumps(row)


def test_purge_destroys_reidentification_vault_entry(tmp_path) -> None:
    """SEC-08 / APP 11.2: purging an audit_id destroys the encrypted vault entry
    so the original PII can no longer be re-identified, while OTHER documents'
    entries survive intact."""
    key = Fernet.generate_key().decode()
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path=str(path), encryption_key=key, enabled=True)
    drop_id = log.write(document_id="doc-drop", spans=_spans(), model_used="mock")
    keep_id = log.write(document_id="doc-keep", spans=_spans(), model_used="mock")

    removed = log.purge([drop_id])
    assert removed == 1

    # The purged document can no longer be re-identified...
    assert log.reidentify(drop_id) == []
    # ...but the surviving document is fully intact.
    recovered = log.reidentify(keep_id)
    assert len(recovered) == 1
    assert recovered[0]["value"] == "123 456 782"
    # The raw (encrypted) value for the dropped doc is gone from the file.
    assert drop_id not in path.read_text(encoding="utf-8")


def test_purge_is_safe_noop_when_empty_or_missing(tmp_path) -> None:
    log = AuditLog(path=str(tmp_path / "missing.jsonl"), encryption_key=None, enabled=True)
    assert log.purge(["anything"]) == 0  # file absent
    log.write(document_id="doc1", spans=_spans(), model_used="mock")
    assert log.purge([]) == 0  # nothing requested
    assert log.purge(["unknown-id"]) == 0  # no match
    assert (tmp_path / "missing.jsonl").exists()
