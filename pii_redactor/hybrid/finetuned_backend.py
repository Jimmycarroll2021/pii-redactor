"""Finetuned openai/privacy-filter backend (LoRA adapter loaded via PEFT).

Drop-in replacement for ``OpenAIPrivacyFilter`` that loads the base
``openai/privacy-filter`` model and merges a LoRA adapter on top via PEFT.
After merge, inference is identical to a vanilla token-classification
pipeline — no PEFT overhead per call.

Used when ``PIIR_BACKEND=transformers_au_finetuned`` and
``PIIR_LORA_ADAPTER`` points at an adapter directory (default
``/mnt/ai/adapters/redact-au-1b/best``).
"""

# References:
#   Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., &
#   Chen, W. (2022). LoRA: Low-Rank Adaptation of Large Language Models. ICLR 2022.
#   arxiv:2106.09685.
#   See `docs/references/hu-2022-lora.pdf` and
#   `docs/references/REFERENCES.md` (citekey: hu-2022-lora).
#
#   This module loads a LoRA adapter (rank-decomposition update matrices) on top of
#   the `openai/privacy-filter` base via the HuggingFace PEFT library.

from __future__ import annotations

import logging
import os
from typing import Any

from .openai_backend import OpenAIPrivacyFilter

logger = logging.getLogger(__name__)


class FinetunedOpenAIBackend(OpenAIPrivacyFilter):
    """openai/privacy-filter base + LoRA adapter loaded via PEFT.

    Inherits all the predict / predict_with_scores logic from the parent
    class. Only the model-load path is overridden: instead of constructing
    the HF pipeline from the bare base model id, we:

      1. Load base + tokenizer
      2. Load LoRA adapter via PEFT
      3. merge_and_unload() the adapter into the base
      4. Build the HF pipeline from the merged model

    The merge step trades a tiny load-time cost for zero-overhead inference.
    """

    DEFAULT_ADAPTER_PATH = "/mnt/ai/adapters/redact-au-1b/best"
    DEFAULT_BASE_MODEL = "openai/privacy-filter"

    def __init__(
        self,
        adapter_path: str | None = None,
        base_model: str | None = None,
        device: int | None = None,
        torch_dtype: str | None = "bfloat16",
        score_threshold: float | None = None,
    ):
        # Resolve adapter path: arg > env > default
        self.adapter_path = (
            adapter_path
            or os.environ.get("PIIR_LORA_ADAPTER")
            or self.DEFAULT_ADAPTER_PATH
        )
        base = base_model or os.environ.get(
            "PIIR_FINETUNED_BASE_MODEL", self.DEFAULT_BASE_MODEL
        )
        super().__init__(
            model_id=base,
            device=device,
            torch_dtype=torch_dtype,
            score_threshold=score_threshold,
        )
        # Mark that we need to swap the pipeline's model after load
        self._adapter_loaded = False

    def _ensure_loaded(self) -> None:
        """Load base + apply LoRA + merge into the pipeline.

        Replaces the parent's _ensure_loaded so the LoRA adapter is applied
        before any predict() call. We load the model manually, merge the
        adapter, then construct the pipeline around the merged model.
        """
        if self._pipeline is not None and self._adapter_loaded:
            return
        try:
            import torch
            from peft import PeftModel
            from transformers import (
                AutoModelForTokenClassification,
                AutoTokenizer,
                pipeline as hf_pipeline,
            )
        except ImportError as exc:
            raise RuntimeError(
                "peft + transformers + torch are required for the "
                "transformers_au_finetuned backend. Install with: "
                "pip install 'pii-redactor-au[hybrid]' && pip install peft"
            ) from exc

        if self._requested_device is None:
            device = 0 if torch.cuda.is_available() else -1
        else:
            device = self._requested_device

        dtype = self._requested_dtype or "bfloat16"
        torch_dtype = (
            torch.bfloat16 if dtype == "bfloat16"
            else (torch.float16 if dtype == "float16" else torch.float32)
        )

        logger.info(
            "Loading finetuned openai/privacy-filter: base=%s adapter=%s "
            "device=%s dtype=%s",
            self.model_id,
            self.adapter_path,
            device,
            dtype,
        )

        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        base_model = AutoModelForTokenClassification.from_pretrained(
            self.model_id, torch_dtype=torch_dtype
        )
        if not os.path.exists(self.adapter_path):
            raise FileNotFoundError(
                f"LoRA adapter not found at {self.adapter_path!r}. "
                "Set PIIR_LORA_ADAPTER or pass adapter_path explicitly."
            )
        peft_model = PeftModel.from_pretrained(base_model, self.adapter_path)
        # Merge LoRA into the base for fastest inference (no PEFT overhead per call)
        merged = peft_model.merge_and_unload()
        if device >= 0:
            merged = merged.to(f"cuda:{device}")
        merged.eval()

        self._pipeline = hf_pipeline(
            task="token-classification",
            model=merged,
            tokenizer=tokenizer,
            device=device,
            aggregation_strategy=self.aggregation_strategy,
        )
        self._device = device
        self._adapter_loaded = True

    @property
    def backend_name(self) -> str:
        return "transformers_au_finetuned"

    @property
    def adapter_id(self) -> str:
        return os.path.basename(self.adapter_path) or "redact-au-1b"

    @property
    def name(self) -> str:
        return f"{self.model_id}+{self.adapter_id}"
