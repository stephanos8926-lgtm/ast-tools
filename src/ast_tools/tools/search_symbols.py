"""MCP tool: Search symbols in the indexed codebase.

Usage:
    search_symbols(query: str, kind_filter: list[str] | None = None, limit: int = 50)

Example:
    search_symbols("database connection", kind_filter=["function", "class"])
    search_symbols("get_*", limit=20)
"""

import logging
from typing import Any

from ..database import database_context
from ..database import search_symbols as db_search_symbols
from ..database.connection import get_db_path

logger = logging.getLogger(__name__)


def _tool_search_symbols(args: dict[str, Any]) -> dict[str, Any]:
    """Search indexed symbols using full-text search (FTS5).

    Args:
        query: Search query (FTS5 syntax: keywords, phrases, OR/AND/NOT)
        kind_filter: Optional list of symbol kinds to filter
        limit: Maximum results to return (default: 50)

    Returns:
        Dict with results list and optional error message
    """
    query = args.get("query", "")
    kind_filter = args.get("kind_filter")
    limit = int(args.get("limit", 50))

    if not query:
        return {
            "error": "query is required",
            "error_code": "INVALID_INPUT",
            "tool": "search_symbols",
        }

    try:
        db_path = get_db_path()

        if not db_path.exists():
            return {
                "error": "Index not initialized. Run refresh_index first.",
                "error_code": "INDEX_NOT_FOUND",
                "tool": "search_symbols",
                "results": [],
            }

        with database_context() as conn:
            results = db_search_symbols(conn, query, kind_filter, limit)

            return {
                "query": query,
                "kind_filter": kind_filter,
                "limit": limit,
                "results": [
                    {
                        "name": row["name"],
                        "qualified_name": row["qualified_name"],
                        "kind": row["kind"],
                        "file_path": row["file_path"],
                        "start_line": row["start_line"],
                        "end_line": row["end_line"],
                        "signature": row["signature"],
                        "docstring": row["docstring"][:200] + "..."
                        if row["docstring"] and len(row["docstring"]) > 200
                        else row["docstring"],
                    }
                    for row in results
                ],
                "count": len(results),
                "tool": "search_symbols",
            }

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        return {
            "error": f"Search failed: {e}",
            "error_code": "INTERNAL",
            "tool": "search_symbols",
            "results": [],
        }
