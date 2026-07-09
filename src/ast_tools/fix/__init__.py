"""
Auto-fix pipeline for ast-tools.

This module provides a unified auto-fix pipeline that orchestrates
multiple fixers (formatters, linters, type checkers) across languages
with convergence loop and safety classification.
"""

from .config import FixConfig, load_fix_config
from .engine import FixContext, FixEngine, FixResult, SafetyLevel
from .fixers import (
    CppFixer,
    GoFixer,
    MarkdownFixer,
    PythonFixer,
    RustFixer,
    TypeScriptFixer,
    get_fixer_for_language,
)

__all__ = [
    "CppFixer",
    "FixConfig",
    "FixContext",
    "FixEngine",
    "FixResult",
    "GoFixer",
    "MarkdownFixer",
    "PythonFixer",
    "RustFixer",
    "SafetyLevel",
    "TypeScriptFixer",
    "get_fixer_for_language",
    "load_fix_config",
]
