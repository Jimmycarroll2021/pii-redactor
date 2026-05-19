"""Hybrid OpenAI + AU validator pipeline.

This module wraps `openai/privacy-filter` (Apache 2.0, ~50M active params,
~110 ms/doc on a single RTX 4090) as a fast first-pass NER, then runs the
existing Australian validators + regex layer on top to:

1. Disambiguate OpenAI's `account_number` bucket into the precise AU
   sub-category (TFN, Medicare, MRN, IHI, BSB, ABN, ACN, driver licence,
   passport, Centrelink CRN, etc.) using checksum validation.
2. Catch usernames + AU phone/address fragments OpenAI consistently misses.
3. Return the same RedactionResult schema as the stock pipeline so the
   hybrid backend is a drop-in replacement.

Selectable via PIIR_BACKEND=transformers_au.
"""
from .au_resolver import resolve_account_numbers
from .llama_pass import LlamaNERPass
from .openai_backend import OpenAIPrivacyFilter
from .pipeline import (
    DEFAULT_GATE_MIN_SCORE,
    DEFAULT_GATE_MIN_TOKENS,
    DEFAULT_GATE_MODE,
    GATE_MODE_ALWAYS,
    GATE_MODE_CONFIDENCE,
    GATE_MODE_NEVER,
    HybridDetector,
    build_hybrid_pipeline,
    should_invoke_llama,
)
from .regex_supplement import supplement_with_regex
from .vllm_pass import VLLMNERPass, select_llama_backend

__all__ = [
    "DEFAULT_GATE_MIN_SCORE",
    "DEFAULT_GATE_MIN_TOKENS",
    "DEFAULT_GATE_MODE",
    "GATE_MODE_ALWAYS",
    "GATE_MODE_CONFIDENCE",
    "GATE_MODE_NEVER",
    "HybridDetector",
    "LlamaNERPass",
    "OpenAIPrivacyFilter",
    "VLLMNERPass",
    "build_hybrid_pipeline",
    "resolve_account_numbers",
    "select_llama_backend",
    "should_invoke_llama",
    "supplement_with_regex",
]
