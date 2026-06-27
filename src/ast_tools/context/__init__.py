"""Context injection package for ast-tools.

Provides automatic injection of relevant code context into LLM prompts
based on multi-factor relevance scoring, budget management, and diversity constraints.
"""

from .formatters import MarkdownFormatter, count_tokens
from .history import InjectionHistory
from .injector import ContextInjector

__all__ = [
    "ContextInjector",
    "InjectionHistory",
    "MarkdownFormatter",
    "count_tokens",
]
