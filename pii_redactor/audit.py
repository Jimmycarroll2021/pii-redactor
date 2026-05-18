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
                if self._fernet and span.value:
                    encrypted_value = self._fernet.encrypt(
                        span.value.encode("utf-8")
                    ).decode("ascii")

                entry = AuditEntry(
                    audit_id=audit_id,
                    document_id=document_id,
                    timestamp=timestamp,
                    category=span.category.value,
                    span_start=span.start,
                    span_end=span.end,
                    value_encrypted=encrypted_value,
                    placeholder=span.placeholder or "",
                    confidence=span.confidence,
                    validator_passed=span.validator_passed,
                    model_used=model_used,
                )
                f.write(json.dumps(entry.__dict__) + "\n")
        return audit_id

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
                    value = self._fernet.decrypt(
                        entry["value_encrypted"].encode("ascii")
                    ).decode("utf-8")
                entry["value"] = value
                out.append(entry)
        return out
