"""Co-change analysis MCP tools.

Provides co_change_predict, co_change_hotspots, co_change_history,
and co_change_diff tools wrapping GitMiner and hotspot detection.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _get_db_path(db_path: str | None = None) -> str:
    """Resolve database path."""
    if db_path:
        return db_path
    return str(Path.home() / ".cache" / "ast-tools" / "codebase.db")


def _ensure_tables(conn) -> None:
    """Ensure co-change tables exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS co_change_pairs (
            id INTEGER PRIMARY KEY,
            symbol1_id TEXT NOT NULL,
            symbol2_id TEXT NOT NULL,
            frequency INTEGER DEFAULT 0,
            avg_gap REAL DEFAULT 0.0,
            last_co_change INTEGER,
            coupling REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS churn_metrics (
            file_path TEXT PRIMARY KEY,
            commit_count INTEGER DEFAULT 0,
            lines_added INTEGER DEFAULT 0,
            lines_deleted INTEGER DEFAULT 0,
            authors_count INTEGER DEFAULT 0,
            last_modified INTEGER,
            instability REAL DEFAULT 0.0
        )
    """)


def _tool_co_change_predict(params: dict[str, Any]) -> dict[str, Any]:
    """Given a file or symbol, return files that tend to change with it.

    Args:
        symbol: Symbol name or file path to check
        top_n: Max results (default: 10)
        db_path: Override DB path

    Returns:
        dict with symbol, suggestions sorted by coupling descending
    """
    symbol = params.get("symbol", "")
    top_n = params.get("top_n", 10)
    db_path = _get_db_path(params.get("db_path"))

    if not symbol:
        raise ValueError("symbol is required")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)

    try:
        rows = conn.execute(
            """SELECT symbol1_id, symbol2_id, frequency, coupling, avg_gap
            FROM co_change_pairs
            WHERE symbol1_id = ? OR symbol2_id = ?
            ORDER BY coupling DESC
            LIMIT ?""",
            (symbol, symbol, top_n),
        ).fetchall()

        suggestions = []
        for r in rows:
            partner = r["symbol2_id"] if r["symbol1_id"] == symbol else r["symbol1_id"]
            suggestions.append({
                "partner": partner,
                "frequency": r["frequency"],
                "coupling": r["coupling"],
                "avg_gap_commits": r["avg_gap"],
            })

        return {
            "symbol": symbol,
            "suggestions": suggestions,
            "total_found": len(suggestions),
        }
    finally:
        conn.close()


def _tool_co_change_hotspots(params: dict[str, Any]) -> dict[str, Any]:
    """Find top-N riskiest files (highest churn x coupling).

    Args:
        top_n: Number of hotspots (default: 10)
        db_path: Override DB path

    Returns:
        dict with hotspots sorted by score descending
    """
    top_n = params.get("top_n", 10)
    db_path = _get_db_path(params.get("db_path"))

    try:
        from ast_tools.cochange.hotspot import compute_hotspots
        hotspots = compute_hotspots(db_path, top_n=top_n)
        return {"hotspots": hotspots, "total_found": len(hotspots)}
    except ImportError:
        return {"error": "hotspot module not available", "hotspots": [], "total_found": 0}


def _tool_co_change_history(params: dict[str, Any]) -> dict[str, Any]:
    """Get churn/change history for a specific file.

    Args:
        file_path: Path to the file
        db_path: Override DB path

    Returns:
        dict with file churn metrics
    """
    file_path = params.get("file_path", "")
    db_path = _get_db_path(params.get("db_path"))

    if not file_path:
        raise ValueError("file_path is required")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)

    try:
        row = conn.execute(
            "SELECT * FROM churn_metrics WHERE file_path = ?",
            (file_path,),
        ).fetchone()

        if not row:
            return {
                "file_path": file_path,
                "found": False,
                "message": f"No churn data for '{file_path}'. Run mine_pairs first.",
            }

        return {
            "file_path": file_path,
            "found": True,
            "commit_count": row["commit_count"],
            "lines_added": row["lines_added"],
            "lines_deleted": row["lines_deleted"],
            "authors_count": row["authors_count"],
            "last_modified": row["last_modified"],
            "instability": row["instability"],
        }
    finally:
        conn.close()


def _tool_co_change_diff(params: dict[str, Any]) -> dict[str, Any]:
    """Identify symbols at risk when changing this symbol.

    Uses coupling data to warn about what else would need updating.

    Args:
        symbol: The symbol being changed
        db_path: Override DB path

    Returns:
        dict with at_risk symbols
    """
    predict_result = _tool_co_change_predict(params)
    if "error" in predict_result:
        return predict_result

    return {
        "changing": params.get("symbol", ""),
        "at_risk": predict_result.get("suggestions", []),
        "risk_count": len(predict_result.get("suggestions", [])),
    }


# Public aliases for MCP registration
def co_change_predict(args: dict[str, Any]) -> dict[str, Any]:
    return _tool_co_change_predict(args)


def co_change_hotspots(args: dict[str, Any]) -> dict[str, Any]:
    return _tool_co_change_hotspots(args)


def co_change_history(args: dict[str, Any]) -> dict[str, Any]:
    return _tool_co_change_history(args)


def co_change_diff(args: dict[str, Any]) -> dict[str, Any]:
    return _tool_co_change_diff(args)
