# Forward Audit: Phase 9 Schema Enrichments

**Date:** 2026-07-24  
**Auditor:** Lucien (inline)  
**Mode:** HIGH  
**Scope:** Validate spec → implementation feasibility

---

## 1. Current State Assessment

### 1.1 Database Schema (v4)

**Existing tables:**
- `symbols` — Core symbol table with lang, kind, signature, docstring
- `symbols_fts` — FTS5 full-text search
- `symbols_vec` — sqlite-vec for 384-dim embeddings (Phase 2)
- `edges` — Callgraph edges (calls, imports, inherits, instantiates)
- `file_cache` — Content-hash tracking
- `schema_version` — Version tracking (current: v4)

**✅ Good news:** The `edges` table already exists! Phase 9 callgraph work is **partially implemented**.

### 1.2 Existing Tools (28 tools registered)

From `src/ast_tools/tools/__init__.py`:
- Core: `ast_grep`, `ast_edit`, `ast_read`, `structural_analysis`, `impact_analysis`, `module_imports`
- Search: `search_symbols`, `semantic_search`, `find_references`, `list_symbols`
- **Dependency tools:** `circular_dependencies`, `external_dependencies`, `dead_code_detection`, `dependency_chain`, `api_surface_diff`
- Index: `refresh_index`, `index_status`, `watch_add`, `watch_status`, `reindex_path`
- Curator: `curator_audit`, `curator_summary`, `curator_status`

**✅ Good news:** Dependency analysis tools already exist (`dependency.py`, `dependency_tools.py`).

### 1.3 Embeddings Infrastructure

From `src/ast_tools/embeddings/`:
- `model.py` — Embedding model wrapper (BGE-small-en-v1.5)
- `store.py` — Embedding storage/retrieval
- `__init__.py` — Public API

**✅ Good news:** Embeddings infrastructure is complete (Phase 2).

---

## 2. Gap Analysis: Spec vs. Current State

### 2.1 Callgraph Edges

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Edge types: calls, imports, inherits, implements | ✅ Has: calls, imports, inherits, instantiates | ⚠️ `implements` missing, `instantiates` ≠ `implements` |
| Resolved symbol IDs (source_id, target_id) | ✅ Both exist | OK |
| Edge metadata (JSON) | ❌ No metadata column | **NEW: ADD COLUMN** |
| API: callgraph callers/callees | ⚠️ Partial (dependency_tools.py) | **ENHANCE** |
| API: cycle detection | ✅ `circular_dependencies` tool exists | OK |

**Migration needed:**
```sql
-- Add metadata column to edges
ALTER TABLE edges ADD COLUMN metadata JSON;

-- Add edge_type 'implements'
-- SQLite CHECK constraints can't be modified, so we need to recreate the table
-- OR use a pragmatic approach: insert 'implements' and update CHECK via migration

-- Alternative: Create new callgraph_edges table (Phase 9 spec approach)
```

**Recommendation:** Keep existing `edges` table, add `metadata` column, add `implements` to edge_type CHECK. Create `callgraph_edges` as a **view** over `edges` for backward compatibility.

### 2.2 Dependency Metrics

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Fan-in/fan-out | ⚠️ Implicit in `edges` table | **COMPUTE + CACHE** |
| SPOF score | ❌ Not computed | **NEW TABLE** |
| Instability metric | ❌ Not computed | **NEW TABLE** |
| PageRank centrality | ❌ Not computed | **NEW TABLE** |
| API: dependencies tool | ✅ `dependency_chain` exists | **ENHANCE** |
| API: SPOF analysis | ❌ Not implemented | **NEW TOOL** |

**Migration needed:**
```sql
CREATE TABLE dependency_metrics (
    symbol_id TEXT PRIMARY KEY,
    fan_in INTEGER DEFAULT 0,
    fan_out INTEGER DEFAULT 0,
    spof_score REAL DEFAULT 0.0,
    instability REAL DEFAULT 0.0,
    centrality REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE INDEX idx_dependency_spof ON dependency_metrics(spof_score DESC);
```

### 2.3 Embedding Similarity

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Embeddings in symbols | ✅ `symbols_vec` table exists | OK |
| Precomputed cosine similarity | ❌ Not cached | **NEW TABLE** |
| KNN graph | ❌ Not built | **NEW TABLE** |
| API: similar symbols | ❌ Not implemented | **NEW TOOL** |
| API: batch embedding compute | ⚠️ `store.py` has basic support | **ENHANCE** |

**Migration needed:**
```sql
CREATE TABLE embedding_similarity (
    symbol_id_1 TEXT NOT NULL,
    symbol_id_2 TEXT NOT NULL,
    cosine_similarity REAL NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id_1, symbol_id_2),
    FOREIGN KEY (symbol_id_1) REFERENCES symbols(id),
    FOREIGN KEY (symbol_id_2) REFERENCES symbols(id)
);

CREATE TABLE knn_graph (
    symbol_id TEXT NOT NULL,
    neighbor_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    similarity REAL NOT NULL,
    PRIMARY KEY (symbol_id, neighbor_id),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (neighbor_id) REFERENCES symbols(id)
);
```

### 2.4 Performance Optimization

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Batch inserts | ⚠️ Some use executemany | **AUDIT + FIX** |
| Index strategies | ⚠️ Basic indexes exist | **OPTIMIZE** |
| Query optimization | ❌ Not profiled | **PROFILE + FIX** |
| sqlite-vec F32_BLOB | ✅ Using vec0 (correct) | OK |

**No migration needed** — code changes only.

---

## 3. Feasibility Assessment

### 3.1 Technical Feasibility: ✅ HIGH

**Why feasible:**
- Existing `edges` table covers 75% of callgraph requirements
- Dependency tools already exist (`dependency_tools.py`, 12K+ lines)
- Embeddings infrastructure complete (Phase 2)
- sqlite-vec already integrated
- Schema migration framework in place (`register_migration` decorator)

**Challenges:**
1. **Edge type CHECK constraint** — SQLite can't modify CHECK constraints. Need to either:
   - Recreate `edges` table (risky, requires data copy)
   - Use trigger-based validation (cleaner)
   - Create new `callgraph_edges` table (per spec, but duplicates data)
   
   **Recommendation:** Use trigger-based validation. Add a trigger that rejects invalid edge_types.

2. **KNN graph computation** — O(n²) for all-pairs similarity. For 1M symbols:
   - Naive: 1T comparisons (impossible)
   - **Solution:** Use faiss or hnswlib for approximate nearest neighbors (ANN)
   - Alternative: Chunked computation (10K symbols/batch, 100 batches)

3. **Performance targets** — p50 <50ms for similarity search:
   - Requires precomputed KNN graph
   - Index on `knn_graph(symbol_id, rank)`
   - Query: `SELECT * FROM knn_graph WHERE symbol_id = ? ORDER BY rank LIMIT 10`

### 3.2 Implementation Effort

| Wave | Files | Estimated Time | Risk |
|------|-------|----------------|------|
| Wave 1: Schema + Migrations | 4 | 1-2h | Low |
| Wave 2: Callgraph Edges | 6 | 2-3h | Low (existing infrastructure) |
| Wave 3: Dependency Metrics | 5 | 2h | Low-Medium (PageRank computation) |
| Wave 4: Embedding Similarity | 6 | 3-4h | Medium (KNN graph computation) |
| Wave 5: Performance | 3 | 2h | Medium (requires profiling) |
| Wave 6: Documentation | 4 | 1-2h | Low |

**Total:** 10-14 hours (reasonable for HIGH mode)

### 3.3 Backward Compatibility

**Impact:** Minimal

- Existing tools continue to work (no breaking changes)
- `edges` table enhanced (not replaced)
- New tables are additive
- Old queries unaffected

**Migration strategy:**
1. Add `metadata` column to `edges` (non-breaking ALTER)
2. Create `dependency_metrics`, `embedding_similarity`, `knn_graph` tables (additive)
3. Enhance existing tools (backward-compatible API)

---

## 4. Risk Register

### 4.1 High-Priority Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| KNN graph computation OOM | Medium | High | Chunked processing (10K symbols/batch), use hnswlib for ANN |
| Edge type validation breaks existing code | Low | High | Use trigger-based validation (graceful, not hard CHECK) |
| PageRank computation slow | Medium | Medium | Limit to top-1000 symbols by fan-in, or use iterative approximation |
| Similarity search >50ms p95 | Medium | Medium | Precompute KNN, use indexes, cache hot queries |

### 4.2 Medium-Priority Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration 009 fails on existing DB | Low | Medium | Test on copy of production DB, have rollback script |
| Embedding model unloadable (CPU) | Low | Medium | Fallback to keyword-only similarity (FTS5 + BM25) |
| Foreign key constraints break inserts | Low | Low | Enable FK after data loaded, or use DEFERRED constraints |

---

## 5. Recommended Implementation Adjustments

### 5.1 Schema Changes (Adjusted from Spec)

**Keep existing `edges` table**, enhance it:
```sql
-- Add metadata column
ALTER TABLE edges ADD COLUMN metadata JSON;

-- Add trigger for edge_type validation (allows 'implements' in addition to existing)
CREATE TRIGGER IF NOT EXISTS validate_edge_type
BEFORE INSERT ON edges
BEGIN
    SELECT CASE
        WHEN NEW.edge_type NOT IN ('calls', 'imports', 'inherits', 'instantiates', 'implements')
        THEN RAISE(ABORT, 'Invalid edge_type')
    END;
END;
```

**Create new tables:**
```sql
-- dependency_metrics (as per spec)
-- embedding_similarity (as per spec)
-- knn_graph (as per spec)
```

### 5.2 Tool Adjustments

**Reuse existing tools:**
- `circular_dependencies` → rename to `detect_cycles` (alias)
- `dependency_chain` → enhance with fan-in/fan-out
- Add new: `spof_analysis`, `similarity_search`, `knn_compute`

**Why:** Minimizes code duplication, preserves backward compatibility.

### 5.3 KNN Graph Strategy

**Spec approach:** Precompute all-pairs similarity  
**Problem:** O(n²) for 1M symbols = 1T comparisons

**Adjusted approach:**
1. **Approximate Nearest Neighbors (ANN)** — Use `hnswlib` or `faiss`
   - Build index once (<30min for 1M symbols)
   - Query: <10ms per symbol
   - Memory: ~500MB for 1M symbols × 384 dim

2. **Chunked exact computation** (fallback if ANN unavailable)
   - Process 10K symbols/batch
   - Total time: ~60min for 1M symbols
   - Memory: <2GB

**Recommendation:** Use hnswlib (MIT license, pip-installable).

---

## 6. Success Criteria (Adjusted)

### 6.1 Migration Success
- [ ] Migration 009 applied without errors
- [ ] Rollback tested on staging DB
- [ ] Existing tools continue to work
- [ ] New tables created with correct schema

### 6.2 Feature Success
- [ ] Callgraph API: callers/callees <10ms p50
- [ ] Dependency metrics: fan-in/out computed for all symbols
- [ ] SPOF analysis: identifies top-20 SPOFs correctly
- [ ] Similarity search: <50ms p50, <200ms p95
- [ ] KNN graph: built for entire codebase (<60min)

### 6.3 Test Success
- [ ] 90%+ code coverage
- [ ] All tests pass (pytest -v)
- [ ] Performance benchmarks meet targets
- [ ] No memory leaks (<2GB peak)

---

## 7. Go/No-Go Decision

**Verdict:** ✅ **GO**

**Rationale:**
- 75% of infrastructure already exists (edges, embeddings, dependency tools)
- Spec is well-defined and feasible
- Risks are manageable with mitigations
- Backward compatibility preserved
- Estimated effort (10-14h) is reasonable for HIGH mode

**Recommended adjustments:**
1. Use trigger-based edge_type validation (not CHECK constraint recreation)
2. Use hnswlib for KNN graph (not naive all-pairs similarity)
3. Reuse existing dependency tools (enhance, don't duplicate)
4. Chunked KNN computation as fallback

**Ready for implementation with these adjustments.**

---

## 8. Open Questions

1. **Edge type semantics:** Is `instantiates` (existing) different from `implements` (new)? 
   - `instantiates`: `obj = MyClass()` → runtime instantiation
   - `implements`: `class C(Protocol)` → structural conformance
   - **Recommendation:** Keep both, they're different relationships

2. **KNN graph update strategy:** How often to recompute?
   - Options: On every index refresh (expensive), or on-demand (lazy)
   - **Recommendation:** Lazy recompute — mark KNN as stale, recompute on first query after freshness threshold (default: 24h)

3. **PageRank scope:** Compute for all symbols or subset?
   - All symbols: Expensive (1M nodes), but accurate
   - Top-10K by fan-in: Fast, captures most important symbols
   - **Recommendation:** Iterative approximation (100 iterations max), all symbols, cached

---

**Forward audit complete. Implementation can proceed with adjustments noted above.**