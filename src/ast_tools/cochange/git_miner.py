"""GitMiner — parse git log to extract co-change pairs and churn metrics.

Extracts file-level co-change pairs from git history using `git log --numstat`.
Stores results in the existing ast-tools schema v5 database.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from ast_tools.config.unified import RUNTIME

logger = logging.getLogger("ast-tools.cochange.git_miner")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS co_change_pairs (
    id INTEGER PRIMARY KEY,
    symbol1_id TEXT NOT NULL,
    symbol2_id TEXT NOT NULL,
    frequency INTEGER DEFAULT 0,
    avg_gap REAL DEFAULT 0.0,
    last_co_change INTEGER,
    coupling REAL DEFAULT 0.0,
    FOREIGN KEY (symbol1_id) REFERENCES symbols(id) ON DELETE CASCADE,
    FOREIGN KEY (symbol2_id) REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS churn_metrics (
    file_path TEXT PRIMARY KEY,
    commit_count INTEGER DEFAULT 0,
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    authors_count INTEGER DEFAULT 0,
    last_modified INTEGER,
    instability REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_co_change_pairs_s1 ON co_change_pairs(symbol1_id);
CREATE INDEX IF NOT EXISTS idx_co_change_pairs_s2 ON co_change_pairs(symbol2_id);
CREATE INDEX IF NOT EXISTS idx_co_change_pairs_coupling ON co_change_pairs(coupling DESC);
CREATE INDEX IF NOT EXISTS idx_churn_commits ON churn_metrics(commit_count DESC);
"""


class GitMiner:
    """Parse git history and extract co-change pairs + churn metrics."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    def _run_git_log(self, max_commits: int = 5000) -> str:
        """Run git log --numstat and return raw output."""
        cmd = [
            "git",
            "log",
            f"--max-count={max_commits}",
            "--numstat",
            "--format=%H%x1e%at%x1e%s%x1e%ae",
            "--no-merges",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.repo_path),
                timeout=RUNTIME.timeout_git_log,
            )
            if result.returncode != 0:
                logger.warning("git log returned %d: %s", result.returncode, result.stderr[:200])
                return ""
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.warning(f"git log timed out after {RUNTIME.timeout_git_log}s")
            return ""
        except FileNotFoundError:
            logger.warning("git not found — cannot mine co-change data")
            return ""
        except Exception as e:
            logger.warning("git log failed: %s", e)
            return ""

    def mine(self, max_commits: int = 5000) -> dict[str, Any]:
        """Parse git log and return co-change pairs + file metrics.

        Returns:
            dict with:
                - pairs: (file_a, file_b) -> {frequency, timestamps, coupling}
                - files: file_path -> {commit_count, lines_added, lines_deleted, authors, last_modified}
                - commits_processed: int
        """
        raw = self._run_git_log(max_commits)
        if not raw:
            return {"pairs": {}, "files": {}, "commits_processed": 0}

        # Parse records separated by \x1e
        file_changes: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "commits": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "authors": set(),
                "timestamps": [],
            }
        )
        co_change_counts: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"frequency": 0, "timestamps": []}
        )

        lines = raw.split("\n")
        i = 0
        commits_processed = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Check if this is a commit header (starts with a 40-char hex hash)
            if len(line) >= 40 and all(c in "0123456789abcdef" for c in line[:40]):
                # Parse commit header
                parts = line.split("\x1e")
                if len(parts) < 4:
                    i += 1
                    continue
                parts[0]
                try:
                    timestamp = int(parts[1])
                except ValueError:
                    timestamp = int(time.time())
                author_email = parts[3]
                commits_processed += 1
                i += 1

                # Collect files changed in this commit
                commit_files: list[str] = []
                while i < len(lines):
                    nl = lines[i].strip()
                    if not nl:
                        i += 1
                        continue  # skip blank lines between header and numstat
                    # If next line starts a new commit, stop
                    if len(nl) >= 40 and all(c in "0123456789abcdef" for c in nl[:40]):
                        break

                    # Parse numstat: added_tabs, deleted_tabs, filepath
                    parts = nl.split("\t", 2)
                    if len(parts) != 3:
                        i += 1
                        continue

                    added_str, deleted_str, filepath = parts
                    # Skip binary files (added = deleted = "-")
                    if added_str == "-" and deleted_str == "-":
                        i += 1
                        continue

                    try:
                        added = int(added_str) if added_str != "-" else 0
                        deleted = int(deleted_str) if deleted_str != "-" else 0
                    except ValueError:
                        i += 1
                        continue

                    # Only track .py files for co-change (configurable later)
                    if filepath.endswith(".py"):
                        commit_files.append(filepath)

                    fc = file_changes[filepath]
                    fc["commits"] += 1
                    fc["lines_added"] += added
                    fc["lines_deleted"] += deleted
                    fc["authors"].add(author_email)
                    fc["timestamps"].append(timestamp)

                    i += 1

                # Build co-change pairs within this commit
                commit_files = list(set(commit_files))
                for j in range(len(commit_files)):
                    for k in range(j + 1, len(commit_files)):
                        f1, f2 = sorted([commit_files[j], commit_files[k]])
                        pair_key = (f1, f2)
                        cp = co_change_counts[pair_key]
                        cp["frequency"] += 1
                        cp["timestamps"].append(timestamp)
            else:
                i += 1

        # Compute coupling scores
        pairs_output: dict[str, dict[str, Any]] = {}
        for (f1, f2), data in co_change_counts.items():
            fc1 = file_changes[f1]["commits"]
            fc2 = file_changes[f2]["commits"]
            coupling = data["frequency"] / min(fc1, fc2) if fc1 > 0 and fc2 > 0 else 0.0
            timestamps = sorted(data["timestamps"])
            gaps = []
            for t in range(1, len(timestamps)):
                gaps.append(timestamps[t] - timestamps[t - 1])
            avg_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
            pairs_output[f"{f1}:::{f2}"] = {
                "file1": f1,
                "file2": f2,
                "frequency": data["frequency"],
                "coupling": round(coupling, 4),
                "avg_gap": round(avg_gap, 2),
                "last_co_change": timestamps[-1] if timestamps else 0,
            }

        files_output: dict[str, dict[str, Any]] = {}
        for fpath, fc in file_changes.items():
            timestamps = sorted(fc["timestamps"])
            total = fc["lines_added"] + fc["lines_deleted"]
            instability = round(fc["lines_deleted"] / total, 4) if total > 0 else 0.0
            files_output[fpath] = {
                "file_path": fpath,
                "commit_count": fc["commits"],
                "lines_added": fc["lines_added"],
                "lines_deleted": fc["lines_deleted"],
                "authors_count": len(fc["authors"]),
                "last_modified": timestamps[-1] if timestamps else 0,
                "instability": instability,
            }

        return {
            "pairs": pairs_output,
            "files": files_output,
            "commits_processed": commits_processed,
        }

    def _resolve_file_to_symbols(self, file_path: str, conn) -> list[str]:
        """Resolve a file path to symbol IDs in the database."""
        import sqlite3

        try:
            rows = conn.execute(
                "SELECT id FROM symbols WHERE file_path = ? OR file_path LIKE ?",
                (file_path, f"%/{file_path}"),
            ).fetchall()
            return [r[0] for r in rows]
        except sqlite3.OperationalError:
            return []

    def mine_pairs(self, db_path: str | Path) -> int:
        """Mine git history and store co-change pairs + churn metrics to DB.

        Args:
            db_path: Path to the ast-tools SQLite database.

        Returns:
            Number of co-change pairs stored.
        """
        import sqlite3

        result = self.mine()
        if result["commits_processed"] == 0:
            logger.info("No commits to mine")
            return 0

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)

        stored = 0
        try:
            # Store co-change pairs (resolve file paths to symbol IDs)
            for _pair_key, data in result["pairs"].items():
                symbols1 = self._resolve_file_to_symbols(data["file1"], conn)
                symbols2 = self._resolve_file_to_symbols(data["file2"], conn)

                if not symbols1 or not symbols2:
                    continue

                # Store pair for each symbol combination
                for s1 in symbols1:
                    for s2 in symbols2:
                        if s1 == s2:
                            continue
                        s1_id, s2_id = sorted([s1, s2])
                        conn.execute(
                            """INSERT OR REPLACE INTO co_change_pairs
                            (symbol1_id, symbol2_id, frequency, avg_gap, last_co_change, coupling)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                s1_id,
                                s2_id,
                                data["frequency"],
                                data["avg_gap"],
                                data["last_co_change"],
                                data["coupling"],
                            ),
                        )
                        stored += 1

            # Store churn metrics
            for fpath, fc in result["files"].items():
                conn.execute(
                    """INSERT OR REPLACE INTO churn_metrics
                    (file_path, commit_count, lines_added, lines_deleted, authors_count, last_modified, instability)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fpath,
                        fc["commit_count"],
                        fc["lines_added"],
                        fc["lines_deleted"],
                        fc["authors_count"],
                        fc["last_modified"],
                        fc["instability"],
                    ),
                )

            conn.commit()
            logger.info(
                "Stored %d co-change pairs and %d file churn metrics from %d commits",
                stored,
                len(result["files"]),
                result["commits_processed"],
            )
        finally:
            conn.close()

        return stored
