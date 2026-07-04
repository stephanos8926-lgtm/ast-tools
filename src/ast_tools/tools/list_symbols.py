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
    """List symbols — either in a specific file or all symbols in the project.

    Args:
        file_path: Path to the source file (None/empty for all symbols)
        project_root: Project root for context (optional)
        kind: Filter by symbol kind (optional)
        lang: Filter by language (optional)
        limit: Max results (default 50)

    Returns:
        Dict with list of symbols or error message
    """
    file_path = args.get("file_path", "")
    kind = args.get("kind")
    lang = args.get("lang")
    limit = args.get("limit", 50)
    project_root = args.get("project_root")

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
            if file_path:
                results = list_symbols_by_file(conn, file_path)
            else:
                # List all symbols with optional filters
                query = """
                    SELECT id, name, qualified_name, kind, file_path as file_path,
                           start_line, end_line, signature, is_public, lang
                    FROM symbols
                    WHERE 1=1
                """
                params = []
                if kind:
                    query += " AND kind = ?"
                    params.append(kind)
                if lang:
                    query += " AND lang = ?"
                    params.append(lang)
                query += " ORDER BY file_path, start_line"
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                results = conn.execute(query, params).fetchall()

            return {
                "project_root": project_root or ".",
                "symbols": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "qualified_name": row["qualified_name"],
                        "kind": row["kind"],
                        "file": row["file_path"] if "file_path" in row.keys() else file_path,
                        "line": row["start_line"],
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
