"""Parallel narrative-NER pass using llama3.1:8b via Ollama.

The openai/privacy-filter backend is fast and well-calibrated but
conservative — on the Gretel-100 corpus it drops 18 pp of address
recall, 7 pp of DOB recall, and 14 pp of name recall vs the CPU
llama3.1:8b baseline. The baseline's recall is driven by prompt
engineering ("over-extraction acceptable; when in doubt prefer to
extract") that no calibrated NER head reproduces.

This module wires llama3.1:8b — served via Ollama on the RTX 4090
(GPU memory: openai ~2.7 GB + llama3.1 Q4_K_M ~5 GB; comfortably
under the 24 GB cap) — as a parallel NER pass to the
OpenAIPrivacyFilter. The hybrid detector unions both passes' spans
before the AU resolver, so the narrative recall the calibrated head
misses is recovered from llama's softer prompt-driven extraction.

Returned span schema matches OpenAIPrivacyFilter.predict():

    (openai_category, start_char, end_char, value)

Where ``openai_category`` is one of the 8 OpenAI categories. We map
the llama-emitted PIICategory back into OpenAI's space so the
downstream resolver sees a uniform input.

Configuration
-------------
- ``PIIR_LLAMA_BASE_URL``      Default ``http://host.docker.internal:11434``
- ``PIIR_LLAMA_MODEL``         Default ``llama3.1:8b``
- ``PIIR_LLAMA_TIMEOUT_S``     Default ``60``
- ``PIIR_LLAMA_ENABLED``       Default ``true`` (set ``false`` to disable)
- ``PIIR_LLAMA_MAX_CHARS``     Default ``8000`` — skip the llama pass for
                               documents longer than this (latency budget)

Soft-fail by design: any error (Ollama unreachable, model missing,
JSON parse fail) returns []. The OpenAI pass still produces results;
the hybrid degrades gracefully to v0.2.0 behaviour.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from ..llm_client import OllamaClient
from ..models import PIICategory
from ..prompts import build_prompt
from ..detector import PIIDetector

logger = logging.getLogger(__name__)


# Map redact-au PIICategory → OpenAI's 8 categories so the downstream
# AU resolver + merger sees a uniform input regardless of which NER
# pass emitted the span. Categories the resolver itself produces
# (TFN, ABN, Medicare, …) are passed through as `account_number` so
# the resolver re-validates them with checksums — this is the same
# round-trip OpenAI's `account_number` spans take.
_LLAMA_TO_OPENAI: dict[PIICategory, str] = {
    PIICategory.NAME: "private_person",
    PIICategory.ADDRESS: "private_address",
    PIICategory.EMAIL: "private_email",
    PIICategory.PHONE: "private_phone",
    PIICategory.DATE: "private_date",
    PIICategory.DATE_OF_BIRTH: "private_date",
    PIICategory.URL: "private_url",
    PIICategory.USERNAME: "secret",
    PIICategory.PATIENT_ID: "account_number",
    PIICategory.GENERIC_ID: "account_number",
    # AU regulated identifiers — round-trip through the resolver so the
    # validator_passed flag is populated.
    PIICategory.TFN: "account_number",
    PIICategory.ABN: "account_number",
    PIICategory.ACN: "account_number",
    PIICategory.MEDICARE: "account_number",
    PIICategory.BSB_ACCOUNT: "account_number",
    PIICategory.HEALTHCARE_IDENTIFIER: "account_number",
    PIICategory.MEDICAL_RECORD_NUMBER: "account_number",
    PIICategory.CRN: "account_number",
    PIICategory.DRIVER_LICENCE: "account_number",
    PIICategory.PASSPORT: "account_number",
}


def _env_truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class LlamaNERPass:
    """Narrative NER pass via Ollama-served llama3.1:8b.

    Mirrors the OpenAIPrivacyFilter interface (predict / warmup / name)
    so it can be plugged into HybridDetector as a peer NER backend.
    """

    DEFAULT_BASE_URL = "http://host.docker.internal:11434"
    DEFAULT_MODEL = "llama3.1:8b"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        enabled: bool | None = None,
        max_chars: int | None = None,
        num_ctx: int | None = None,
        num_gpu: int | None = None,
    ):
        self.base_url = base_url or os.environ.get(
            "PIIR_LLAMA_BASE_URL", self.DEFAULT_BASE_URL
        )
        self.model = model or os.environ.get(
            "PIIR_LLAMA_MODEL", self.DEFAULT_MODEL
        )
        self.timeout_s = timeout_s if timeout_s is not None else _env_float(
            "PIIR_LLAMA_TIMEOUT_S", 60.0
        )
        self.enabled = enabled if enabled is not None else _env_truthy(
            "PIIR_LLAMA_ENABLED", True
        )
        self.max_chars = max_chars if max_chars is not None else _env_int(
            "PIIR_LLAMA_MAX_CHARS", 8000
        )
        # KV-cache budget. llama3.1's native 131k context inflates KV to
        # 31 GB on GPU — set num_ctx to a tight window so the model + cache
        # stay 100% resident on the 4090's 24 GB.
        self.num_ctx = num_ctx if num_ctx is not None else _env_int(
            "PIIR_LLAMA_NUM_CTX", 4096
        )
        self.num_gpu = num_gpu if num_gpu is not None else _env_int(
            "PIIR_LLAMA_NUM_GPU", 999  # -> fully offload
        )
        self._client: OllamaClient | None = None
        self._loaded = False

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def _ensure_loaded(self) -> None:
        if self._client is not None:
            return
        self._client = OllamaClient(
            base_url=self.base_url,
            model=self.model,
            timeout=self.timeout_s,
            extra_options={
                "num_ctx": self.num_ctx,
                "num_gpu": self.num_gpu,
            },
        )

    def warmup(self) -> None:
        """Issue a no-op extraction to warm Ollama's model cache."""
        if not self.enabled:
            logger.info("llama narrative pass disabled (PIIR_LLAMA_ENABLED=false)")
            return
        self._ensure_loaded()
        try:
            self.predict("Hello, my name is Alice.")
            self._loaded = True
            logger.info("llama narrative pass warmup ok (%s)", self.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llama narrative pass warmup failed: %s", exc)

    def predict(self, text: str) -> list[tuple[str, int, int, str]]:
        """Run llama, parse entities, locate in source, return OpenAI-shape tuples."""
        if not text or not self.enabled:
            return []
        if len(text) > self.max_chars:
            logger.debug(
                "llama pass skipped: doc %d chars > max_chars %d",
                len(text),
                self.max_chars,
            )
            return []
        self._ensure_loaded()
        assert self._client is not None  # for type checkers
        # Use the existing prompt template — it's the same one that produced
        # 99.6% / 100% on the CPU baseline.
        categories = [c.value for c in PIICategory]
        system, user = build_prompt(text, categories)
        try:
            raw = self._client.complete(
                system_prompt=system,
                user_prompt=user,
                grammar=None,
                temperature=0.0,
                max_tokens=2048,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("llama narrative pass call failed: %s", exc)
            return []

        try:
            entities = PIIDetector._parse_response(raw, fail_on_parse_error=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llama narrative pass parse failed: %s", exc)
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

    def unload(self) -> None:  # parity with OpenAIPrivacyFilter
        self._client = None
        self._loaded = False


def _iter_occurrences(text: str, value: str) -> "Any":
    """Yield every (non-overlapping) start index of ``value`` in ``text``.

    Mirrors PIIDetector._locate_in_source so the llama pass produces the
    same span enumeration as the legacy detector.
    """
    if not value:
        return []
    out: list[int] = []
    idx = 0
    while True:
        pos = text.find(value, idx)
        if pos == -1:
            break
        out.append(pos)
        idx = pos + len(value)
    return out
