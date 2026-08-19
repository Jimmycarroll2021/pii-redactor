"""GBNF grammar generation for llama.cpp constrained sampling.

This is the methodological innovation from Wiest et al. — by constraining
the model's token sampling to a grammar that only produces valid JSON of
the expected shape, you remove the entire class of failure modes around
malformed output. The model literally cannot emit anything that won't
parse.

llama.cpp accepts grammars in GBNF (GGML BNF) format. The grammar below
generates JSON of the form:
    {"pii": [{"category": "name", "value": "..."}, ...]}

Backends that don't support GBNF (HF Inference, OpenAI without function
calling) fall back to prompt instruction + defensive parsing.
"""
from __future__ import annotations

from .models import PIICategory

GBNF_TEMPLATE = r'''
root        ::= "{" ws "\"pii\":" ws "[" ws (entity (ws "," ws entity)*)? ws "]" ws "}"
entity      ::= "{" ws "\"category\":" ws category ws "," ws "\"value\":" ws string ws "}"
category    ::= {categories}
string      ::= "\"" char* "\""
char        ::= [^"\\] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F]{{4}} )
ws          ::= [ \t\n]*
'''.strip()


def build_grammar(categories: list[PIICategory] | None = None) -> str:
    """Generate a GBNF grammar string for the given categories.

    If `categories` is None, all PIICategory values are used.
    """
    if categories is None:
        categories = list(PIICategory)
    cat_alts = " | ".join(f'"\\"{c.value}\\""' for c in categories)
    return GBNF_TEMPLATE.replace("{categories}", cat_alts)


def build_default_grammar() -> str:
    """Default grammar covering all built-in categories."""
    return build_grammar()
