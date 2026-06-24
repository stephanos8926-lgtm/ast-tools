"""Unit tests for database query functions."""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import hashlib
from datetime import datetime

from ast_tools.database.connection import get_connection
from ast_tools.database.schema import init_schema, SCHEMA_VERSION
from ast_tools.database.queries import (
    insert_symbols_batch,
    insert_edges_batch,
    insert_file_cache_entry,
    get_file_cache_entry,
    update_file_cache_entry_hash,
    delete_file_cache_entry,
    get_index_stats,
    count_symbols_by_kind,
    search_symbols_fts,
    find_symbol_definition,
    get_symbols_in_file,
)
from ast_tools.types import Symbol, Edge, SymbolKind, EdgeKind, IndexStats, FileCacheEntry


@pytest.fixture
def db_conn():
    """Fixture for a temporary in-memory database connection with schema initialized."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    conn = get_connection(db_path)
    init_schema(conn)
    yield conn
    conn.close()
    Path(db_path).unlink(missing_ok=True)
    Path(str(db_path) + "-shm").unlink(missing_ok=True)
    Path(str(db_path) + "-wal").unlink(missing_ok=True)


def create_file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class TestInsertFunctions:
    """Tests for insert functions."""

    def test_insert_symbols_batch(self, db_conn: sqlite3.Connection):
        """Should insert symbols in a batch and update FTS table."""
        symbols = [
            Symbol(id="file1.py:foo", name="foo", qualified_name="foo", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=1, end_line=3, signature="def foo():", docstring="", is_public=True, content_hash="hash1"),
            Symbol(id="file1.py:bar", name="bar", qualified_name="bar", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=5, end_line=7, signature="def bar():", docstring="", is_public=True, content_hash="hash2"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_test")

        cursor = db_conn.execute("SELECT qualified_name, kind FROM symbols")
        results = cursor.fetchall()
        assert len(results) == 2
        assert ("foo", SymbolKind.FUNCTION.value) in results

        # Check FTS index
        cursor = db_conn.execute("SELECT COUNT(*) FROM symbols_fts WHERE symbols_fts MATCH 'foo'")
        assert cursor.fetchone()[0] == 1

    def test_insert_edges_batch(self, db_conn: sqlite3.Connection):
        """Should insert edges in a batch."""
        # First, insert the symbols that these edges will link
        symbols = [
            Symbol(id="file1.py:caller", name="caller", qualified_name="caller", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=1, end_line=3, signature="def caller():", docstring="", is_public=True, content_hash="hash_c"),
            Symbol(id="file1.py:callee", name="callee", qualified_name="callee", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=5, end_line=7, signature="def callee():", docstring="", is_public=True, content_hash="hash_d"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_edge")

        edges = [
            Edge(source_symbol_id="file1.py:caller", target_symbol_id="file1.py:callee", edge_type=EdgeKind.CALLS, metadata={})
        ]
        insert_edges_batch(db_conn, edges)

        cursor = db_conn.execute("SELECT source_symbol_id, target_symbol_id, edge_type FROM edges")
        results = cursor.fetchall()
        assert len(results) == 1
        assert ("file1.py:caller", "file1.py:callee", EdgeKind.CALLS.value) in results

    def test_insert_file_cache_entry(self, db_conn: sqlite3.Connection):
        """Should insert a file cache entry."""
        file_path = "/app/src/module.py"
        file_hash = create_file_hash("content")
        entry = FileCacheEntry(file_path=file_path, file_hash=file_hash, last_indexed=datetime.now(), project_id="test_project")
        insert_file_cache_entry(db_conn, entry)

        cursor = db_conn.execute("SELECT file_path, file_hash FROM file_cache WHERE file_path=?", (file_path,))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == file_path
        assert result[1] == file_hash


class TestGetFunctions:
    """Tests for get functions."""

    def test_get_file_cache_entry(self, db_conn: sqlite3.Connection):
        """Should retrieve a file cache entry."""
        file_path = "/app/src/module.py"
        file_hash = create_file_hash("content")
        entry = FileCacheEntry(file_path=file_path, file_hash=file_hash, last_indexed=datetime.now(), project_id="test_project")
        insert_file_cache_entry(db_conn, entry)

        retrieved_entry = get_file_cache_entry(db_conn, file_path)
        assert retrieved_entry is not None
        assert retrieved_entry.file_path == file_path
        assert retrieved_entry.file_hash == file_hash

    def test_get_file_cache_entry_nonexistent(self, db_conn: sqlite3.Connection):
        """Should return None for a nonexistent entry."""
        retrieved_entry = get_file_cache_entry(db_conn, "/nonexistent.py")
        assert retrieved_entry is None

    def test_get_index_stats(self, db_conn: sqlite3.Connection):
        """Should return correct index statistics."""
        symbols = [
            Symbol(id="file1.py:foo", name="foo", qualified_name="foo", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=1, end_line=3, signature="def foo():", docstring="", is_public=True, content_hash="hash1"),
            Symbol(id="file2.py:bar", name="bar", qualified_name="bar", kind=SymbolKind.CLASS, file_path="file2.py", start_line=1, end_line=5, signature="class Bar:", docstring="", is_public=True, content_hash="hash2"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_stats")

        edges = [
            Edge(source_symbol_id="file1.py:foo", target_symbol_id="file2.py:bar", edge_type=EdgeKind.CALLS, metadata={})
        ]
        insert_edges_batch(db_conn, edges)

        stats = get_index_stats(db_conn, "project_stats")
        assert stats.total_files == 2
        assert stats.total_symbols == 2
        assert stats.total_edges == 1
        assert stats.last_indexed is not None

    def test_count_symbols_by_kind(self, db_conn: sqlite3.Connection):
        """Should count symbols correctly by kind."""
        symbols = [
            Symbol(id="file1.py:foo", name="foo", qualified_name="foo", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=1, end_line=3, signature="def foo():", docstring="", is_public=True, content_hash="hash1"),
            Symbol(id="file1.py:bar", name="bar", qualified_name="bar", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=5, end_line=7, signature="def bar():", docstring="", is_public=True, content_hash="hash2"),
            Symbol(id="file2.py:baz", name="baz", qualified_name="baz", kind=SymbolKind.CLASS, file_path="file2.py", start_line=1, end_line=5, signature="class Baz:", docstring="", is_public=True, content_hash="hash3"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_count")

        func_count = count_symbols_by_kind(db_conn, SymbolKind.FUNCTION, "project_count")
        assert func_count == 2

        class_count = count_symbols_by_kind(db_conn, SymbolKind.CLASS, "project_count")
        assert class_count == 1

        total_count = count_symbols_by_kind(db_conn, None, "project_count")
        assert total_count == 3

    def test_search_symbols_fts(self, db_conn: sqlite3.Connection):
        """Should perform FTS search on symbols."""
        symbols = [
            Symbol(id="file1.py:func_a", name="func_a", qualified_name="func_a", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=1, end_line=3, signature="def func_a():", docstring="This is function A", is_public=True, content_hash="hashA"),
            Symbol(id="file2.py:class_b", name="class_b", qualified_name="class_b", kind=SymbolKind.CLASS, file_path="file2.py", start_line=1, end_line=5, signature="class ClassB:", docstring="Handles processing", is_public=True, content_hash="hashB"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_fts")

        results = search_symbols_fts(db_conn, "function A", "project_fts")
        assert len(results) == 1
        assert results[0].name == "func_a"

        results = search_symbols_fts(db_conn, "processing", "project_fts")
        assert len(results) == 1
        assert results[0].name == "class_b"

        results = search_symbols_fts(db_conn, "nonexistent", "project_fts")
        assert len(results) == 0

    def test_find_symbol_definition(self, db_conn: sqlite3.Connection):
        """Should find symbol definition by qualified name."""
        symbol = Symbol(id="file1.py:func_test", name="func_test", qualified_name="func_test", kind=SymbolKind.FUNCTION, file_path="file1.py", start_line=10, end_line=12, signature="def func_test():", docstring="", is_public=True, content_hash="hash_def")
        insert_symbols_batch(db_conn, [symbol], "project_def")

        retrieved = find_symbol_definition(db_conn, "func_test", "project_def")
        assert retrieved is not None
        assert retrieved.name == "func_test"
        assert retrieved.file_path == "file1.py"

        nonexistent = find_symbol_definition(db_conn, "nonexistent_func", "project_def")
        assert nonexistent is None

    def test_get_symbols_in_file(self, db_conn: sqlite3.Connection):
        """Should retrieve all symbols belonging to a specific file."""
        symbols = [
            Symbol(id="file_a.py:sym1", name="sym1", qualified_name="sym1", kind=SymbolKind.FUNCTION, file_path="file_a.py", start_line=1, end_line=3, signature="def sym1():", docstring="", is_public=True, content_hash="hash1"),
            Symbol(id="file_a.py:sym2", name="sym2", qualified_name="sym2", kind=SymbolKind.CLASS, file_path="file_a.py", start_line=5, end_line=7, signature="class Sym2:", docstring="", is_public=True, content_hash="hash2"),
            Symbol(id="file_b.py:sym3", name="sym3", qualified_name="sym3", kind=SymbolKind.FUNCTION, file_path="file_b.py", start_line=1, end_line=3, signature="def sym3():", docstring="", is_public=True, content_hash="hash3"),
        ]
        insert_symbols_batch(db_conn, symbols, "project_file_symbols")

        file_symbols = get_symbols_in_file(db_conn, "file_a.py", "project_file_symbols")
        assert len(file_symbols) == 2
        assert {s.name for s in file_symbols} == {"sym1", "sym2"}

        empty_file_symbols = get_symbols_in_file(db_conn, "nonexistent.py", "project_file_symbols")
        assert len(empty_file_symbols) == 0


class TestUpdateDeleteFunctions:
    """Tests for update and delete functions."""

    def test_update_file_cache_entry_hash(self, db_conn: sqlite3.Connection):
        """Should update the hash of an existing file cache entry."""
        file_path = "/app/src/old.py"
        old_hash = create_file_hash("old content")
        new_hash = create_file_hash("new content")
        entry = FileCacheEntry(file_path=file_path, file_hash=old_hash, last_indexed=datetime.now(), project_id="project_update")
        insert_file_cache_entry(db_conn, entry)

        update_file_cache_entry_hash(db_conn, file_path, new_hash)

        updated_entry = get_file_cache_entry(db_conn, file_path)
        assert updated_entry is not None
        assert updated_entry.file_hash == new_hash

    def test_delete_file_cache_entry(self, db_conn: sqlite3.Connection):
        """Should delete a file cache entry."""
        file_path = "/app/src/delete_me.py"
        file_hash = create_file_hash("content")
        entry = FileCacheEntry(file_path=file_path, file_hash=file_hash, last_indexed=datetime.now(), project_id="project_delete")
        insert_file_cache_entry(db_conn, entry)

        delete_file_cache_entry(db_conn, file_path)

        deleted_entry = get_file_cache_entry(db_conn, file_path)
        assert deleted_entry is None