"""Unit tests for schema and migrations."""

import tempfile
from pathlib import Path

import pytest

from ast_tools.database.connection import get_connection
from ast_tools.database.schema import (
    SCHEMA_VERSION,
    init_schema,
    migrate,
)

pytestmark = pytest.mark.integration


class TestInitSchema:
    """Test schema initialization."""

    def test_init_schema_creates_tables(self):
        """init_schema should create all required tables."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            # Check all tables exist
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            assert "symbols" in tables
            assert "edges" in tables
            assert "file_cache" in tables
            assert "schema_version" in tables  # Singular, not plural

            conn.close()

    def test_init_schema_creates_indexes(self):
        """init_schema should create required indexes."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            # Check indexes exist (actual names from implementation)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

            assert "idx_symbols_qualified" in indexes  # Not 'idx_symbols_qualified_name'
            assert "idx_edges_source" in indexes
            assert "idx_edges_target" in indexes

            conn.close()

    def test_init_schema_creates_fts5(self):
        """init_schema should create FTS5 virtual table."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            # Check FTS5 table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='symbols_fts'"
            )
            assert cursor.fetchone() is not None

            conn.close()

    def test_init_schema_sets_version(self):
        """init_schema should record schema version."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            cursor = conn.execute(
                "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert (
                row[0] == 1
            )  # init_schema only initializes to v1; migrate() brings to SCHEMA_VERSION

            conn.close()

    def test_init_schema_idempotent(self):
        """init_schema should be safe to call multiple times."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            # Call twice
            init_schema(conn)
            init_schema(conn)

            # Should still work
            conn.execute("SELECT COUNT(*) FROM symbols")

            conn.close()


class TestMigrate:
    """Test migration framework."""

    def test_migrate_with_no_changes(self):
        """migrate should do nothing if schema is current."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            # Should not raise
            migrate(conn)

            conn.close()

    def test_migrate_detects_version(self):
        """migrate should detect current schema version."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_path = Path(tmp.name)
            conn = get_connection(db_path)

            init_schema(conn)

            # Check version is recorded
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            version = cursor.fetchone()[0]
            assert version == SCHEMA_VERSION

            conn.close()
