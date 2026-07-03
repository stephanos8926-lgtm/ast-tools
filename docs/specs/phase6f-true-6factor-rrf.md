# Phase 6F: True 6-Factor RRF — SPEC v1

**Date:** 2026-07-03  
**Mode:** MEDIUM (plan-and-audit)  
**Author:** Lucien  
**Status:** Draft — pending audits + sign-off  

---

## Problem Statement

The project claims "6-factor hybrid search (RRF)" in docs, README, and marketing. This claim is **partially false**:

1. **`semantic_search` MCP tool** — uses only **2-factor RRF** (FTS5 BM25 keyword + vector cosine). Factors 3-6 (recency, usage, kind, callgraph) are never consulted.

2. **`ContextInjector`** — defines 6 weighted factors but **callgraph depth is a hardcoded `0.5` stub** — always returns the same score regardless of actual callgraph data. Additionally, it uses **weighted linear sum**, not RRF (which is a different fusion method: `Σ 1/(rank_i + k)` vs `Σ weight_i × score_i`).

3. **The irony:** All 6 data dimensions already exist or are computable from the database:
   - `symbols.indexed_at` → recency ranking
   - `dependency_metrics.fan_in + fan_out` → usage ranking (total connections = importance)
   - `symbols.kind` → kind-priority ranking
   - `dependency_metrics.centrality` → callgraph centrality ranking
   - Vector embeddings → semantic similarity
   - FTS5 BM25 → keyword relevance

**Nobody wired them into the ranking.** This spec closes that gap.

---

## Goals

| ID | Priority | Description | Effort |
|----|----------|-------------|--------|
| F1 | P0 | Extract RRF fusion into shared utility (`utils/rrf.py`) | ~1h |
| F2 | P0 | Add factors 3-6 (recency, usage, kind, centrality) to `semantic_search` | ~2h |
| F3 | P1 | Fix `ContextInjector` callgraph stub — read real centrality from DB | ~30min |
| F4 | P2 | Option: switch `ContextInjector` from weighted sum to RRF | ~2h |
| F5 | P0 | Update documentation to accurately describe 6-factor RRF | ~1h |
| F6 | P0 | Tests: each factor independently + fusion + edge cases | ~2h |

**Total: ~8.5h** (F1+F2+F5+F6 = ~6h for P0, + F3=30min P1, + F4=2h P2)

---

## Compatibility & Behavior Rules

1. **RRF formula** (standardized): `score(symbol) = Σ 1 / (rank_i(symbol) + k)` for factors i=1..6  
   - `k = 60` (standard RRF constant for high-dimensional fusion; current `RRF_K = 1.5` is for 2-factor which won't work for 6-factor — see note in plan)
   
2. **Existing behavior preserved:** `semantic_search` without the new factors must produce identical results. The new factors are additive — they boost symbols that would have been at lower positions.

3. **Graceful degradation:** If `dependency_metrics` table is empty (no centrality data), callgraph factor degrades to uniform 0.5 (no-op). Never error.

4. **Performance:** Each new factor adds 1 DB query + 1 sort pass. Total should stay under 150ms for k=10 queries.

5. **`ContextInjector` must remain backward compatible** — fix the stub only, don't break the existing weighted-sum API unless F4 is approved.

---

## File Manifest

| File | Action | Description | Est LOC |
|------|--------|-------------|---------|
| `src/ast_tools/utils/rrf.py` | **CREATE** | Shared RRF utility: `rrf_fuse(ranked_lists, k)`, `rank_symbols(symbols, key_func)` | ~80 |
| `src/ast_tools/tools/semantic_search.py` | MODIFY | Replace inline RRF with call to `utils/rrf.py`, add factors 3-6 | ~+60/-20 |
| `src/ast_tools/context/injector.py` | MODIFY | Replace `callgraph_score = 0.5` stub with real DB read from `dependency_metrics.centrality` | ~+30/-5 |
| `docs/specs/phase6f-true-6factor-rrf.md` | CREATE | This spec | ~80 |
| `docs/plans/phase6f-true-6factor-rrf.md` | CREATE | Implementation plan | ~80 |
| `tests/tools/test_rrf.py` | **CREATE** | Unit tests for RRF utility | ~150 |
| `tests/tools/test_semantic_search_6f.py` | **CREATE** | Integration tests for 6-factor semantic_search | ~150 |
| `tests/context/test_injector_rrf.py` | **CREATE** | Tests for fixed ContextInjector callgraph | ~80 |
| `README.md` | MODIFY | Update 6-factor RRF description | ~+10/-5 |
| `docs/AST_TOOLS_QUICKSTART.md` | MODIFY | Update semantic_search docs | ~+10/-5 |
| `docs/DOCUMENTATION_INDEX.md` | MODIFY | Add Phase 6F entry | ~+5/-0 |
| `CHANGELOG.md` | MODIFY | Add entry under Unreleased | ~+10/-0 |

---

## Acceptance Criteria

- [ ] `utils/rrf.py` exported: `rrf_fuse(ranked_lists: list[list[str]], k: int = 60) -> dict[str, float]`
- [ ] `semantic_search` uses all 6 factors: FTS5, vector, recency, usage, kind, centrality
- [ ] `semantic_search` results with 2 factors match pre-change results exactly
- [ ] `semantic_search` results with 6 factors are strictly better (relevant symbols ranked higher)
- [ ] `ContextInjector.callgraph_score` reads real `dependency_metrics.centrality` from DB
- [ ] `ContextInjector` falls back to 0.5 when centrality data is missing
- [ ] All 686+ existing tests still pass
- [ ] No performance regression >20% on query time
- [ ] README accurately describes "6-factor hybrid RRF search"
- [ ] Phase 6F added to SESSION_STATE.md and DOCUMENTATION_INDEX.md