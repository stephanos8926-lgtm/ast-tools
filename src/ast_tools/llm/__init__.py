"""LLM-powered fix generation and analysis."""

from .diff_parser import ParseResult, parse_and_validate_diff
from .prompts import Prompts

__all__ = [
    "LLMClient",
    "LLMFixContext",
    "LLMFixResult",
    "ParseResult",
    "Prompts",
    "parse_and_validate_diff",
]


def __getattr__(name):
    """Lazy import client module to avoid import-time errors."""
    if name in ("LLMClient", "LLMFixContext", "LLMFixResult"):
        from .client import LLMClient, LLMFixContext, LLMFixResult

        return globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
