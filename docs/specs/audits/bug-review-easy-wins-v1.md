# Bug Review — ast-tools Codebase (CLI + Dead Code Features)

**Date:** 2026-06-28  
**Auditor:** Hermes Agent (Bug Review)  
**Mode:** MEDIUM (plan-and-audit)  
**Scope:** Existing code quality issues affecting CLI + dead code features

---

## Executive Summary

**14 issues found** across the codebase that could impact CLI + dead code features:
- 🔴 **Critical:** 3 (connection leaks, silent failures, race conditions)
- 🟠 **High:** 3 (path traversal inconsistency, error key inconsistency, unbounded growth)
- 🟡 **Medium:** 4 (missing types, code duplication, bounds checks, transactions)
- 🟢 **Low:** 4 (TODO comments, hardcoded timeouts, logging, input validation)

---

## 🔴 Critical Issues

### 1. Connection Leak in `semantic_search.py`

**File:** `src/ast_tools/tools/semantic_search.py:339-362, 398`  
**Problem:** Database connections not always closed on error paths. When auto-refresh triggers, connection closed then re-opened, but if re-open fails, original connection already closed.

**Exploit scenario:**
```python
# Concurrent requests + auto-refresh → connection exhaustion
# SQLite has limited connection pool
```

**Fix:** Use `database_context()` context manager or try/finally blocks.

**Effort:** 2h

---

### 2. Silent Exception Swallowing

**Files:** 
- `src/ast_tools/indexer/extractor.py:173-174, 225-226, 347-348`
- `src/ast_tools/indexer/cache.py:151-152, 180-181`
- `src/project_tools.py:40, 101`

**Problem:** Extraction failures logged but silently ignored. Users can't distinguish "no dead code" from "failed to analyze".

**Impact:** Dead code detection will miss symbols due to parse failures with no indication.

**Fix:** Track and report failures in results. Return error counts.

**Effort:** 4h

---

### 3. Race Condition in Database Access

**File:** `src/ast_tools/database/queries.py` (all query functions)  
**Problem:** Multi-step operations lack transaction atomicity. `refresh_index.py:175-194` inserts symbols, then edges — if edges fail, symbols are orphaned.

**Fix:** Ensure all related operations in single transaction. Add explicit rollback.

**Effort:** 3h

---

## 🟠 High Issues

### 4. Unbounded Memory Growth

**File:** `src/ast_tools/tools/dependency.py:19-28` (DependencyNode)  
**Problem:** Recursive `DependencyNode` structure can create deep nesting without bounds. `find_dead_code()` collects all definitions/references without limit.

**Fix:** Add max depth/recursion limits. Bounded collection with early termination.

**Effort:** 3h

---

### 5. Path Traversal Vulnerability — Inconsistent Protection

**Files:**
- `src/ast_tools/tools/ast_edit.py:144-150` ✅ (protected)
- `src/ast_tools/indexer/cache.py:106-113` ❌ (weak — logs then continues!)
- `src/ast_tools/tools/refresh_index.py` ❌ (no validation)

**Problem:** Inconsistent security posture. Attacker could exploit unprotected paths.

**Fix:** Apply consistent path validation across ALL file operations. Reject (not just log) traversal attempts.

**Effort:** 4h (critical for CLI security!)

---

### 6. Error Key Inconsistency

**Pattern variations:**
- `{"error": "...", "error_code": "..."}` ✅ (most tools)
- `{"error": "..."}` ❌ (some fallback paths)
- Missing `tool` field ❌

**Examples:**
- `ast_grep.py:38-48` ✅
- `ast_edit.py:138-142` ✅
- `semantic_search.py:408` ❌
- `dependency.py:62-64` ❌ (silent skip, no error)

**Fix:** Standardize error schema. All errors must include: `error`, `error_code`, `tool`.

**Effort:** 3h

---

## 🟡 Medium Issues

### 7. Missing Type Annotations

**Files:**
- `src/ast_tools/tools/dependency.py:82-103` (`dfs()` inner function)
- `src/ast_tools/indexer/extractor.py:404-421`
- `src/ast_tools/lsp_client.py:170-193`
- `src/project_tools.py:305-308`

**Fix:** Add complete type annotations for public APIs and inner functions.

**Effort:** 6h

---

### 8. Code Duplication

**Files:**
- `src/ast_tools/tools/structural_analysis.py:17-41` vs `find_references.py:9-48`
- `src/project_tools.py:119-144` vs `src/ast_tools/tools/refresh_index.py:59-80`

**Fix:** Extract shared utilities to `src/ast_tools/utils/`. Import, don't duplicate.

**Effort:** 4h

---

### 9. Bounded Loops Missing

**Files:**
- `src/ast_tools/tools/semantic_search.py:286-302` (embedding batch loop)
- `src/ast_tools/tools/dependency.py:43-64` (scans all files)
- `src/ast_tools/tools/refresh_index.py:139-203` (file indexing loop)

**Risk:** Large projects (10K+ files) could timeout or exhaust memory.

**Fix:** Add `max_files`, `max_iterations` parameters. Progress reporting.

**Effort:** 4h

---

### 10. Inconsistent Transaction Usage

**Problem:** Functions like `insert_symbols_batch()` rely on caller to provide transaction context. Some use `with conn:`, others don't.

**Fix:** Document transaction requirements. Consider auto-transactional functions.

**Effort:** 3h

---

## 🟢 Low Issues

### 11. Leftover TODO Comments

**File:** `src/ast_tools/tools/ast_grep.py:8-16`  
**Problem:** `top_level` parameter documented but does nothing (placeholder implementation).

**Fix:** Implement or remove from schema.

**Effort:** 2h

---

### 12. Hardcoded Timeout Values

**File:** `src/ast_tools/tools/ast_grep.py:36`  
**Problem:** 30-second timeout may be too short for large codebases. Not configurable.

**Fix:** Make timeout configurable via tool parameter.

**Effort:** 1h

---

### 13. Logger Configuration Not Propagated

**Files:** Multiple (`extractor.py:21`, `queries.py:16`, `cache.py:28`)  
**Problem:** `logger = logging.getLogger(__name__)` but no root logger setup. Warnings may not appear.

**Fix:** Add library-level handler or document logging requirements.

**Effort:** 2h

---

### 14. Missing Input Validation

**File:** `src/ast_tools/tools/dependency.py:219-299` (`find_dead_code()`)  
**Problem:** No validation of `project_root` parameter. Empty string or non-directory causes silent failure.

**Fix:** Add input validation at function start.

**Effort:** 1h

---

## Recommended Priority Order

| Priority | Issue # | Fix | Effort |
|----------|---------|-----|--------|
| 🔴 P0 | #1 | Fix connection leaks | 2h |
| 🔴 P0 | #2 | Stop silent failures | 4h |
| 🔴 P0 | #3 | Fix race conditions | 3h |
| 🟠 P1 | #5 | Path traversal consistency | 4h |
| 🟠 P1 | #6 | Error key standardization | 3h |
| 🟠 P1 | #4 | Bounded memory growth | 3h |
| 🟡 P2 | #9 | Bounded loops | 4h |
| 🟡 P2 | #10 | Transaction consistency | 3h |
| 🟡 P2 | #8 | Code deduplication | 4h |
| 🟡 P2 | #7 | Type annotations | 6h |
| 🟢 P3 | #11-14 | Polish items | 6h |

**Total estimated effort:** 42h for all fixes

**For CLI + Dead Code specifically:**
- MUST FIX before launch: #1, #2, #3, #5, #6 (16h)
- SHOULD FIX in Phase 1: #4, #9 (7h)
- CAN DEFER: #7, #8, #10, #11-14 (19h)

---

*Bug review complete. Findings ready for synthesis with other audits.*