"""Unit tests for symbol-related database queries."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ast_tools.database.connection import get_connection
from ast_tools.database.queries import (
    find_symbol_definition,
    get_symbol_by_id,
    insert_symbol,
    insert_symbols_batch,
    list_symbols_by_file,
    search_symbols,
)
from ast_tools.database.schema import init_schema
from ast_tools.types import Symbol, SymbolKind


@pytest.fixture
def db_conn():
    """Fixture for a temporary in-memory database connection with schema initialized."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    conn = get_connection(db_path)
    init_schema(conn)
    yield conn
    conn.close()
    db_path.unlink(missing_ok=True)


class TestSymbolQueries:
    """Tests for symbol insertion and retrieval."""

    def test_insert_and_get_symbol(self, db_conn: sqlite3.Connection):
        """Should insert a single symbol and retrieve it by ID."""
        symbol = Symbol(
            id="file1.py:foo",
            name="foo",
            qualified_name="foo",
            kind=SymbolKind.FUNCTION,
            file_path="file1.py",
            start_line=1,
            end_line=3,
            signature="def foo():",
            docstring="docs",
            is_public=True,
            content_hash="hash1",
        )
        insert_symbol(db_conn, symbol)

        row = get_symbol_by_id(db_conn, "file1.py:foo")
        assert row is not None
        assert row["name"] == "foo"
        assert row["kind"] == SymbolKind.FUNCTION.value

    def test_insert_symbols_batch(self, db_conn: sqlite3.Connection):
        """Should insert symbols in a batch."""
        symbols = [
            Symbol(
                id=f"f.py:s{i}",
                name=f"s{i}",
                qualified_name=f"s{i}",
                kind=SymbolKind.FUNCTION,
                file_path="f.py",
                start_line=i,
                end_line=i + 1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h",
            )
            for i in range(5)
        ]
        insert_symbols_batch(db_conn, symbols)

        cursor = db_conn.execute("SELECT COUNT(*) FROM symbols")
        assert cursor.fetchone()[0] == 5

    def test_search_symbols_fts(self, db_conn: sqlite3.Connection):
        """Should perform FTS search on symbols."""
        symbols = [
            Symbol(
                id="f1.py:a",
                name="func_a",
                qualified_name="func_a",
                kind=SymbolKind.FUNCTION,
                file_path="f1.py",
                start_line=1,
                end_line=2,
                signature="",
                docstring="Search me",
                is_public=True,
                content_hash="h1",
            ),
            Symbol(
                id="f2.py:b",
                name="class_b",
                qualified_name="class_b",
                kind=SymbolKind.CLASS,
                file_path="f2.py",
                start_line=1,
                end_line=5,
                signature="",
                docstring="Ignore me",
                is_public=True,
                content_hash="h2",
            ),
        ]
        insert_symbols_batch(db_conn, symbols)

        results = search_symbols(db_conn, "Search")
        assert len(results) == 1
        assert results[0]["name"] == "func_a"

    def test_find_symbol_definition(self, db_conn: sqlite3.Connection):
        """Should find symbol by qualified name."""
        symbol = Symbol(
            id="f1.py:test",
            name="test",
            qualified_name="test",
            kind=SymbolKind.FUNCTION,
            file_path="f1.py",
            start_line=1,
            end_line=2,
            signature="",
            docstring="",
            is_public=True,
            content_hash="h",
        )
        insert_symbol(db_conn, symbol)

        row = find_symbol_definition(db_conn, "test")
        assert row is not None
        assert row["id"] == "f1.py:test"

    def test_list_symbols_by_file(self, db_conn: sqlite3.Connection):
        """Should list symbols for a specific file."""
        symbols = [
            Symbol(
                id="f1.py:s1",
                name="s1",
                qualified_name="s1",
                kind=SymbolKind.FUNCTION,
                file_path="f1.py",
                start_line=1,
                end_line=2,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h",
            ),
            Symbol(
                id="f1.py:s2",
                name="s2",
                qualified_name="s2",
                kind=SymbolKind.FUNCTION,
                file_path="f1.py",
                start_line=3,
                end_line=4,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h",
            ),
            Symbol(
                id="f2.py:s3",
                name="s3",
                qualified_name="s3",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=2,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h",
            ),
        ]
        insert_symbols_batch(db_conn, symbols)

        results = list_symbols_by_file(db_conn, "f1.py")
        assert len(results) == 2
        assert {r["name"] for r in results} == {"s1", "s2"}
