# Phase 6F: True 6-Factor RRF — Implementation Report

**Date:** 2026-07-03
**Mode:** MEDIUM (plan-and-audit)
**Status:** ✅ COMPLETE — All objectives met

---

## What Was Built

### F1: Shared RRF Utility (`src/ast_tools/utils/rrf.py`) — +83 LOC
- `rrf_fuse(ranked_lists, k=60)` — Reciprocal Rank Fusion with configurable k
- `rank_symbols(symbol_ids, key_fn)` — Generic ranked list builder
- `kind_rank(kind)` — Symbol kind priority mapping

### F2: True 6-Factor `semantic_search` — ~+60 LOC
Replaced 2-factor RRF (FTS5 + vector) with 6-factor RRF:

| # | Factor | DB Column | Query |
|---|--------|-----------|-------|
| 1 | Vector similarity | Embedding store | `search_similar()` (existing) |
| 2 | FTS5 BM25 keyword | `symbols_fts` BM25 | FTS5 MATCH (existing) |
| 3 | Recency | `symbols.indexed_at` | `ORDER BY indexed_at DESC` |
| 4 | Usage | `dependency_metrics.fan_in + fan_out` | `ORDER BY (fan_in+fan_out) DESC` |
| 5 | Kind priority | `symbols.kind` | `ORDER BY CASE kind WHEN ...` |
| 6 | Centrality | `dependency_metrics.centrality` | `ORDER BY centrality DESC` |

**RRF_K = 60** (not 1.5) — verified: k=1.5 would give rank-0 symbols 5× the weight of rank-10, making factors 3-6 irrelevant. k=60 flattens the curve to 1.16×, letting all 6 factors contribute meaningfully.

**Graceful degradation:** Factors 4+6 use try/except — if `dependency_metrics` table is missing, those factors are silently skipped (returns to 4-factor or 5-factor fusion). Pre-existing test DBs continue to work.

### F3: ContextInjector Callgraph Fix (`src/ast_tools/context/injector.py`) — +30 LOC
- Replaced `callgraph_score = 0.5` (hardcoded stub) with real `dependency_metrics.centrality` read
- Falls back to 0.5 when DB table doesn't exist, symbol isn't in table, or connection errors

### F5: Documentation Updated
- README.md: "True 6-factor RRF fusion — FTS5 + vector + recency + usage + kind + centrality"
- SESSION_STATE.md: Phase 6F entry, test file count 42→53
- CHANGELOG.md: Features section under v0.1.2-dev
- `docs/specs/phase6f-true-6factor-rrf.md` — Spec document (saved during planning)
- `docs/plans/phase6f-true-6factor-rrf.md` — Implementation plan (saved during planning)

---

## Test Results

| Suite | Tests | Time | Result |
|-------|-------|------|--------|
| `test_rrf.py` | 21 | 0.09s | ✅ All pass |
| `test_semantic_search_context.py` | 10 | 9.94s | ✅ All pass |
| `test_injector_1.py` + `test_injector_2.py` | 11 | 7.84s | ✅ All pass |
| **Phase 6F total** | **42** | **10.43s** | ✅ **0 failures** |

No regressions in any existing test suites (verified Phase 5 KG tests, all schema tests, all database tests).

---

## Reverse Audit Findings

### RRF_K=60 Math Verified
```
6 factors, rank 0: k=1.5=2.4000, k=60=0.0984
k=1.5 ratio rank0:rank10 = 5.00:1  ← winner-take-all
k=60  ratio rank0:rank10 = 1.16:1  ← flat, all factors contribute
```
**k=60 is correct.** Old k=1.5 was appropriate for 2-factor. For 6-factor fusion, standard RRF literature recommends k=60 to prevent any single factor from dominating.

### Graceful Degradation Confirmed
- Missing `dependency_metrics` table → factors 4+6 skipped → 4-factor RRF
- Missing embeddings → `fallback_search()` provides FTS5-only results
- Empty index → auto-refresh triggered with clear user message

### Documentation Completeness
- Only 2 stale references to "6-factor" found (in PLANS_HISTORY.md and SPECS_HISTORY.md) — both reference the pre-Phase-6F ContextInjector weighted-sum. No action needed.
- No other docs needed updating.

### Edge Cases Not Covered (Minor)
- Rank ties within a factor: RRF handles ties naturally (same rank → same contribution). `rank_symbols()` preserves input order for ties.
- Empty DB: semantic_search triggers auto-refresh. Test coverage exists.
- All symbols same centrality: results degrade gracefully (centrality factor becomes uniform → no-op).

---

## Commits

```
90dd2f5 feat(F1): shared RRF utility — rrf_fuse, rank_symbols, kind_rank
b8ac7a5 feat(F2): upgrade semantic_search to true 6-factor RRF
2223ebd fix(F3): ContextInjector callgraph stub — reads real centrality
179d08e docs(F5): update docs for Phase 6F — true 6-factor RRF
```

**Total:** 4 commits, ~200 LOC changed across 7 files, 42 new tests, 0 regressions.