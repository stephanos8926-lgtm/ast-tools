# Spectral Clustering Improvement Plan

## Executive Summary
The spectral clustering feature in ast-tools (merged from `feat/spectral-clustering`) is a genuinely novel algorithmic feature — Fiedler vector-based module decomposition with multi-signal fusion. This document outlines improvements across algorithmic quality, performance, usability, and integration.

---

## 1. Algorithmic Improvements

### 1.1 Cluster Naming Enhancement
**Current:** Longest common prefix (LCP) of module paths  
**Problem:** Fails for flat structures (`auth.py`, `db.py`, `api.py` → "auth" vs "db" vs "api" all different)  
**Solution:** Hybrid naming:
- LCP as primary (works for nested packages)
- Fallback: TF-IDF keywords from module source + embeddings
- Fallback: Semantic labels from embedding similarity to known patterns

**Implementation:** Extend `_derive_cluster_name()` and `_assign_cluster_names()`

```python
def _derive_cluster_name(modules: list[str], module_docs: dict[str, str] | None = None) -> str:
    # 1. Try LCP
    lcp = _longest_common_prefix(modules)
    if lcp and len(lcp) > 3:
        return lcp.rstrip('.')
    
    # 2. Try TF-IDF on source code
    if module_docs:
        keywords = _extract_tfidf_keywords([module_docs[m] for m in modules])
        if keywords:
            return keywords[0]
    
    # 3. Fallback: structural heuristic
    return _structural_cluster_name(modules)
```

### 1.2 Incremental Laplacian Updates
**Problem:** Full recomputation O(N³) on every file change  
**Solution:** Low-rank updates for Laplacian when edges change

```python
def update_laplacian_incremental(
    old_laplacian: np.ndarray,
    old_adjacency: np.ndarray,
    edge_changes: list[tuple[int, int, float]],  # (i, j, new_weight)
) -> np.ndarray:
    """Sherman-Morrison-Woodbury for rank-k updates to L_sym"""
    # For each edge change, update degree matrix and apply SMW
    pass
```

### 1.3 Scalable Eigensolver for Large Graphs
**Current:** Power iteration with dense matrix inversion O(N³)  
**Limit:** ~500 modules practical  
**Solution:** 
- Lanczos algorithm via `scipy.sparse.linalg.eigsh` (when scipy available)
- Nyström approximation for >1000 nodes
- Randomized SVD for semantic affinity matrix

```python
def _fiedler_vector_scalable(laplacian: np.ndarray, n: int) -> tuple[np.ndarray, float]:
    if n < 500:
        return _fiedler_vector_power_iteration(laplacian)
    elif SCIPY_AVAILABLE:
        from scipy.sparse.linalg import eigsh
        from scipy.sparse import csr_matrix
        sparse_L = csr_matrix(laplacian)
        vals, vecs = eigsh(sparse_L, k=2, which='SM')
        return vecs[:, 1], float(vals[1])
    else:
        return _fiedler_vector_nystrom(laplacian, n)
```

### 1.4 Multi-Resolution Clustering
**Current:** Single recursive bipartitioning  
**Enhancement:** Return hierarchy at multiple resolutions
- Level 0: Coarse (2-4 clusters) — architecture overview
- Level 1: Medium (5-15 clusters) — subsystem decomposition  
- Level 2: Fine (20+ clusters) — module-level

---

## 2. Performance Optimizations

### 2.1 Sparse Matrix Representation
**Current:** Dense N×N adjacency for everything  
**Issue:** Memory O(N²), most entries zero  
**Fix:** Use `scipy.sparse.csr_matrix` for adjacency, Laplacian

```python
from scipy.sparse import csr_matrix, diags

def _normalized_laplacian_sparse(adj: csr_matrix) -> csr_matrix:
    d = np.array(adj.sum(axis=1)).flatten()
    d_inv_sqrt = np.where(d > 1e-10, 1.0 / np.sqrt(d), 0.0)
    D_inv_sqrt = diags(d_inv_sqrt)
    return D_inv_sqrt @ (diags(d) - adj) @ D_inv_sqrt
```

### 2.2 Parallel Graph Construction
**Current:** Sequential file parsing  
**Fix:** `concurrent.futures.ProcessPoolExecutor` for language-specific extractors

```python
def _build_module_adjacency_parallel(project_root: str, max_workers: int = 4):
    files_by_lang = _group_files_by_language(project_root)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            lang: executor.submit(_extract_lang_imports, lang, files)
            for lang, files in files_by_lang.items()
        }
        # Merge results
```

### 2.3 Embedding Caching
**Current:** Re-encodes all module docs on every run  
**Fix:** Cache embeddings keyed by (file_path, content_hash, model_name)

```python
class EmbeddingCache:
    def __init__(self, cache_dir: Path, max_size_mb: int = 100):
        self.cache = moka.sync.Cache(max_size=max_size_mb * 1024 * 1024)
    
    def get_embedding(self, file_path: Path, model: str) -> np.ndarray | None:
        key = f"{file_path}:{hash(file_path.read_bytes())}:{model}"
        return self.cache.get(key)
    
    def put_embedding(self, file_path: Path, model: str, embedding: np.ndarray):
        key = f"{file_path}:{hash(file_path.read_bytes())}:{model}"
        self.cache.set(key, embedding)
```

### 2.4 Lazy Graph Construction
**Current:** Builds all signal matrices upfront  
**Fix:** Build on-demand, short-circuit if quality threshold met with import graph alone

---

## 3. Usability & API Improvements

### 3.1 Streaming/Progress Reporting
```python
class SpectralProgress:
    def __init__(self, callback: Callable[[str, float], None]):
        self.callback = callback
    
    def report(self, stage: str, progress: float):
        self.callback(stage, progress)
```

### 3.2 Configuration Profiles
```python
SPECTRAL_PROFILES = {
    "fast":      {"semantic_weight": 0.0, "cochange_weight": 0.0, "use_call_graph": False},
    "balanced":  {"semantic_weight": 0.3, "cochange_weight": 0.4, "use_call_graph": True},
    "thorough":  {"semantic_weight": 0.5, "cochange_weight": 0.6, "use_call_graph": True, "max_commits": 5000},
}
```

### 3.3 Visualization Output
- Export GraphViz DOT for partition tree
- Export clusters as Mermaid diagrams
- JSON schema with cluster metadata for external tools

---

## 4. Integration with ast-tools Ecosystem

### 4.1 MCP Tool Enhancements
- `suggest_modules` → add `profile` parameter, streaming progress
- New tool: `module_dependencies` — export raw adjacency for external analysis
- New tool: `cluster_hierarchy` — multi-resolution output

### 4.2 LSP Code Actions
- "Show module cluster" — hover reveals cluster membership
- "Suggest refactor" — propose moving modules to reduce coupling

### 4.3 Watch Mode Integration
When config watcher detects changes:
- Incremental update to import graph
- Re-cluster only affected partition subtree
- Notify LSP clients of cluster changes

---

## 5. Quality & Testing

### 5.1 Synthetic Benchmarks
- Barabási-Albert scale-free graphs (realistic code structure)
- Stochastic block model (known ground truth clusters)
- Grid graphs (pathological for spectral methods)

### 5.2 Regression Tests
- Cluster stability under small perturbations
- Determinism with fixed RNG seed
- Quality monotonicity with signal fusion

---

## 6. Documentation
- Architecture decision record (ADR) for spectral approach vs alternatives
- Parameter tuning guide
- Performance characterization (N vs time/memory)

---

## Priority Order

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Sparse matrices + scipy eigsh | Medium | High (enables >1000 modules) |
| P0 | Embedding caching | Low | High (semantic mode speedup) |
| P1 | Cluster naming (TF-IDF fallback) | Medium | High (usability) |
| P1 | Configuration profiles | Low | High (UX) |
| P2 | Incremental Laplacian updates | High | Medium (watch mode) |
| P2 | Parallel graph construction | Medium | Medium (large projects) |
| P2 | Multi-resolution output | Low | Medium (analysis depth) |
| P3 | Nyström approximation | High | Low (extreme scale) |
| P3 | Visualization exports | Low | Medium (presentation) |

---

## Next Steps
1. Implement sparse matrix + scipy eigsh (P0)
2. Add embedding cache with moka (P0)
3. Create configuration profiles (P1)
4. Improve cluster naming with TF-IDF fallback (P1)
5. Add incremental update hooks for watch mode (P2)