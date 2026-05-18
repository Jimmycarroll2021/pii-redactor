"""Policy profiles for PII firewall deployments."""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "kg_rag_default": {
        "description": "High-recall pre-ingestion firewall for KG/RAG pipelines.",
        "env": {
            "PIIR_FAIL_ON_LLM_ERROR": "true",
            "PIIR_AUDIT_ENABLED": "true",
            "PIIR_USERNAME_MODE": "high_recall",
            "PIIR_MAX_TEXT_CHARS": "200000",
            "PIIR_MAX_BATCH_DOCS": "1000",
            "PIIR_MAX_CONCURRENCY": "8",
        },
        "required_metadata": [
            "source_id",
            "redaction_audit_id",
            "pii_count",
            "pii_categories",
            "redaction_policy",
            "model_used",
            "gate_status",
        ],
    },
    "healthcare_high_recall": {
        "description": "Maximum recall profile for clinical and patient data.",
        "env": {
            "PIIR_FAIL_ON_LLM_ERROR": "true",
            "PIIR_AUDIT_ENABLED": "true",
            "PIIR_USERNAME_MODE": "high_recall",
            "PIIR_MAX_TEXT_CHARS": "200000",
            "PIIR_MAX_BATCH_DOCS": "500",
            "PIIR_MAX_CONCURRENCY": "6",
        },
        "required_metadata": [
            "source_id",
            "redaction_audit_id",
            "pii_count",
            "pii_categories",
            "redaction_policy",
            "model_used",
            "gate_status",
        ],
    },
    "legal_review": {
        "description": "Fail-closed legal review profile with audit retention.",
        "env": {
            "PIIR_FAIL_ON_LLM_ERROR": "true",
            "PIIR_AUDIT_ENABLED": "true",
            "PIIR_USERNAME_MODE": "high_recall",
            "PIIR_MAX_TEXT_CHARS": "300000",
            "PIIR_MAX_BATCH_DOCS": "250",
            "PIIR_MAX_CONCURRENCY": "4",
        },
        "required_metadata": [
            "source_id",
            "redaction_audit_id",
            "pii_count",
            "pii_categories",
            "redaction_policy",
            "model_used",
            "gate_status",
        ],
    },
    "logs_low_noise": {
        "description": "Lower-noise log profile. Not safe as the default for KG/RAG ingestion.",
        "env": {
            "PIIR_FAIL_ON_LLM_ERROR": "true",
            "PIIR_AUDIT_ENABLED": "true",
            "PIIR_USERNAME_MODE": "strict",
            "PIIR_MAX_TEXT_CHARS": "100000",
            "PIIR_MAX_BATCH_DOCS": "2000",
            "PIIR_MAX_CONCURRENCY": "12",
        },
        "required_metadata": [
            "source_id",
            "redaction_audit_id",
            "pii_count",
            "pii_categories",
            "redaction_policy",
            "model_used",
            "gate_status",
        ],
    },
}


def apply_policy_to_environment(profile: str, force: bool = False) -> dict[str, Any]:
    """Apply profile env defaults and return the profile snapshot."""
    if profile not in POLICY_PROFILES:
        raise ValueError(
            f"Unknown PIIR policy profile '{profile}'. "
            f"Available: {', '.join(sorted(POLICY_PROFILES))}"
        )
    policy = POLICY_PROFILES[profile]
    for key, value in policy["env"].items():
        if force or key not in os.environ:
            os.environ[key] = value
    return policy_snapshot(profile)


def policy_snapshot(profile: str) -> dict[str, Any]:
    """Return a serializable policy snapshot without secrets."""
    if profile not in POLICY_PROFILES:
        raise ValueError(
            f"Unknown PIIR policy profile '{profile}'. "
            f"Available: {', '.join(sorted(POLICY_PROFILES))}"
        )
    snapshot = deepcopy(POLICY_PROFILES[profile])
    snapshot["name"] = profile
    return snapshot


def available_policy_profiles() -> list[str]:
    return sorted(POLICY_PROFILES)
