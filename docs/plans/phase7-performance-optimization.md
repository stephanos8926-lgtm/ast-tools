# Phase 7: Performance Optimization Implementation Plan

**Goal:** Reduce ast-tools cold start, index time, and test suite latency.
**Est:** 8h
**Current baseline:** 55 tools, 330+ tests, 25.08s test suite (tools + database + indexer + co-change)

## Bottlenecks

| # | Bottleneck | Current | Target | Tool |
|---|-----------|---------|--------|------|
| 1 | `sentence-transformers` cold load | ~10-15s | <3s or lazy/non-blocking | cProfile, time |
| 2 | Index rebuild on first `semantic_search` | ~20s+ | <2s incremental | time, profiling |
| 3 | No AST pattern cache | ~5-10ms per ast_grep call | <1ms after first hit | functools.lru_cache |
| 4 | SQLite connection overhead | ~5ms per connect | connection pool reuse | sqlite3 connection caching |
| 5 | Test suite sequential | 25.08s | <12s (pytest-xdist parallel) | pytest -n auto |
| 6 | Large result set truncation | unenforced | enforced token budget | tiktoken |

---

### Task 1: Lazy Embedding Model Loading

**Files:** `src/ast_tools/embeddings/model.py`
**Effort:** 1h

- Wrap `SentenceTransformer(...)` in `@lru_cache` or lazy property
- Load only on first `encode()` call, not at import time
- Verify: `python3 -c "from ast_tools.embeddings import model; import time; t=time.time(); model._ensure_loaded(); print(f'Loaded in {time.time()-t:.2f}s')"`

**Target:** First import <0.1s (was 10s+)

### Task 2: Index Auto-Init with Incremental Default

**Files:** `src/ast_tools/tools/refresh_index.py:144-170`
**Effort:** 1h

- `refresh_index` already has incremental (SHA256 hash diff) — make it the default
- `refresh_index(force=False)` = incremental; `force=True` = full rebuild
- Add check: if no `schema_version`, run `init_schema` + full build silently
- Verify: `time ast-tools refresh_index` after a small code change

**Target:** Incremental <1s (files changed), full <10s (small projects)

### Task 3: AST Pattern Cache

**Files:** `src/ast_tools/tools/ast_grep.py`
**Effort:** 1.5h

- Add `functools.lru_cache(maxsize=128)` to pattern compilation step
- Key: `(pattern, lang, path)` tuple
- Add cache stats via `ast_grep(cache_stats=True)` param
- Verify: repeat call 100x → measure total time

### Task 4: Connection Caching

**Files:** `src/ast_tools/database/connection.py`
**Effort:** 1.5h

- Cache per-thread connection via `threading.local()`
- Add `get_cached_connection()` → reuse or create
- Add `close_cached_connections()` cleanup
- Verify: 10 rapid queries in loop → measure overhead difference

### Task 5: Parallel Test Suite

**Files:** `pyproject.toml`, `tests/conftest.py`
**Effort:** 1h

- Add `pytest-xdist` to dev deps
- Add `-n auto --dist worksteal --tb=short` to pytest addopts
- Ensure fixture isolation (no global state in conftest)
- Verify: `python3 -m pytest tests/tools/ tests/database/ tests/indexer/ -n auto --dist worksteal -q --tb=short`

**Target:** <12s for 330+ tests

### Task 6: Token Budget Enforcement

**Files:** `src/ast_tools/tools/semantic_search.py`
**Effort:** 1.5h

- Already has `token_budget` param — verify it's enforced with integration test
- Add `truncated` flag to response (true if results were cut)
- Add `total_tokens` to response metadata
- Add test: query that would return 20K tokens with budget=4096 → verify truncated

---

## Rollback

Each task commit is independent. Rollback: `git revert <commit-hash>` per task.
