# Reverse Audit: Phase 9 Schema Enrichments

**Date:** 2026-07-24  
**Auditor:** Lucien (inline)  
**Scope:** Critical gaps, failure modes, security, performance, testing

---

## 1. Missing Requirements / Edge Cases

### 1.1 Callgraph Edges

**Gap:** No handling for **dynamic calls** (reflection, `getattr`, decorators)

```python
# These won't be captured by static AST analysis:
getattr(obj, method_name)()
funcs[name]()  # Higher-order functions
@decorator
def wrapped(): ...  # Call goes to decorator, not wrapped
```

**Impact:** Callgraph will be incomplete for dynamic code patterns.

**Recommendation:**
- Document limitation in `callgraph-edges.md`
- Add `resolution_state` column to edges: `resolved`, `unresolved_dynamic`, `partial`
- For unresolved calls, store the best-effort target (e.g., `getattr` call → store attribute name)

### 1.2 Implements Detection

**Gap:** Spec says "detect protocol/interface classes" but doesn't define the algorithm

**Missing:**
- How to distinguish `class C(ABC)` from `class C(SomeConcreteClass)`?
- How to handle multiple inheritance where only some bases are protocols?
- What about structural typing without explicit inheritance (duck typing)?

**Recommendation:**
```python
# Concrete detection algorithm:
def is_protocol(class_node):
    # Check if inherits from: abc.ABC, typing.Protocol, typing.RuntimeProtocol
    for base in class_node.bases:
        if resolve_name(base) in ('abc.ABC', 'typing.Protocol', 'typing.RuntimeProtocol'):
            return True
    # Check for @abstractmethod decorators
    for method in class_node.body:
        if isinstance(method, ast.FunctionDef):
            for decorator in method.decorators:
                if resolve_name(decorator) == 'abc.abstractmethod':
                    return True
    return False
```

### 1.3 Embedding Similarity

**Gap:** No handling for **embedding staleness**

When code changes, embeddings become stale. Spec mentions KNN graph but not invalidation strategy.

**Recommendation:**
```sql
-- Add staleness tracking
ALTER TABLE embedding_similarity ADD COLUMN is_stale INTEGER DEFAULT 0;
ALTER TABLE knn_graph ADD COLUMN computed_at TIMESTAMP;

-- Or use content_hash comparison
ALTER TABLE embedding_similarity ADD COLUMN symbol_1_hash TEXT;
ALTER TABLE embedding_similarity ADD COLUMN symbol_2_hash TEXT;
```

**Strategy:**
1. On symbol update: mark related similarities as `is_stale=1`
2. On query: filter `WHERE is_stale=0` or recompute on-the-fly
3. Background job: recompute stale similarities periodically

---

## 2. Overlooked Failure Modes

### 2.1 Migration Failures

**Risk:** Migration 009 fails mid-way (power loss, disk full, constraint violation)

**Missing:**
- Transaction boundaries (all-or-nothing)
- Progress tracking (resume from checkpoint)
- Data validation post-migration

**Recommendation:**
```python
def migrate_v4_to_v5(conn):
    with conn:  # Transaction wrapper
        # Step 1: Add metadata column (reversible)
        conn.execute("ALTER TABLE edges ADD COLUMN metadata JSON")
        
        # Step 2: Create tables (reversible)
        conn.execute("CREATE TABLE dependency_metrics (...)")
        conn.execute("CREATE TABLE embedding_similarity (...)")
        conn.execute("CREATE TABLE knn_graph (...)")
        
        # Step 3: Create trigger (reversible)
        conn.execute("CREATE TRIGGER validate_edge_type ...")
        
        # Step 4: Update version (committed only if all above succeed)
        conn.execute("UPDATE schema_version SET version = 5")
    
    # Validate post-migration
    assert get_schema_version(conn) == 5
    assert table_exists(conn, 'dependency_metrics')
```

### 2.2 KNN Graph Build Failures

**Risk:** Out-of-memory during KNN computation (1M symbols × 384 dim)

**Missing:**
- Memory monitoring during build
- Graceful degradation (smaller batches, swap to disk)
- Kill switch if memory exceeds threshold

**Recommendation:**
```python
import psutil

def compute_knn_graph(batch_size=10000, memory_threshold=0.8):
    for batch in chunks(all_symbols, batch_size):
        # Check memory before each batch
        if psutil.virtual_memory().percent > memory_threshold * 100:
            logger.warning(f"Memory at {psutil.virtual_memory().percent}%, reducing batch size")
            batch_size = batch_size // 2
        
        # Compute batch
        compute_batch_similarities(batch)
        
        # GC after each batch
        gc.collect()
```

### 2.3 PageRank Non-Convergence

**Risk:** PageRank doesn't converge within 100 iterations (cyclic graphs, dangling nodes)

**Missing:**
- Convergence monitoring
- Fallback for non-convergence
- Handling of dangling nodes (symbols with no outgoing edges)

**Recommendation:**
```python
def compute_pagerank(graph, max_iterations=100, tolerance=1e-6):
    prev_scores = None
    for i in range(max_iterations):
        scores = iteration(graph, prev_scores)
        
        # Check convergence
        if prev_scores is not None:
            delta = max(abs(scores[k] - prev_scores[k]) for k in scores)
            if delta < tolerance:
                logger.info(f"PageRank converged at iteration {i}")
                break
        
        prev_scores = scores
    
    else:
        logger.warning(f"PageRank did not converge after {max_iterations} iterations")
        # Return best-effort scores
    
    return scores
```

---

## 3. Security Gaps

### 3.1 Callgraph as Attack Surface

**Risk:** Callgraph exposes internal code structure → aids attackers in finding:
- Security-critical functions (auth, crypto, validation)
- SPOFs (single points of failure to target)
- Dependency chains (supply chain attack vectors)

**Missing:**
- Access control on callgraph queries
- Rate limiting (prevent enumeration attacks)
- Redaction of sensitive symbols

**Recommendation:**
```python
# Config-based redaction
REDACTED_PATTERNS = [
    r'.*auth.*',
    r'.*password.*',
    r'.*secret.*',
    r'.*key.*',
]

def should_redact_symbol(symbol_name: str) -> bool:
    for pattern in REDACTED_PATTERNS:
        if re.match(pattern, symbol_name, re.IGNORECASE):
            return True
    return False

def callgraph_callers(symbol: str) -> list:
    if should_redact_symbol(symbol):
        raise PermissionError(f"Callgraph access denied for sensitive symbol: {symbol}")
    # ... normal implementation
```

### 3.2 Embedding Leakage

**Risk:** Embeddings encode semantic information about code → could leak:
- API keys accidentally included in docstrings
- Comments with sensitive information
- Internal naming conventions

**Missing:**
- Embedding content audit
- Sanitization before embedding

**Recommendation:**
```python
def sanitize_for_embedding(content: str) -> str:
    # Remove potential secrets
    content = re.sub(r'api[_-]?key\s*[=:]\s*["\'][^"\']+["\']', 'API_KEY=[REDACTED]', content)
    content = re.sub(r'password\s*[=:]\s*["\'][^"\']+["\']', 'password=[REDACTED]', content)
    content = re.sub(r'token\s*[=:]\s*["\'][^"\']+["\']', 'token=[REDACTED]', content)
    return content
```

---

## 4. Performance Concerns

### 4.1 Query Performance Not Profiled

**Gap:** Spec targets p50 <50ms but no profiling plan

**Missing:**
- Baseline performance measurements
- Hot query identification
- Index effectiveness testing

**Recommendation:**
```python
# pytest-benchmark fixtures
def benchmark_callgraph_queries():
    import random
    symbols = random.sample(all_symbols, 100)
    
    # Warm up cache
    for s in symbols:
        callgraph_callers(s)
    
    # Benchmark
    @benchmark
    def test_callgraph_callers():
        for s in random.sample(symbols, 10):
            callgraph_callers(s)
```

### 4.2 KNN Graph Build Time

**Gap:** <60min target for 1M symbols but no breakdown

**Reality check:**
- Naive all-pairs: 1T comparisons → ~100+ hours (too slow)
- hnswlib ANN: ~30min (achievable)
- Chunked exact: ~60min (borderline)

**Missing:**
- hnswlib dependency (not in current requirements)
- Fallback strategy if hnswlib unavailable

**Recommendation:**
```toml
# pyproject.toml
[project.optional-dependencies]
similarity = [
    "hnswlib>=0.7.0",  # For fast KNN graph build
    "numpy>=1.20.0",
]
```

### 4.3 Memory Bloat from Metadata

**Gap:** `metadata JSON` column in edges can grow unbounded

**Risk:** Metadata bloat → database size explosion

**Recommendation:**
```sql
-- Add size limit via CHECK constraint
CREATE TRIGGER check_metadata_size
BEFORE INSERT ON edges
BEGIN
    SELECT CASE
        WHEN length(NEW.metadata) > 1024
        THEN RAISE(ABORT, 'Metadata exceeds 1KB limit')
    END;
END;
```

---

## 5. Backward Compatibility Issues

### 5.1 Existing `edges` Table Enhancement

**Issue:** Spec creates new `callgraph_edges` table but existing code uses `edges`

**Risk:** Two tables with overlapping data → confusion, inconsistency

**Recommendation:**
- **Don't create** `callgraph_edges` as separate table
- **Enhance** existing `edges` table (add metadata, add `implements` to validation)
- Create **view** `callgraph_edges AS SELECT * FROM edges` for API compatibility

### 5.2 Tool Name Conflicts

**Issue:** Existing tools: `circular_dependencies`, `dependency_chain`  
New tools: `detect_cycles`, `ast_dependencies`

**Risk:** Duplicate functionality, user confusion

**Recommendation:**
- Keep existing tools (backward compatibility)
- Add aliases: `detect_cycles = circular_dependencies`
- Enhance existing tools with new features (don't replace)

---

## 6. Testing Gaps

### 6.1 No Performance Testing Plan

**Missing:**
- Load testing (concurrent queries)
- Endurance testing (long-running indexing)
- Stress testing (memory exhaustion)

**Recommendation:**
```python
# tests/performance/test_load.py
def test_concurrent_callgraph_queries():
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(callgraph_callers, random_symbol)
            for _ in range(100)
        ]
        results = [f.result() for f in futures]
    
    # Verify all succeeded
    assert all(r is not None for r in results)

# tests/performance/test_endurance.py
def test_long_running_index():
    start_time = time.time()
    index_large_codebase(100_000_files)
    elapsed = time.time() - start_time
    
    assert elapsed < 3600  # <1 hour
    assert get_memory_usage() < 2_000_000_000  # <2GB
```

### 6.2 No Rollback Testing

**Missing:**
- Rollback migration tested
- Data integrity post-rollback
- Rollback time measurements

**Recommendation:**
```python
# tests/database/test_migration_009_rollback.py
def test_rollback():
    # Apply migration
    migrate_to_v5(db_path)
    assert get_schema_version() == 5
    
    # Insert test data
    insert_test_edges()
    insert_test_metrics()
    
    # Rollback
    rollback_to_v4(db_path)
    assert get_schema_version() == 4
    
    # Verify data integrity (original data intact)
    verify_original_data_intact()
```

### 6.3 No Edge Case Tests

**Missing test scenarios:**
- Empty codebase (0 symbols)
- Single-file codebase
- Circular inheritance: `class A(B): ...; class B(A): ...`
- Diamond inheritance: `class C(A, B): ...; class D(A, B): ...`
- Massive fan-in: 10K symbols depend on one symbol
- Massive fan-out: One symbol depends on 10K symbols

**Recommendation:**
```python
# tests/edge_cases/test_extreme_graphs.py
def test_diamond_inheritance():
    # A -> C, B -> C, A -> D, B -> D
    # Should detect: C and D both inherit from A and B
    edges = build_callgraph(diamond_code)
    assert has_path(edges, 'C', 'A')
    assert has_path(edges, 'C', 'B')
    assert has_path(edges, 'D', 'A')
    assert has_path(edges, 'D', 'B')

def test_massive_fan_in():
    # Create 10K symbols that all call one function
    code = generate_massive_fan_in_code(num_callers=10_000)
    edges = build_callgraph(code)
    fan_in = count_callers(edges, 'target_function')
    assert fan_in == 10_000
```

---

## 7. Summary of Critical Gaps

| Category | Gap | Priority | Effort to Fix |
|----------|-----|----------|---------------|
| **Requirements** | Dynamic calls not handled | Medium | Low (document limitation) |
| **Requirements** | `implements` detection algorithm unclear | High | Medium (implement algorithm) |
| **Requirements** | Embedding staleness not tracked | High | Low (add `is_stale` column) |
| **Failure Modes** | Migration lacks transaction boundaries | High | Low (add `with conn:`) |
| **Failure Modes** | KNN build can OOM | High | Medium (add memory monitoring) |
| **Failure Modes** | PageRank may not converge | Medium | Low (add convergence check) |
| **Security** | Callgraph exposes sensitive symbols | Medium | Low (add redaction) |
| **Security** | Embeddings may leak secrets | High | Low (add sanitization) |
| **Performance** | No profiling plan | Medium | Low (add pytest-benchmark) |
| **Performance** | hnswlib dependency not declared | Low | Trivial (add to requirements) |
| **Backward Compat** | Two edges tables would duplicate data | High | Low (use view instead) |
| **Testing** | No performance tests | Medium | Medium (add load/endurance tests) |
| **Testing** | No rollback tests | High | Low (add rollback test) |
| **Testing** | No edge case tests | Medium | Medium (add extreme graph tests) |

---

## 8. Recommendations Summary

### Must-Fix Before Implementation (High Priority)

1. **Embedding staleness tracking** — Add `is_stale` column to `embedding_similarity`
2. **Migration transaction boundaries** — Wrap in `with conn:` block
3. **KNN memory monitoring** — Add `psutil` checks, reduce batch size dynamically
4. **`implements` detection algorithm** — Define concrete algorithm in spec
5. **Secret sanitization** — Sanitize content before embedding computation
6. **Backward compatibility** — Use view for `callgraph_edges`, don't duplicate table
7. **Rollback testing** — Test rollback procedure before deployment

### Should-Fix (Medium Priority)

8. **Dynamic calls limitation** — Document in `callgraph-edges.md`
9. **PageRank convergence** — Add convergence check, return best-effort if non-convergent
10. **Callgraph redaction** — Add config-based redaction for sensitive symbols
11. **Performance profiling** — Add pytest-benchmark fixtures
12. **Edge case tests** — Test diamond inheritance, massive fan-in/out

### Nice-to-Have (Low Priority)

13. **hnswlib dependency** — Add to optional dependencies
14. **Metadata size limit** — Add CHECK constraint or trigger

---

## 9. Go/No-Go Recommendation

**Verdict:** ✅ **GO with fixes**

**Condition:** All "Must-Fix" items (1-7) must be addressed before implementation begins.

**Rationale:**
- Gaps are addressable with low-to-medium effort
- No fundamental architectural flaws
- Existing infrastructure (edges, embeddings) reduces risk
- Security gaps are preventable with simple mitigations
- Performance targets are achievable with proper profiling

**Revised timeline:** 12-16 hours (added 2-4h for must-fix items)

---

**Reverse audit complete.**