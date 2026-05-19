"""Parallel narrative-NER pass using llama3.1:8b served via vLLM.

Mirrors :mod:`pii_redactor.hybrid.llama_pass` but talks to a
vLLM-compatible OpenAI Chat Completions endpoint instead of Ollama.

vLLM's PagedAttention + continuous batching gives the same model
serial-per-slot Ollama latency under load (1.6 d/s ceiling with
``OLLAMA_NUM_PARALLEL=4``) but ~5-8 d/s under concurrent×8 load, which
is the throughput bar v0.3.2 has to clear.

Returned span schema matches :class:`LlamaNERPass.predict` so this
class plugs into :class:`HybridDetector` as a drop-in replacement.

Configuration
-------------
- ``PIIR_VLLM_BASE_URL``        Default ``http://host.docker.internal:11500``
- ``PIIR_VLLM_MODEL``           Default ``llama3.1-8b-awq``
- ``PIIR_VLLM_TIMEOUT_S``       Default ``60``
- ``PIIR_LLAMA_ENABLED``        Default ``true`` (shared with Ollama pass)
- ``PIIR_LLAMA_MAX_CHARS``      Default ``8000`` (shared with Ollama pass)
- ``PIIR_VLLM_QUANT``           Default ``awq`` (advisory; surfaced via /info)

Soft-fail by design: any error (unreachable, bad JSON, etc.) returns
``[]`` so the OpenAI Privacy Filter pass still produces results.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from ..detector import PIIDetector
from ..models import PIICategory
from ..prompts import build_prompt
from .llama_pass import (
    _LLAMA_TO_OPENAI,
    _env_float,
    _env_int,
    _env_truthy,
    _iter_occurrences,
)

logger = logging.getLogger(__name__)


class VLLMNERPass:
    """Narrative NER pass via a vLLM-hosted OpenAI-compatible endpoint.

    The wire protocol is OpenAI Chat Completions
    (``POST /v1/chat/completions``) with ``response_format={"type":"json_object"}``
    to take advantage of vLLM's guided-decoding JSON support.
    """

    DEFAULT_BASE_URL = "http://host.docker.internal:11500"
    DEFAULT_MODEL = "llama3.1-8b-awq"
    DEFAULT_QUANT = "awq_marlin"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        enabled: bool | None = None,
        max_chars: int | None = None,
        quant: str | None = None,
    ):
        self.base_url = (
            base_url
            or os.environ.get("PIIR_VLLM_BASE_URL", self.DEFAULT_BASE_URL)
        ).rstrip("/")
        self.model = model or os.environ.get("PIIR_VLLM_MODEL", self.DEFAULT_MODEL)
        self.timeout_s = (
            timeout_s
            if timeout_s is not None
            else _env_float("PIIR_VLLM_TIMEOUT_S", 60.0)
        )
        self.enabled = (
            enabled
            if enabled is not None
            else _env_truthy("PIIR_LLAMA_ENABLED", True)
        )
        self.max_chars = (
            max_chars
            if max_chars is not None
            else _env_int("PIIR_LLAMA_MAX_CHARS", 8000)
        )
        self.quant = quant or os.environ.get("PIIR_VLLM_QUANT", self.DEFAULT_QUANT)
        self._loaded = False

    @property
    def name(self) -> str:
        return f"vllm:{self.model}"

    def health_check(self) -> bool:
        """Return True if the vLLM endpoint answers ``/v1/models``."""
        import urllib.error  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        try:
            with urllib.request.urlopen(
                f"{self.base_url}/v1/models", timeout=min(self.timeout_s, 5.0)
            ) as resp:
                return resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            logger.debug("vLLM health_check failed: %s", exc)
            return False

    def warmup(self) -> None:
        """Issue a no-op extraction to warm vLLM's KV cache."""
        if not self.enabled:
            logger.info("vLLM narrative pass disabled (PIIR_LLAMA_ENABLED=false)")
            return
        try:
            self.predict("Hello, my name is Alice.")
            self._loaded = True
            logger.info("vLLM narrative pass warmup ok (%s)", self.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vLLM narrative pass warmup failed: %s", exc)

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        """POST chat-completions to vLLM and return the raw assistant text."""
        from ..llm_client import _post_with_retry  # noqa: PLC0415

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            # Capped below 2048 so prompt+output stays inside the 4096
            # max-model-len configured on the sidecar vLLM. The narrative
            # extractions are JSON arrays of entities and never exceed
            # ~600 tokens in practice on the Gretel-100 + Medical-50
            # fixtures; 1024 is a comfortable ceiling.
            "max_tokens": int(
                os.environ.get("PIIR_VLLM_MAX_TOKENS", "1024")
            ),
            # vLLM supports OpenAI's response_format JSON mode via its
            # guided-decoding xgrammar backend. If the deployed vLLM build
            # doesn't, the server returns a 400; we soft-fail upstream.
            "response_format": {"type": "json_object"},
        }
        resp = _post_with_retry(
            f"{self.base_url}/v1/chat/completions",
            payload,
            self.timeout_s,
            retries=3,
        )
        body = resp.json()
        try:
            return body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"vLLM response malformed: {body!r}") from exc

    def predict(self, text: str) -> list[tuple[str, int, int, str]]:
        """Run vLLM, parse entities, locate in source, return OpenAI-shape tuples."""
        if not text or not self.enabled:
            return []
        if len(text) > self.max_chars:
            logger.debug(
                "vLLM pass skipped: doc %d chars > max_chars %d",
                len(text),
                self.max_chars,
            )
            return []
        categories = [c.value for c in PIICategory]
        system, user = build_prompt(text, categories)
        try:
            raw = self._complete(system, user)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vLLM narrative pass call failed: %s", exc)
            return []

        try:
            entities = PIIDetector._parse_response(raw, fail_on_parse_error=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vLLM narrative pass parse failed: %s", exc)
            return []

        out: list[tuple[str, int, int, str]] = []
        for category, value in entities:
            if not value:
                continue
            openai_cat = _LLAMA_TO_OPENAI.get(category, "account_number")
            for span_start in _iter_occurrences(text, value):
                span_end = span_start + len(value)
                out.append((openai_cat, span_start, span_end, value))
        return out

    def unload(self) -> None:  # parity with sibling passes
        self._loaded = False


def select_llama_backend(
    backend: str | None = None,
) -> tuple[str, Any]:
    """Pick the active llama backend.

    Returns ``(backend_name, pass_instance)`` where ``backend_name`` is one
    of ``"vllm"``, ``"ollama"``, or ``"disabled"``.

    Resolution order:

    1. Explicit ``backend`` argument (``"vllm"`` / ``"ollama"`` / ``"auto"``).
    2. ``PIIR_LLAMA_BACKEND`` env var (same values).
    3. Default ``"auto"``.

    In ``auto`` mode the vLLM endpoint is health-checked; if it answers,
    vLLM is used. Otherwise we fall back to Ollama. If
    ``PIIR_LLAMA_ENABLED=false`` is set the function returns the
    ``"disabled"`` sentinel and a ``None`` instance.
    """
    if not _env_truthy("PIIR_LLAMA_ENABLED", True):
        return "disabled", None
    # v0.4.0: default flipped from "auto" → "disabled" (LoRA-finetuned base
    # now carries the narrative recall load). Users can opt back into the
    # llama pass with PIIR_LLAMA_BACKEND=vllm or ollama.
    requested = (backend or os.environ.get("PIIR_LLAMA_BACKEND", "disabled")).lower()
    if requested == "disabled":
        return "disabled", None
    if requested not in {"vllm", "ollama", "auto"}:
        logger.warning(
            "Unknown PIIR_LLAMA_BACKEND=%r, falling back to disabled", requested
        )
        return "disabled", None

    if requested == "ollama":
        from .llama_pass import LlamaNERPass  # noqa: PLC0415

        return "ollama", LlamaNERPass()

    if requested == "vllm":
        return "vllm", VLLMNERPass()

    # auto: prefer vllm, fall back to ollama
    candidate = VLLMNERPass()
    if candidate.health_check():
        logger.info("auto-selected vLLM llama backend at %s", candidate.base_url)
        return "vllm", candidate

    from .llama_pass import LlamaNERPass  # noqa: PLC0415

    logger.info("vLLM unreachable, falling back to Ollama llama backend")
    return "ollama", LlamaNERPass()
