"""Context injection package for ast-tools.

Provides automatic injection of relevant code context into LLM prompts
based on multi-factor relevance scoring, budget management, and diversity constraints.
"""

from .history import InjectionHistory
from .formatters import MarkdownFormatter, count_tokens
from .injector import ContextInjector

__all__ = [
    "InjectionHistory",
    "MarkdownFormatter",
    "count_tokens",
    "ContextInjector",
]