"""MCP tool: Get index statistics.

Usage:
    index_status()

Returns:
    Statistics about the indexed codebase (files, symbols, edges, last update)
"""

import logging
from typing import Any

from ..database import count_symbols_by_kind, database_context, get_index_stats
from ..database.connection import get_db_path

logger = logging.getLogger(__name__)


def _tool_index_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get statistics about the semantic index.

    Returns:
        Dict with indexed_files, total_symbols, total_edges, last_update, symbols_by_kind
    """
    try:
        db_path = get_db_path()

        if not db_path.exists():
            return {
                "error": "Index not initialized. Run refresh_index first.",
                "error_code": "INDEX_NOT_FOUND",
                "tool": "index_status",
                "indexed_files": 0,
                "total_symbols": 0,
                "total_edges": 0,
                "last_update": None,
                "symbols_by_kind": [],
            }

        with database_context() as conn:
            stats = get_index_stats(conn)
            kind_counts = count_symbols_by_kind(conn)

            return {
                "indexed_files": stats["indexed_files"],
                "total_symbols": stats["total_symbols"],
                "total_edges": stats["total_edges"],
                "last_update": stats["last_update"],
                "symbols_by_kind": [
                    {"kind": row["kind"], "count": row["count"]} for row in kind_counts
                ],
                "cache_path": str(db_path.parent),
                "tool": "index_status",
            }

    except Exception as e:
        logger.exception(f"Status check failed: {e}")
        return {
            "error": f"Status check failed: {e}",
            "error_code": "INTERNAL",
            "tool": "index_status",
            "indexed_files": 0,
            "total_symbols": 0,
            "total_edges": 0,
            "last_update": None,
            "symbols_by_kind": [],
        }
