# Spec: Incremental Indexing (Phase 8)

**Version:** 1.0  
**Author:** Lucien  
**Date:** 2026-06-30  
**Mode:** MEDIUM  

---

## Problem Statement

### Current State
The semantic index (`refresh_index`) already does **file-level** incremental indexing:
- Computes SHA256 hash of each file
- Skips files whose hash hasn't changed
- Only re-indexes modified files

### The Gap
When a file **has** changed, the current implementation:
1. **Deletes ALL symbols** for that file (`DELETE FROM symbols WHERE file_path = ?`)
2. **Re-inserts ALL symbols** from scratch

**Problems:**
1. **Symbol ID instability** — Unchanged symbols get new IDs, breaking:
   - Callgraph edges (reference old symbol IDs)
   - Embeddings (orphaned vectors pointing to deleted IDs)
   - Usage tracking (history lost)
2. **Embedding waste** — Embeddings for unchanged symbols are regenerated
3. **Edge churn** — All edges for the file are deleted/recreated, even if only one function changed
4. **Audit trail loss** — `indexed_at` timestamps reset for unchanged symbols

### Use Cases
- **Large codebases** (100+ files): Only 2-3 files change per edit session, but 100% get re-indexed
- **CI pipelines**: Full index takes 5-10 min, incremental should take seconds
- **Long-running projects**: Preserve symbol history across months of development

---

## Goals

| ID | Priority | Goal |
|----|----------|------|
| **G1** | P0 | Symbol-level diff: Only insert/delete/update changed symbols per file |
| **G2** | P0 | Preserve symbol IDs for unchanged symbols (edges, embeddings intact) |
| **G3** | P1 | Preserve embeddings for unchanged symbols (no regeneration) |
| **G4** | P1 | Preserve callgraph edges for unchanged symbol pairs |
| **G5** | P2 | CLI command for incremental indexing (`ast index --incremental`) |
| **G6** | P2 | Index statistics showing files/symbols added/skipped/removed |
| **G7** | P3 | Multi-repo support: Index multiple projects into one database |

---

## Compatibility / Behavior Rules

### Backward Compatibility
- Existing `refresh_index` tool continues to work (full re-index)
- Existing database schema unchanged (no migrations needed)
- Existing tools (`ast_grep`, `semantic_search`, `ast_read`) unaffected

### Edge Cases
1. **File renamed** → Treat as new file (new path = new symbol IDs)
2. **File deleted** → Remove all symbols, edges, embeddings for that file
3. **File unchanged** → Skip entirely (current behavior, preserved)
4. **File partially changed** (e.g., one function modified) → Only update that function's symbol
5. **Symbol moved to different file** → Treat as delete + insert (different file_path)
6. **Symbol renamed** → Treat as delete + insert (different name)
7. **Concurrent edits** → Database locking prevents corruption (already handled)

### Error Handling
- If diff computation fails → Fall back to full re-index for that file
- Log warnings for fallback cases
- Never leave database in partial state (transaction per file)

---

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/indexer/diff.py` | **NEW** | Symbol-level diff engine (compare old vs new symbols) |
| `src/ast_tools/tools/refresh_index.py` | **MODIFY** | Add incremental update path (use diff engine) |
| `src/ast_tools/tools/index_status.py` | **NEW** | Index status tracking (added/removed/changed counts) |
| `src/ast_tools/cli.py` | **MODIFY** | Add `ast index` command |
| `tests/test_diff.py` | **NEW** | Unit tests for diff engine |
| `tests/test_incremental_index.py` | **NEW** | Integration tests for incremental indexing |

---

## Acceptance Criteria

### Must Have (P0)
- [ ] `diff.py` module with `compute_symbol_diff(old_symbols, new_symbols)` function
- [ ] Diff returns: `added`, `removed`, `modified`, `unchanged` symbol lists
- [ ] `refresh_index` uses diff when `incremental=True` (default)
- [ ] Unchanged symbols retain their IDs
- [ ] Modified symbols: Update in-place (preserve ID, update signature/docstring)
- [ ] Removed symbols: Delete symbol + edges + embeddings
- [ ] Added symbols: Insert new symbol + edges + embeddings

### Should Have (P1)
- [ ] Embeddings preserved for unchanged symbols (no regeneration)
- [ ] Edges preserved for unchanged symbol pairs
- [ ] Index statistics: `symbols_added`, `symbols_removed`, `symbols_modified`, `symbols_unchanged`
- [ ] Fallback to full re-index if diff fails

### Nice to Have (P2)
- [ ] CLI command: `ast index --incremental` (default), `ast index --full`
- [ ] CLI command: `ast index --status` (show index statistics)
- [ ] CLI command: `ast index --prune` (remove symbols for deleted files)

### Performance Targets
- Incremental index of 100-file project with 1 file changed: **< 5 seconds** (vs 30-60s full re-index)
- Memory usage: **< 100MB** for diff computation on large projects
- Database size: No growth from unchanged symbols

---

## Technical Approach

### Diff Algorithm
```python
def compute_symbol_diff(
    old_symbols: list[Symbol],
    new_symbols: list[Symbol]
) -> DiffResult:
    """
    Compare symbol lists and classify each symbol as:
    - unchanged: name + file_path + signature + docstring match
    - modified: name + file_path match, but signature/docstring changed
    - removed: exists in old but not in new
    - added: exists in new but not in old
    
    Matching key: (file_path, qualified_name)
    """
```

### Incremental Update Flow
```
1. Find all files in project
2. For each file:
   a. Compute content hash
   b. If hash unchanged → skip (existing behavior)
   c. If hash changed or new:
      - Parse file → get new symbols
      - Get old symbols from DB
      - Compute diff
      - Apply diff in transaction:
        * DELETE removed symbols (cascade: edges, embeddings)
        * UPDATE modified symbols (preserve ID, update content)
        * INSERT new symbols
        * Leave unchanged symbols alone
3. Update file_cache
4. Return statistics
```

### Database Queries
- No schema changes needed
- Use existing `DELETE ... WHERE id = ?` for removed
- Use existing `UPDATE ... WHERE id = ?` for modified
- Use existing `INSERT ... ON CONFLICT` for new

---

## Rollback Plan
- Each phase committed separately
- If incremental path fails → `refresh_index` falls back to old full-reindex behavior
- Feature flag: `incremental=False` forces full re-index (escape hatch)

---

## Out of Scope
- Multi-repo support (Phase 9)
- Real-time file watching (already in watcher daemon)
- Remote/cloud indexing
- Symbol-level diff across file renames (future enhancement)
