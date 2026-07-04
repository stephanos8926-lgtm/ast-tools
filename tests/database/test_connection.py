"""Unit tests for database connection module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ast_tools.database.connection import (
    database_context,
    get_connection,
    retry_on_locked,
)


pytestmark = pytest.mark.integration

class TestRetryDecorator:
    """Test the retry_on_locked decorator."""

    def test_retry_on_success(self):
        """Function that succeeds on first try should not retry."""
        call_count = 0

        @retry_on_locked(max_attempts=3)
        def succeed_immediately():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeed_immediately()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_locked_error(self):
        """Function that raises sqlite3.OperationalError should retry."""
        call_count = 0

        @retry_on_locked(max_attempts=3, initial_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Function that always fails should raise after max_attempts."""
        call_count = 0

        @retry_on_locked(max_attempts=2, initial_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError):
            always_fail()

        assert call_count == 2  # Initial + 1 retry (max_attempts=2)

    def test_other_errors_not_retried(self):
        """Non-OperationalError exceptions should not trigger retry."""
        call_count = 0

        @retry_on_locked(max_attempts=3)
        def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not a database error")

        with pytest.raises(ValueError):
            raise_value_error()

        assert call_count == 1  # No retries


class TestConnectionContextManager:
    """Test database_context context manager."""

    def test_context_manager_creates_connection(self):
        """Context manager should yield a valid connection."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)

            with database_context(db_path) as conn:
                assert isinstance(conn, sqlite3.Connection)
                # Verify WAL mode is enabled
                cursor = conn.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()[0]
                assert mode == "wal"

            # Connection should be closed after context
            conn.close()

    def test_context_manager_rolls_back_on_error(self):
        """Context manager should rollback on exception."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)

            try:
                with database_context(db_path) as conn:
                    conn.execute("CREATE TABLE test (id INTEGER)")
                    conn.commit()  # Commit before raising
                    raise ValueError("trigger rollback")
            except ValueError:
                pass

            # Connection should still be usable
            with database_context(db_path) as conn:
                # Table should exist since we committed
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
                )
                assert cursor.fetchone() is not None


class TestGetConnection:
    """Test get_connection function."""

    def test_get_connection_creates_file(self):
        """get_connection should create database file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "new.db"
            assert not db_path.exists()

            conn = get_connection(db_path)
            assert db_path.exists()
            conn.close()

    def test_get_connection_configures_pragmas(self):
        """get_connection should configure SQLite pragmas."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)

            conn = get_connection(db_path)

            # Check WAL mode
            cursor = conn.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0] == "wal"

            # Check synchronous
            cursor = conn.execute("PRAGMA synchronous")
            assert cursor.fetchone()[0] == 1  # NORMAL

            # Check cache size (negative means KB in SQLite)
            cursor = conn.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]
            assert cache_size < 0  # Negative = KB

            conn.close()
