# Implementation Plan: Incremental Indexing (Phase 8)

**Version:** 1.0  
**Based on:** docs/specs/incremental-indexing-v1.md  
**Mode:** MEDIUM  

---

## File Manifest

| # | File | Action | Lines | Description |
|---|------|--------|-------|-------------|
| 1 | `src/ast_tools/indexer/diff.py` | **CREATE** | ~200 | Symbol-level diff engine |
| 2 | `src/ast_tools/tools/refresh_index.py` | **MODIFY** | +100/-30 | Add incremental path |
| 3 | `src/ast_tools/tools/index_status.py` | **CREATE** | ~80 | Index status tool |
| 4 | `src/ast_tools/cli.py` | **MODIFY** | +60 | Add `ast index` command |
| 5 | `src/ast_tools/tools/__init__.py` | **MODIFY** | +2 | Register new tools |
| 6 | `tests/test_diff.py` | **CREATE** | ~250 | Diff engine unit tests |
| 7 | `tests/test_incremental_index.py` | **CREATE** | ~200 | Integration tests |

**Total new code:** ~530 lines  
**Total tests:** ~450 lines  

---

## Implementation Order

### Phase 1: Diff Engine (`diff.py`)
**Depends on:** Nothing  
**Estimated:** 2-3h

#### Tasks
1. [ ] Create `diff.py` module with:
   - `SymbolMatcher` class: match symbols by `(file_path, qualified_name)`
   - `compute_symbol_diff(old_symbols, new_symbols) -> DiffResult`
   - `DiffResult` dataclass: `added`, `removed`, `modified`, `unchanged`
   - `SymbolStatus` enum: ADDED, REMOVED, MODIFIED, UNCHANGED
   - `is_symbol_unchanged(old, new) -> bool` (compare signature + docstring)
   - `is_symbol_modified(old, new) -> bool` (same identity, different content)

2. [ ] Key design decisions:
   - Match key: `(file_path, qualified_name)` — stable across line changes
   - "Unchanged": signature AND docstring match exactly
   - "Modified": name matches but signature or docstring changed
   - "Removed": name in old but not in new
   - "Added": name in new but not in old

3. [ ] Edge cases:
   - Empty file → all symbols removed
   - New file → all symbols added
   - File with only docstring changes → symbols marked modified
   - File with only whitespace changes → symbols marked unchanged

#### Tests (`tests/test_diff.py`)
- [ ] Test: identical symbol lists → all unchanged
- [ ] Test: one symbol added → 1 added, rest unchanged
- [ ] Test: one symbol removed → 1 removed, rest unchanged
- [ ] Test: signature changed → 1 modified, rest unchanged
- [ ] Test: docstring changed → 1 modified
- [ ] Test: empty old → all added
- [ ] Test: empty new → all removed
- [ ] Test: symbol renamed → 1 removed + 1 added
- [ ] Test: symbol moved to different file → 1 removed + 1 added
- [ ] Test: 1000 symbols with 1 change → only 1 modified

---

### Phase 2: Incremental Update Logic (`refresh_index.py`)
**Depends on:** Phase 1 (diff.py)  
**Estimated:** 3-4h

#### Tasks
1. [ ] Add `incremental` parameter to `_tool_refresh_index` (default: `True`)
2. [ ] When `incremental=True`:
   - Parse file → get new symbols
   - Fetch old symbols from DB for this file
   - Call `compute_symbol_diff(old, new)`
   - Apply diff in single transaction:
     ```python
     with conn:
         # Remove deleted symbols (cascade: edges + embeddings)
         for sym in diff.removed:
             delete_symbol_cascade(conn, sym.id)
         
         # Update modified symbols (preserve ID)
         for sym in diff.modified:
             update_symbol(conn, sym)
         
         # Insert new symbols
         insert_symbols_batch(conn, [s for s in diff.added])
         
         # Update edges for modified symbols
         update_edges_for_modified(conn, diff.modified)
     ```
3. [ ] Add helper functions to `queries.py`:
   - `delete_symbol_cascade(conn, symbol_id)` — delete symbol + edges + embeddings
   - `update_symbol(conn, symbol)` — update signature/docstring/embedding_text by ID
   - `get_symbols_by_file(conn, file_path)` — fetch all symbols for a file
4. [ ] When `incremental=False`: use existing full-reindex behavior (escape hatch)
5. [ ] Add statistics to return value:
   - `symbols_added`, `symbols_removed`, `symbols_modified`, `symbols_unchanged`
   - `edges_added`, `edges_removed`
   - `embeddings_preserved`, `embeddings_regenerated`

#### Tests (`tests/test_incremental_index.py`)
- [ ] Test: incremental index of unchanged project → 0 changes
- [ ] Test: incremental index with 1 file changed → only that file's symbols updated
- [ ] Test: incremental index with new file → all new symbols added
- [ ] Test: incremental index with deleted file → all symbols removed
- [ ] Test: incremental index with modified function → symbol ID preserved
- [ ] Test: incremental index fallback on error → falls back to full reindex
- [ ] Test: concurrent incremental indexes → no corruption

---

### Phase 3: Index Status Tool (`index_status.py`)
**Depends on:** Phase 2  
**Estimated:** 1h

#### Tasks
1. [ ] Create `index_status.py` with:
   - `get_index_status(project_path) -> dict`
   - Returns: files indexed, symbols count, edges count, last update, index health
   - `get_incremental_stats(project_path) -> dict`
   - Returns: files pending, symbols added/removed/modified since last full index

#### Tests
- [ ] Test: status on empty project
- [ ] Test: status after full index
- [ ] Test: status after incremental index

---

### Phase 4: CLI Command (`cli.py`)
**Depends on:** Phase 2, Phase 3  
**Estimated:** 1h

#### Tasks
1. [ ] Add `ast index` command with subcommands:
   - `ast index` — incremental index (default)
   - `ast index --full` — force full re-index
   - `ast index --status` — show index statistics
   - `ast index --prune` — remove symbols for deleted files
   - `ast index --embeddings` — generate embeddings for new symbols
2. [ ] Add output formats: table (default), JSON, markdown
3. [ ] Add progress indicator for large projects

#### Tests
- [ ] Test: `ast index --help` shows all subcommands
- [ ] Test: `ast index` runs incrementally
- [ ] Test: `ast index --full` runs full reindex
- [ ] Test: `ast index --status` returns JSON stats

---

### Phase 5: Integration & Polish
**Depends on:** All phases  
**Estimated:** 1-2h

#### Tasks
1. [ ] Register new tools in `__init__.py`:
   - `index_status` (MCP tool)
2. [ ] Update `DOCUMENTATION_INDEX.md`
3. [ ] Add CLI reference to `docs/CLI_REFERENCE.md`
4. [ ] Run full test suite: `pytest tests/ -x -q`
5. [ ] Run lint: `ruff check src/`
6. [ ] Commit each phase separately

---

## TDD Test Plan

### Unit Tests (`tests/test_diff.py`) — 10 tests
1. `test_identical_symbols_unchanged`
2. `test_single_symbol_added`
3. `test_single_symbol_removed`
4. `test_signature_modified`
5. `test_docstring_modified`
6. `test_empty_old_all_added`
7. `test_empty_new_all_removed`
8. `test_symbol_renamed_as_remove_add`
9. `test_symbol_moved_as_remove_add`
10. `test_large_diff_one_change`

### Integration Tests (`tests/test_incremental_index.py`) — 7 tests
1. `test_incremental_unchanged_project`
2. `test_incremental_one_file_changed`
3. `test_incremental_new_file`
4. `test_incremental_deleted_file`
5. `test_incremental_symbol_id_preserved`
6. `test_incremental_fallback_on_error`
7. `test_incremental_concurrent_safe`

### CLI Tests (add to existing `tests/test_cli.py`) — 4 tests
1. `test_cli_index_help`
2. `test_cli_index_incremental`
3. `test_cli_index_full`
4. `test_cli_index_status`

---

## Rollback Plan

| Phase | Commit | Rollback |
|-------|--------|----------|
| 1 | `feat: symbol-level diff engine` | `git revert HEAD` |
| 2 | `feat: incremental update logic in refresh_index` | `git revert HEAD` |
| 3 | `feat: index status tool` | `git revert HEAD` |
| 4 | `feat: ast index CLI command` | `git revert HEAD` |
| 5 | `chore: register tools, update docs` | `git revert HEAD` |

**Escape hatch:** `refresh_index(incremental=False)` always available

---

## Acceptance Criteria Checklist

- [ ] `diff.py` module exists with `compute_symbol_diff()`
- [ ] `refresh_index` defaults to `incremental=True`
- [ ] Unchanged symbols retain IDs after re-index
- [ ] Modified symbols updated in-place (no new ID)
- [ ] Removed symbols cascade-deleted (edges + embeddings)
- [ ] `ast index` CLI command works
- [ ] `ast index --status` shows statistics
- [ ] All existing tests still pass
- [ ] New tests: 21+ tests passing
- [ ] Lint clean: 0 new errors
- [ ] Backward compatible: `refresh_index(force=True)` works as before

---

## Estimated Total Effort

| Phase | Effort | Cumulative |
|-------|--------|------------|
| 1: Diff Engine | 3h | 3h |
| 2: Incremental Logic | 4h | 7h |
| 3: Status Tool | 1h | 8h |
| 4: CLI Command | 1h | 9h |
| 5: Integration | 2h | **11h** |

**Target:** Complete in 2 sessions (5-6h each)
