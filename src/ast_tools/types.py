"""Shared type definitions for ast-tools semantic indexing.

This module contains dataclasses and type aliases used across indexer, database,
and tools packages. Centralizing types here prevents circular imports.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum


class SymbolKind(str, Enum):
    """Valid symbol kinds in the index."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"


class EdgeKind(str, Enum):
    """Valid edge types between symbols."""
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    INSTANTIATES = "instantiates"
    IMPLEMENTS = "implements"  # Phase 9: Interface/protocol implementation


class ResolutionState(int, Enum):
    """Edge resolution states."""
    UNRESOLVED = 0
    RESOLVED = 1
    STALE = 2


@dataclass
class Symbol:
    """Represents a code symbol (function, class, method, etc.).
    
    Attributes:
        id: Unique identifier (file_path:qualified_name)
        name: Simple symbol name
        qualified_name: Dotted path (e.g., "module.Class.method")
        kind: Type of symbol (function, class, etc.)
        file_path: Absolute or relative path to source file
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)
        signature: Function/method signature string
        docstring: Docstring content if present
        is_public: True if symbol doesn't start with underscore
        content_hash: SHA256 hash of file content at index time
        embedding: 384-dim vector embedding for semantic search (optional)
        lang: Programming language code (python, rust, go, typescript, etc.)
    """
    id: str
    name: str
    qualified_name: str
    kind: SymbolKind | str
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    is_public: bool = True
    content_hash: str = ""
    embedding: Optional[List[float]] = None  # Phase 2: vector embedding
    lang: str = "python"  # Programming language
    
    def __post_init__(self):
        """Validate and normalize kind field."""
        if isinstance(self.kind, str):
            self.kind = SymbolKind(self.kind.lower())
        
        # Auto-detect public status if not set
        if self.name.startswith("_"):
            self.is_public = False


@dataclass
class Edge:
    """Represents a relationship between two symbols.
    
    Attributes:
        source_id: ID of the source symbol (the caller/importer)
        target_name: Name of target symbol (may be unresolved)
        target_id: ID of target symbol if resolved
        edge_type: Type of relationship
        resolution_state: Whether target has been resolved
        metadata: Optional JSON metadata (Phase 9: edge context)
    """
    source_id: str
    target_name: str
    edge_type: EdgeKind | str
    target_id: Optional[str] = None
    resolution_state: ResolutionState | int = ResolutionState.UNRESOLVED
    metadata: Optional[dict] = None  # Phase 9: additional context
    
    def __post_init__(self):
        """Validate and normalize edge_type and resolution_state."""
        if isinstance(self.edge_type, str):
            self.edge_type = EdgeKind(self.edge_type.lower())
        if isinstance(self.resolution_state, int):
            self.resolution_state = ResolutionState(self.resolution_state)


@dataclass
class FileCache:
    """Cached metadata for an indexed file.
    
    Attributes:
        file_path: Path to the source file
        content_hash: SHA256 hash of file content
        last_indexed: Unix timestamp of last indexing
        symbol_count: Number of symbols extracted
    """
    file_path: str
    content_hash: str
    last_indexed: int
    symbol_count: int = 0


# Alias for test compatibility
FileCacheEntry = FileCache


@dataclass
class IndexStats:
    """Statistics about the codebase index.
    
    Attributes:
        indexed_files: Number of files in index
        total_symbols: Total symbols across all files
        total_edges: Total edges (relationships)
        cache_path: Path to cache directory
        last_update: Unix timestamp of last update
    """
    indexed_files: int
    total_symbols: int
    total_edges: int
    cache_path: str
    last_update: int


# Type aliases for convenience
SymbolList = List[Symbol]
EdgeList = List[Edge]
SymbolDict = dict[str, Symbol]
EdgeTuple = Tuple[str, str, str]  # (source_id, target_name, edge_type)

__all__ = [
    # Enums
    "SymbolKind",
    "EdgeKind",
    "ResolutionState",
    # Dataclasses
    "Symbol",
    "Edge",
    "FileCache",
    "IndexStats",
    # Type aliases
    "SymbolList",
    "EdgeList",
    "SymbolDict",
    "EdgeTuple",
]