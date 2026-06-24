"""MCP tool: hybrid semantic + keyword search."""

import json
import logging
from typing import Optional
from pathlib import Path

from src.ast_tools.database.connection import get_connection
from src.ast_tools.embeddings import generate_embedding, search_similar

logger = logging.getLogger(__name__)

RRF_K = 1.5  # Reciprocal Rank Fusion constant


def hybrid_search(
    conn,
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None
) -> list[dict]:
    """
    Hybrid search: FTS5 keyword + vector semantic with RRF fusion.

    Args:
        conn: SQLite connection
        query: Search query text
        k: Number of results to return
        kind: Optional symbol kind filter (function, class, method, etc.)
        lang: Optional language filter (python, rust, go, typescript, etc.)

    Returns:
        List of symbol dicts ordered by fused relevance score
    """
    # 1. Generate query embedding
    query_emb = generate_embedding(query)

    # 2. Vector similarity search (returns 2k for fusion)
    vec_results = search_similar(conn, query_emb, k=k * 2)

    # 3. FTS5 keyword search with JOIN to get symbol_id
    fts_sql = """
        SELECT s.id as symbol_id, bm25(symbols_fts) as score
        FROM symbols_fts
        JOIN symbols s ON s.rowid = symbols_fts.rowid
        WHERE symbols_fts MATCH ?
    """
    params = [query]
    if kind:
        fts_sql += " AND s.kind = ?"
        params.append(kind)
    if lang:
        fts_sql += " AND s.lang = ?"
        params.append(lang)
    fts_sql += " LIMIT ?"
    params.append(k * 2)

    fts_rows = conn.execute(fts_sql, params).fetchall()
    fts_results = [(row['symbol_id'], row['score']) for row in fts_rows]

    # 4. Reciprocal Rank Fusion
    fused_scores = {}

    # Vector results: rank by distance (lower = better)
    for i, (symbol_id, _) in enumerate(vec_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)

    # FTS5 results: rank by BM25 score (lower = better)
    for i, (symbol_id, score) in enumerate(fts_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)

    # 5. Sort by fused score (higher = better)
    top_k = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:k]

    # 6. Fetch full symbol details
    symbols = []
    if top_k:
        placeholders = ",".join("?" for _ in top_k)
        symbol_ids = [sid for sid, _ in top_k]
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE id IN ({placeholders})",
            symbol_ids
        ).fetchall()

        # Preserve fused ranking order
        row_map = {row['id']: dict(row) for row in rows}
        for symbol_id, _ in top_k:
            if symbol_id in row_map:
                symbols.append(row_map[symbol_id])

    return symbols


async def _tool_semantic_search(
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None,
    db_path: Optional[str] = None
) -> str:
    """
    Search symbols by semantic similarity (meaning) + keyword matching.

    Args:
        query: Search query - finds code by meaning, not just keywords
               e.g., "authentication handler", "database connection pool", "error retry logic"
        k: Number of results to return (default: 10, max: 50)
        kind: Optional symbol kind filter: function, class, method, variable, import, constant
        lang: Optional language filter: python, rust, go, typescript, javascript, cpp, c, json, yaml, bash
        db_path: Optional custom database path

    Returns:
        JSON array of symbol objects with fields:
        - id, name, qualified_name, kind, file_path, start_line, end_line
        - signature, docstring, is_public, content_hash, indexed_at, lang
    """
    # Validate k
    if k < 1:
        k = 1
    elif k > 50:
        k = 50

    try:
        conn = get_connection(Path(db_path) if db_path else None)
        results = hybrid_search(conn, query, k, kind, lang)
        conn.close()
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return json.dumps({"error": str(e)}, indent=2)


# Export for MCP server registration
semantic_search_tool = {
    "name": "semantic_search",
    "description": "Search symbols by semantic similarity (meaning) + keyword matching. Finds code by what it does, not just by name.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - finds code by meaning, e.g. 'authentication handler', 'database pool', 'error retry'"
            },
            "k": {
                "type": "integer",
                "description": "Number of results (default: 10, max: 50)",
                "default": 10,
                "minimum": 1,
                "maximum": 50
            },
            "kind": {
                "type": "string",
                "description": "Optional symbol kind filter",
                "enum": ["function", "class", "method", "variable", "import", "constant"]
            },
            "lang": {
                "type": "string",
                "description": "Optional language filter",
                "enum": ["python", "rust", "go", "typescript", "javascript", "cpp", "c", "json", "yaml", "bash"]
            },
            "db_path": {
                "type": "string",
                "description": "Optional custom database path"
            }
        },
        "required": ["query"]
    },
    "handler": _tool_semantic_search
}