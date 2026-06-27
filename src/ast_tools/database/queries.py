"""Database query functions for semantic index operations.

All query functions are decorated with @retry_on_locked to handle concurrent access.
Batch operations use executemany() for 10x performance improvement over single inserts.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any

from ..embeddings import generate_embedding, insert_embedding, insert_embeddings_batch
from ..types import Symbol
from .connection import retry_on_locked

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Symbol Queries
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def search_symbols(
    conn: sqlite3.Connection, query: str, kind_filter: list[str] | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    """Search symbols using FTS5 full-text search.

    Args:
        conn: SQLite connection
        query: Search query (FTS5 syntax: keywords, phrases, OR/AND/NOT)
        kind_filter: Optional list of symbol kinds to filter (e.g., ['function', 'class'])
        limit: Maximum results to return

    Returns:
        List of matching symbols with all columns

    Example:
        >>> search_symbols(conn, "database OR query", kind_filter=['function'])
        [{'id': '...', 'name': 'query_db', ...}, ...]
    """
    # Build FTS5 query
    fts_query = "SELECT rowid FROM symbols_fts WHERE symbols_fts MATCH ? LIMIT ?"
    fts_params: list[Any] = [query, limit]

    # Get matching rowids from FTS5
    fts_results = conn.execute(fts_query, fts_params).fetchall()

    if not fts_results:
        return []

    rowids = [row["rowid"] for row in fts_results]

    # Build main query with optional kind filter
    kind_clause = ""
    if kind_filter:
        placeholders = ",".join(["?" for _ in kind_filter])
        kind_clause = f"AND kind IN ({placeholders})"

    query_sql = f"""
        SELECT id, name, qualified_name, kind, file_path, start_line, end_line,
               signature, docstring, is_public, content_hash, indexed_at
        FROM symbols
        WHERE rowid IN ({",".join(["?" for _ in rowids])})
        {kind_clause}
        ORDER BY name
    """

    params: list[Any] = rowids
    if kind_filter:
        params.extend(kind_filter)

    return conn.execute(query_sql, params).fetchall()


@retry_on_locked()
def find_symbol_definition(conn: sqlite3.Connection, qualified_name: str) -> sqlite3.Row | None:
    """Find a symbol by its qualified name.

    Args:
        conn: SQLite connection
        qualified_name: Fully qualified symbol name (e.g., "module.Class.method")

    Returns:
        Symbol row or None if not found

    Example:
        >>> find_symbol_definition(conn, "ast_tools.database.connection.get_connection")
        {'id': '...', 'name': 'get_connection', ...}
    """
    query = """
        SELECT id, name, qualified_name, kind, file_path, start_line, end_line,
               signature, docstring, is_public, content_hash, indexed_at
        FROM symbols
        WHERE qualified_name = ?
        LIMIT 1
    """
    row = conn.execute(query, (qualified_name,)).fetchone()
    return row


@retry_on_locked()
def list_symbols_by_file(conn: sqlite3.Connection, file_path: str) -> list[sqlite3.Row]:
    """List all symbols in a specific file.

    Args:
        conn: SQLite connection
        file_path: Path to the source file

    Returns:
        List of symbols defined in the file
    """
    query = """
        SELECT id, name, qualified_name, kind, start_line, end_line,
               signature, docstring, is_public
        FROM symbols
        WHERE file_path = ?
        ORDER BY start_line
    """
    return conn.execute(query, (file_path,)).fetchall()


@retry_on_locked()
def get_symbol_by_id(conn: sqlite3.Connection, symbol_id: str) -> sqlite3.Row | None:
    """Get a symbol by its unique ID.

    Args:
        conn: SQLite connection
        symbol_id: Symbol ID (file_path:qualified_name)

    Returns:
        Symbol row or None if not found
    """
    query = """
        SELECT id, name, qualified_name, kind, file_path, start_line, end_line,
               signature, docstring, is_public, content_hash, indexed_at
        FROM symbols
        WHERE id = ?
        LIMIT 1
    """
    return conn.execute(query, (symbol_id,)).fetchone()


# ──────────────────────────────────────────────────────────────────────────────
# Edge Queries
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def find_references(conn: sqlite3.Connection, symbol_id: str) -> list[sqlite3.Row]:
    """Find all references to a symbol (edges where this symbol is the target).

    Args:
        conn: SQLite connection
        symbol_id: Target symbol ID

    Returns:
        List of edges referencing this symbol
    """
    query = """
        SELECT e.id, e.source_id, e.target_name, e.target_id, e.edge_type,
               e.resolution_state,
               s.name as source_name, s.file_path as source_file
        FROM edges e
        LEFT JOIN symbols s ON e.source_id = s.id
        WHERE e.target_id = ?
        ORDER BY e.edge_type, s.file_path
    """
    return conn.execute(query, (symbol_id,)).fetchall()


@retry_on_locked()
def get_symbol_edges(conn: sqlite3.Connection, symbol_id: str) -> list[sqlite3.Row]:
    """Get all edges originating from a symbol.

    Args:
        conn: SQLite connection
        symbol_id: Source symbol ID

    Returns:
        List of edges from this symbol
    """
    query = """
        SELECT id, source_id, target_name, target_id, edge_type, resolution_state
        FROM edges
        WHERE source_id = ?
        ORDER BY edge_type, target_name
    """
    return conn.execute(query, (symbol_id,)).fetchall()


# ──────────────────────────────────────────────────────────────────────────────
# Insert Operations (Batch-optimized)
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def insert_symbol(conn: sqlite3.Connection, symbol: Symbol) -> None:
    """Insert a single symbol into the database.

    Args:
        conn: SQLite connection
        symbol: Symbol dataclass instance

    Note:
        Uses INSERT OR REPLACE to handle re-indexing of files.
        FTS5 triggers automatically sync the virtual table.
    """
    query = """
        INSERT OR REPLACE INTO symbols
        (id, name, qualified_name, kind, file_path, start_line, end_line,
         signature, docstring, is_public, content_hash, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        symbol.id,
        symbol.name,
        symbol.qualified_name,
        symbol.kind.value if hasattr(symbol.kind, "value") else symbol.kind,
        symbol.file_path,
        symbol.start_line,
        symbol.end_line,
        symbol.signature,
        symbol.docstring,
        1 if symbol.is_public else 0,
        symbol.content_hash,
        int(datetime.now().timestamp()),
    )
    conn.execute(query, params)


@retry_on_locked()
def insert_symbols_batch(conn: sqlite3.Connection, symbols: list[Symbol]) -> int:
    """Insert multiple symbols in a single batch operation.

    Args:
        conn: SQLite connection
        symbols: List of Symbol dataclass instances

    Returns:
        Number of symbols inserted

    Note:
        Uses executemany() for 10x performance improvement over individual inserts.
        Wraps in transaction for atomicity.
    """
    if not symbols:
        return 0

    query = """
        INSERT OR REPLACE INTO symbols
        (id, name, qualified_name, kind, file_path, start_line, end_line,
         signature, docstring, is_public, content_hash, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params_list = [
        (
            sym.id,
            sym.name,
            sym.qualified_name,
            sym.kind.value if hasattr(sym.kind, "value") else sym.kind,
            sym.file_path,
            sym.start_line,
            sym.end_line,
            sym.signature,
            sym.docstring,
            1 if sym.is_public else 0,
            sym.content_hash,
            int(datetime.now().timestamp()),
        )
        for sym in symbols
    ]

    conn.executemany(query, params_list)
    return len(symbols)


@retry_on_locked()
def insert_edge(
    conn: sqlite3.Connection,
    source_id: str,
    target_name: str,
    edge_type: str,
    target_id: str | None = None,
    resolution_state: int = 0,
) -> None:
    """Insert a single edge (relationship between symbols).

    Args:
        conn: SQLite connection
        source_id: Source symbol ID
        target_name: Target symbol name (may be unresolved)
        edge_type: Type of edge (calls, imports, inherits, instantiates)
        target_id: Resolved target symbol ID (if known)
        resolution_state: 0=unresolved, 1=resolved, 2=stale
    """
    query = """
        INSERT OR REPLACE INTO edges
        (source_id, target_name, edge_type, target_id, resolution_state)
        VALUES (?, ?, ?, ?, ?)
    """
    params = (source_id, target_name, edge_type, target_id, resolution_state)
    conn.execute(query, params)


@retry_on_locked()
def insert_edges_batch(
    conn: sqlite3.Connection, edges: list[tuple[str, str, str, str | None, int]]
) -> int:
    """Insert multiple edges in a batch operation.

    Args:
        conn: SQLite connection
        edges: List of (source_id, target_name, edge_type, target_id, resolution_state)

    Returns:
        Number of edges inserted
    """
    if not edges:
        return 0

    query = """
        INSERT OR REPLACE INTO edges
        (source_id, target_name, edge_type, target_id, resolution_state)
        VALUES (?, ?, ?, ?, ?)
    """

    conn.executemany(query, edges)
    return len(edges)


# ──────────────────────────────────────────────────────────────────────────────
# Embedding Operations (Phase 2)
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def insert_symbol_embedding(conn: sqlite3.Connection, symbol_id: str, text: str) -> list[float]:
    """Generate and insert embedding for a symbol.

    Args:
        conn: SQLite connection
        symbol_id: Symbol ID
        text: Text to embed (signature + docstring)

    Returns:
        Generated embedding vector
    """
    embedding = generate_embedding(text)
    insert_embedding(conn, symbol_id, embedding)
    return embedding


@retry_on_locked()
def insert_symbol_embeddings_batch(conn: sqlite3.Connection, symbols: list[Symbol]) -> int:
    """Generate and insert embeddings for multiple symbols.

    Args:
        conn: SQLite connection
        symbols: List of Symbol dataclass instances with signature/docstring

    Returns:
        Number of embeddings inserted

    Note:
        Only inserts embeddings for symbols that have signature or docstring.
        Uses batch processing for efficiency.
    """
    if not symbols:
        return 0

    # Filter symbols with embeddable text
    symbol_texts = []
    for sym in symbols:
        text = f"{sym.signature or ''} {sym.docstring or ''}".strip()
        if text:
            symbol_texts.append((sym.id, text))

    if not symbol_texts:
        return 0

    # Generate embeddings
    texts = [t for _, t in symbol_texts]
    embeddings = generate_embeddings(texts)

    # Insert
    data = [(sid, emb) for (sid, _), emb in zip(symbol_texts, embeddings, strict=False)]
    insert_embeddings_batch(conn, data)

    return len(data)


@retry_on_locked()
def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    from ..embeddings import generate_batch_embeddings

    return generate_batch_embeddings(texts)


# ──────────────────────────────────────────────────────────────────────────────
# File Cache Operations
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def get_cached_hash(conn: sqlite3.Connection, file_path: str) -> str | None:
    """Get the cached content hash for a file.

    Args:
        conn: SQLite connection
        file_path: Path to the file

    Returns:
        Content hash if cached, None otherwise
    """
    query = "SELECT content_hash FROM file_cache WHERE file_path = ?"
    row = conn.execute(query, (file_path,)).fetchone()
    return row["content_hash"] if row else None


@retry_on_locked()
def update_file_cache(
    conn: sqlite3.Connection, file_path: str, content_hash: str, symbol_count: int = 0
) -> None:
    """Update the file cache after indexing.

    Args:
        conn: SQLite connection
        file_path: Path to the indexed file
        content_hash: SHA256 hash of file content
        symbol_count: Number of symbols extracted
    """
    query = """
        INSERT OR REPLACE INTO file_cache
        (file_path, content_hash, last_indexed, symbol_count)
        VALUES (?, ?, ?, ?)
    """
    params = (file_path, content_hash, int(datetime.now().timestamp()), symbol_count)
    conn.execute(query, params)


@retry_on_locked()
def get_file_cache(conn: sqlite3.Connection, file_path: str) -> sqlite3.Row | None:
    """Get full file cache entry.

    Args:
        conn: SQLite connection
        file_path: Path to the file

    Returns:
        File cache row or None
    """
    query = """
        SELECT file_path, content_hash, last_indexed, symbol_count
        FROM file_cache
        WHERE file_path = ?
    """
    return conn.execute(query, (file_path,)).fetchone()


# ──────────────────────────────────────────────────────────────────────────────
# Statistics
# ──────────────────────────────────────────────────────────────────────────────


@retry_on_locked()
def get_index_stats(conn: sqlite3.Connection) -> dict:
    """Get index statistics.

    Args:
        conn: SQLite connection

    Returns:
        Dict with indexed_files, total_symbols, total_edges, last_update
    """
    stats = {}

    # File count
    row = conn.execute("SELECT COUNT(*) as count FROM file_cache").fetchone()
    stats["indexed_files"] = row["count"]

    # Symbol count
    row = conn.execute("SELECT COUNT(*) as count FROM symbols").fetchone()
    stats["total_symbols"] = row["count"]

    # Edge count
    row = conn.execute("SELECT COUNT(*) as count FROM edges").fetchone()
    stats["total_edges"] = row["count"]

    # Last update
    row = conn.execute("SELECT MAX(last_indexed) as last FROM file_cache").fetchone()
    stats["last_update"] = row["last"]

    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Compatibility Aliases (for test compatibility)
# ──────────────────────────────────────────────────────────────────────────────


def insert_file_cache_entry(
    conn: sqlite3.Connection, file_path: str | None = None, file_hash: str | None = None, entry=None
) -> None:
    """Insert a file cache entry (alias for update_file_cache).

    Compatibility wrapper for tests that expect this function name.
    Can be called with either (conn, file_path, file_hash) or (conn, entry).
    """
    # Handle positional entry argument (common test pattern: insert_file_cache_entry(conn, entry))
    if (
        file_path is not None
        and file_hash is None
        and entry is None
        and hasattr(file_path, "file_path")
        and hasattr(file_path, "content_hash")
    ):
        # Check if file_path is actually a FileCache entry object
        entry = file_path
        file_path = None

    if entry is not None:
        # Called with entry object
        file_path = entry.file_path
        file_hash = entry.content_hash
    update_file_cache(conn, file_path, file_hash, 0)


def get_file_cache_entry(conn: sqlite3.Connection, file_path: str) -> sqlite3.Row | None:
    """Get a file cache entry (alias for get_file_cache)."""
    return get_file_cache(conn, file_path)


def update_file_cache_entry_hash(conn: sqlite3.Connection, file_path: str, new_hash: str) -> None:
    """Update the hash for a file cache entry."""
    update_file_cache(conn, file_path, new_hash, 0)


def delete_file_cache_entry(conn: sqlite3.Connection, file_path: str) -> None:
    """Delete a file cache entry."""
    conn.execute("DELETE FROM file_cache WHERE file_path = ?", (file_path,))
    conn.commit()


def search_symbols_fts(
    conn: sqlite3.Connection,
    query: str,
    project_id: str | None = None,  # Ignored for compatibility  # noqa: ARG001
) -> list[sqlite3.Row]:
    """Search symbols using FTS5 (alias for search_symbols)."""
    return search_symbols(conn, query, limit=50)


def get_symbols_in_file(
    conn: sqlite3.Connection,
    file_path: str,
    project_id: str | None = None,  # Ignored for compatibility  # noqa: ARG001
) -> list[sqlite3.Row]:
    """Get all symbols in a file (alias for list_symbols_by_file)."""
    return list_symbols_by_file(conn, file_path)


def count_symbols_by_kind(
    conn: sqlite3.Connection,
    kind: str | None = None,
    project_id: str | None = None,  # Ignored for compatibility  # noqa: ARG001
) -> list[sqlite3.Row]:
    """Get symbol counts grouped by kind (returns list of rows like original).

    If kind is None, returns all kinds with counts.
    """
    if kind is None:
        query = """
            SELECT kind, COUNT(*) as count
            FROM symbols
            GROUP BY kind
            ORDER BY count DESC
        """
        return conn.execute(query).fetchall()
    else:
        query = """
            SELECT kind, COUNT(*) as count
            FROM symbols
            WHERE kind = ?
            GROUP BY kind
        """
        return conn.execute(query, (kind.value if hasattr(kind, "value") else kind,)).fetchall()
