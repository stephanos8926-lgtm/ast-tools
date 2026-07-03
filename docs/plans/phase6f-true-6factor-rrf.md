# Phase 6F: True 6-Factor RRF — Implementation Plan v1

**Date:** 2026-07-03  
**Mode:** MEDIUM (plan-and-audit)  
**Author:** Lucien  
**Dependencies:** None — standalone workstream  
**Blocks:** Phase A (docs accuracy needed before publishing)  

---

## File Manifest (Detailed)

| File | Action | Current LOC | Est Δ | Purpose |
|------|--------|-------------|-------|---------|
| `src/ast_tools/utils/rrf.py` | CREATE | — | +80 | Shared RRF utility |
| `src/ast_tools/tools/semantic_search.py` | MODIFY | 475 | +60/-20 | 6-factor expansion |
| `src/ast_tools/context/injector.py` | MODIFY | 287 | +30/-5 | Fix callgraph stub |
| `tests/tools/test_rrf.py` | CREATE | — | +150 | RRF unit tests |
| `tests/tools/test_semantic_search_6f.py` | CREATE | — | +150 | 6-factor integration tests |
| `tests/context/test_injector_rrf.py` | CREATE | — | +80 | ContextInjector tests |
| `README.md` | MODIFY | 190 | +10/-5 | Document 6-factor |
| `docs/AST_TOOLS_QUICKSTART.md` | MODIFY | 569 | +10/-5 | Update semantic_search docs |
| `docs/SESSION_STATE.md` | MODIFY | 80 | +5/-0 | Add Phase 6F |
| `docs/DOCUMENTATION_INDEX.md` | MODIFY | 80 | +5/-0 | Add Phase 6F entry |
| `CHANGELOG.md` | MODIFY | 170 | +10/-0 | Add Unreleased entry |
| `docs/specs/phase6f-true-6factor-rrf.md` | CREATE | — | +80 | Spec (this doc) |

**Total: ~720 LOC across 12 files (4 new, 8 modified)**

---

## Task Breakdown

### Phase F1: Shared RRF Utility (`src/ast_tools/utils/rrf.py`)
**~1h | 3 files**

1. Create `src/ast_tools/utils/rrf.py` with:
   - `rrr_fuse(ranked_lists: list[list[str]], k: int = 60) → dict[str, float]`  
     Standard RRF: `score[id] += 1 / (rank_i + k)` for each factor. Returns fused score dict.
     **Why k=60:** Standard RRF literature recommends k=60 for datasets with 4+ ranking dimensions. The current k=1.5 was appropriate for 2-factor fusion but amplifies noise with 6 factors.
   - `rank_symbols(symbol_ids: list[str], key_fn: Callable[[str], float], reverse: bool = True) → list[str]`  
     Given a key function per symbol, returns symbol IDs sorted by that key (production of a ranked list).
   - Importable from `ast_tools.utils.rrf`
   
2. Create `tests/tools/test_rrf.py`:
   - Test `rrf_fuse` with 2 ranked lists → correct fusion
   - Test `rrf_fuse` with 6 ranked lists → correct fusion
   - Test `rrf_fuse` with empty lists → empty
   - Test `rrf_fuse` with all same rank → equal scores
   - Test `rank_symbols` with numeric key → correct order
   - Test `rank_symbols` with ties → stable ordering
   - Test k parameter changes weight distribution

3. Verify: `PYTHONPATH=src python3 -m pytest tests/tools/test_rrf.py -v`

### Phase F2: 6-Factor `semantic_search`
**~2h | 2 files**

1. In `src/ast_tools/tools/semantic_search.py`:
   - Replace inline RRF code with `from ast_tools.utils.rrf import rrf_fuse, rank_symbols`
   - Build 6 ranked lists instead of 2:
     
     | Factor | Rank Source | DB Query |
          |--------|-------------|----------|
          | FTS5 | `bm25(symbols_fts)` score → sort desc | Already queried |
          | Vector | Cosine distance → sort asc | Already queried |
          | Recency | `symbols.indexed_at` (Unix timestamp) → sort desc (0 for NULL) | `SELECT id FROM symbols ORDER BY indexed_at DESC NULLS LAST` |
          | Usage | `dependency_metrics.fan_in + dependency_metrics.fan_out` (total connections) → sort desc | `SELECT symbol_id, (fan_in + fan_out) as total_edges FROM dependency_metrics ORDER BY total_edges DESC NULLS LAST` |
          | Kind | Priority map → sort desc | Static: `function=5, class=4, method=3, variable=2, import=1, constant=1` |
          | Centrality | `dependency_metrics.centrality` → sort desc (0 for NULL) | `SELECT symbol_id FROM dependency_metrics ORDER BY centrality DESC NULLS LAST` |
   
   - Each new factor adds at most 1 cheap DB query (sorted index scan on indexed column)
   - Pass all 6 ranked lists to `rrf_fuse(k=60)`
   - **Graceful degradation:** If DB queries fail or return empty, skip that factor (treat as neutral — no rank contribution)

2. Create `tests/tools/test_semantic_search_6f.py`:
   - Test 2-factor results match pre-change output (no regression)
   - Test 6-factor produces different (better) results
   - Test each new factor independently: recency boost, usage boost, kind boost, centrality boost
   - Test graceful degradation when `dependency_metrics` table is empty
   - Test graceful degradation when `last_indexed` is all NULL
   - Test performance: `k=10 < 150ms` target

3. Verify: `PYTHONPATH=src python3 -m pytest tests/tools/test_semantic_search_6f.py -v`

### Phase F3: Fix ContextInjector Callgraph Stub
**~30min | 2 files**

1. In `src/ast_tools/context/injector.py`:
   - Replace lines ~196-197:
     ```python
     # Callgraph depth — placeholder
     callgraph_score = 0.5
     ```
     With:
     ```python
     # Callgraph centrality from dependency_metrics (10%)
     callgraph_score = self._get_centrality_score(symbol.id)\
         if hasattr(symbol, 'id') else 0.5
     ```
   - Add private method:
     ```python
     def _get_centrality_score(self, symbol_id: str) -> float:
         """Read centrality from dependency_metrics. Normalized to [0,1]."""
         try:
             with database_context(self.db_path) as conn:
                 row = conn.execute(
                     "SELECT centrality FROM dependency_metrics WHERE symbol_id = ?",
                     (symbol_id,)
                 ).fetchone()
                 if row and row['centrality'] is not None:
                     return min(1.0, float(row['centrality']))
         except Exception:
             pass
         return 0.5  # fallback
     ```

2. Create `tests/context/test_injector_rrf.py`:
   - Test `_get_centrality_score` returns value from DB
   - Test `_get_centrality_score` returns 0.5 when symbol not in dependency_metrics
   - Test `_get_centrality_score` returns 0.5 when table doesn't exist (graceful)
   - Test integration: relevance_score uses real centrality

3. Verify: `PYTHONPATH=src python3 -m pytest tests/context/test_injector_rrf.py -v`

**Note:** Phase F4 (switch ContextInjector to RRF) scoped as P2 — deferred unless approved. Current weighted-sum approach has merit (intuitive weights, easier to debug). RRF would make it consistent with semantic_search but changes scoring behavior. User decision needed.

### Phase F5: Documentation Update
**~1h | 5 files**

1. `README.md`: Update feature bullet from "Hybrid search: 6-factor semantic + keyword fusion (RRF)" to accurate description:
   - "**Hybrid search**: True 6-factor RRF fusion — FTS5 keyword + vector semantic + recency + usage frequency + symbol kind + callgraph centrality. Fused via Reciprocal Rank Fusion (k=60) for robust multi-dimension ranking."

2. `docs/AST_TOOLS_QUICKSTART.md`: Update semantic_search docs to mention all 6 factors. Update the "Features" section. Update the tool count verification line.

3. `docs/SESSION_STATE.md`: Add Phase 6F entry in the phase table.

4. `docs/DOCUMENTATION_INDEX.md`: Add Phase 6F spec and plan entries.

5. `CHANGELOG.md`: Add under Unreleased:
   ```markdown
   - **True 6-factor RRF**: semantic_search now fuses FTS5 + vector + recency + usage + kind + callgraph centrality
   - **Fixed ContextInjector**: callgraph factor reads real centrality from DB (was hardcoded 0.5 stub)
   ```

### Phase F6: Test Suite Final Verification
**~30min**

1. Run full test suite: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
2. Verify 686+ tests pass with no regressions
3. Verify performance: `semantic_search` k=10 < 150ms

---

## TDD Test Plan

| Test File | Tests | Type |
|-----------|-------|------|
| `tests/tools/test_rrf.py` | rrf_fuse correctness, empty lists, ties, rank_symbols, k parameter | Unit |
| `tests/tools/test_semantic_search_6f.py` | 2-factor regression, 6-factor results, per-factor boosts, graceful degradation, perf | Integration |
| `tests/context/test_injector_rrf.py` | _get_centrality_score, fallback values, integration with relevance_score | Integration |

---

## Rollback Plan

Each phase commits independently for rollback safety:

| Commit | Contents | Rollback |
|--------|----------|----------|
| `F1: feat: shared RRF utility` | utils/rrf.py + tests | `git revert <sha>` |
| `F2: feat: 6-factor semantic_search` | semantic_search.py + tests | `git revert <sha>` |
| `F3: fix: ContextInjector callgraph stub` | injector.py + tests | `git revert <sha>` |
| `F5: docs: update for 6-factor RRF` | README, quickstart, session state, changelog | `git revert <sha>` |

If anything breaks, `git revert` the offending commit. All phases are independent — reverting F2 doesn't affect F1.

---

## Forward Audit Checklist

- [ ] `utils/rrf.py` does NOT duplicate existing RRF logic (extracts from semantic_search.py)
- [ ] RRF k=60 justification: standard literature value for 6+ dimensions; current k=1.5 was for 2-factor
- [ ] No circular imports: utils/ doesn't import from tools/ or context/
- [ ] `dependency_metrics.centrality` is the correct column (verified against schema.py)
- [ ] Graceful degradation handles missing tables, missing rows, NULL values
- [ ] Performance: each new factor = 1 DB query. 6-factor = 6 queries vs 2 before. But these are cheap sorted index scans, not full table scans.

## Reverse Audit Checklist

- [ ] Any other code that uses RRF inline? If yes, migrate to shared utility.
- [ ] Any doc pages that describe semantic_search differently? Cross-check all 19 active docs.
- [ ] `ContextInjector` has `_get_centrality_score` import path issue: `database_context` needs proper import.
- [ ] Does `injector.py` already have access to `self.db_path`? Verify constructor.
- [ ] Pre-existing 7 CLI test failures — do they interact with RRF at all? Should not, they're CLI-format tests.