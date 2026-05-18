"""Core data models for the PII redactor.

RedactionResult is safe to pass downstream — it never carries original
PII values. Original values live only in the encrypted audit log, keyed
by audit_id, and can only be recovered with the audit encryption key.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class PIICategory(str, Enum):
    """PII categories supported by the detector.

    Standard categories follow the Wiest et al. taxonomy (NEJM AI, 2024).
    Australian categories extend it with Commonwealth-specific identifiers.
    """

    # Standard
    NAME = "name"
    DATE_OF_BIRTH = "date_of_birth"
    DATE = "date"
    ADDRESS = "address"
    PATIENT_ID = "patient_id"
    MEDICAL_RECORD_NUMBER = "medical_record_number"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    USERNAME = "username"
    GENERIC_ID = "generic_id"
    IP_ADDRESS = "ip_address"
    HEALTHCARE_IDENTIFIER = "healthcare_identifier"

    # Australian government
    TFN = "tfn"                       # Tax File Number
    MEDICARE = "medicare"
    ABN = "abn"                       # Australian Business Number
    ACN = "acn"                       # Australian Company Number
    DRIVER_LICENCE = "driver_licence"
    PASSPORT = "passport"
    BSB_ACCOUNT = "bsb_account"       # Bank account
    CRN = "centrelink_crn"            # Centrelink Customer Reference Number


@dataclass
class PIISpan:
    """A detected PII span in source text.

    `value` carries the original detected text only inside the detector
    pipeline. Spans returned in RedactionResult have their value cleared.
    """
    category: PIICategory
    start: int
    end: int
    value: Optional[str] = None
    confidence: float = 1.0
    validator_passed: Optional[bool] = None  # None when no validator exists
    placeholder: Optional[str] = None

    def overlaps(self, other: "PIISpan") -> bool:
        return not (self.end <= other.start or other.end <= self.start)

    def __len__(self) -> int:
        return self.end - self.start


@dataclass
class DocumentRequest:
    """A document submitted for de-identification."""
    text: str
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RedactionResult:
    """Result of de-identification. Safe to pass downstream.

    Original PII values are not present. They can be recovered from the
    audit log using `audit_id` if the caller is authorised.
    """
    document_id: str
    redacted_text: str
    pii_count: int
    spans: list[PIISpan]
    audit_id: str
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        pii_table = self.pii_table()
        return {
            "document_id": self.document_id,
            "redacted_text": self.redacted_text,
            "pii_count": self.pii_count,
            "spans": [
                {
                    "category": s.category.value,
                    "start": s.start,
                    "end": s.end,
                    "placeholder": s.placeholder,
                    "confidence": s.confidence,
                    "validator_passed": s.validator_passed,
                }
                for s in self.spans
            ],
            "pii_table": pii_table,
            "audit_id": self.audit_id,
            "processed_at": self.processed_at.isoformat(),
            "model_used": self.model_used,
        }

    def pii_table(self) -> list[dict[str, Any]]:
        """Return a safe catalog of redacted PII.

        This mirrors the LLM-Anonymizer paper's extracted-PII table while
        deliberately excluding original PII values. Re-identification remains
        audit-key controlled via AuditLog.
        """
        return [
            {
                "category": s.category.value,
                "placeholder": s.placeholder,
                "span_start": s.start,
                "span_end": s.end,
                "confidence": s.confidence,
                "validator_passed": s.validator_passed,
            }
            for s in self.spans
        ]
