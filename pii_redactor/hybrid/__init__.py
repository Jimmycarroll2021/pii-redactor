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
from .pipeline import HybridDetector, build_hybrid_pipeline
from .regex_supplement import supplement_with_regex

__all__ = [
    "HybridDetector",
    "LlamaNERPass",
    "OpenAIPrivacyFilter",
    "build_hybrid_pipeline",
    "resolve_account_numbers",
    "supplement_with_regex",
]
