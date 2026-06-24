# Reverse Audit: Semantic DB Phase 1 Spec + Plan

**Audit Date:** 2026-06-23  
**Auditor:** Hermes Agent (reverse audit subagent)  
**Spec Reference:** `docs/specs/semantic-db-phase1-v1.md`  
**Plan Reference:** `docs/plans/semantic-db-phase1-v1.md`  

---

## Executive Summary

**Total Issues Found:** 47  
- 🔴 **Critical:** 8 issues (will cause failures or data corruption)
- 🟠 **High:** 12 issues (missing functionality blocking core use cases)
- 🟡 **Medium:** 15 issues (quality/reliability gaps)
- 🔵 **Low:** 12 issues (nice-to-have improvements)

**Overall Risk Assessment:** 🟠 **HIGH** — Multiple critical gaps in error handling, memory management, and data integrity must be addressed before implementation.

---

## 🔴 Critical Issues (8)

### C1. No LRU Eviction for AST Cache
**Location:** `indexer/cache.py`  
**Issue:** ASTCache has no maximum size limit or eviction policy. Cache will grow unbounded until disk is full.  
**Impact:** Production systems with large codebases will exhaust disk space.  
**Fix Required:** Implement LRU cache with configurable max size (e.g., 1GB), eviction policy, and cache cleanup utility.  
**Spec Reference:** Test plan mentions "LRU eviction" (line 93) but implementation omits it entirely.

### C2. SyntaxError Not Handled in Parser
**Location:** `indexer/parser.py`, `indexer/extractor.py`  
**Issue:** `ast.parse()` raises `SyntaxError` on invalid Python files. No try/except in proposed code.  
**Impact:** Single malformed file crashes entire indexing run.  
**Fix Required:** Wrap parse calls in try/except, log syntax errors, continue indexing other files.

### C3. No Migration Functions Defined
**Location:** `database/schema.py`  
**Issue:** Has `SCHEMA_VERSION` and `needs_migration()` but zero actual migration logic. What happens when version 2 exists?  
**Impact:** Users cannot upgrade database schema. Breaking change on next version.  
**Fix Required:** Implement migration framework with `migrate_v1_to_v2()`, `migrate_v2_to_v3()`, etc.

### C4. Pickle Security Vulnerability
**Location:** `indexer/cache.py`  
**Issue:** `pickle.load()` on cache files without verification. Pickle is inherently unsafe — malicious cache files can execute arbitrary code.  
**Impact:** If cache directory is compromised, code execution possible.  
**Fix Required:** Use safer serialization (JSON + custom AST representation) or add HMAC verification of cache files.

### C5. Race Condition in Bulk Indexing
**Location:** `tools/refresh_index.py`  
**Issue:** No transaction batching. Symbols inserted one-at-a-time with individual commits.Two simultaneous refresh calls can corrupt `file_cache` entries.  
**Impact:** Data corruption under concurrent access.  
**Fix Required:** Wrap entire file indexing in single transaction. Add application-level lock for refresh operations.

### C6. No Handling for "Database Is Locked"
**Location:** `database/connection.py`  
**Issue:** `busy_timeout = 5000` set but no retry logic if timeout exceeded. SQLite can still raise `OperationalError: database is locked`.  
**Impact:** Tool calls fail unpredictably under concurrent load.  
**Fix Required:** Implement retry decorator with exponential backoff for database operations.

### C7. Path Traversal Risk in Cache
**Location:** `indexer/cache.py`  
**Issue:** `_get_cache_path()` uses `file_path.replace("/", "_")` without sanitization. Files with `..` in path could escape cache directory.  
**Impact:** Potential security vulnerability, cache file collisions.  
**Fix Required:** Use `pathlib.Path(file_path).resolve()` and validate path is within project root.

### C8. Incomplete refresh_index Implementation
**Location:** `tools/refresh_index.py`  
**Issue:** Code has placeholder comments: `"Implement insert_symbol call"`, `"Implement get_cached_hash call"`. Not production-ready.  
**Impact:** Tool will not function as written.  
**Fix Required:** Complete implementation with actual database calls.

---

## 🟠 High Priority Issues (12)

### H1. Dead Code: Tree-Sitter Parser Never Used
**Location:** `indexer/parser.py`  
**Issue:** `parse_tree_sitter()` method defined but never called. `extractor.py` uses only `ast.parse()`.  
**Impact:** Maintenance burden for unused code.  
**Fix Required:** Either integrate tree-sitter into extraction logic or defer to Phase 2.

### H2. Missing Test Package Inits
**Location:** `tests/indexer/`, `tests/database/`  
**Issue:** Plan creates test directories but omits `__init__.py` files.  
**Impact:** Pytest may fail to discover tests.  
**Fix Required:** Add `tests/indexer/__init__.py` and `tests/database/__init__.py`.

### H3. No Downgrade Migration Support
**Location:** `database/schema.py`  
**Issue:** Users with DB from future version cannot downgrade.  
**Impact:** Forces users to delete DB if they downgrade ast-tools.  
**Fix Required:** Implement `migrate_downgrade()` functions.

### H4. No Batch Insert for Performance
**Location:** `database/queries.py`, `tools/refresh_index.py`  
**Issue:** Symbols inserted one-at-a-time. For 10K LOC codebase (~500 symbols), this is 500 separate INSERT statements.  
**Impact:** Indexing 10x slower than necessary.  
**Fix Required:** Implement `insert_symbols_batch(conn, symbols)` using executemany().

### H5. No Progress Reporting for Long Operations
**Location:** `tools/refresh_index.py`  
**Issue:** No way to track indexing progress. User sees nothing for potentially minutes on large codebases.  
**Impact:** Poor UX, users may cancel prematurely.  
**Fix Required:** Add progress callback or yield progress updates.

### H6. No Interrupt Resume Capability
**Location:** `tools/refresh_index.py`  
**Issue:** Interrupted indexing must restart from beginning.  
**Impact:** Wasted compute on large codebases.  
**Fix Required:** Track per-file state, resume from last successfully indexed file.

### H7. Circular Import Risk
**Location:** `indexer/extractor.py`  
**Issue:** Imports `from ..database import Symbol`. If database layer ever needs extractor types, circular import occurs.  
**Impact:** Import errors, fragile module structure.  
**Fix Required:** Move `Symbol` dataclass to shared module (e.g., `ast_tools/types.py`).

### H8. No Tests for FTS5 Trigger Behavior
**Location:** Test plan  
**Issue:** Triggers for FTS5 sync (symbols_ai, symbols_ad, symbols_au) are critical but untested.  
**Impact:** FTS5 index could desync from main table without detection.  
**Fix Required:** Add tests: insert symbol → verify FTS5 row exists, delete → verify FTS5 row removed.

### H9. No Tests for Schema Migration Logic
**Location:** `tests/database/test_schema.py`  
**Issue:** Only `test_initial_schema_created` planned. No migration tests.  
**Impact:** Migration bugs slip into production.  
**Fix Required:** Add `test_migration_v1_to_v2`, `test_needs_migration_detection`.

### H10. No Encoding Error Handling
**Location:** `tools/refresh_index.py`  
**Issue:** `Path(file_path).read_text()` assumes UTF-8. Files with different encoding crash.  
**Impact:** Indexing fails on files with encoding declarations or binary content.  
**Fix Required:** Use `read_text(encoding='utf-8', errors='ignore')` or detect encoding from BOM/declaration.

### H11. No Permission Error Handling
**Location:** Multiple files  
**Issue:** No handling for `PermissionError` when reading files or creating directories.  
**Impact:** Crashes on read-only files or restricted directories.  
**Fix Required:** Catch `PermissionError`, log warning, skip file.

### H12. Empty Files Not Handled
**Location:** `indexer/extractor.py`  
**Issue:** `ast.parse("")` raises `SyntaxError: unexpected EOF while parsing`.  
**Impact:** Empty `__init__.py` files crash indexing.  
**Fix Required:** Check for empty content before parsing, skip or treat as valid (0 symbols).

---

## 🟡 Medium Priority Issues (15)

### M1. No Connection Pooling
**Location:** `database/connection.py`  
**Issue:** Each tool call creates new connection. Overhead adds up under load.  
**Fix Required:** Implement simple connection pool or use `sqlite3` connection caching.

### M2. No Cache Size Configuration
**Location:** `indexer/cache.py`  
**Issue:** Hard-coded cache behavior, no user configuration.  
**Fix Required:** Add config via environment variables or config file.

### M3. No Logging
**Location:** All modules  
**Issue:** Zero logging statements. Impossible to debug production issues.  
**Fix Required:** Add structured logging with configurable log levels.

### M4. No Metrics Collection
**Location:** All modules  
**Issue:** No way to measure cache hit rate, indexing time per file, query latency.  
**Fix Required:** Add metrics counters, consider Prometheus integration.

### M5. No Debug Mode
**Location:** All modules  
**Issue:** Cannot enable verbose output for troubleshooting.  
**Fix Required:** Add `AST_TOOLS_DEBUG` environment variable support.

### M6. Hard-Coded Cache Paths
**Location:** `database/connection.py`, `indexer/cache.py`  
**Issue:** `~/.cache/ast-tools/` hard-coded. No way to override.  
**Fix Required:** Respect `XDG_CACHE_HOME`, allow env var override.

### M7. No Vacuum/Analyze Operations
**Location:** `database/queries.py`  
**Issue:** FTS5 indexes grow unbounded. No scheduled vacuum.  
**Impact:** Database bloat over time.  
**Fix Required:** Add `vacuum_database()` and `analyze_database()` functions, schedule periodic runs.

### M8. No Handling for Symlinks
**Location:** `tools/refresh_index.py`  
**Issue:** `glob("**/*.py")` follows symlinks. Same file could be indexed multiple times.  
**Impact:** Duplicate symbols, wasted compute.  
**Fix Required:** Track indexed file inodes or resolve symlinks before indexing.

### M9. No Handling for Very Long Paths
**Location:** `indexer/cache.py`  
**Issue:** Cache file path generation could exceed filesystem limits (255 chars).  
**Impact:** Cache write failures on deep directory structures.  
**Fix Required:** Hash file_path for cache filename instead of string replacement.

### M10. No Edge Resolution Implementation
**Location:** `database/queries.py`, `indexer/extractor.py`  
**Issue:** Edges table has `target_id` but no resolution logic to populate it.  
**Impact:** Edges stored with unresolved targets, limited query capability.  
**Fix Required:** Implement symbol resolution pass after initial extraction.

### M11. Windows Path Separator Not Considered
**Location:** `indexer/cache.py`  
**Issue:** Cache uses `/` replacement. Windows uses `\`.  
**Impact:** Cache collisions or failures on Windows.  
**Fix Required:** Use `pathlib.Path.as_posix()` for consistent hashing.

### M12. No README Updates
**Location:** Documentation  
**Issue:** New tools not documented in README.md.  
**Fix Required:** Add section documenting 5 new MCP tools with examples.

### M13. No Usage Examples for New Tools
**Location:** Documentation  
**Issue:** No example queries or typical workflows shown.  
**Fix Required:** Add examples: "Search for all database functions", "Find callers of X".

### M14. No Troubleshooting Guide
**Location:** Documentation  
**Issue:** Users have no guidance for common issues (corrupted cache, locked DB).  
**Fix Required:** Add troubleshooting section to docs.

### M15. No Performance Tuning Docs
**Location:** Documentation  
**Issue:** Users cannot optimize for their codebase size.  
**Fix Required:** Document pragma tuning, cache size recommendations.

---

## 🔵 Low Priority Issues (12)

### L1. No Configuration File
**Issue:** All settings hard-coded or env vars. Consider adding `ast-tools.toml` config file.

### L2. No API Documentation
**Issue:** No generated docs (Sphinx, pdoc) for new modules.

### L3. No Type Hints on All Functions
**Issue:** Some functions in plan snippets lack complete type annotations.

### L4. No Docstrings on All Classes
**Issue:** Partial docstrings in proposed code.

### L5. No CLI Tool for Manual Indexing
**Issue:** Only MCP tools provided. Consider adding `ast-tools index` CLI command.

### L6. No Cache Statistics Tool
**Issue:** Cannot query cache hit/miss rates via MCP tool.

### L7. No Index Health Check
**Issue:** No tool to verify index integrity (dangling edges, orphan symbols).

### L8. No Parallel Indexing
**Issue:** Files indexed sequentially. Could use multiprocessing for large codebases.

### L9. No Incremental Index Optimization
**Issue:** Changed file detection requires reading every file. Could use git diff for speedup.

### L10. No Symbol Kind Expansion
**Issue:** Limited to 6 kinds. Consider: decorator, context_manager, generator, async_function.

### L11. No Edge Kind Expansion
**Issue:** Limited to 4 edge types. Consider: assigns, decorates, raises, yields.

### L12. No Unit Test for Tree-Sitter Fallback
**Issue:** If tree-sitter path is ever enabled, no tests exist.

---

## Full Issue List (Compact)

| ID | Severity | Category | Location | Summary |
|----|----------|----------|----------|---------|
| C1 | 🔴 | Memory | cache.py | No LRU eviction |
| C2 | 🔴 | Error handling | parser.py, extractor.py | SyntaxError not caught |
| C3 | 🔴 | Migration | schema.py | No migration functions |
| C4 | 🔴 | Security | cache.py | Pickle vulnerability |
| C5 | 🔴 | Concurrency | refresh_index.py | Race condition in bulk insert |
| C6 | 🔴 | Error handling | connection.py | No retry on DB locked |
| C7 | 🔴 | Security | cache.py | Path traversal risk |
| C8 | 🔴 | Completeness | refresh_index.py | Incomplete implementation |
| H1 | 🟠 | Dead code | parser.py | Tree-sitter never used |
| H2 | 🟠 | Test coverage | tests/indexer/, tests/database/ | Missing __init__.py |
| H3 | 🟠 | Migration | schema.py | No downgrade support |
| H4 | 🟠 | Performance | queries.py | No batch insert |
| H5 | 🟠 | UX | refresh_index.py | No progress reporting |
| H6 | 🟠 | UX | refresh_index.py | No interrupt resume |
| H7 | 🟠 | Architecture | extractor.py | Circular import risk |
| H8 | 🟠 | Test coverage | test_schema.py | No FTS5 trigger tests |
| H9 | 🟠 | Test coverage | test_schema.py | No migration tests |
| H10 | 🟠 | Error handling | refresh_index.py | No encoding error handling |
| H11 | 🟠 | Error handling | multiple | No permission error handling |
| H12 | 🟠 | Error handling | extractor.py | Empty files crash |
| M1 | 🟡 | Performance | connection.py | No connection pooling |
| M2 | 🟡 | Config | cache.py | No cache size config |
| M3 | 🟡 | Observability | all | No logging |
| M4 | 🟡 | Observability | all | No metrics |
| M5 | 🟡 | Observability | all | No debug mode |
| M6 | 🟡 | Config | connection.py, cache.py | Hard-coded paths |
| M7 | 🟡 | Maintenance | queries.py | No vacuum/analyze |
| M8 | 🟡 | Correctness | refresh_index.py | Symlink handling |
| M9 | 🟡 | Robustness | cache.py | Long path handling |
| M10 | 🟡 | Completeness | queries.py | No edge resolution |
| M11 | 🟡 | Portability | cache.py | Windows paths |
| M12 | 🟡 | Documentation | README.md | No README updates |
| M13 | 🟡 | Documentation | examples | No usage examples |
| M14 | 🟡 | Documentation | troubleshooting | No troubleshooting guide |
| M15 | 🟡 | Documentation | performance | No tuning docs |
| L1 | 🔵 | Config | global | No config file |
| L2 | 🔵 | Documentation | api | No API docs |
| L3 | 🔵 | Code quality | all | Incomplete type hints |
| L4 | 🔵 | Code quality | all | Incomplete docstrings |
| L5 | 🔵 | UX | cli | No CLI indexing command |
| L6 | 🔵 | Observability | tools | No cache stats tool |
| L7 | 🔵 | Correctness | tools | No index health check |
| L8 | 🔵 | Performance | indexer | No parallel indexing |
| L9 | 🔵 | Performance | indexer | No git-based incremental |
| L10 | 🔵 | Features | extractor.py | Limited symbol kinds |
| L11 | 🔵 | Features | extractor.py | Limited edge kinds |
| L12 | 🔵 | Test coverage | test_parser.py | No tree-sitter tests |

---

## Recommendations

### Before Implementation (Must Fix):
1. **C1, C2, C3, C4, C5, C6, C8** — All critical issues must be addressed in implementation plan.
2. **H2, H8, H9, H10, H11, H12** — High-priority error handling and test gaps.

### During Implementation (Should Fix):
3. **H1, H3, H4, H5, H6, H7** — Address dead code, migration, performance, and architecture issues.
4. **M1, M3, M6, M7, M10** — Core infrastructure for production use.

### Post-Implementation (Could Fix):
5. **M2, M4, M5, M8, M9, M11-M15** — Quality of life improvements.
6. **L1-L12** — Enhancements for future phases.

---

## Sign-off

**Audit Complete:** Yes  
**Ready for Implementation:** No — Critical issues must be resolved first.  
**Recommended Action:** Update spec and plan to address all 🔴 critical and 🟠 high priority issues before beginning Phase 1 implementation.