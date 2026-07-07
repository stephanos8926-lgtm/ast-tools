#!/usr/bin/env python3
import pytest

pytestmark = pytest.mark.integration

"""Integration tests for incremental indexing (Phase 8)."""


from ast_tools.database import (
    delete_symbol_cascade,
    get_symbols_by_file,
    init_schema,
    insert_symbols_batch,
    update_file_cache,
    update_symbol_fields,
)
from ast_tools.database.connection import database_context
from ast_tools.indexer.diff import compute_symbol_diff
from ast_tools.types import Symbol, SymbolKind

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    with database_context(db_path) as conn:
        init_schema(conn)
        yield db_path


def make_symbol(
    name: str,
    file_path: str = "src/module.py",
    kind: SymbolKind = SymbolKind.FUNCTION,
    signature: str = "def foo()",
    docstring: str = "A function.",
    start_line: int = 1,
    end_line: int = 5,
    symbol_id: str | None = None,
) -> Symbol:
    """Helper to create a Symbol."""
    return Symbol(
        id=symbol_id or f"{file_path}:{name}",
        name=name,
        qualified_name=name,
        kind=kind,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        signature=signature,
        docstring=docstring,
        lang="python",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Incremental Update Flow
# ──────────────────────────────────────────────────────────────────────────────


class TestIncrementalUpdate:
    def test_new_file_full_index(self, tmp_db):
        """New file with no old symbols → all symbols added."""
        old_symbols = []
        new_symbols = [
            make_symbol("func_a", file_path="src/new.py", symbol_id="src/new.py:func_a"),
            make_symbol("func_b", file_path="src/new.py", symbol_id="src/new.py:func_b"),
        ]

        compute_symbol_diff(old_symbols, new_symbols)

        with database_context(tmp_db) as conn:
            init_schema(conn)
            insert_symbols_batch(conn, new_symbols)
            update_file_cache(conn, "src/new.py", "abc123", 2)
            conn.commit()

            stored = get_symbols_by_file(conn, "src/new.py")
            assert len(stored) == 2

    def test_unchanged_file_skipped(self, tmp_db):
        """File with no changes → diff shows all unchanged."""
        old_symbols = [
            make_symbol("func_a", symbol_id="src/module.py:func_a"),
            make_symbol("func_b", symbol_id="src/module.py:func_b"),
        ]
        new_symbols = [
            make_symbol("func_a", symbol_id="src/module.py:func_a"),
            make_symbol("func_b", symbol_id="src/module.py:func_b"),
        ]

        diff = compute_symbol_diff(old_symbols, new_symbols)
        assert diff.unchanged_count == 2
        assert diff.added_count == 0
        assert diff.removed_count == 0
        assert diff.modified_count == 0
        assert not diff.has_changes

    def test_modified_symbol_preserves_id(self, tmp_db):
        """Modified symbol → ID preserved, fields updated."""
        old_symbols = [
            make_symbol("func_a", signature="def func_a(x)", symbol_id="src/module.py:func_a"),
        ]
        new_symbols = [
            make_symbol("func_a", signature="def func_a(x, y)", symbol_id="src/module.py:func_a"),
        ]

        diff = compute_symbol_diff(old_symbols, new_symbols)
        assert diff.modified_count == 1

        with database_context(tmp_db) as conn:
            init_schema(conn)
            insert_symbols_batch(conn, old_symbols)

            # Apply incremental update
            for sym in diff.modified:
                update_symbol_fields(conn, sym)

            stored = get_symbols_by_file(conn, "src/module.py")
            assert len(stored) == 1
            assert stored[0].signature == "def func_a(x, y)"
            assert stored[0].id == "src/module.py:func_a"  # ID preserved!

    def test_removed_symbol_cascade(self, tmp_db):
        """Removed symbol → cascade delete (symbol + edges)."""
        old_symbols = [
            make_symbol("func_a", symbol_id="src/module.py:func_a"),
            make_symbol("func_b", symbol_id="src/module.py:func_b"),
        ]

        with database_context(tmp_db) as conn:
            init_schema(conn)
            insert_symbols_batch(conn, old_symbols)
            conn.commit()

            # Verify both exist
            stored = get_symbols_by_file(conn, "src/module.py")
            assert len(stored) == 2

            # Delete one
            delete_symbol_cascade(conn, "src/module.py:func_a")
            conn.commit()

            # Verify only one remains
            stored = get_symbols_by_file(conn, "src/module.py")
            assert len(stored) == 1
            assert stored[0].name == "func_b"

    def test_mixed_changes(self, tmp_db):
        """File with add + remove + modify + unchanged → correct diff."""
        old_symbols = [
            make_symbol("func_a", signature="def func_a()", symbol_id="src/module.py:func_a"),
            make_symbol("func_b", signature="def func_b()", symbol_id="src/module.py:func_b"),
            make_symbol("func_c", signature="def func_c()", symbol_id="src/module.py:func_c"),
        ]
        new_symbols = [
            make_symbol(
                "func_a", signature="def func_a()", symbol_id="src/module.py:func_a"
            ),  # Unchanged
            make_symbol(
                "func_b", signature="def func_b(x)", symbol_id="src/module.py:func_b"
            ),  # Modified
            make_symbol(
                "func_d", signature="def func_d()", symbol_id="src/module.py:func_d"
            ),  # Added
            # func_c removed
        ]

        diff = compute_symbol_diff(old_symbols, new_symbols)
        assert diff.unchanged_count == 1  # func_a
        assert diff.modified_count == 1  # func_b
        assert diff.added_count == 1  # func_d
        assert diff.removed_count == 1  # func_c

    def test_incremental_stats(self, tmp_db):
        """Verify incremental indexing produces correct statistics."""
        old_symbols = [
            make_symbol("func_a", symbol_id="src/module.py:func_a"),
        ]
        new_symbols = [
            make_symbol(
                "func_a", signature="def func_a() -> str", symbol_id="src/module.py:func_a"
            ),
            make_symbol("func_b", symbol_id="src/module.py:func_b"),
        ]

        diff = compute_symbol_diff(old_symbols, new_symbols)

        stats = {
            "symbols_added": diff.added_count,
            "symbols_removed": diff.removed_count,
            "symbols_modified": diff.modified_count,
            "symbols_unchanged": diff.unchanged_count,
        }

        assert stats["symbols_added"] == 1
        assert stats["symbols_removed"] == 0
        assert stats["symbols_modified"] == 1
        assert stats["symbols_unchanged"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_file_to_symbols(self, tmp_db):
        """Empty file → all symbols are added."""
        diff = compute_symbol_diff([], [make_symbol("func_a")])
        assert diff.added_count == 1
        assert diff.unchanged_count == 0

    def test_symbols_to_empty_file(self, tmp_db):
        """File becomes empty → all symbols removed."""
        diff = compute_symbol_diff([make_symbol("func_a")], [])
        assert diff.removed_count == 1
        assert diff.added_count == 0

    def test_both_empty(self, tmp_db):
        """Both empty → no changes."""
        diff = compute_symbol_diff([], [])
        assert not diff.has_changes
        assert diff.total_old == 0
        assert diff.total_new == 0

    def test_large_diff_performance(self):
        """1000 symbols with 1 change → fast diff."""
        old = [make_symbol(f"func_{i}", symbol_id=f"src/mod.py:func_{i}") for i in range(1000)]
        new = [make_symbol(f"func_{i}", symbol_id=f"src/mod.py:func_{i}") for i in range(1000)]
        new[500] = make_symbol(
            "func_500", signature="def func_500(new)", symbol_id="src/mod.py:func_500"
        )

        diff = compute_symbol_diff(old, new)
        assert diff.modified_count == 1
        assert diff.unchanged_count == 999
        assert diff.has_changes
