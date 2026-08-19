"""End-to-end pipeline tests with the MockClient backend.

The MockClient detects PII via regex first-pass only, so these tests
exercise the full chunk → detect → validate → redact → audit flow
without needing an actual LLM.
"""
import json
from pathlib import Path

from pii_redactor import (
    AuditLog,
    Config,
    PIIDetector,
    Pipeline,
    Redactor,
    build_pipeline,
)
from pii_redactor.llm_client import MockClient


def _build_test_pipeline(tmp_path: Path, key: str | None = None) -> Pipeline:
    return Pipeline(
        detector=PIIDetector(llm_client=MockClient(), use_grammar=False),
        redactor=Redactor(style="numbered"),
        audit=AuditLog(
            path=str(tmp_path / "audit.jsonl"),
            encryption_key=key,
            enabled=True,
        ),
        model_name="mock",
    )


def test_detects_australian_identifiers(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    text = (
        "Hello team, please process the form. "
        "TFN: 123 456 782, "
        "ABN: 33 051 775 556, "
        "Email: jdoe@example.gov.au, "
        "Phone: 02 6271 7000."
    )
    result = pipeline.process_document(text)

    cats = {s.category.value for s in result.spans}
    assert "tfn" in cats
    assert "abn" in cats
    assert "email" in cats


def test_redacted_text_contains_no_originals(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    text = "TFN: 123 456 782 and ABN: 33 051 775 556"
    result = pipeline.process_document(text)

    assert "123 456 782" not in result.redacted_text
    assert "33 051 775 556" not in result.redacted_text
    assert "[REDACTED_TFN_001]" in result.redacted_text
    assert "[REDACTED_ABN_001]" in result.redacted_text


def test_invalid_checksum_no_residue_leak(tmp_path):
    # 999 999 999 fails the TFN/ACN checksums. Fail-closed: the token must be
    # redacted (not left as cleartext residue from a shorter overlapping match)
    # and the document flagged needs_review. Regression for VULN-01 / SEC-01:
    # the old behaviour dropped the failed span and leaked the tail "999".
    pipeline = _build_test_pipeline(tmp_path)
    text = "Bad TFN: 999 999 999"
    result = pipeline.process_document(text)

    assert "999 999 999" not in result.redacted_text
    # No digit run of the original value may survive anywhere in the output.
    assert "999" not in result.redacted_text
    assert result.needs_review is True
    assert any(s.needs_review for s in result.spans)


def test_returned_spans_have_no_original_values(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    text = "TFN: 123 456 782"
    result = pipeline.process_document(text)

    for span in result.spans:
        assert span.value is None  # never leak originals downstream


def test_audit_records_detections_with_encryption(tmp_path):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    pipeline = _build_test_pipeline(tmp_path, key=key)
    text = "TFN: 123 456 782"
    result = pipeline.process_document(text)

    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    lines = audit_file.read_text().strip().splitlines()
    assert len(lines) >= 1

    entry = json.loads(lines[0])
    assert entry["audit_id"] == result.audit_id
    assert entry["category"] == "tfn"
    assert entry["value_encrypted"]  # non-empty


def test_reidentify_recovers_original_value(tmp_path):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    pipeline = _build_test_pipeline(tmp_path, key=key)
    text = "TFN: 123 456 782"
    result = pipeline.process_document(text)

    recovered = pipeline.audit.reidentify(result.audit_id)
    assert any(e.get("value") == "123 456 782" for e in recovered)


def test_coreference_preserved_in_numbered_redaction(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    # Same ABN appears twice — should get the same placeholder
    text = "ABN: 33 051 775 556 ... and again ABN: 33 051 775 556"
    result = pipeline.process_document(text)

    assert result.redacted_text.count("[REDACTED_ABN_001]") == 2


def test_build_pipeline_from_env_uses_mock_by_default():
    # Default config should give us a working mock pipeline
    pipeline = build_pipeline(Config(audit_log_path="/tmp/test_audit.jsonl"))
    result = pipeline.process_document("Email me: test@example.com")
    assert result.pii_count >= 1


def test_serialisable_to_dict(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("Email: test@example.com")
    d = result.to_dict()
    # Must round-trip through JSON
    json.dumps(d)
    assert d["pii_count"] == len(d["spans"])


def test_phone_bracketed_area_code_detected(tmp_path):
    # Regression for Bug 1: (0X) XXXX XXXX format must be detected end-to-end.
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("Contact us at (02) 6271 7000 for assistance.")
    cats = {s.category.value for s in result.spans}
    assert "phone" in cats, f"Expected 'phone' in {cats}"


def test_abn_string_does_not_produce_phone_span(tmp_path):
    # Regression for Bug 3: digit run inside a bad ABN must not become a phone span.
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("Invalid ABN: 12 345 678 901")
    phone_spans = [s for s in result.spans if s.category.value == "phone"]
    assert len(phone_spans) == 0, f"Unexpected phone spans: {phone_spans}"


def test_crn_detected_by_regex(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("Client CRN: 555444333A")
    cats = {s.category.value for s in result.spans}
    assert "centrelink_crn" in cats, f"Expected 'centrelink_crn' in {cats}"


def test_medical_identifiers_detected_without_redacting_labels(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("Patient ID: PT-448812 and MRN HOSP-998271")
    cats = {s.category.value for s in result.spans}
    assert "patient_id" in cats
    assert "medical_record_number" in cats
    assert "Patient ID:" in result.redacted_text
    assert "MRN" in result.redacted_text
    assert "PT-448812" not in result.redacted_text
    assert "HOSP-998271" not in result.redacted_text


def test_pii_table_excludes_original_values(tmp_path):
    pipeline = _build_test_pipeline(tmp_path)
    result = pipeline.process_document("MRN HOSP-998271")
    table = result.pii_table()
    assert table
    assert "HOSP-998271" not in str(table)
    assert table[0]["category"] == "medical_record_number"


def test_ollama_client_posts_correct_payload(monkeypatch):
    import json as _json
    from unittest.mock import MagicMock

    from pii_redactor import llm_client as llm_mod
    from pii_redactor.llm_client import OllamaClient

    captured = {}

    def fake_post_with_retry(url, payload, timeout, retries=3):
        captured["url"] = url
        captured["payload"] = payload
        resp = MagicMock()
        resp.json.return_value = {
            "model": "llama3",
            "message": {
                "role": "assistant",
                "content": _json.dumps(
                    {"pii": [{"category": "email", "value": "test@example.com"}]}
                ),
            },
            "done": True,
        }
        return resp

    monkeypatch.setattr(llm_mod, "_post_with_retry", fake_post_with_retry)

    client = OllamaClient(base_url="http://localhost:11434", model="llama3")
    raw = client.complete(system_prompt="sys", user_prompt="user")
    parsed = _json.loads(raw)
    assert parsed["pii"][0]["value"] == "test@example.com"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["model"] == "llama3"
    assert captured["payload"]["stream"] is False
    assert any(m["role"] == "system" for m in captured["payload"]["messages"])
