"""The public pipeline API.

This is what upstream pipeline code calls. One method, one return type,
no surprises:

    pipeline = build_pipeline()  # or build_pipeline(config=...)
    result = pipeline.process_document("Hello, my TFN is 123 456 782")
    print(result.redacted_text)

The pipeline is also constructible from individual components if you
want full control over the LLM client, redactor style, etc.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .audit import AuditLog
from .config import Config
from .detector import PIIDetector
from .llm_client import HFInferenceClient, LlamaCppClient, LLMClient, MockClient, OllamaClient
from .models import DocumentRequest, RedactionResult
from .redactor import Redactor

logger = logging.getLogger(__name__)


class Pipeline:
    """End-to-end PII de-identification pipeline."""

    def __init__(
        self,
        detector: PIIDetector,
        redactor: Redactor,
        audit: AuditLog,
        model_name: Optional[str] = None,
    ):
        self.detector = detector
        self.redactor = redactor
        self.audit = audit
        self.model_name = model_name

    def _run(self, text: str, document_id: Optional[str]) -> RedactionResult:
        """Core synchronous processing logic shared by sync and async paths."""
        request = DocumentRequest(
            text=text,
            document_id=document_id or DocumentRequest(text="").document_id,
        )
        spans = self.detector.detect(request.text)
        redacted_text, safe_spans = self.redactor.redact(request.text, spans)
        audit_id = self.audit.write(
            document_id=request.document_id,
            spans=spans,
            model_used=self.model_name,
        )
        return RedactionResult(
            document_id=request.document_id,
            redacted_text=redacted_text,
            pii_count=len(safe_spans),
            spans=safe_spans,
            audit_id=audit_id,
            model_used=self.model_name,
        )

    def process_document(
        self,
        text: str,
        document_id: Optional[str] = None,
    ) -> RedactionResult:
        """Synchronous de-identification. Blocks until complete."""
        return self._run(text, document_id)

    async def process_document_async(
        self,
        text: str,
        document_id: Optional[str] = None,
    ) -> RedactionResult:
        """Async de-identification. Runs the blocking detector in a thread-pool
        executor so the event loop is not blocked during LLM HTTP calls.

        Use this from FastAPI endpoints and batch pipelines. Concurrent calls
        are naturally limited by the executor's max_workers (defaults to
        min(32, cpu_count+4) in Python 3.10+).
        """
        return await asyncio.to_thread(self._run, text, document_id)


def build_llm_client(config: Config) -> LLMClient:
    """Pick the LLM backend per config."""
    if config.backend == "llama_cpp":
        return LlamaCppClient(
            base_url=config.llama_cpp_url,
            model_name=config.llama_cpp_model_name,
            timeout=config.llm_timeout_seconds,
            retries=config.llm_retries,
        )
    if config.backend == "hf":
        return HFInferenceClient(
            model_id=config.hf_model_id,
            token=config.hf_token,
        )
    if config.backend == "ollama":
        return OllamaClient(
            base_url=config.ollama_url,
            model=config.ollama_model,
            timeout=config.llm_timeout_seconds,
            retries=config.llm_retries,
        )
    if config.backend == "mock":
        return MockClient()
    if config.backend == "transformers_au":
        # The hybrid backend doesn't use the LLMClient protocol; it owns its
        # own OpenAIPrivacyFilter. build_pipeline() short-circuits before
        # this is called for transformers_au, but if a caller invokes
        # build_llm_client directly we return a Mock so existing tooling
        # that probes for `.name` keeps working.
        return MockClient()
    raise ValueError(f"Unknown backend: {config.backend}")


def build_pipeline(
    config: Optional[Config] = None,
    use_regex_prepass: bool = True,
) -> Pipeline:
    """Construct a pipeline from config (or env).

    The `transformers_au` backend dispatches to the hybrid OpenAI + AU
    validator pipeline (see `pii_redactor.hybrid`). All other backends
    follow the original LLM-detector flow.
    """
    cfg = config or Config.from_env()
    if cfg.backend == "transformers_au":
        # Local import — avoids loading transformers when the hybrid
        # backend isn't selected.
        from .hybrid import build_hybrid_pipeline

        return build_hybrid_pipeline(cfg)

    llm = build_llm_client(cfg)
    use_grammar = cfg.backend == "llama_cpp"
    detector = PIIDetector(
        llm_client=llm,
        chunk_size=cfg.chunk_size_chars,
        chunk_overlap=cfg.chunk_overlap_chars,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        use_grammar=use_grammar,
        use_regex_prepass=use_regex_prepass,
        fail_on_llm_error=cfg.fail_on_llm_error,
    )
    redactor = Redactor(style=cfg.placeholder_style)
    audit = AuditLog(
        path=cfg.audit_log_path,
        encryption_key=cfg.audit_encryption_key,
        enabled=cfg.audit_enabled,
    )
    return Pipeline(
        detector=detector,
        redactor=redactor,
        audit=audit,
        model_name=llm.name,
    )
