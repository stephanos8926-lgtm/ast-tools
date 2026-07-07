"""Unit tests for edge-related database queries."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from ast_tools.database.connection import get_connection
from ast_tools.database.queries import (
    find_references,
    get_symbol_edges,
    insert_edge,
    insert_edges_batch,
)
from ast_tools.database.schema import init_schema
from ast_tools.types import EdgeKind, Symbol, SymbolKind

pytestmark = pytest.mark.integration


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


class TestEdgeQueries:
    """Tests for edge insertion and retrieval."""

    def test_insert_and_find_edge(self, db_conn: sqlite3.Connection):
        """Should insert an edge and find it via references."""
        # Setup symbols
        s1 = Symbol(
            id="f1.py:s1",
            name="s1",
            qualified_name="s1",
            kind=SymbolKind.FUNCTION,
            file_path="f1.py",
            start_line=1,
            end_line=1,
            signature="",
            docstring="",
            is_public=True,
            content_hash="h1",
        )
        s2 = Symbol(
            id="f2.py:s2",
            name="s2",
            qualified_name="s2",
            kind=SymbolKind.FUNCTION,
            file_path="f2.py",
            start_line=1,
            end_line=1,
            signature="",
            docstring="",
            is_public=True,
            content_hash="h2",
        )

        # We need symbols in the DB for the JOIN in find_references to work well
        from ast_tools.database.queries import insert_symbols_batch

        insert_symbols_batch(db_conn, [s1, s2])

        # Insert edge: s1 calls s2
        insert_edge(
            db_conn,
            source_id="f1.py:s1",
            target_name="s2",
            edge_type=EdgeKind.CALLS.value,
            target_id="f2.py:s2",
        )

        # Find references to s2
        refs = find_references(db_conn, "f2.py:s2")
        assert len(refs) == 1
        assert refs[0]["source_id"] == "f1.py:s1"
        assert refs[0]["edge_type"] == EdgeKind.CALLS.value

    def test_insert_edges_batch(self, db_conn: sqlite3.Connection):
        """Should insert multiple edges in a batch."""
        # Insert symbols first (edges reference them)
        from ast_tools.database.queries import insert_symbols_batch

        symbols = [
            Symbol(
                id="f1.py:s1",
                name="s1",
                qualified_name="s1",
                kind=SymbolKind.FUNCTION,
                file_path="f1.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h1",
            ),
            Symbol(
                id="f2.py:t1",
                name="t1",
                qualified_name="t1",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h2",
            ),
            Symbol(
                id="f2.py:t2",
                name="t2",
                qualified_name="t2",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h3",
            ),
        ]
        insert_symbols_batch(db_conn, symbols)

        # Batch format: List[Tuple[source_id, target_name, edge_type, target_id, resolution_state]]
        edges = [
            ("f1.py:s1", "t1", EdgeKind.CALLS.value, "f2.py:t1", 1),
            ("f1.py:s1", "t2", EdgeKind.CALLS.value, "f2.py:t2", 1),
        ]
        insert_edges_batch(db_conn, edges)

        cursor = db_conn.execute("SELECT COUNT(*) FROM edges")
        assert cursor.fetchone()[0] == 2

    def test_get_symbol_edges(self, db_conn: sqlite3.Connection):
        """Should retrieve all edges originating from a symbol."""
        # Insert symbols first
        from ast_tools.database.queries import insert_symbols_batch

        symbols = [
            Symbol(
                id="f1.py:s1",
                name="s1",
                qualified_name="s1",
                kind=SymbolKind.FUNCTION,
                file_path="f1.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h1",
            ),
            Symbol(
                id="f2.py:s2",
                name="s2",
                qualified_name="s2",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h2",
            ),
            Symbol(
                id="f2.py:t1",
                name="t1",
                qualified_name="t1",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h3",
            ),
            Symbol(
                id="f2.py:t2",
                name="t2",
                qualified_name="t2",
                kind=SymbolKind.FUNCTION,
                file_path="f2.py",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                is_public=True,
                content_hash="h4",
            ),
        ]
        insert_symbols_batch(db_conn, symbols)

        edges = [
            ("f1.py:s1", "t1", EdgeKind.CALLS.value, "f2.py:t1", 1),
            ("f1.py:s1", "t2", EdgeKind.CALLS.value, "f2.py:t2", 1),
            ("f2.py:s2", "t1", EdgeKind.CALLS.value, "f2.py:t1", 1),
        ]
        insert_edges_batch(db_conn, edges)

        s1_edges = get_symbol_edges(db_conn, "f1.py:s1")
        assert len(s1_edges) == 2

        s2_edges = get_symbol_edges(db_conn, "f2.py:s2")
        assert len(s2_edges) == 1
