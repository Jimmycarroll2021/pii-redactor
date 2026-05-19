"""Thin wrapper around the openai/privacy-filter token-classification pipeline.

Holds the HF transformers pipeline as a long-lived object (model stays on GPU
across calls), normalises predictions into PIISpan-compatible tuples, and
optionally resolves to character-offset spans against the source text.

Span schema returned (list of tuples):
    (openai_category, start_char, end_char, value)

Where `openai_category` is one of:
    private_person, private_address, private_email, private_phone,
    private_date, private_url, account_number, secret

Design notes
------------
- Lazy import of transformers/torch so the rest of the library still imports
  on environments without them (CPU dev boxes, the API container that
  doesn't need GPU, etc.).
- aggregation_strategy="simple" groups subwords into whole entities and gives
  per-entity start/end character offsets in the original text — that's what
  we need to round-trip to PIISpan.
- The pipeline is constructed once and reused. Reset via .unload() if needed.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# The 8 categories openai/privacy-filter emits. Anything else is a model
# regression and we just pass it through (the downstream code is defensive).
OPENAI_CATEGORIES = frozenset(
    {
        "private_person",
        "private_address",
        "private_email",
        "private_phone",
        "private_date",
        "private_url",
        "account_number",
        "secret",
    }
)

# Map OpenAI categories to redact-au PIICategory values. Anything that lands
# in `account_number` or `secret` will be re-resolved by the AU resolver;
# the value here is the *fallback* type if no AU validator matches.
OPENAI_TO_AU_PRIMARY = {
    "private_person": "name",
    "private_address": "address",
    "private_email": "email",
    "private_phone": "phone",
    "private_date": "date",
    "private_url": "url",
    "account_number": "generic_id",
    "secret": "generic_id",
}


class OpenAIPrivacyFilter:
    """Wraps the HF token-classification pipeline for openai/privacy-filter.

    The model is loaded once (GPU-resident) and reused. Inference is
    sequential per-document but the model itself is fast (~110 ms on a
    4090 for a 1k-token doc).
    """

    DEFAULT_MODEL_ID = "openai/privacy-filter"
    # Default Viterbi/score floor. The model is calibrated conservatively;
    # production-recall use needs to lower this to widen the span set the
    # AU resolver + regex layer can dedupe / re-categorise downstream.
    # 0.0 = accept every span the aggregator emits.
    DEFAULT_SCORE_THRESHOLD = 0.0

    def __init__(
        self,
        model_id: str | None = None,
        device: int | None = None,
        aggregation_strategy: str = "simple",
        torch_dtype: str | None = None,
        score_threshold: float | None = None,
    ):
        self.model_id = model_id or os.environ.get(
            "PIIR_HF_MODEL", self.DEFAULT_MODEL_ID
        )
        self.aggregation_strategy = os.environ.get(
            "PIIR_HF_AGGREGATION", aggregation_strategy
        )
        if score_threshold is None:
            env_thr = os.environ.get("PIIR_HF_SCORE_THRESHOLD")
            score_threshold = (
                float(env_thr) if env_thr is not None else self.DEFAULT_SCORE_THRESHOLD
            )
        self.score_threshold = float(score_threshold)
        # device=None -> auto-pick. 0 = first CUDA, -1 = CPU.
        self._requested_device = device
        self._requested_dtype = torch_dtype
        self._pipeline: Any = None
        self._device: int | None = None

    # ----------------------------------------------------------------- load

    def _ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        try:
            import torch
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:  # pragma: no cover - exercised at runtime
            raise RuntimeError(
                "transformers + torch are required for the hybrid (transformers_au) "
                "backend. Install with: pip install 'pii-redactor-au[hybrid]'."
            ) from exc

        if self._requested_device is None:
            device = 0 if torch.cuda.is_available() else -1
        else:
            device = self._requested_device
        kwargs: dict[str, Any] = {
            "task": "token-classification",
            "model": self.model_id,
            "device": device,
            "aggregation_strategy": self.aggregation_strategy,
            "trust_remote_code": False,
        }
        if self._requested_dtype:
            kwargs["torch_dtype"] = self._requested_dtype
        logger.info(
            "Loading %s on device=%s dtype=%s aggregation=%s score_threshold=%.3f",
            self.model_id,
            device,
            self._requested_dtype or "auto",
            self.aggregation_strategy,
            self.score_threshold,
        )
        self._pipeline = hf_pipeline(**kwargs)
        self._device = device

    @property
    def name(self) -> str:
        return self.model_id

    @property
    def device(self) -> int | None:
        self._ensure_loaded()
        return self._device

    def warmup(
        self,
        sample_text: str = (
            "Hello, my name is Alice and my email is alice@example.com."
        ),
    ) -> None:
        """Force model load + one inference to fault GPU memory."""
        self._ensure_loaded()
        try:
            self._pipeline(sample_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Warmup inference failed: %s", exc)

    def unload(self) -> None:
        """Release the pipeline + GPU memory."""
        self._pipeline = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

    # ----------------------------------------------------------------- call

    def predict(self, text: str) -> list[tuple[str, int, int, str]]:
        """Run the model and return character-offset spans.

        Returns list of (openai_category, start, end, value) tuples.
        Spans are filtered to those whose extracted value can be located
        in the source text (the model occasionally returns trimmed
        subword fragments at chunk boundaries — those are dropped).
        """
        if not text:
            return []
        self._ensure_loaded()
        try:
            preds = self._pipeline(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI privacy-filter inference failed: %s", exc)
            return []

        out: list[tuple[str, int, int, str]] = []
        for p in preds:
            # Apply the configured score floor. The aggregator already
            # returns a `score` field on each entity in [0, 1]; spans below
            # the floor are dropped so the AU resolver doesn't see noise.
            score = p.get("score", 1.0)
            try:
                if float(score) < self.score_threshold:
                    continue
            except (TypeError, ValueError):
                pass
            cat = p.get("entity_group") or p.get("entity")
            if not cat:
                continue
            start = p.get("start")
            end = p.get("end")
            word = p.get("word", "")
            # Strip leading whitespace artefacts from BPE
            value = word.lstrip()
            if value != word and isinstance(start, int):
                start += len(word) - len(value)
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if start < 0 or end <= start or end > len(text):
                continue
            # Final source-text slice (trust the offsets over the word)
            slice_value = text[start:end].strip()
            if not slice_value:
                continue
            # Re-shrink to the stripped slice
            inner = text[start:end]
            lstripped = inner.lstrip()
            rstripped_len = len(lstripped) - len(lstripped.rstrip())
            real_start = start + (len(inner) - len(lstripped))
            real_end = end - rstripped_len
            if real_end <= real_start:
                continue
            out.append((cat, real_start, real_end, text[real_start:real_end]))
        return out
