#!/usr/bin/env python3
"""Symbol-level diff engine for incremental indexing.

Compares old symbol list (from database) with new symbol list (from fresh parse)
and classifies each symbol as: added, removed, modified, or unchanged.

This enables incremental indexing: only changed symbols are updated in the database,
preserving IDs (and thus edges, embeddings, usage history) for unchanged symbols.

Matching key: (file_path, qualified_name)
Unchanged: signature AND docstring match exactly
Modified: same match key but signature or docstring changed
Removed: exists in old but not in new
Added: exists in new but not in old
"""

from dataclasses import dataclass, field
from enum import Enum

from ast_tools.symbols import Symbol

# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class DiffResult:
    """Result of comparing old vs new symbol lists.

    Attributes:
        added: Symbols present in new but not in old
        removed: Symbols present in old but not in new
        modified: Symbols with same identity but changed content
        unchanged: Symbols that are identical
    """

    added: list[Symbol] = field(default_factory=list)
    removed: list[Symbol] = field(default_factory=list)
    modified: list[Symbol] = field(default_factory=list)
    unchanged: list[Symbol] = field(default_factory=list)

    @property
    def added_count(self) -> int:
        return len(self.added)

    @property
    def removed_count(self) -> int:
        return len(self.removed)

    @property
    def modified_count(self) -> int:
        return len(self.modified)

    @property
    def unchanged_count(self) -> int:
        return len(self.unchanged)

    @property
    def total_old(self) -> int:
        return len(self.removed) + len(self.modified) + len(self.unchanged)

    @property
    def total_new(self) -> int:
        return len(self.added) + len(self.modified) + len(self.unchanged)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)


class SymbolStatus(Enum):
    """Status of a symbol after diff computation."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


# ──────────────────────────────────────────────────────────────────────────────
# Core Functions
# ──────────────────────────────────────────────────────────────────────────────


def make_symbol_key(symbol: Symbol) -> tuple[str, str]:
    """Create a unique key for symbol matching.

    Key format: (file_path, qualified_name)

    This is stable across line number changes, whitespace changes,
    and other non-semantic modifications.
    """
    return (symbol.file_path, symbol.qualified_name)


def is_symbol_unchanged(old: Symbol, new: Symbol) -> bool:
    """Check if a symbol is unchanged between old and new version.

    Unchanged = same signature AND same docstring.
    """
    return old.signature == new.signature and old.docstring == new.docstring


def is_symbol_modified(old: Symbol, new: Symbol) -> bool:
    """Check if a symbol is modified (same identity, different content).

    Modified = same match key but different signature or docstring.
    """
    return make_symbol_key(old) == make_symbol_key(new) and not is_symbol_unchanged(old, new)


def find_symbol_by_key(symbols: list[Symbol], file_path: str, qualified_name: str) -> Symbol | None:
    """Find a symbol by its match key (file_path, qualified_name).

    Args:
        symbols: List of symbols to search
        file_path: File path component of the key
        qualified_name: Qualified name component of the key

    Returns:
        Matching symbol or None
    """
    target_key = (file_path, qualified_name)
    for sym in symbols:
        if make_symbol_key(sym) == target_key:
            return sym
    return None


def compute_symbol_diff(
    old_symbols: list[Symbol],
    new_symbols: list[Symbol],
) -> DiffResult:
    """Compute symbol-level diff between old and new symbol lists.

    Classifies each symbol as:
    - ADDED: exists in new but not in old
    - REMOVED: exists in old but not in new
    - MODIFIED: same identity (file_path, qualified_name) but different content
    - UNCHANGED: identical signature and docstring

    Args:
        old_symbols: Symbols from the database (previous index state)
        new_symbols: Symbols from fresh file parse (current state)

    Returns:
        DiffResult with classified symbols
    """
    result = DiffResult()

    # Build lookup maps for O(n) instead of O(n²)
    old_by_key: dict[tuple[str, str], Symbol] = {}
    for sym in old_symbols:
        key = make_symbol_key(sym)
        old_by_key[key] = sym

    new_by_key: dict[tuple[str, str], Symbol] = {}
    for sym in new_symbols:
        key = make_symbol_key(sym)
        new_by_key[key] = sym

    # Find added and modified symbols
    for key, new_sym in new_by_key.items():
        old_sym = old_by_key.get(key)
        if old_sym is None:
            # Symbol exists in new but not in old → added
            result.added.append(new_sym)
        elif is_symbol_unchanged(old_sym, new_sym):
            # Symbol exists in both and is identical → unchanged
            result.unchanged.append(new_sym)
        else:
            # Symbol exists in both but content changed → modified
            result.modified.append(new_sym)

    # Find removed symbols
    for key, old_sym in old_by_key.items():
        if key not in new_by_key:
            # Symbol exists in old but not in new → removed
            result.removed.append(old_sym)

    return result
