"""Configuration via environment variables.

Reads from env or .env file. All settings have sensible defaults so the
package can be imported and run with zero config in mock mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .policies import apply_policy_to_environment


@dataclass
class Config:
    """Runtime configuration."""

    # LLM backend selection
    # "mock" | "llama_cpp" | "hf" | "ollama" | "transformers_au" |
    # "transformers_au_finetuned" (v0.4.0+ — openai/privacy-filter + LoRA)
    backend: str = "mock"
    # LoRA adapter path (used when backend == transformers_au_finetuned).
    lora_adapter_path: str = "/mnt/ai/adapters/redact-au-1b/best"
    policy_profile: str = "kg_rag_default"

    # llama.cpp server
    llama_cpp_url: str = "http://localhost:8080"
    llama_cpp_model_name: str = "llama-3-8b-instruct"

    # Hugging Face Inference
    hf_model_id: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    hf_token: Optional[str] = None

    # Ollama local inference
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Scale: max concurrent LLM calls (used by FastAPI batch endpoint)
    max_concurrency: int = 8
    # Per-request timeout for HTTP-backed local LLM clients
    llm_timeout_seconds: float = 120.0
    # Retry attempts for HTTP-backed LLM clients (LlamaCpp, Ollama)
    llm_retries: int = 3

    # Detection
    chunk_size_chars: int = 4000
    chunk_overlap_chars: int = 400  # ~100 tokens — matches Wiest et al. overlap strategy
    temperature: float = 0.0       # deterministic output; critical for reproducible audits
    max_tokens: int = 2048
    fail_on_llm_error: bool = False

    # Audit
    audit_log_path: str = "./audit.jsonl"
    audit_encryption_key: Optional[str] = None  # Fernet key. None disables encryption.
    audit_enabled: bool = True

    # Redaction
    placeholder_style: str = "numbered"  # "numbered" | "category" | "asterisk"

    @classmethod
    def from_env(cls) -> "Config":
        """Build config from environment variables prefixed with PIIR_."""
        policy_profile = os.environ.get("PIIR_POLICY_PROFILE", "kg_rag_default")
        apply_policy_to_environment(policy_profile, force=False)
        return cls(
            policy_profile=policy_profile,
            backend=os.environ.get("PIIR_BACKEND", "mock"),
            lora_adapter_path=os.environ.get(
                "PIIR_LORA_ADAPTER", "/mnt/ai/adapters/redact-au-1b/best"
            ),
            llama_cpp_url=os.environ.get("PIIR_LLAMA_CPP_URL", "http://localhost:8080"),
            llama_cpp_model_name=os.environ.get(
                "PIIR_LLAMA_CPP_MODEL", "llama-3-8b-instruct"
            ),
            hf_model_id=os.environ.get(
                "PIIR_HF_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct"
            ),
            hf_token=os.environ.get("PIIR_HF_TOKEN") or os.environ.get("HF_TOKEN"),
            ollama_url=os.environ.get("PIIR_OLLAMA_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434",
            ollama_model=os.environ.get("PIIR_OLLAMA_MODEL")
            or os.environ.get("OLLAMA_MODEL")
            or "llama3",
            max_concurrency=int(os.environ.get("PIIR_MAX_CONCURRENCY", "8")),
            llm_timeout_seconds=float(os.environ.get("PIIR_LLM_TIMEOUT_SECONDS", "120")),
            llm_retries=int(os.environ.get("PIIR_LLM_RETRIES", "3")),
            chunk_size_chars=int(os.environ.get("PIIR_CHUNK_SIZE", "4000")),
            chunk_overlap_chars=int(os.environ.get("PIIR_CHUNK_OVERLAP", "200")),
            temperature=float(os.environ.get("PIIR_TEMPERATURE", "0.1")),
            max_tokens=int(os.environ.get("PIIR_MAX_TOKENS", "2048")),
            fail_on_llm_error=os.environ.get(
                "PIIR_FAIL_ON_LLM_ERROR", "false"
            ).lower()
            == "true",
            audit_log_path=os.environ.get("PIIR_AUDIT_PATH", "./audit.jsonl"),
            audit_encryption_key=os.environ.get("PIIR_AUDIT_KEY"),
            audit_enabled=os.environ.get("PIIR_AUDIT_ENABLED", "true").lower()
            == "true",
            placeholder_style=os.environ.get("PIIR_PLACEHOLDER_STYLE", "numbered"),
        )
