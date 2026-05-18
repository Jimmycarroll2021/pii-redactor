"""Gradio Space entry point.

This is the demo UI that imports from the same `pii_redactor` library
that powers the pipeline component. Deployed at:
    https://huggingface.co/spaces/JimmyBhoy/pii-redactor

Backend selection:
- Default for the Space: HF Inference API with Llama-3.1-8B-Instruct
  (no llama.cpp server needed inside the Space).
- For local development / production pipelines: llama.cpp.
- For quick demos when neither is available: the Mock backend, which
  uses regex first-pass only.

The Space sets PIIR_BACKEND=hf and PIIR_HF_TOKEN via Spaces secrets.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import gradio as gr

from pii_redactor import Config, build_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- setup

# Build pipeline once at module load. Spaces re-uses the process across calls.
def _build() -> Any:
    cfg = Config.from_env()
    # If running on a Space and no HF token, fall back to mock so the demo
    # still works for someone exploring without auth.
    if cfg.backend == "hf" and not cfg.hf_token:
        logger.warning(
            "No HF token found, falling back to mock backend. "
            "Set HF_TOKEN as a Space secret to enable LLM-based detection."
        )
        cfg.backend = "mock"
    return build_pipeline(cfg), cfg


_PIPELINE, _CFG = _build()

# ----------------------------------------------------------------- examples

EXAMPLES = [
    [
        "Hi team, please update the case file for Sarah Mitchell (DOB 14/03/1987). "
        "Her TFN is 123 456 782 and Medicare number 2957 20197 1. Reach her on "
        "0412 345 678 or sarah.mitchell@example.com.au. Mailing address: "
        "Unit 4, 27 Northbourne Avenue, Canberra ACT 2601."
    ],
    [
        "Vendor onboarding for Acme Logistics Pty Ltd, ABN 33 051 775 556, "
        "ACN 051 775 556. Contact: Jamie Patel, jpatel@acmelogistics.com.au, "
        "(02) 6271 7000. Bank details: BSB 062-000, Account 12345678."
    ],
    [
        "Internal note: client requests payment by 30/06/2026. Their reference "
        "is CRN 555 444 333A. We've validated their identity using passport "
        "PA1234567 and NSW driver licence 12345678."
    ],
]


# ------------------------------------------------------------- UI handlers

def redact_text(
    text: str,
    placeholder_style: str,
) -> tuple[list[tuple[str, str | None]], str, str]:
    """Run redaction. Returns (highlighted_pairs, redacted_text, json_blob)."""
    if not text or not text.strip():
        return [], "", "{}"

    # Apply placeholder style override on the existing pipeline
    _PIPELINE.redactor.style = placeholder_style

    result = _PIPELINE.process_document(text)

    # Build (text, label) pairs for HighlightedText
    pairs: list[tuple[str, str | None]] = []
    cursor = 0
    spans = sorted(result.spans, key=lambda s: s.start)
    for span in spans:
        if cursor < span.start:
            pairs.append((text[cursor : span.start], None))
        pairs.append((text[span.start : span.end], span.category.value.upper()))
        cursor = span.end
    if cursor < len(text):
        pairs.append((text[cursor:], None))

    summary = result.to_dict()
    summary["categories_found"] = sorted(
        {s.category.value for s in result.spans}
    )
    return pairs, result.redacted_text, json.dumps(summary, indent=2)


# ------------------------------------------------------------- UI layout

INTRO_MD = f"""
# PII Redactor — Australian Government Edition

Pre-ingestion PII de-identification using the methodology from Wiest et al.
(NEJM AI, 2024), extended with Australian Commonwealth identifiers.

**Detected categories:** names, addresses, dates of birth, phone, email,
patient IDs, medical record numbers, healthcare identifiers, TFN, Medicare,
ABN, ACN, driver licences, passports, BSB / accounts, Centrelink CRN.

**Validation:** TFN, ABN, ACN and Medicare detections are confirmed against
their official checksum algorithms. Format-only matches are filtered out.

**Output model:** redacted text plus a safe PII table. Original values are
never returned downstream; they are only recoverable from the encrypted audit
log when an audit key is configured.

**Backend in use:** `{_CFG.backend}` ({getattr(_PIPELINE, "model_name", "unknown")})

> This is a demo. Don't paste real PII. The Space writes detections to a
> per-session audit log; for production deployments, run the same library
> behind your own infrastructure.
"""

with gr.Blocks(title="PII Redactor — AU Edition") as demo:
    gr.Markdown(INTRO_MD)

    with gr.Row():
        with gr.Column():
            input_text = gr.Textbox(
                label="Source text",
                placeholder="Paste text containing PII here...",
                lines=10,
            )
            placeholder_style = gr.Radio(
                choices=["numbered", "category", "asterisk"],
                value="numbered",
                label="Placeholder style",
            )
            submit = gr.Button("Redact", variant="primary")
            gr.Examples(examples=EXAMPLES, inputs=[input_text])

        with gr.Column():
            highlighted = gr.HighlightedText(
                label="Detected PII (highlighted)",
                show_legend=True,
            )
            redacted_out = gr.Textbox(
                label="Redacted output",
                lines=10,
            )
            details = gr.Code(label="Detection detail (JSON)", language="json")

    submit.click(
        fn=redact_text,
        inputs=[input_text, placeholder_style],
        outputs=[highlighted, redacted_out, details],
    )

    gr.Markdown(
        "---\n"
        "Source: [github.com/JimmyBhoy/pii-redactor](https://github.com/JimmyBhoy/pii-redactor) | "
        "Method: [Wiest et al., NEJM AI, 2024](https://ai.nejm.org/doi/full/10.1056/AIdbp2400537)"
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")))
