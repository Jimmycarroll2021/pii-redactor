"""Encrypted audit trail.

Each detection is written as a JSONL line with the original PII value
encrypted using Fernet (AES-128-CBC + HMAC). With the encryption key,
authorised callers can re-identify spans for compliance review or
authorised case work. Without the key, the log records what was detected
and where, but not the values.

If no encryption key is configured, the log is disabled by default and
a warning is emitted. Set `audit_enabled=True` and provide a key to
enable. We refuse to write plaintext PII to the audit log under any
circumstances.

Generate a key once: `python -c "from cryptography.fernet import Fernet; \
print(Fernet.generate_key().decode())"`
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import PIISpan

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    audit_id: str
    document_id: str
    timestamp: str
    category: str
    span_start: int
    span_end: int
    value_encrypted: str  # base64 Fernet token, or "" if encryption disabled
    placeholder: str
    confidence: float
    validator_passed: Optional[bool]
    model_used: Optional[str]


class AuditLog:
    def __init__(
        self,
        path: str = "./audit.jsonl",
        encryption_key: Optional[str] = None,
        enabled: bool = True,
    ):
        self.path = Path(path)
        self.enabled = enabled
        self._fernet = None

        if not enabled:
            logger.info("Audit log disabled by config.")
            return

        if encryption_key:
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(encryption_key.encode())
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Invalid Fernet key supplied. Audit will record metadata "
                    "only, no encrypted values. Error: %s",
                    exc,
                )
        else:
            logger.warning(
                "Audit log enabled but no encryption key supplied. The log "
                "will record metadata but not original values. Set "
                "PIIR_AUDIT_KEY to enable re-identification."
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        document_id: str,
        spans: list[PIISpan],
        model_used: Optional[str] = None,
    ) -> str:
        """Write an audit batch for a single document. Returns the audit_id."""
        audit_id = str(uuid.uuid4())
        if not self.enabled:
            return audit_id

        timestamp = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as f:
            for span in spans:
                encrypted_value = ""
                if self._fernet:
                    # SEC-05: bundle the value AND precise offsets into ONE
                    # encrypted token. The cleartext row must not localise PII
                    # against the source document; offsets are recoverable only
                    # via reidentify() with the key.
                    payload = json.dumps(
                        {"value": span.value, "span_start": span.start, "span_end": span.end}
                    )
                    encrypted_value = self._fernet.encrypt(payload.encode("utf-8")).decode("ascii")

                entry = AuditEntry(
                    audit_id=audit_id,
                    document_id=document_id,
                    timestamp=timestamp,
                    category=span.category.value,
                    # Offsets withheld from cleartext (SEC-05 offset oracle): -1 =
                    # "not disclosed; recover via reidentify()". Category alone
                    # discloses no more than the placeholders already in the
                    # redacted output.
                    span_start=-1,
                    span_end=-1,
                    value_encrypted=encrypted_value,
                    placeholder=span.placeholder or "",
                    confidence=span.confidence,
                    validator_passed=span.validator_passed,
                    model_used=model_used,
                )
                f.write(json.dumps(entry.__dict__) + "\n")
        return audit_id

    def purge(self, audit_ids: Iterable[str]) -> int:
        """Destroy every audit entry whose audit_id is in ``audit_ids``.

        Returns the number of JSONL lines removed. This is the engine side of a
        retention/deletion request (APP 11.2 "destroy or de-identify"): when a
        document's redacted copy is deleted, the encrypted re-identification
        vault entries that could reconstruct its original PII must be destroyed
        with it. Atomic: a temp file is written then renamed over the original,
        so a crash mid-purge cannot leave a half-written log. Safe no-op when
        the log is disabled, the file is absent, or ``audit_ids`` is empty.
        """
        targets = {str(audit_id) for audit_id in audit_ids if audit_id}
        if not targets or not self.path.exists():
            return 0

        tmp_path = self.path.with_name(self.path.name + ".purge-tmp")
        removed = 0
        with self.path.open("r", encoding="utf-8") as src, tmp_path.open(
            "w", encoding="utf-8"
        ) as dst:
            for line in src:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    # Preserve unparseable lines rather than silently dropping
                    # an entry we cannot match — fail-closed on retention.
                    dst.write(stripped + "\n")
                    continue
                if entry.get("audit_id") in targets:
                    removed += 1
                    continue
                dst.write(stripped + "\n")
        tmp_path.replace(self.path)
        return removed

    def reidentify(self, audit_id: str) -> list[dict]:
        """Decrypt all entries for an audit_id. Requires the encryption key.

        Returns a list of dicts with the original value populated. Empty
        list if not found or if no key is configured.
        """
        if not self._fernet:
            raise RuntimeError(
                "Cannot re-identify without an encryption key. "
                "Set PIIR_AUDIT_KEY before calling."
            )

        out = []
        if not self.path.exists():
            return out
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry["audit_id"] != audit_id:
                    continue
                value = None
                if entry.get("value_encrypted"):
                    decrypted = self._fernet.decrypt(
                        entry["value_encrypted"].encode("ascii")
                    ).decode("utf-8")
                    # New format: JSON {value, span_start, span_end}.
                    # Legacy format: the raw value as a bare string.
                    try:
                        payload = json.loads(decrypted)
                    except (json.JSONDecodeError, ValueError):
                        payload = None
                    if isinstance(payload, dict) and "value" in payload:
                        value = payload.get("value")
                        if payload.get("span_start") is not None:
                            entry["span_start"] = payload["span_start"]
                            entry["span_end"] = payload["span_end"]
                    else:
                        value = decrypted
                entry["value"] = value
                out.append(entry)
        return out
