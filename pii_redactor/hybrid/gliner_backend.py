"""GLiNER substrate backend — the license-clean (Apache-2.0) replacement for the
broken openai/privacy-filter checkpoint.

Why this exists
---------------
The base ``openai/privacy-filter`` checkpoint will not load on stock transformers
(custom architecture) and previously failed open. The substrate bake-off
(2026-06-26) picked ``urchade/gliner_multi_pii-v1`` (Apache-2.0): 98.76% char
recall / 2.08% per-doc name leak — the best *shippable* substrate (piiranha wins
on recall but is cc-by-nc-nd, so it cannot ship).

GLiNER is a label-prompted, zero-shot NER architecture — NOT a HF
token-classification model — so it cannot be loaded through
``OpenAIPrivacyFilter`` via ``PIIR_HF_MODEL``. It needs its own backend, but it
satisfies the same duck-typed substrate contract the hybrid pipeline consumes:
``warmup()`` / ``predict()`` / ``predict_with_scores()`` / ``name``. The AU
validator moat, the always-on regex floor, merge-with-AU-priority, and the
fail-closed gate all sit on top unchanged — substrate-independent.

The substrate only needs to supply the NER-dependent categories (person /
organisation / location / address / date). AU regulatory IDs
(TFN/Medicare/ABN/ACN/BSB/CRN) are owned by the regex floor's checksum
validators downstream, so they are NOT prompted here.

Span schema returned: ``(gliner_label, start_char, end_char, value[, score])`` —
the label strings are mapped to PIICategory downstream via
``OPENAI_TO_AU_PRIMARY`` (see openai_backend.py).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Prompt labels. Focused on the NER-dependent categories (regex floor owns AU
# IDs). Every label here MUST also exist as a key in OPENAI_TO_AU_PRIMARY or it
# falls back to generic_id downstream.
GLINER_LABELS = [
    "person",
    "organization",
    "address",
    "location",
    "email",
    "phone number",
    "date of birth",
    "date",
    "driver's license number",
]


class GlinerBackend:
    """GLiNER substrate backend implementing the hybrid substrate contract.

    Single-pass over the document. NOTE: GLiNER has a bounded token window
    (~384 tokens for gliner_multi_pii-v1); very long documents may miss spans
    past the window — long-doc windowing is a tracked follow-up, verified by the
    name-recall eval before any production claim.
    """

    DEFAULT_MODEL_ID = "urchade/gliner_multi_pii-v1"
    # Recall-oriented floor (GLiNER's own default is 0.5). Lower => wider span
    # set for the AU resolver + merge to dedupe; higher => less over-redaction.
    # Tunable via PIIR_GLINER_THRESHOLD; this is the precision/recall knob.
    DEFAULT_THRESHOLD = 0.4

    def __init__(
        self,
        model_id: str | None = None,
        threshold: float | None = None,
        labels: list[str] | None = None,
        device: int | None = None,
    ):
        self.model_id = model_id or os.environ.get("PIIR_GLINER_MODEL", self.DEFAULT_MODEL_ID)
        if threshold is None:
            env_thr = os.environ.get("PIIR_GLINER_THRESHOLD")
            threshold = float(env_thr) if env_thr is not None else self.DEFAULT_THRESHOLD
        self.threshold = float(threshold)
        self.labels = labels or GLINER_LABELS
        self._requested_device = device
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from gliner import GLiNER
        except ImportError as exc:  # pragma: no cover - exercised at runtime
            raise RuntimeError(
                "gliner is required for the transformers_au_gliner backend. "
                "Install with: pip install gliner"
            ) from exc

        logger.info("Loading GLiNER %s threshold=%.3f", self.model_id, self.threshold)
        model = GLiNER.from_pretrained(self.model_id)
        try:
            import torch

            if self._requested_device is not None:
                model = model.to(f"cuda:{self._requested_device}")
            elif torch.cuda.is_available():
                model = model.to("cuda")
        except Exception:  # noqa: BLE001 - CPU fallback is fine
            pass
        self._model = model

    @property
    def name(self) -> str:
        return self.model_id

    def warmup(self, sample_text: str = "Hello, my name is Alice.") -> None:
        self._ensure_loaded()
        try:
            self._model.predict_entities(sample_text, self.labels, threshold=self.threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GLiNER warmup inference failed: %s", exc)

    def unload(self) -> None:
        self._model = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass

    def predict(self, text: str) -> list[tuple[str, int, int, str]]:
        return [(c, s, e, v) for (c, s, e, v, _score) in self.predict_with_scores(text)]

    def predict_with_scores(self, text: str) -> list[tuple[str, int, int, str, float]]:
        if not text:
            return []
        self._ensure_loaded()
        try:
            ents = self._model.predict_entities(text, self.labels, threshold=self.threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GLiNER inference failed: %s", exc)
            return []

        out: list[tuple[str, int, int, str, float]] = []
        for ent in ents:
            label = ent.get("label")
            start = ent.get("start")
            end = ent.get("end")
            if not label or not isinstance(start, int) or not isinstance(end, int):
                continue
            if start < 0 or end <= start or end > len(text):
                continue
            # Trust the offsets; trim whitespace so spans don't eat padding.
            inner = text[start:end]
            lstripped = inner.lstrip()
            rstripped = lstripped.rstrip()
            if not rstripped:
                continue
            real_start = start + (len(inner) - len(lstripped))
            real_end = real_start + len(rstripped)
            score = ent.get("score", 1.0)
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                score_f = 1.0
            out.append((label, real_start, real_end, text[real_start:real_end], score_f))
        return out
