"""MCP tool: List symbols in a file.

Usage:
    list_symbols(file_path: str)

Example:
    list_symbols("src/ast_tools/database/connection.py")
"""

import logging
from typing import Any

from ..database import database_context, list_symbols_by_file
from ..database.connection import get_db_path

logger = logging.getLogger(__name__)


def _tool_list_symbols(args: dict[str, Any]) -> dict[str, Any]:
    """List all symbols in a specific file.

    Args:
        file_path: Path to the source file

    Returns:
        Dict with list of symbols or error message
    """
    file_path = args.get("file_path", "")

    if not file_path:
        return {
            "error": "file_path is required",
            "error_code": "INVALID_INPUT",
            "tool": "list_symbols",
        }

    try:
        db_path = get_db_path()

        if not db_path.exists():
            return {
                "error": "Index not initialized. Run refresh_index first.",
                "error_code": "INDEX_NOT_FOUND",
                "tool": "list_symbols",
                "symbols": [],
            }

        with database_context() as conn:
            results = list_symbols_by_file(conn, file_path)

            return {
                "file_path": file_path,
                "symbols": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "qualified_name": row["qualified_name"],
                        "kind": row["kind"],
                        "start_line": row["start_line"],
                        "end_line": row["end_line"],
                        "signature": row["signature"],
                        "is_public": bool(row["is_public"]),
                    }
                    for row in results
                ],
                "count": len(results),
                "tool": "list_symbols",
            }

    except Exception as e:
        logger.exception(f"List failed: {e}")
        return {
            "error": f"List failed: {e}",
            "error_code": "INTERNAL",
            "tool": "list_symbols",
            "symbols": [],
        }
