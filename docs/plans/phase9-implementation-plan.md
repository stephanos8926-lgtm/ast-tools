# Phase 9 Schema Enrichments: Implementation Plan

**Version:** 1.0  
**Date:** 2026-07-24  
**Mode:** HIGH (20+ files, public API, schema migration, performance-critical)  
**Status:** Ready for Implementation

---

## 1. Specification Summary

From `docs/phase9-spec.md` (601 lines):

### 9.1 New Capabilities

| Feature | Description | Impact |
|---------|-------------|--------|
| **Callgraph Edges** | 4 types: `calls`, `imports`, `inherits`, `implements` | Core architecture understanding |
| **Dependency Tracking** | Fan-in/fan-out metrics, circular detection via DFS | Impact analysis, SPOF detection |
| **Embedding Similarity** | Precomputed cosine matrix, KNN graph (k=10) | "Find similar code" queries |
| **Schema Extensions** | New tables: `callgraph_edges`, `dependency_metrics`, `embedding_similarity` | Database migration required |
| **API Endpoints** | 6 new tools: `/callgraph`, `/dependencies`, `/similar`, `/cycles`, `/embeddings/compute`, `/embeddings/batch` | Enhanced MCP tool surface |
| **Performance Targets** | Index <60min (1M files), Query p50 <50ms, p95 <200ms, p99 <500ms | Infrastructure requirements |

### 9.2 Database Migration (Migration 009)

**New Tables:**
```sql
CREATE TABLE callgraph_edges (
    id INTEGER PRIMARY KEY,
    source_symbol_id INTEGER NOT NULL,
    target_symbol_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('calls', 'imports', 'inherits', 'implements')),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (target_symbol_id) REFERENCES symbols(id),
    UNIQUE(source_symbol_id, target_symbol_id, edge_type)
);

CREATE TABLE dependency_metrics (
    symbol_id INTEGER PRIMARY KEY,
    fan_in INTEGER DEFAULT 0,
    fan_out INTEGER DEFAULT 0,
    sPOF_score REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE TABLE embedding_similarity (
    symbol_id_1 INTEGER NOT NULL,
    symbol_id_2 INTEGER NOT NULL,
    cosine_similarity REAL NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id_1, symbol_id_2),
    FOREIGN KEY (symbol_id_1) REFERENCES symbols(id),
    FOREIGN KEY (symbol_id_2) REFERENCES symbols(id)
);

CREATE INDEX idx_embedding_sim ON embedding_similarity(symbol_id_1, cosine_similarity DESC);
```

### 9.3 New API Endpoints

```python
# New MCP tools in src/ast_tools/tools/
callgraph.py          # /callgraph, /callgraph/callees, /callgraph/callers
dependencies.py       # /dependencies, /cycles
similarity.py         # /similar, /embeddings/compute, /embeddings/batch
```

---

## 2. Implementation Roadmap

### Wave 1: Schema + Migrations (Files: 4)
**Duration:** 1-2 hours  
**Dependencies:** None

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/db/migrations/009_schema_enrichments.py` | CREATE | ~200 |
| `src/ast_tools/db/schema.py` | PATCH (add new tables) | +50 |
| `tests/db/test_migration_009.py` | CREATE | ~100 |
| `tests/db/test_schema_enrichments.py` | CREATE | ~150 |

**Success Criteria:**
- [ ] Migration 009 applied successfully
- [ ] New tables exist with correct schema
- [ ] Indexes created (idx_embedding_sim, idx_callgraph_edge_type)
- [ ] Foreign key constraints enforced
- [ ] Rollback tested

### Wave 2: Callgraph Edges (Files: 6)
**Duration:** 2-3 hours  
**Dependencies:** Wave 1 complete

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/callgraph.py` | CREATE | ~300 |
| `src/ast_tools/analysis/callgraph_builder.py` | CREATE | ~250 |
| `tests/tools/test_callgraph.py` | CREATE | ~200 |
| `tests/analysis/test_callgraph_builder.py` | CREATE | ~150 |
| `docs/callgraph-edges.md` | CREATE | ~100 |
| `src/ast_tools/tools/__init__.py` | PATCH (register new tools) | +20 |

**Tools:**
1. `ast_grep_callgraph` — Build callgraph for project
2. `ast_callgraph_callees` — What does X call?
3. `ast_callgraph_callers` — Who calls X?

**Success Criteria:**
- [ ] Callgraph edges extracted via AST traversal
- [ ] 3 tools functional with correct output
- [ ] Tests pass (90%+ coverage)
- [ ] Performance: <10sec for 10K file project

### Wave 3: Dependency Tracking (Files: 5)
**Duration:** 2 hours  
**Dependencies:** Wave 2 (shares callgraph infrastructure)

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/dependencies.py` | CREATE | ~250 |
| `src/ast_tools/analysis/dependency_tracker.py` | CREATE | ~200 |
| `tests/tools/test_dependencies.py` | CREATE | ~150 |
| `docs/dependency-tracking.md` | CREATE | ~80 |
| `src/ast_tools/tools/__init__.py` | PATCH | +10 |

**Tools:**
1. `ast_dependencies` — Get fan-in/fan-out for symbol
2. `ast_detect_cycles` — Find circular dependencies
3. `ast_spof_analysis` — Identify single points of failure

**Success Criteria:**
- [ ] Fan-in/fan-out computed correctly
- [ ] Cycle detection via DFS (Tarjan's or similar)
- [ ] SPOF score calculated (high fan-in + low fan-out = SPOF)
- [ ] Tests pass

### Wave 4: Embedding Similarity (Files: 6)
**Duration:** 3-4 hours  
**Dependencies:** Wave 1 (schema), Wave 3 (optional)

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/similarity.py` | CREATE | ~300 |
| `src/ast_tools/embeddings/similarity_engine.py` | CREATE | ~350 |
| `src/ast_tools/embeddings/batch_computer.py` | CREATE | ~200 |
| `tests/tools/test_similarity.py` | CREATE | ~200 |
| `tests/embeddings/test_similarity_engine.py` | CREATE | ~150 |
| `docs/similarity-search.md` | CREATE | ~100 |

**Tools:**
1. `ast_similar` — Find similar code (by semantic similarity)
2. `ast_embeddings_compute` — Compute embeddings for symbols
3. `ast_embeddings_batch` — Batch compute embeddings

**Implementation Notes:**
- Use local transformer: `BAAI/bge-small-en-v1.5` (384 dim, CPU-only)
- Embeddings cached in `symbols.embeddings` (existing column)
- Similarity precomputed and cached in `embedding_similarity` table
- KNN graph: k=10 nearest neighbors per symbol

**Success Criteria:**
- [ ] Embeddings generated correctly (384-dim vectors)
- [ ] Cosine similarity computed accurately
- [ ] KNN graph built for entire codebase
- [ ] Query: <50ms p50 latency
- [ ] Batch compute: <60min for 1M symbols

### Wave 5: Performance Optimization (Files: 3)
**Duration:** 2 hours  
**Dependencies:** Waves 1-4

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/optimization/index_tuner.py` | CREATE | ~150 |
| `src/ast_tools/optimization/query_optimizer.py` | CREATE | ~200 |
| `tests/optimization/test_performance.py` | CREATE | ~100 |

**Optimizations:**
1. **Batch inserts** — Use `executemany` for migrations
2. **Index strategies** — Partial indexes, covering indexes
3. **Query optimization** — Use CTEs, avoid N+1 queries
4. **sqlite-vec integration** — Ensure F32_BLOB storage, not TEXT

**Success Criteria:**
- [ ] Index build time: <60min for 1M symbols
- [ ] Query p50: <50ms, p95: <200ms, p99: <500ms
- [ ] Memory: <500MB peak during indexing

### Wave 6: Documentation + Integration (Files: 4)
**Duration:** 1-2 hours  
**Dependencies:** Waves 1-5

| File | Action | Lines |
|------|--------|-------|
| `docs/phase9-implementation-guide.md` | CREATE | ~300 |
| `docs/api-reference/enrichments.md` | CREATE | ~200 |
| `QUICKSTART_PHASE9.md` | CREATE | ~100 |
| `src/ast_tools/README.md` | PATCH (add new tools reference) | +50 |

---

## 3. Test Strategy

### Unit Tests
- Migration 009: Schema validation, FK constraints
- Callgraph builder: Edge extraction accuracy
- Dependency tracker: Fan-in/out, cycle detection
- Similarity engine: Cosine similarity, KNN graph

### Integration Tests
- End-to-end tool calls (MCP endpoints)
- Performance benchmarks
- Memory profiling

### Acceptance Criteria
- [ ] 90%+ code coverage
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance targets met
- [ ] No memory leaks (>500MB peak)

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration 009 breaks existing DB | Low | High | Rollback script, backup before migration |
| Performance targets not met | Medium | Medium | Profile early, optimize hot paths |
| sqlite-vec integration issues | Medium | High | Fallback to pure SQLite + FTS5 |
| Circular dependency detection slow | Low | Low | DFS with memoization, early exit |
| Embedding batch compute OOM | Medium | Medium | Chunked processing (10K symbols/batch) |

**Rollback Plan:**
```bash
# If Migration 009 fails:
cp ~/.ast-tools/ast-tools.db ~/.ast-tools/ast-tools.db.bak
# Restore from backup if needed:
cp ~/.ast-tools/ast-tools.db.bak ~/.ast-tools/ast-tools.db
```

---

## 5. Verification Checklist

Before claiming Phase 9 complete:

- [ ] All 6 new tools functional (`ast_callgraph_*`, `ast_dependencies`, `ast_detect_cycles`, `ast_similar`, `ast_embeddings_*`)
- [ ] Migration 009 applied successfully
- [ ] Indexes created and verified
- [ ] Performance benchmarks meet targets
- [ ] 90%+ test coverage
- [ ] Documentation complete
- [ ] Backward compatibility verified (old queries still work)
- [ ] Rollback tested on staging data

---

## 6. Implementation Order

**Recommended sequence:**

1. **Wave 1** (Schema + Migrations) — Foundation
2. **Wave 2** (Callgraph) — Core capability
3. **Wave 3** (Dependencies) — Builds on callgraph
4. **Wave 4** (Similarity) — Independent, but needs schema
5. **Wave 5** (Optimization) — After features work
6. **Wave 6** (Docs) — Final polish

**Parallel execution:** Waves 2 + 4 could run in parallel (independent), but Wave 3 depends on Wave 2.

---

## 7. Git Strategy

**Branch:** `feature/phase9-schema-enrichments`

**Commits:**
- `feat: Phase 9 — Migration 009 (schema enrichments)` — Wave 1
- `feat: Add callgraph edge extraction + tools` — Wave 2
- `feat: Add dependency tracking + cycle detection` — Wave 3
- `feat: Add embedding similarity + KNN graph` — Wave 4
- `perf: Optimize indexing + query performance` — Wave 5
- `docs: Add Phase 9 implementation guide + API reference` — Wave 6

**PR:** Single PR with 6 commits (or 6 smaller PRs if preferred)

---

## 8. Sign-off Required

**Before implementation begins:**

- [ ] Spec reviewed and understood
- [ ] Forward audit completed
- [ ] Reverse audit completed (if dispatched)
- [ ] Synthesis plan approved
- [ ] Mode: HIGH confirmed
- [ ] TDD approach understood (tests FIRST)

**User sign-off:** `Confirmed, proceed with HIGH mode — Steven`

---

## 9. Implementation Notes

**TDD Enforcement (HIGH mode):**
- Write failing test FIRST
- Implement minimum to pass test
- Refactor (if needed)
- Repeat for each feature

**Inline vs. Subagent:**
- **Inline:** Waves 1, 2, 3 (complex, core infrastructure)
- **Subagent:** Waves 4, 5, 6 (can be parallelized, less critical)

**Estimated Total Duration:** 10-14 hours
- Wave 1: 1-2h
- Wave 2: 2-3h
- Wave 3: 2h
- Wave 4: 3-4h
- Wave 5: 2h
- Wave 6: 1-2h

**Critical Path:** Waves 1 → 2 → 3 → 4 → 5 → 6

---

**Ready for implementation.**