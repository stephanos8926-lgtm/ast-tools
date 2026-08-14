"""Tests for database connection concurrency and lock-retry behavior.

Validates that write-heavy paths (file reindexing) survive concurrent
access without raising "database is locked" — the classic failure mode
when the watchdog reindexes while a search or another write is active.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from typing import TYPE_CHECKING

import pytest

from ast_tools.database.connection import (
    get_connection,
    retry_on_locked,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path: Path):
    """Create an isolated WAL-mode database for concurrency tests."""
    db = tmp_path / "concurrency.db"
    conn = get_connection(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)"
    )
    conn.commit()
    conn.close()
    return db


class TestRetryOnLocked:
    """retry_on_locked retries on lock errors with backoff."""

    def test_retries_on_locked_error(self):
        """A function raising 'database is locked' retries and succeeds."""

        calls = {"n": 0}

        @retry_on_locked(max_attempts=3, initial_delay=0.01)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert flaky() == "ok"
        assert calls["n"] == 3

    def test_gives_up_after_max_attempts(self):
        """Persistent lock errors raise after retries are exhausted."""

        @retry_on_locked(max_attempts=3, initial_delay=0.01)
        def always_locked():
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError, match="locked after"):
            always_locked()

    def test_non_lock_errors_raise_immediately(self):
        """Non-lock SQLite errors propagate without retrying."""

        @retry_on_locked(max_attempts=3, initial_delay=0.01)
        def other_error():
            raise sqlite3.OperationalError("no such table: xyz")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            other_error()


class TestAtomicReindexTransaction:
    """The reindex DELETE+INSERT must be atomic (single transaction)."""

    def test_database_context_commits_atomic_write(self, tmp_db):
        """A multi-statement write inside `with conn:` commits atomically.

        If a lock/timeout interrupts between DELETE and INSERT, the partial
        state must not persist. This exercises the wrapper used by reindex.
        """
        from ast_tools.database.connection import database_context

        with database_context(tmp_db) as conn:
            conn.execute("DELETE FROM items")
            conn.execute("INSERT INTO items (name) VALUES ('a')")
            conn.execute("INSERT INTO items (name) VALUES ('b')")

        with get_connection(tmp_db) as conn:
            rows = conn.execute("SELECT name FROM items ORDER BY id").fetchall()
            assert [r["name"] for r in rows] == ["a", "b"]


class TestConcurrentWriteSurvival:
    """Write-heavy reindex must survive concurrent access without locking up."""

    def test_concurrent_writer_retries_and_completes(self, tmp_db):
        """A dedicated reindex writer using retry completes despite a reader lock."""
        results: dict[str, object] = {}
        barrier = threading.Barrier(2)

        def writer():
            # Simulate the watchdog reindex write path.
            @retry_on_locked(max_attempts=5, initial_delay=0.02)
            def _write():
                conn = get_connection(tmp_db)
                try:
                    # Hold a write transaction briefly to provoke contention.
                    conn.execute("BEGIN IMMEDIATE")
                    time.sleep(0.05)
                    conn.execute("DELETE FROM items")
                    conn.execute("INSERT INTO items (name) VALUES ('w1')")
                    conn.commit()
                finally:
                    conn.close()

            barrier.wait()
            _write()
            results["writer_ok"] = True

        reader_ok = {"v": False}

        def reader():
            # Simulate the search path reading concurrently.
            barrier.wait()
            try:
                for _ in range(50):
                    conn = get_connection(tmp_db)
                    conn.execute("SELECT COUNT(*) FROM items").fetchone()
                    conn.close()
                    time.sleep(0.005)
                reader_ok["v"] = True
            except sqlite3.OperationalError as e:
                reader_ok["v"] = f"READER_LOCKED: {e}"

        wt = threading.Thread(target=writer)
        rt = threading.Thread(target=reader)
        wt.start()
        rt.start()
        wt.join(timeout=10)
        rt.join(timeout=10)

        assert results.get("writer_ok") is True, f"writer failed: {results}"
        assert reader_ok["v"] is True, f"reader failed: {reader_ok}"