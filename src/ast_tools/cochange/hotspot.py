"""Hotspot detection — combines churn + coupling to find high-risk files."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def compute_hotspots(
    db_path: str | Path,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Find top-N files with highest (churn * coupling) score.

    Args:
        db_path: Path to the ast-tools SQLite database.
        top_n: Number of hotspots to return.

    Returns:
        List of dicts sorted by hotspot_score descending, each with:
            file_path, commit_count, lines_added, lines_deleted,
            instability, coupled_files, avg_coupling, hotspot_score
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        churn_rows = conn.execute(
            "SELECT * FROM churn_metrics ORDER BY instability DESC"
        ).fetchall()

        if not churn_rows:
            return []

        results = []
        for row in churn_rows:
            fp = row["file_path"]
            coupling_data = conn.execute(
                """SELECT AVG(coupling) as avg_coupling, COUNT(*) as coupled_files
                FROM co_change_pairs
                WHERE symbol1_id = ? OR symbol2_id = ?""",
                (fp, fp),
            ).fetchone()

            avg_coupling = (
                coupling_data["avg_coupling"]
                if coupling_data and coupling_data["avg_coupling"]
                else 0.0
            )
            coupled_files = coupling_data["coupled_files"] if coupling_data else 0
            instability = row["instability"]

            results.append(
                {
                    "file_path": fp,
                    "commit_count": row["commit_count"],
                    "lines_added": row["lines_added"],
                    "lines_deleted": row["lines_deleted"],
                    "instability": instability,
                    "coupled_files": coupled_files,
                    "avg_coupling": avg_coupling,
                    "hotspot_score": round(instability * avg_coupling, 4),
                }
            )

        results.sort(key=lambda x: -x["hotspot_score"])
        return results[:top_n]
    finally:
        conn.close()
