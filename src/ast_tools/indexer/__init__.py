"""Indexer package for semantic codebase analysis.

Submodules:
    parser: AST parsing with error handling
    extractor: Symbol and edge extraction
    cache: JSON-based cache with LRU eviction
"""

from .parser import Parser, parse_file
from .extractor import SymbolExtractor, extract_symbols
from .cache import ASTCache

__all__ = [
    "Parser",
    "SymbolExtractor",
    "extract_symbols",
    "ASTCache",
]