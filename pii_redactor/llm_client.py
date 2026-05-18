"""LLM client abstraction.

The detector talks to LLMs through a small Protocol so the inference
backend is swappable. Four implementations ship with the library:

- LlamaCppClient: HTTP client for a llama.cpp server. Supports GBNF
  grammar-constrained sampling, which is the paper's intended path.
- HFInferenceClient: Hugging Face Inference API. Used for the Gradio
  Space demo where running llama.cpp inside the Space isn't feasible.
  No grammar enforcement — relies on prompt instruction and defensive
  parsing.
- OllamaClient: HTTP client for a locally-running Ollama instance.
  No grammar enforcement. Ideal for local development with models
  already pulled via `ollama pull`.
- MockClient: deterministic stub for tests.

Scale notes
-----------
LlamaCppClient and OllamaClient use per-thread requests.Session instances
(via threading.local) so TCP connections are pooled and reused across calls
without thread-safety concerns. Both clients implement exponential-backoff
retry (3 attempts, 100ms/200ms/400ms) to survive transient network errors.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Optional, Protocol


# ── Per-thread HTTP session (connection pooling without thread-safety issues) ─

_tls = threading.local()


def _get_session():
    """Return a thread-local requests.Session with connection pooling."""
    import requests
    from requests.adapters import HTTPAdapter

    if not hasattr(_tls, "session"):
        s = requests.Session()
        # 4 keep-alive connections per host per thread — covers llama.cpp + Ollama
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _tls.session = s
    return _tls.session


def _post_with_retry(url: str, payload: dict, timeout: float, retries: int = 3) -> Any:
    """POST with exponential-backoff retry. Returns parsed response object."""
    import requests

    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(retries):
        try:
            resp = _get_session().post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(0.1 * (2 ** attempt))  # 100ms, 200ms, 400ms
    raise last_exc


# ── Protocol ──────────────────────────────────────────────────────────────────

class LLMClient(Protocol):
    """Minimal interface a backend must satisfy."""

    name: str

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        grammar: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Return the model's raw text response."""
        ...


# ── Backends ──────────────────────────────────────────────────────────────────

class LlamaCppClient:
    """HTTP client for a llama.cpp server (`llama-server` binary).

    Supports GBNF grammar-constrained sampling (the paper's intended path).
    Uses connection pooling and exponential-backoff retry.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model_name: str = "llama-3-8b-instruct",
        timeout: float = 120.0,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.name = model_name
        self.timeout = timeout
        self.retries = retries

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        grammar: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_prompt}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        payload: dict[str, Any] = {
            "prompt": prompt,
            "temperature": temperature,
            "n_predict": max_tokens,
            "stop": ["<|eot_id|>", "<|end_of_text|>"],
        }
        if grammar:
            payload["grammar"] = grammar

        resp = _post_with_retry(
            f"{self.base_url}/completion", payload, self.timeout, self.retries
        )
        return resp.json()["content"]


class HFInferenceClient:
    """Hugging Face Inference API client. Used for the Gradio Space demo.

    Doesn't support grammar enforcement. Relies on prompt instruction
    plus defensive JSON extraction in the detector.
    """

    def __init__(
        self,
        model_id: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
        token: Optional[str] = None,
    ):
        from huggingface_hub import InferenceClient  # local import

        self._client = InferenceClient(model=model_id, token=token)
        self.name = model_id

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        grammar: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        # grammar is silently ignored; HF Inference doesn't support GBNF.
        result = self._client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.choices[0].message.content or ""


class OllamaClient:
    """HTTP client for a locally-running Ollama instance.

    Hits /api/chat (OpenAI-compatible format). No grammar enforcement —
    Ollama does not support GBNF. Uses connection pooling and
    exponential-backoff retry.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout: float = 120.0,
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.timeout = timeout
        self.retries = retries

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        grammar: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        # grammar is silently ignored; Ollama does not support GBNF.
        payload: dict[str, Any] = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            resp = _post_with_retry(
                f"{self.base_url}/api/chat", payload, self.timeout, self.retries
            )
            return resp.json()["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code != 404:
                raise

        generate_payload: dict[str, Any] = {
            "model": self.name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        resp = _post_with_retry(
            f"{self.base_url}/api/generate",
            generate_payload,
            self.timeout,
            self.retries,
        )
        return resp.json().get("response", "")


class MockClient:
    """Deterministic stub for tests and offline development.

    Detects PII using only the regex first-pass from validators.PATTERNS,
    so tests can exercise the full pipeline without an LLM.
    """

    name = "mock"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        grammar: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        matches = re.findall(r'"""(.+?)"""', user_prompt, re.DOTALL)
        text = matches[-1] if matches else ""

        from .validators import regex_first_pass

        hits = regex_first_pass(text)
        return json.dumps(
            {
                "pii": [
                    {"category": cat.value, "value": value}
                    for cat, _start, _end, value in hits
                ]
            }
        )
