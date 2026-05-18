"""PII Redactor — pre-ingestion PII de-identification using zero-shot LLM
detection with grammar-constrained output.

Implements the methodology from Wiest et al., NEJM AI 2024
('Deidentifying Medical Documents with Local, Privacy-Preserving Large
Language Models'), extended with Australian government identifier
detection (TFN, Medicare, ABN, ACN, etc) including checksum validation.

Public API:

    from pii_redactor import build_pipeline

    pipeline = build_pipeline()
    result = pipeline.process_document(text)
    print(result.redacted_text)
"""
from .audit import AuditLog
from .config import Config
from .detector import PIIDetector
from .llm_client import HFInferenceClient, LLMClient, LlamaCppClient, MockClient, OllamaClient
from .models import DocumentRequest, PIICategory, PIISpan, RedactionResult
from .pipeline import Pipeline, build_llm_client, build_pipeline
from .redactor import Redactor
from .validators import (
    regex_first_pass,
    validate_abn,
    validate_acn,
    validate_medicare,
    validate_tfn,
)

__version__ = "0.1.0"

__all__ = [
    "AuditLog",
    "Config",
    "DocumentRequest",
    "HFInferenceClient",
    "LLMClient",
    "LlamaCppClient",
    "MockClient",
    "OllamaClient",
    "PIICategory",
    "PIIDetector",
    "PIISpan",
    "Pipeline",
    "RedactionResult",
    "Redactor",
    "build_llm_client",
    "build_pipeline",
    "regex_first_pass",
    "validate_abn",
    "validate_acn",
    "validate_medicare",
    "validate_tfn",
]
