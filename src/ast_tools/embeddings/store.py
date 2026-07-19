"""sqlite-vec integration for vector storage and similarity search.

Provides efficient vector operations using sqlite-vec C extension.
Pure SQLite - no external database required.
"""

import logging
import sqlite3
import struct

from ast_tools.config.unified import RUNTIME

logger = logging.getLogger(__name__)

# Vector configuration — sourced from RUNTIME
EMBEDDING_DIM = RUNTIME.embedding_dim


def _floats_to_bytes(floats: list[float]) -> bytes:
    """Convert list of floats to bytes (little-endian IEEE 754)."""
    return struct.pack(f"<{len(floats)}f", *floats)


def _bytes_to_floats(data: bytes) -> list[float]:
    """Convert bytes to list of floats."""
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension into SQLite connection.

    Must be called after connection creation, before any vector operations.

    Args:
        conn: SQLite connection (WAL mode recommended)

    Raises:
        ImportError: If sqlite-vec is not installed
        sqlite3.OperationalError: If extension loading fails

    Note:
        - Enables load_extension temporarily (security safe)
        - Idempotent - safe to call multiple times
        - Works with WAL mode
    """
    try:
        import sqlite_vec
    except ImportError:
        raise ImportError("sqlite-vec not installed. Install with: pip install sqlite-vec")

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    logger.debug("sqlite-vec extension loaded")


def insert_embedding(conn: sqlite3.Connection, symbol_id: str, embedding: list[float]) -> None:
    """Insert or update embedding for a single symbol.

    Args:
        conn: SQLite connection (with sqlite-vec loaded)
        symbol_id: Symbol ID (must exist in symbols table)
        embedding: 384-dimensional embedding vector

    Raises:
        ValueError: If embedding dimension != 384
        sqlite3.Error: If insert fails

    Note:
        - Uses INSERT OR REPLACE for idempotency
        - Commits transaction automatically
        - Vector stored as BLOB (bytes) in sqlite-vec format
    """
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(embedding)}"
        )

    # Convert to bytes (sqlite-vec expects BLOB in IEEE 754 little-endian format)
    embedding_bytes = _floats_to_bytes(embedding)

    # sqlite-vec vec0 tables don't support INSERT OR REPLACE, so delete first
    conn.execute("DELETE FROM symbols_vec WHERE symbol_id = ?", (symbol_id,))
    conn.execute(
        "INSERT INTO symbols_vec (symbol_id, embedding) VALUES (?, ?)", (symbol_id, embedding_bytes)
    )
    conn.commit()


def insert_embeddings_batch(
    conn: sqlite3.Connection, symbol_embeddings: list[tuple[str, list[float]]]
) -> None:
    """Batch insert embeddings for multiple symbols.

    Args:
        conn: SQLite connection (with sqlite-vec loaded)
        symbol_embeddings: List of (symbol_id, embedding) tuples

    Raises:
        ValueError: If any embedding has wrong dimension
        sqlite3.Error: If batch insert fails

    Note:
        - Uses executemany for efficiency (10-100x faster than individual inserts)
        - Commits single transaction for all inserts
        - Automatically validates all dimensions before insert
    """
    if not symbol_embeddings:
        return

    # Validate all embeddings first
    for symbol_id, embedding in symbol_embeddings:
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension mismatch for {symbol_id}: "
                f"expected {EMBEDDING_DIM}, got {len(embedding)}"
            )

    # sqlite-vec vec0 tables don't support INSERT OR REPLACE
    # Delete existing embeddings first, then insert
    symbol_ids = [sid for sid, _ in symbol_embeddings]
    placeholders = ",".join("?" for _ in symbol_ids)
    conn.execute(f"DELETE FROM symbols_vec WHERE symbol_id IN ({placeholders})", symbol_ids)

    # Convert to bytes and insert
    data = [(sid, _floats_to_bytes(emb)) for sid, emb in symbol_embeddings]

    conn.executemany("INSERT INTO symbols_vec (symbol_id, embedding) VALUES (?, ?)", data)
    conn.commit()


def search_similar(
    conn: sqlite3.Connection, query_embedding: list[float], k: int = 10
) -> list[tuple[str, float]]:
    """Find most similar symbols by cosine similarity.

    Args:
        conn: SQLite connection (with sqlite-vec loaded)
        query_embedding: 384-dimensional query embedding
        k: Number of results to return (default: 10)

    Returns:
        List of (symbol_id, distance) tuples, ordered by distance (closest first)

    Note:
        - Distance = 1 - cosine_similarity (0 = identical, 2 = opposite)
        - Uses sqlite-vec MATCH operator for efficient KNN search
        - Typical latency: <5ms for 10K symbols
    """
    if len(query_embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Query embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(query_embedding)}"
        )

    query_bytes = _floats_to_bytes(query_embedding)

    rows = conn.execute(
        """
        SELECT symbol_id, distance
        FROM symbols_vec
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
    """,
        (query_bytes, k),
    ).fetchall()

    return [(row[0], row[1]) for row in rows]


def get_embedding_count(conn: sqlite3.Connection) -> int:
    """Get total number of symbols with embeddings.

    Args:
        conn: SQLite connection

    Returns:
        Count of rows in symbols_vec table
    """
    row = conn.execute("SELECT COUNT(*) as count FROM symbols_vec").fetchone()
    return row[0] if row else 0


def get_symbols_without_embeddings(conn: sqlite3.Connection, limit: int = 1000) -> list[str]:
    """Get symbol IDs that don't have embeddings yet.

    Useful for incremental backfill operations.

    Args:
        conn: SQLite connection
        limit: Maximum number of IDs to return

    Returns:
        List of symbol IDs without embeddings
    """
    rows = conn.execute(
        """
        SELECT s.id FROM symbols s
        LEFT JOIN symbols_vec v ON s.id = v.symbol_id
        WHERE v.symbol_id IS NULL
        LIMIT ?
    """,
        (limit,),
    ).fetchall()

    return [row[0] for row in rows]


def delete_embedding(conn: sqlite3.Connection, symbol_id: str) -> None:
    """Delete embedding for a symbol.

    Args:
        conn: SQLite connection
        symbol_id: Symbol ID to remove
    """
    conn.execute("DELETE FROM symbols_vec WHERE symbol_id = ?", (symbol_id,))
    conn.commit()


def delete_embeddings_for_file(conn: sqlite3.Connection, file_path: str) -> int:
    """Delete all embeddings for symbols in a file.

    Called when file is re-indexed (content hash changed).

    Args:
        conn: SQLite connection
        file_path: Path of file being re-indexed

    Returns:
        Number of embeddings deleted
    """
    cursor = conn.execute(
        """
        DELETE FROM symbols_vec
        WHERE symbol_id IN (
            SELECT id FROM symbols WHERE file_path = ?
        )
    """,
        (file_path,),
    )
    conn.commit()
    return cursor.rowcount
