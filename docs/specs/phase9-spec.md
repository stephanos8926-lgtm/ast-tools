# Phase 9 Specification: Schema Enrichments

**Version:** 1.0  
**Date:** 2026-07-24  
**Status:** Specification Complete  
**Mode:** HIGH (20+ files, public API, schema migration, performance-critical)

---

## 1. Executive Summary

Phase 9 extends the AST-Tools semantic database with **four major capabilities**:

1. **Callgraph Edges** — Track function calls, imports, inheritance, and implementation relationships
2. **Dependency Metrics** — Compute fan-in/fan-out, detect circular dependencies, identify SPOFs
3. **Embedding Similarity** — Precomputed cosine similarity matrix with KNN graph for "find similar code"
4. **Performance Optimization** — Index build targets (<60min for 1M files), query latency targets (p50 <50ms)

**Impact:** Transforms AST-Tools from structural search → **architectural understanding**. Users can now ask "what depends on this?", "show me similar implementations", "find circular dependencies".

---

## 2. Callgraph Edges

### 2.1 Edge Types

| Type | Description | Example |
|------|-------------|---------|
| `calls` | Function/method invocation | `foo()` → `foo` |
| `imports` | Module import relationship | `from foo import bar` → `bar` |
| `inherits` | Class inheritance | `class Child(Parent)` → `Parent` |
| `implements` | Protocol/interface implementation | `class MyMapper(Mapping)` → `Mapping` |

### 2.2 Database Schema

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

CREATE INDEX idx_callgraph_source ON callgraph_edges(source_symbol_id);
CREATE INDEX idx_callgraph_target ON callgraph_edges(target_symbol_id);
CREATE INDEX idx_callgraph_type ON callgraph_edges(edge_type);
```

### 2.3 Extraction Algorithm

**Calls:**
- AST traversal: `ast.Call` nodes
- Resolve name to symbol via scope analysis
- Handle chained calls: `obj.method()` → `method` on `obj`'s class
- Handle async calls: `await foo()` → same as sync

**Imports:**
- AST: `ast.Import`, `ast.ImportFrom`
- Resolve to imported symbols
- Track star imports: `from foo import *` → all symbols in `foo`
- Track relative imports: `from . import sibling`

**Inherits:**
- AST: `ast.ClassDef.bases`
- Resolve base class names to symbols
- Handle multiple inheritance: `class C(A, B)` → edges to both A and B

**Implements:**
- Detect protocol/interface classes (ABC, Protocol, TypedDict)
- Match method signatures (structural typing)
- Infer from type hints: `x: Mapping` → implements `Mapping`

### 2.4 New API Endpoints

```python
# New MCP tools
mcp_ast_tools_callgraph(symbol: str, edge_type: Optional[str] = None, direction: str = "out") -> dict
    # Returns adjacency list for symbol
    # direction: "out" (callees), "in" (callers), "both"

mcp_ast_tools_callgraph_callees(symbol: str) -> list[Symbol]
    # What does this symbol call?

mcp_ast_tools_callgraph_callers(symbol: str) -> list[Symbol]
    # What calls this symbol? (fan-in)

mcp_ast_tools_detect_cycles(start_symbol: Optional[str] = None, max_depth: int = 10) -> list[list[str]]
    # Find circular dependencies via DFS
    # Returns list of cycles (each cycle is list of symbol names)
```

---

## 3. Dependency Metrics

### 3.1 Metrics Definitions

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Fan-in** | Count of symbols that depend ON this symbol | High = widely used, critical |
| **Fan-out** | Count of symbols this symbol depends ON | High = many dependencies, fragile |
| **SPOF Score** | `fan_in / (fan_in + fan_out)` normalized to [0,1] | High = single point of failure |
| **Instability** | `fan_out / (fan_in + fan_out)` | High = unstable (changes propagate) |
| **Centrality** | PageRank over callgraph | High = architecturally central |

### 3.2 Database Schema

```sql
CREATE TABLE dependency_metrics (
    symbol_id INTEGER PRIMARY KEY,
    fan_in INTEGER DEFAULT 0,
    fan_out INTEGER DEFAULT 0,
    sPOF_score REAL DEFAULT 0.0,
    instability REAL DEFAULT 0.0,
    centrality REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE INDEX idx_dependency_spof ON dependency_metrics(sPOF_score DESC);
CREATE INDEX idx_dependency_instability ON dependency_metrics(instability DESC);
```

### 3.3 Computation Algorithm

**Fan-in/Fan-out:**
```python
# From callgraph_edges table
fan_in = SELECT COUNT(*) FROM callgraph_edges WHERE target_symbol_id = ?
fan_out = SELECT COUNT(*) FROM callgraph_edges WHERE source_symbol_id = ?
```

**SPOF Score:**
```python
spof_score = fan_in / (fan_in + fan_out) if (fan_in + fan_out) > 0 else 0.0
```

**Centrality (PageRank):**
```python
# Use networkx or custom implementation
# Damping factor: 0.85
# Max iterations: 100
# Convergence threshold: 1e-6
```

### 3.4 New API Endpoints

```python
mcp_ast_tools_dependencies(symbol: str, include_transitive: bool = False, max_depth: int = 3) -> dict
    # Returns fan-in, fan-out, and dependency tree
    # include_transitive: include indirect dependencies
    # max_depth: limit traversal depth

mcp_ast_tools_spof_analysis(project_root: Optional[str] = None, threshold: float = 0.8) -> list[Symbol]
    # Identify symbols with SPOF score > threshold
    # Returns sorted list (highest SPOF first)
```

---

## 4. Embedding Similarity

### 4.1 Embedding Model

**Model:** `BAAI/bge-small-en-v1.5`  
**Dimensions:** 384  
**Platform:** CPU-only (no CUDA required)  
**Library:** `sentence-transformers`  
**License:** MIT

**Why this model:**
- Small enough for CPU inference (~100ms per symbol)
- 384-dim vectors fit in memory (1M symbols × 384 × 4 bytes = 1.5GB)
- High quality for code semantics (trained on code + natural language)
- Compatible with sqlite-vec F32_BLOB storage

### 4.2 Database Schema

```sql
-- Embeddings stored in existing symbols table (Phase 8)
ALTER TABLE symbols ADD COLUMN embeddings BLOB;  -- F32_BLOB, 384 dimensions

-- Similarity cache (precomputed)
CREATE TABLE embedding_similarity (
    symbol_id_1 INTEGER NOT NULL,
    symbol_id_2 INTEGER NOT NULL,
    cosine_similarity REAL NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id_1, symbol_id_2),
    FOREIGN KEY (symbol_id_1) REFERENCES symbols(id),
    FOREIGN KEY (symbol_id_2) REFERENCES symbols(id)
);

-- KNN graph: top-k similar symbols for each symbol
CREATE TABLE knn_graph (
    symbol_id INTEGER NOT NULL,
    neighbor_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    similarity REAL NOT NULL,
    PRIMARY KEY (symbol_id, neighbor_id),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (neighbor_id) REFERENCES symbols(id)
);

CREATE INDEX idx_embedding_sim ON embedding_similarity(symbol_id_1, cosine_similarity DESC);
CREATE INDEX idx_knn_symbol ON knn_graph(symbol_id, rank);
```

### 4.3 Similarity Computation

**Cosine Similarity:**
```python
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**KNN Graph Construction:**
```python
# For each symbol, find top-k most similar
k = 10
for symbol_id in all_symbols:
    emb = get_embedding(symbol_id)
    similarities = [(other_id, cosine(emb, other_emb)) 
                    for other_id, other_emb in all_embeddings 
                    if other_id != symbol_id]
    top_k = sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
    save_to_knn_graph(symbol_id, top_k)
```

**Performance Optimization:**
- **Approximate Nearest Neighbors (ANN):** Use `faiss` or `hnswlib` for faster search
- **Batch computation:** Compute similarities in batches (10K symbols/batch)
- **Incremental updates:** Only recompute when symbols change

### 4.4 New API Endpoints

```python
mcp_ast_tools_similar(symbol: str, k: int = 10, min_similarity: float = 0.7) -> list[Symbol]
    # Find k most similar symbols with similarity >= threshold
    # Returns symbols with similarity scores

mcp_ast_tools_embeddings_compute(symbols: Optional[list[str]] = None, batch_size: int = 100) -> dict
    # Compute embeddings for all symbols (or specified subset)
    # Returns progress, errors, timing info

mcp_ast_tools_embeddings_batch(batch_id: str) -> dict
    # Check status of batch embedding computation
```

---

## 5. Performance Targets

### 5.1 Index Build Targets

| Metric | Target | Stretch |
|--------|--------|---------|
| Callgraph extraction (10K files) | <10 min | <5 min |
| Dependency metrics (10K symbols) | <2 min | <1 min |
| Embedding computation (10K symbols) | <20 min | <10 min |
| KNN graph (10K symbols) | <30 min | <15 min |
| **Total (1M files)** | **<60 min** | **<30 min** |

### 5.2 Query Latency Targets

| Query Type | p50 | p95 | p99 |
|------------|-----|-----|-----|
| Callgraph lookup (callees/callers) | <10ms | <50ms | <100ms |
| Dependency metrics | <5ms | <20ms | <50ms |
| Similarity search (k=10) | <50ms | <200ms | <500ms |
| Cycle detection (max_depth=10) | <100ms | <500ms | <1s |

### 5.3 Memory Targets

| Component | Peak Memory |
|-----------|-------------|
| Callgraph in memory | <100MB |
| Embeddings (1M symbols) | <1.5GB |
| KNN graph (1M symbols × 10 neighbors) | <100MB |
| **Total peak** | **<2GB** |

---

## 6. Migration Strategy

### 6.1 Migration 009

**File:** `src/ast_tools/db/migrations/009_schema_enrichments.py`

**Steps:**
1. Create `callgraph_edges` table
2. Create `dependency_metrics` table
3. Create `embedding_similarity` table
4. Create `knn_graph` table
5. Add `embeddings` column to `symbols` (if not exists from Phase 8)
6. Create indexes
7. Populate initial data (optional, can be done post-migration)

**Rollback:**
```sql
DROP TABLE IF EXISTS knn_graph;
DROP TABLE IF EXISTS embedding_similarity;
DROP TABLE IF EXISTS dependency_metrics;
DROP TABLE IF EXISTS callgraph_edges;
-- Note: Cannot drop embeddings column from symbols (SQLite limitation)
```

### 6.2 Backward Compatibility

**Guarantees:**
- Old queries continue to work (no breaking changes to existing tables)
- New tools are additive (no removal of existing tools)
- Migration is reversible (except embeddings column)

**Breaking Changes:**
- None (fully backward compatible)

---

## 7. Security Considerations

### 7.1 Threat Model

| Asset | Threat | Mitigation |
|-------|--------|------------|
| Source code | Exfiltration via callgraph | Read-only access, no network egress |
| Embeddings | Model poisoning | Use official pretrained models only |
| Dependency graph | Supply chain confusion | Clear provenance tracking |

### 7.2 Input Validation

- All symbol names validated against allowlist (alphanumeric + `_`)
- File paths restricted to workspace root
- Query parameters sanitized (SQL injection prevention via parameterized queries)
- Batch sizes limited (max 10K symbols/request)

---

## 8. Testing Strategy

### 8.1 Unit Tests

- Migration 009: Schema validation, FK constraints
- Callgraph builder: Edge extraction accuracy
- Dependency tracker: Fan-in/out, cycle detection
- Similarity engine: Cosine similarity, KNN graph

### 8.2 Integration Tests

- End-to-end tool calls (MCP endpoints)
- Performance benchmarks
- Memory profiling

### 8.3 Acceptance Criteria

- [ ] 90%+ code coverage
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance targets met
- [ ] No memory leaks (>2GB peak)

---

## 9. References

- Phase 8 Spec: `docs/phase8-context-injection-spec.md`
- Phase 8B Spec: `docs/phase8b-spec.md`
- Phase 9 Plan: `docs/plans/phase9-implementation-plan.md`
- sqlite-vec Docs: https://github.com/asg017/sqlite-vec
- BGE Model: https://huggingface.co/BAAI/bge-small-en-v1.5
- PageRank: https://en.wikipedia.org/wiki/PageRank

---

**End of Specification**