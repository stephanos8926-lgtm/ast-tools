"""Indexer package for semantic codebase analysis.

Submodules:
    parser: AST parsing with error handling
    extractor: Symbol and edge extraction
    cache: JSON-based cache with LRU eviction
"""

from .cache import ASTCache
from .extractor import SymbolExtractor, extract_symbols
from .parser import Parser, parse_file

__all__ = [
    "ASTCache",
    "Parser",
    "SymbolExtractor",
    "extract_symbols",
    "parse_file",
]
