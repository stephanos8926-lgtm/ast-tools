#!/usr/bin/env python3
import pytest
pytestmark = pytest.mark.unit

"""Unit tests for symbol-level diff engine (Phase 8: Incremental Indexing)."""

import pytest
from ast_tools.types import Symbol, SymbolKind, Edge, EdgeKind
from ast_tools.indexer.diff import (
    compute_symbol_diff,
    DiffResult,
    SymbolStatus,
    find_symbol_by_key,
    is_symbol_unchanged,
    is_symbol_modified,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def make_symbol(
    name: str,
    file_path: str = "src/module.py",
    kind: SymbolKind = SymbolKind.FUNCTION,
    signature: str = "def foo()",
    docstring: str = "A function.",
    start_line: int = 1,
    end_line: int = 5,
) -> Symbol:
    """Helper to create a Symbol with sensible defaults."""
    return Symbol(
        id=f"{file_path}:{name}",
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


@pytest.fixture
def sample_symbols() -> list[Symbol]:
    """A list of 3 sample symbols."""
    return [
        make_symbol("func_a", signature="def func_a(x)", docstring="Function A"),
        make_symbol("func_b", signature="def func_b(y)", docstring="Function B"),
        make_symbol("MyClass", kind=SymbolKind.CLASS, signature="class MyClass", docstring="A class"),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Tests: is_symbol_unchanged
# ──────────────────────────────────────────────────────────────────────────────


class TestIsSymbolUnchanged:
    def test_identical_symbols(self):
        a = make_symbol("foo")
        b = make_symbol("foo")
        assert is_symbol_unchanged(a, b) is True

    def test_signature_changed(self):
        a = make_symbol("foo", signature="def foo(x)")
        b = make_symbol("foo", signature="def foo(x, y)")
        assert is_symbol_unchanged(a, b) is False

    def test_docstring_changed(self):
        a = make_symbol("foo", docstring="Old docs")
        b = make_symbol("foo", docstring="New docs")
        assert is_symbol_unchanged(a, b) is False

    def test_both_changed(self):
        a = make_symbol("foo", signature="def foo(x)", docstring="Old")
        b = make_symbol("foo", signature="def foo(x, y)", docstring="New")
        assert is_symbol_unchanged(a, b) is False


# ──────────────────────────────────────────────────────────────────────────────
# Tests: is_symbol_modified
# ──────────────────────────────────────────────────────────────────────────────


class TestIsSymbolModified:
    def test_same_identity_different_content(self):
        a = make_symbol("foo", signature="def foo(x)")
        b = make_symbol("foo", signature="def foo(x, y)")
        assert is_symbol_modified(a, b) is True

    def test_identical_not_modified(self):
        a = make_symbol("foo")
        b = make_symbol("foo")
        assert is_symbol_modified(a, b) is False

    def test_different_name_not_modified(self):
        a = make_symbol("foo")
        b = make_symbol("bar")
        assert is_symbol_modified(a, b) is False


# ──────────────────────────────────────────────────────────────────────────────
# Tests: compute_symbol_diff
# ──────────────────────────────────────────────────────────────────────────────


class TestComputeSymbolDiff:
    def test_identical_lists(self, sample_symbols):
        diff = compute_symbol_diff(sample_symbols, sample_symbols)
        assert len(diff.unchanged) == 3
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.modified) == 0

    def test_one_symbol_added(self, sample_symbols):
        new = sample_symbols + [make_symbol("func_c", signature="def func_c()")]
        diff = compute_symbol_diff(sample_symbols, new)
        assert len(diff.added) == 1
        assert diff.added[0].name == "func_c"
        assert len(diff.unchanged) == 3

    def test_one_symbol_removed(self, sample_symbols):
        new = sample_symbols[:2]  # Remove 3rd
        diff = compute_symbol_diff(sample_symbols, new)
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "MyClass"
        assert len(diff.unchanged) == 2

    def test_one_symbol_modified(self, sample_symbols):
        new = [
            make_symbol("func_a", signature="def func_a(x, z)"),  # Modified
            sample_symbols[1],  # Unchanged
            sample_symbols[2],  # Unchanged
        ]
        diff = compute_symbol_diff(sample_symbols, new)
        assert len(diff.modified) == 1
        assert diff.modified[0].signature == "def func_a(x, z)"
        assert len(diff.unchanged) == 2

    def test_empty_old_all_added(self, sample_symbols):
        diff = compute_symbol_diff([], sample_symbols)
        assert len(diff.added) == 3
        assert len(diff.removed) == 0

    def test_empty_new_all_removed(self, sample_symbols):
        diff = compute_symbol_diff(sample_symbols, [])
        assert len(diff.removed) == 3
        assert len(diff.added) == 0

    def test_symbol_renamed_is_remove_add(self, sample_symbols):
        """Renamed symbol = 1 removed + 1 added."""
        new = [
            make_symbol("func_a_renamed", signature="def func_a(x)"),  # Renamed
            sample_symbols[1],
            sample_symbols[2],
        ]
        diff = compute_symbol_diff(sample_symbols, new)
        assert len(diff.removed) == 1
        assert len(diff.added) == 1
        assert diff.removed[0].name == "func_a"
        assert diff.added[0].name == "func_a_renamed"

    def test_symbol_moved_to_different_file(self, sample_symbols):
        """Symbol in different file = removed + added."""
        new = [
            make_symbol("func_a", file_path="src/other.py"),  # Moved
            sample_symbols[1],
            sample_symbols[2],
        ]
        diff = compute_symbol_diff(sample_symbols, new)
        assert len(diff.removed) == 1
        assert len(diff.added) == 1

    def test_large_diff_one_change(self):
        """1000 symbols with 1 change → only 1 modified."""
        old = [make_symbol(f"func_{i}", signature=f"def func_{i}()") for i in range(1000)]
        new = [make_symbol(f"func_{i}", signature=f"def func_{i}()") for i in range(1000)]
        # Modify symbol 500
        new[500] = make_symbol("func_500", signature="def func_500(new_param)")

        diff = compute_symbol_diff(old, new)
        assert len(diff.modified) == 1
        assert len(diff.unchanged) == 999

    def test_diff_result_counts(self, sample_symbols):
        """Verify total = old + added = new + removed."""
        new = [
            make_symbol("func_a", signature="def func_a(x, z)"),  # Modified
            sample_symbols[1],  # Unchanged
            make_symbol("func_new"),  # Added
            # MyClass removed
        ]
        diff = compute_symbol_diff(sample_symbols, new)
        assert diff.added_count == 1
        assert diff.removed_count == 1
        assert diff.modified_count == 1
        assert diff.unchanged_count == 1
        assert diff.total_old == 3
        assert diff.total_new == 3


# ──────────────────────────────────────────────────────────────────────────────
# Tests: find_symbol_by_key
# ──────────────────────────────────────────────────────────────────────────────


class TestFindSymbolByKey:
    def test_find_existing(self, sample_symbols):
        found = find_symbol_by_key(sample_symbols, "src/module.py", "func_a")
        assert found is not None
        assert found.name == "func_a"

    def test_find_missing(self, sample_symbols):
        found = find_symbol_by_key(sample_symbols, "src/module.py", "nonexistent")
        assert found is None

    def test_find_in_wrong_file(self, sample_symbols):
        found = find_symbol_by_key(sample_symbols, "src/other.py", "func_a")
        assert found is None
