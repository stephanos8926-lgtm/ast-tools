"""MCP tool: Find a symbol definition by qualified name.

Usage:
    find_symbol_definition(qualified_name: str)

Example:
    find_symbol_definition("ast_tools.database.connection.get_connection")
"""

import logging
from typing import Any

from ..database import database_context
from ..database import find_symbol_definition as db_find_symbol
from ..database.connection import get_db_path

logger = logging.getLogger(__name__)


def _tool_find_symbol_definition(args: dict[str, Any]) -> dict[str, Any]:
    """Find a symbol definition by its qualified name.

    Args:
        qualified_name: Fully qualified symbol name (e.g., "module.Class.method")

    Returns:
        Dict with symbol details or error message
    """
    qualified_name = args.get("qualified_name", "")

    if not qualified_name:
        return {
            "error": "qualified_name is required",
            "error_code": "INVALID_INPUT",
            "tool": "find_symbol_definition",
        }

    try:
        db_path = get_db_path()

        if not db_path.exists():
            return {
                "error": "Index not initialized. Run refresh_index first.",
                "error_code": "INDEX_NOT_FOUND",
                "tool": "find_symbol_definition",
            }

        with database_context() as conn:
            result = db_find_symbol(conn, qualified_name)

            if result is None:
                return {
                    "error": f"Symbol not found: {qualified_name}",
                    "error_code": "NOT_FOUND",
                    "tool": "find_symbol_definition",
                }

            return {
                "qualified_name": qualified_name,
                "symbol": {
                    "id": result["id"],
                    "name": result["name"],
                    "qualified_name": result["qualified_name"],
                    "kind": result["kind"],
                    "file_path": result["file_path"],
                    "start_line": result["start_line"],
                    "end_line": result["end_line"],
                    "signature": result["signature"],
                    "docstring": result["docstring"][:500] + "..."
                    if result["docstring"] and len(result["docstring"]) > 500
                    else result["docstring"],
                    "is_public": bool(result["is_public"]),
                },
                "tool": "find_symbol_definition",
            }

    except Exception as e:
        logger.exception(f"Find failed: {e}")
        return {
            "error": f"Find failed: {e}",
            "error_code": "INTERNAL",
            "tool": "find_symbol_definition",
        }
