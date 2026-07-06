"""Metrics store for codebase statistics (time-series).

Stores per-codebase metric snapshots in a local SQLite database.
Only active in daemon mode.

Schema:
    CREATE TABLE codebase_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codebase_id TEXT NOT NULL,
        ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        files INTEGER,
        loc INTEGER,
        functions INTEGER,
        classes INTEGER,
        deps INTEGER,
        size_bytes INTEGER,
        commits_since_last INTEGER,
        new_files INTEGER,
        deleted_files INTEGER,
        inserted_lines INTEGER,
        deleted_lines INTEGER
    );
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class MetricsStore:
    """Time-series metrics store for codebase statistics.

    Stores periodic snapshots of codebase health, size, and
    change velocity metrics. Queryable by codebase_id.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".cache" / "rw-ast-tools" / "metrics.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the metrics schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS codebase_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codebase_id TEXT NOT NULL,
                    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    files INTEGER DEFAULT 0,
                    loc INTEGER DEFAULT 0,
                    functions INTEGER DEFAULT 0,
                    classes INTEGER DEFAULT 0,
                    deps INTEGER DEFAULT 0,
                    size_bytes INTEGER DEFAULT 0,
                    commits_since_last INTEGER DEFAULT 0,
                    new_files INTEGER DEFAULT 0,
                    deleted_files INTEGER DEFAULT 0,
                    inserted_lines INTEGER DEFAULT 0,
                    deleted_lines INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_cb_ts
                ON codebase_snapshots(codebase_id, ts)
            """)
            conn.commit()

    def record_snapshot(self, codebase_id: str, metrics: dict[str, Any]) -> int:
        """Record a metric snapshot for a codebase.

        Args:
            codebase_id: Unique identifier for the codebase.
            metrics: Dict with keys matching the schema columns.

        Returns:
            Row id of the inserted record.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                INSERT INTO codebase_snapshots
                    (codebase_id, files, loc, functions, classes, deps,
                     size_bytes, commits_since_last, new_files,
                     deleted_files, inserted_lines, deleted_lines)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codebase_id,
                    metrics.get("files", 0),
                    metrics.get("loc", 0),
                    metrics.get("functions", 0),
                    metrics.get("classes", 0),
                    metrics.get("deps", 0),
                    metrics.get("size_bytes", 0),
                    metrics.get("commits_since_last", 0),
                    metrics.get("new_files", 0),
                    metrics.get("deleted_files", 0),
                    metrics.get("inserted_lines", 0),
                    metrics.get("deleted_lines", 0),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_latest(self, codebase_id: str) -> dict[str, Any] | None:
        """Get the most recent snapshot for a codebase."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM codebase_snapshots WHERE codebase_id = ? ORDER BY ts DESC LIMIT 1",
                (codebase_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_history(self, codebase_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent snapshots for a codebase, newest first."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM codebase_snapshots WHERE codebase_id = ? ORDER BY ts DESC LIMIT ?",
                (codebase_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_delta(self, codebase_id: str) -> dict[str, Any] | None:
        """Get the difference between the two most recent snapshots.

        Returns None if fewer than 2 snapshots exist.
        """
        history = self.get_history(codebase_id, limit=2)
        if len(history) < 2:
            return None

        latest = history[0]
        prev = history[1]
        delta_keys = [
            "files", "loc", "functions", "classes", "deps",
            "size_bytes", "commits_since_last",
        ]
        return {
            k: (latest.get(k, 0) - prev.get(k, 0))
            for k in delta_keys
        }
