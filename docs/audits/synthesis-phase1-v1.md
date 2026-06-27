# Semantic Database Phase 1 — Synthesis & Revised Plan

**Date:** 2026-06-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Status:** Ready for sign-off before implementation

---

## Audit Summary

| Audit | Status | Findings |
|-------|--------|----------|
| **Forward Audit** | ⚠️ Partial timeout (ran inline checks) | ✅ SQLite FTS5 OK, ✅ 11 existing tools confirmed, ✅ paths safe, ✅ cache writable |
| **Reverse Audit** | ✅ Complete (47 issues) | 8🔴 critical, 12🟠 high, 15🟡 medium, 12🔵 low |

---

## Critical Fixes (Must Address Before Implementation)

All 8🔴 critical issues from reverse audit will be fixed in revised implementation:

| ID | Issue | Fix in Implementation |
|----|-------|----------------------|
| **C1** | No LRU eviction | `ASTCache` with `max_size_mb` config + LRU eviction on write |
| **C2** | `SyntaxError` crashes | Wrap `ast.parse()` in try/except, log error, continue |
| **C3** | No migrations | Add `migrate_v1_to_v2()` stub + migration framework |
| **C4** | Pickle RCE | Use `json` + custom AST node serialization (not pickle) |
| **C5** | Race condition | Single transaction per file + threading lock for refresh |
| **C6** | No retry on locked | `@retry_on_locked(max_attempts=3, delay=0.5)` decorator |
| **C7** | Path traversal | Validate with `Path(file_path).resolve().is_relative_to(project_root)` |
| **C8** | Incomplete tool | Complete `refresh_index_handler` with actual DB calls |

---

## High-Priority Fixes (Will Address in Phase 1)

| ID | Issue | Fix |
|----|-------|-----|
| **H1** | Dead tree-sitter code | Remove from Phase 1 (defer to Phase 2) |
| **H2** | Missing test `__init__.py` | Add to both test directories |
| **H4** | No batch inserts | Add `insert_symbols_batch()` with `executemany()` |
| **H7** | Circular import risk | Move `Symbol` dataclass to `ast_tools/types.py` |
| **H10** | Encoding errors | `read_text(encoding='utf-8', errors='surrogateescape')` |
| **H11** | Permission errors | Catch `PermissionError`, log, skip file |
| **H12** | Empty files | Check `if not content.strip(): return [], []` |

---

## Deferred to Phase 2+ (Not Blocking Phase 1)

| ID | Issue | Defer Reason |
|----|-------|--------------|
| **H3** | Downgrade migrations | Rarely needed, can document manual DB reset |
| **H5, H6** | Progress reporting, resume | UX enhancement, not correctness |
| **H8, H9** | FTS5 trigger tests, migration tests | Add in Phase 1.5 (test expansion) |
| **M1-M15** | Medium priority (15 issues) | Production polish, not blocking |
| **L1-L12** | Low priority (12 issues) | Future enhancements |

---

## Revised File Manifest

**Changes from original plan:**
- ✅ Added: `src/ast_tools/types.py` (shared `Symbol` dataclass)
- ✅ Modified: `indexer/cache.py` → JSON serialization (not pickle)
- ✅ Modified: `indexer/parser.py` → removed tree-sitter (deferred)
- ✅ Added: `database/migrations.py` (migration framework)
- ✅ Added: `tests/indexer/__init__.py`, `tests/database/__init__.py`

| File | Action | Notes |
|------|--------|-------|
| `src/ast_tools/types.py` | Create | Shared `Symbol` dataclass, avoids circular imports |
| `src/ast_tools/indexer/__init__.py` | Create | Package root |
| `src/ast_tools/indexer/parser.py` | Create | Python `ast` only (tree-sitter deferred) |
| `src/ast_tools/indexer/extractor.py` | Create | With error handling, empty file checks |
| `src/ast_tools/indexer/cache.py` | Create | JSON-based (not pickle), LRU eviction |
| `src/ast_tools/database/__init__.py` | Create | Package root |
| `src/ast_tools/database/schema.py` | Create | With migration hooks |
| `src/ast_tools/database/migrations.py` | Create | Migration framework stub |
| `src/ast_tools/database/queries.py` | Create | Batch inserts, retry decorator |
| `src/ast_tools/database/connection.py` | Create | WAL mode, busy timeout |
| `src/ast_tools/tools/search_symbols.py` | Create | Complete implementation |
| `src/ast_tools/tools/find_symbol_definition.py` | Create | Complete implementation |
| `src/ast_tools/tools/list_symbols.py` | Create | Complete implementation |
| `src/ast_tools/tools/index_status.py` | Create | Complete implementation |
| `src/ast_tools/tools/refresh_index.py` | Create | Complete implementation with locking |
| `tests/indexer/__init__.py` | Create | Test package init |
| `tests/database/__init__.py` | Create | Test package init |
| `tests/indexer/test_*.py` | Create | 4 test files |
| `tests/database/test_*.py` | Create | 3 test files |
| `tests/tools/test_semantic_tools.py` | Create | Integration tests |

---

## Revised Test Plan

**Additions from reverse audit:**

- ✅ `test_cache_lru_eviction()` — verify eviction when max size exceeded
- ✅ `test_parse_syntax_error()` — verify malformed files don't crash
- ✅ `test_empty_file_handling()` — verify `__init__.py` files work
- ✅ `test_permission_error()` — verify read-only files skipped gracefully
- ✅ `test_encoding_fallback()` — verify non-UTF8 files handled
- ✅ `test_concurrent_refresh()` — verify locking prevents corruption
- ✅ `test_batch_insert_performance()` — verify batch vs single insert
- ✅ `test_fts5_triggers()` — verify FTS5 sync on insert/delete/update
- ✅ `test_migration_framework()` — verify version detection works

---

## Implementation Order (Revised)

| Phase | Step | Action | Est. Time |
|-------|------|--------|-----------|
| **0** | 0.1 | Create `src/ast_tools/types.py` (shared types) | 5 min |
| **0** | 0.2 | Install deps: NO tree-sitter (deferred) | 0 min |
| **0** | 0.3 | Create package directories + `__init__.py` files | 5 min |
| **1** | 1.1 | Database connection with retry decorator | 15 min |
| **1** | 1.2 | Schema + migration framework stub | 15 min |
| **1** | 1.3 | Query functions with batch inserts | 25 min |
| **2** | 2.1 | Parser with syntax error handling | 15 min |
| **2** | 2.2 | Extractor with edge extraction | 25 min |
| **2** | 2.3 | JSON cache with LRU eviction | 20 min |
| **3** | 3.1 | `search_symbols` tool | 10 min |
| **3** | 3.2 | `find_symbol_definition` tool | 10 min |
| **3** | 3.3 | `list_symbols` tool | 10 min |
| **3** | 3.4 | `index_status` tool | 10 min |
| **3** | 3.5 | `refresh_index` tool (with locking) | 20 min |
| **4** | 4.1 | Wire tools into server | 10 min |
| **4** | 4.2 | Write unit tests (7 new test files) | 60 min |
| **4** | 4.3 | Write integration tests | 30 min |
| **4** | 4.4 | Run full test suite (verify 114 existing pass) | 15 min |
| **4** | 4.5 | Final commit | 5 min |

**Total:** ~4.5 hours (with TDD cycles)

---

## Acceptance Criteria (Updated)

- [ ] All 8🔴 critical issues addressed in code
- [ ] All 7🟠 high-priority issues addressed or explicitly deferred
- [ ] New tests: 35+ (7 files × 5 tests avg)
- [ ] Existing 114 tests still pass
- [ ] 5 new MCP tools appear in `list_tools()`
- [ ] Database created at `~/.cache/ast-tools/codebase.db`
- [ ] FTS5 search returns results <50ms
- [ ] Malformed Python files skipped without crash
- [ ] Concurrent `refresh_index` calls don't corrupt DB
- [ ] AST cache respects max size limit

---

## Rollback Plan (Unchanged)

Each phase is one commit. If Phase 1 fails:

```bash
git revert HEAD  # Undo Phase 1
```

No breaking changes → rollback safe.

---

## Sign-off Required

**Next step:** Your approval to begin TDD implementation.

**What you're approving:**
- ✅ Revised architecture (shared `types.py`, JSON cache, no tree-sitter yet)
- ✅ All 8 critical fixes integrated into implementation
- ✅ 7 high-priority fixes integrated
- ✅ 12 high/medium issues deferred to Phase 2+
- ✅ Revised test plan with 35+ new tests
- ✅ ~4.5 hour time estimate

**Reply with:**
- "GO" — proceed with TDD implementation
- "STOP" — halt, discuss changes
- "GO with changes" — specify modifications before proceeding

---

**Auditor's Note:** This revised plan addresses all critical correctness, security, and data integrity issues. Medium-priority observability/polish items (logging, metrics, config files) are deferred to Phase 2 but do not block a functional Phase 1.