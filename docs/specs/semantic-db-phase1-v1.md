# Semantic Database — Phase 1 Spec

**Version:** 1.0  
**Date:** 2026-06-23  
**Mode:** MEDIUM (plan-and-audit skill)

---

## Problem Statement

**Current state:** ast-tools has 11 powerful structural analysis tools, but each operates on-demand without persistent knowledge of the codebase. Users must re-parse files on every tool call.

**Missing capability:** No persistent symbol index, no cross-file symbol resolution without re-parsing, no incremental updates when files change.

**Impact:** 
- Slower repeated queries on same codebase
- Cannot efficiently answer "show me all symbols in this project"
- No cached AST for large files
- No file change detection → stale results

---

## Goals

| ID | Priority | Description |
|----|----------|-------------|
| G1 | **MUST** | Persistent SQLite symbol database with FTS5 search |
| G2 | **MUST** | Content-hash based cache invalidation |
| G3 | **MUST** | Incremental indexing (only reindex changed files) |
| G4 | **SHOULD** | Python `ast` parser + tree-sitter multi-language support |
| G5 | **SHOULD** | Pickle cache for parsed ASTs (50x speedup) |
| G6 | **COULD** | File watcher for automatic reindexing (Phase 2) |

---

## Compatibility & Behavior Rules

1. **Backward compatibility:** All 11 existing ast-tools MCP tools continue to work unchanged
2. **Database location:** `~/.cache/ast-tools/codebase.db` (user cache dir, not in project)
3. **WAL mode:** Enabled by default for concurrent reads
4. **Content-hash invalidation:** SHA256, cache key = `(file_path, content_hash, python_version)`
5. **Indexing scope:** Configurable via `--include` / `--exclude` patterns (default: `**/*.py`, exclude `**/__pycache__/**`)
6. **Atomic writes:** All DB updates wrapped in transactions
7. **Migration support:** Schema versioning with auto-migration on open

---

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/indexer/__init__.py` | Create | Indexer package root |
| `src/ast_tools/indexer/parser.py` | Create | AST + tree-sitter parser abstraction |
| `src/ast_tools/indexer/extractor.py` | Create | Symbol & edge extraction from AST |
| `src/ast_tools/indexer/cache.py` | Create | Pickle cache with content-hash invalidation |
| `src/ast_tools/database/__init__.py` | Create | Database package root |
| `src/ast_tools/database/schema.py` | Create | Schema definition + migrations |
| `src/ast_tools/database/queries.py` | Create | Query functions (search, lookup, traverse) |
| `src/ast_tools/database/connection.py` | Create | Connection management (WAL, pragmas) |
| `src/ast_tools/tools/search_symbols.py` | Create | MCP tool: FTS5 + BM25 search |
| `src/ast_tools/tools/find_symbol_definition.py` | Create | MCP tool: exact match lookup |
| `src/ast_tools/tools/list_symbols.py` | Create | MCP tool: all symbols in file |
| `src/ast_tools/tools/index_status.py` | Create | MCP tool: cache stats, indexed file count |
| `src/ast_tools/tools/refresh_index.py` | Create | MCP tool: force reindex |
| `tests/indexer/` | Create | Indexer unit tests |
| `tests/database/` | Create | Database unit tests |
| `tests/tools/test_semantic_tools.py` | Create | MCP tool integration tests |

---

## Acceptance Criteria

- [ ] **G1:** SQLite DB created at `~/.cache/ast-tools/codebase.db`, FTS5 search working
- [ ] **G2:** Content-hash invalidation verified (edit file → reindex → new hash)
- [ ] **G3:** Incremental indexing: 10-file change reindexes only 10 files (not all)
- [ ] **G4:** Python `ast` parser extracts functions, classes, methods, imports
- [ ] **G5:** Pickle cache shows 10x+ speedup on second parse
- [ ] **G6:** Deferred to Phase 2 (watchdog integration)
- [ ] All new tools appear in `list_tools()` MCP call
- [ ] All tests pass (new tests + existing 114)
- [ ] Schema migrations tested (v1 → v2 simulation)

---

## Test Plan

### Unit Tests (Indexer)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/indexer/test_parser.py` | 8 | Python `ast` parsing, tree-sitter fallback, error handling |
| `tests/indexer/test_extractor.py` | 12 | Symbol extraction (functions, classes, imports), edge extraction |
| `tests/indexer/test_cache.py` | 10 | Content-hash invalidation, pickle roundtrip, LRU eviction |

### Unit Tests (Database)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/database/test_schema.py` | 6 | Migrations, versioning, rollback |
| `tests/database/test_queries.py` | 15 | FTS5 search, symbol lookup, edge traversal |
| `tests/database/test_connection.py` | 5 | WAL mode, concurrent reads, connection pooling |

### Integration Tests (MCP Tools)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/tools/test_semantic_tools.py` | 20 | End-to-end MCP tool calls via server fixture |

### Performance Benchmarks

| Benchmark | Target |
|-----------|--------|
| Index 10K LOC codebase | <5 seconds |
| Search symbol (FTS5) | <50ms |
| Incremental reindex (10 files) | <500ms |
| AST cache hit | <1ms (vs 50ms parse) |

---

## Rollback Plan

Each phase is one commit. Rollback:

```bash
# Undo Phase 1
git revert HEAD
# OR remove last commit entirely
git reset --hard HEAD~1
```

**No breaking changes:** Existing tools+tests remain untouched → rollback safe.

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| tree-sitter | ^0.22 | Multi-language parsing |
| tree-sitter-python | ^0.21 | Python grammar |
| tree-sitter-typescript | ^0.21 | TypeScript grammar |
| watchdog | ^6.0 | File watching (Phase 2) |

**Existing (already in pyproject.toml):**
- `libcst` (AST editing)
- `anyio` (async)
- `mcp` (server SDK)

---

## Design Decisions

### 1. SQLite over NoSQL
**Why:** Mature, single-file, FTS5 built-in, no external service, ACID.
**Rejected:** Pickle-only (no querying), PostgreSQL (overkill), Chroma (embeddings not needed yet).

### 2. Content-Hash over Mtime
**Why:** Git operations don't always update mtime, content-hash guarantees correctness.
**Trade-off:** Slower (must read file), but correctness > speed.

### 3. Hybrid Parsing (ast + tree-sitter)
**Why:** Python `ast` gives deepest Python analysis (decorators, call extraction), tree-sitter adds multi-language.
**Rejected:** Tree-sitter-only (less precise for Python), ast-only (single language).

### 4. Separate Packages (indexer/, database/)
**Why:** Separation of concerns, testable in isolation, reusable in Phase 2 plugin.
**Rejected:** Single monolithic `indexer.py` (hard to test, violates SRP).

### 5. Cache in ~/.cache (not project dir)
**Why:** Persists across projects, doesn't pollute git, follows XDG spec.
**Rejected:** Project-local `.ast-tools-cache/` (per-project duplication).

---

## Out of Scope (Future Phases)

- **Phase 2:** File watcher (watchdog), auto-reindex
- **Phase 3:** Embeddings + vector search (sqlite-vec)
- **Phase 4:** Cross-project symbol resolution
- **Phase 5:** Graph-based queries (DAG traversal, cycle detection)

---

## Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Time to first symbol search | N/A (no index) | <100ms |
| Time to subsequent search | Full parse (~500ms) | <50ms (indexed) |
| Index 10K LOC codebase | N/A | <5s |
| Incremental reindex (10 files) | N/A | <500ms |
| Test coverage (new code) | 0% | >85% |

---

## Review Feedback

**Pending forward + reverse audits.**

---

**Next Step:** Implementation plan (docs/plans/semantic-db-phase1-v1.md)