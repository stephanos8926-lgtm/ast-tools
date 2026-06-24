# Semantic Database — Phase 2 Spec: Vector Embeddings + Semantic Search

**Version:** 2.0  
**Date:** 2026-07-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Phase 1 Reference:** `docs/specs/semantic-db-phase1-v1.md` (✅ COMPLETE)

---

## Problem Statement

**Current state (Phase 1):** Symbolic search only — FTS5 keyword matching + exact name lookup. Can find `authenticate_user` when searching "authenticate", but cannot find it when searching "login validation" or "password check".

**Missing capability:** Semantic similarity search — find code by *meaning*, not just by keyword matching in names/docstrings.

**Impact:**
- Cannot discover code without knowing exact function names
- No "find similar patterns" capability
- No "what handles authentication?" queries
- No cross-project code pattern discovery

---

## Goals

| ID | Priority | Description |
|----|----------|-------------|
| G1 | **MUST** | Local transformer embedding model (CPU-only, <400MB RAM) |
| G2 | **MUST** | sqlite-vec extension for vector similarity search |
| G3 | **MUST** | Generate embeddings for all symbols (docstring + signature) |
| G4 | **MUST** | Hybrid search: FTS5 (keyword) + vector (semantic) fusion |
| G5 | **SHOULD** | Incremental embedding (only re-embed changed symbols) |
| G6 | **COULD** | Query embedding caching (avoid re-compute same queries) |

---

## Model Selection (CPU Constraint: 4GB RAM)

**Primary:** `bge-small-en-v1.5`
- Dimensions: 384
- Model size: ~130MB
- RAM usage: ~300MB during inference
- Speed: ~50-100 embeddings/sec on CPU
- Quality: Strong for technical text (trained on StackExchange, GitHub, arXiv)
- License: MIT (commercial OK)

**Fallback:** `all-MiniLM-L6-v2`
- Dimensions: 384
- Model size: ~80MB
- RAM usage: ~200MB
- Speed: ~80-150 embeddings/sec
- Quality: Slightly lower but very fast

**Library:** `sentence-transformers` (wraps HuggingFace, easy CPU inference)

---

## Vector Store Architecture

**Option Selected:** `sqlite-vec` extension (pure SQLite, no external DB)

**Why:**
- No new infrastructure (keeps Phase 1 SQLite-only architecture)
- <1ms query time for <100K vectors
- Same connection, same transactions, same WAL mode
- Pure C extension (no Python overhead)
- Active maintenance, stable API

**Schema Extension:**
```sql
CREATE VIRTUAL TABLE symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Storage:** BLOB in main `symbols` table + `symbols_vec` virtual table for indexing

---

## Hybrid Search Strategy

**Reciprocal Rank Fusion (RRF):**
```
RRF_score(doc) = Σ (1 / (rank_i(doc) + k))  for each result list i
```

**Process:**
1. Generate query embedding (384-dim vector)
2. Vector search: top-2k results by cosine similarity
3. FTS5 search: top-2k results by BM25
4. RRF fusion: combine rankings
5. Return top-k fused results

**k value:** 1.5 (standard for RRF, balances keyword vs semantic)

---

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/embeddings/__init__.py` | Create | Embeddings package root |
| `src/ast_tools/embeddings/model.py` | Create | Transformer model loading, embedding generation |
| `src/ast_tools/embeddings/store.py` | Create | sqlite-vec integration, batch insert |
| `src/ast_tools/database/queries.py` | Patch | Add `generate_symbol_embedding`, `semantic_search` |
| `src/ast_tools/database/schema.py` | Patch | Add `symbols_vec` virtual table, migration |
| `src/ast_tools/tools/semantic_search.py` | Create | MCP tool: hybrid search (FTS5 + vector) |
| `src/ast_tools/indexer/extractor.py` | Patch | Call embedding generation during symbol extraction |
| `src/ast_tools/indexer/cache.py` | Patch | Track embedding hash (re-embed if docstring changes) |
| `tests/embeddings/test_model.py` | Create | Model loading, embedding generation tests |
| `tests/embeddings/test_store.py` | Create | sqlite-vec insert/search tests |
| `tests/tools/test_semantic_search.py` | Create | MCP tool integration tests |
| `docs/research/embeddings-phase2-research.md` | Created by subagent | Model comparison, benchmarks |
| `docs/specs/semantic-db-phase2-v2.md` | This file | Interface contracts, architecture |
| `docs/plans/semantic-db-phase2-v2.md` | Phase 2 Plan | Task breakdown, dependencies |

---

## Acceptance Criteria

- [ ] **G1:** Model loads on CPU, <400MB RAM, generates embeddings in <20ms each
- [ ] **G2:** `sqlite-vec` installed, `symbols_vec` table created, cosine similarity search working
- [ ] **G3:** All existing symbols have embeddings (batch generation for Phase 1 data)
- [ ] **G4:** `semantic_search(query, k=10)` returns fused results (keyword + semantic)
- [ ] **G5:** Incremental embedding: editing docstring triggers re-embed, unchanged symbols skipped
- [ ] **G6:** Query caching: same query twice = second is instant (from cache)
- [ ] New `semantic_search` tool appears in `list_tools()` MCP call
- [ ] All tests pass (existing 185 + new ~40 embedding tests = 225+ total)
- [ ] Schema migration tested (v1 → v2 with backfill)

---

## Compatibility & Behavior Rules

1. **Backward compatibility:** All 16 existing ast-tools MCP tools continue to work unchanged
2. **Embedding trigger:** Generate on symbol insert/update (if docstring or signature changes)
3. **Lazy generation:** If model not loaded, `semantic_search` returns error with install instructions
4. **Batch generation:** `refresh_index --embeddings` backfills all missing embeddings
5. **Model cache:** Downloaded model cached at `~/.cache/ast-tools/models/bge-small-en-v1.5/`
6. **Graceful degradation:** If sqlite-vec not installed, tool fails with clear error (not silent)
7. **Dimension validation:** Embedding dimension hard-coded to 384 (schema-level constraint)

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Embedding generation | <20ms/symbol | BGE-small on i3 CPU |
| Vector search (10K symbols) | <5ms | sqlite-vec cosine similarity |
| Hybrid search (fused) | <50ms | FTS5 + vector + RRF fusion |
| Batch backfill (10K symbols) | <5min | ~3-4 hours for 100K symbols |
| RAM overhead | <400MB | Model + embeddings in memory |
| Disk overhead | ~4MB per 10K symbols | 384 floats = 1.5KB per symbol |

---

## Test Plan

### Unit Tests (Embeddings)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/embeddings/test_model.py` | 8 | Model loading, CPU inference, embedding shape validation |
| `tests/embeddings/test_store.py` | 10 | sqlite-vec insert, cosine search, batch operations |

### Integration Tests

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/tools/test_semantic_search.py` | 12 | Hybrid search, edge cases, ranking validation |
| `tests/indexer/test_extractor.py` | +4 | Embedding generation during extraction (incremental) |
| `tests/database/test_schema.py` | +3 | Migration v1→v2, schema validation |

### Performance Tests

| Test | Metric | Target |
|------|--------|--------|
| Generate 100 embeddings | Total time | <2s |
| Search 10K symbols | Query latency | <50ms |
| Backfill 10K symbols | Batch time | <5min |

---

## Security & Privacy

1. **Local-only:** No API calls, all embeddings generated locally (no data leaves machine)
2. **Model integrity:** Verify model checksum on download (SHA256)
3. **No PII in embeddings:** Only docstrings + signatures (no file contents, no comments)
4. **Sandboxed:** sqlite-vec is pure C, no arbitrary code execution

---

## Migration Plan (v1 → v2)

**Step 1: Schema migration**
```sql
-- Add symbols_vec virtual table
CREATE VIRTUAL TABLE symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Step 2: Batch backfill**
```python
# In refresh_index tool
if args.embeddings:
    backfill_embeddings(conn, model, batch_size=100)
```

**Step 3: Incremental updates**
- Modify `insert_symbol()` to generate embedding automatically
- Check `embedding_hash` in file_cache (skip if unchanged)

**Rollback:** If migration fails, restore from WAL checkpoint (pre-migration state)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model too slow on CPU | Medium | High | Fallback to MiniLM (faster, lower quality) |
| sqlite-vec install fails | Low | High | Provide pre-built wheel, fallback to numpy brute-force |
| RAM exhaustion (4GB limit) | Low | High | Batch embedding gen (100 symbols/batch), clear model after batch |
| Hybrid search ranking wrong | Medium | Medium | Tune RRF k-value, add user feedback mechanism |
| Migration corrupts DB | Low | Critical | WAL mode + checkpoint before migration, test on copy first |

---

## Success Metrics

- **Precision@10:** >0.75 for semantic queries (e.g., "auth" → auth-related functions)
- **Recall@10:** >0.60 for semantic queries (finds 60% of relevant symbols in top 10)
- **Latency:** <50ms p95 for hybrid search queries
- **Coverage:** 100% of symbols have embeddings (after backfill)
- **Adoption:** `semantic_search` used in >50% of symbol lookup queries (after 1 month)

---

## Definition of Done

- [ ] All 12 acceptance criteria met
- [ ] All tests passing (225+ total)
- [ ] Schema migration tested (v1→v2→rollback→v2)
- [ ] Performance targets met (embedding gen <20ms, search <50ms)
- [ ] Documentation updated (README, tool docs, Phase 2 report)
- [ ] Forward + reverse audits completed
- [ ] Adversarial audit completed (security, edge cases)
- [ ] All commits pushed to master

---

**Next Phase:** Phase 2 Plan (`docs/plans/semantic-db-phase2-v2.md`) — task breakdown, dependencies, timeline