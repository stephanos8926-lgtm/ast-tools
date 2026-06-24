# Semantic Database — Phase 2 Implementation Plan

**Version:** 2.0  
**Date:** 2026-07-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Spec Reference:** `docs/specs/semantic-db-phase2-v2.md`

---

## Overview

**Goal:** Add vector embeddings + semantic search to the existing Phase 1 semantic database.

**Execution Order:** Sequential phases (shared dependencies)

| Phase | Component | Files | Est. Time |
|-------|-----------|-------|-----------|
| **Phase 0** | Research | Subagent report | 10 min (parallel) |
| **Phase 1** | Spec | Interface contracts, schema ext | 15 min |
| **Phase 2** | Plan | Task breakdown (this file) | 10 min |
| **Phase 3** | Forward Audit | Validate feasibility | 5 min |
| **Phase 4** | Reverse Audit | Identify gaps/risks | 5 min |
| **Phase 5** | Synthesis | Final plan sign-off | 5 min |
| **Phase 6** | Install Deps | sentence-transformers, sqlite-vec | 5 min |
| **Phase 7** | Schema Migration | v1→v2, symbols_vec table | 20 min |
| **Phase 8** | Embedding Model | model.py, CPU inference | 30 min |
| **Phase 9** | Embedding Store | store.py, sqlite-vec integration | 25 min |
| **Phase 10** | Hybrid Search | semantic_search MCP tool | 30 min |
| **Phase 11** | Incremental Embed | extractor.py, cache.py patches | 20 min |
| **Phase 12** | Batch Backfill | refresh_index --embeddings | 15 min |
| **Phase 13** | Tests | 40+ new tests | 40 min |
| **Phase 14** | Adversarial Audit | Security, edge cases | 10 min |
| **Phase 15** | Lint + Dead Code | ruff, unused imports | 10 min |
| **Phase 16** | Docs | Phase 2 report, README updates | 15 min |
| **Phase 17** | Commit + Push | All phases, verify tests | 10 min |

**Total:** ~4.5 hours (with TDD cycles)

---

## Phase 6: Install Dependencies

### Task 6.1: Install Python Packages

**Command:**
```bash
cd ~/Workspaces/ast-tools
pip install sentence-transformers sqlite-vec
```

**Dependencies:**
- `sentence-transformers` — Transformer embedding API (wraps HuggingFace)
- `sqlite-vec` — SQLite vector similarity extension
- `torch` (auto) — PyTorch CPU backend (~100MB)

**Verify:**
```bash
python3 -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('bge-small-en-v1.5'); print('OK')"
python3 -c "import sqlite_vec; print('sqlite-vec version:', sqlite_vec.__version__)"
```

**Commit:**
```bash
git add -A && git commit -m "chore: install embedding dependencies (sentence-transformers, sqlite-vec)"
```

---

## Phase 7: Schema Migration (v1 → v2)

### Task 7.1: Extend Schema

**File:** `src/ast_tools/database/schema.py` (PATCH)

**Add to INITIAL_SCHEMA:**
```sql
-- Vector embeddings for semantic search (Phase 2)
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Add migration function:**
```python
def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate from schema v1 to v2 (add vector embeddings table)."""
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
            symbol_id TEXT PRIMARY KEY,
            embedding FLOAT[384]
        )
    """)
    conn.commit()
```

**Update SCHEMA_VERSION:** `1 → 2`

**Test:** `tests/database/test_schema.py::test_migrate_v1_to_v2`

---

### Task 7.2: Update Schema Init

**File:** `src/ast_tools/database/schema.py` (PATCH)

**Modify `init_schema()`:**
```python
def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(INITIAL_SCHEMA)
    
    # Run migrations if needed
    version = get_schema_version(conn)
    if version < 2:
        migrate_v1_to_v2(conn)
        update_schema_version(conn, 2)
    
    conn.commit()
```

**Test:** `tests/database/test_schema.py::test_init_schema_v2`

---

## Phase 8: Embedding Model

### Task 8.1: Create Model Module

**File:** `src/ast_tools/embeddings/model.py` (NEW)

**Implementation:**
```python
"""Transformer model for generating embeddings."""

from sentence_transformers import SentenceTransformer
from typing import Optional
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model: Optional[SentenceTransformer] = None

def get_model() -> SentenceTransformer:
    """Load or return cached model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def generate_embedding(text: str, model: Optional[SentenceTransformer] = None) -> list[float]:
    """Generate embedding for text (docstring + signature)."""
    if model is None:
        model = get_model()
    embedding = model.encode([text], convert_to_numpy=True)[0]
    return embedding.tolist()

def generate_batch_embeddings(texts: list[str], model: Optional[SentenceTransformer] = None, batch_size: int = 32) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    if model is None:
        model = get_model()
    embeddings = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
    return embeddings.tolist()
```

**Test:** `tests/embeddings/test_model.py::test_generate_embedding`, `test_batch_embeddings`, `test_model_caching`

---

### Task 8.2: Create Embeddings Package Init

**File:** `src/ast_tools/embeddings/__init__.py` (NEW)

```python
"""Embeddings layer for semantic code search."""

from .model import get_model, generate_embedding, generate_batch_embeddings
from .store import insert_embedding, insert_embeddings_batch, search_similar

__all__ = [
    'get_model',
    'generate_embedding',
    'generate_batch_embeddings',
    'insert_embedding',
    'insert_embeddings_batch',
    'search_similar',
]
```

---

## Phase 9: Embedding Store (sqlite-vec)

### Task 9.1: Create Store Module

**File:** `src/ast_tools/embeddings/store.py` (NEW)

**Implementation:**
```python
"""sqlite-vec integration for vector storage and search."""

import sqlite3
from typing import List, Tuple, Optional
import sqlite_vec

def load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

def insert_embedding(conn: sqlite3.Connection, symbol_id: str, embedding: List[float]) -> None:
    """Insert or update embedding for a symbol."""
    embedding_bytes = bytes(embedding)  # Convert to BLOB
    conn.execute("""
        INSERT OR REPLACE INTO symbols_vec (symbol_id, embedding)
        VALUES (?, ?)
    """, (symbol_id, embedding_bytes))
    conn.commit()

def insert_embeddings_batch(conn: sqlite3.Connection, symbol_embeddings: List[Tuple[str, List[float]]]) -> None:
    """Batch insert embeddings."""
    data = [(sid, bytes(emb)) for sid, emb in symbol_embeddings]
    conn.executemany("""
        INSERT OR REPLACE INTO symbols_vec (symbol_id, embedding)
        VALUES (?, ?)
    """, data)
    conn.commit()

def search_similar(conn: sqlite3.Connection, query_embedding: List[float], k: int = 10) -> List[Tuple[str, float]]:
    """Find most similar symbols by cosine similarity."""
    query_bytes = bytes(query_embedding)
    rows = conn.execute("""
        SELECT symbol_id, distance 
        FROM symbols_vec 
        WHERE embedding MATCH ? 
        ORDER BY distance 
        LIMIT ?
    """, (query_bytes, k)).fetchall()
    return [(row['symbol_id'], row['distance']) for row in rows]
```

**Test:** `tests/embeddings/test_store.py::test_load_vec_extension`, `test_insert_embedding`, `test_search_similar`

---

### Task 9.2: Wire Extension Loading

**File:** `src/ast_tools/database/connection.py` (PATCH)

**Add to `get_connection()`:**
```python
from ast_tools.embeddings.store import load_vec_extension

# After creating connection
conn = get_connection(db_path)
load_vec_extension(conn)  # Load sqlite-vec
```

**Test:** Verify `symbols_vec` table accessible after connection

---

## Phase 10: Hybrid Search Tool

### Task 10.1: Create Semantic Search Tool

**File:** `src/ast_tools/tools/semantic_search.py` (NEW)

**Implementation:**
```python
"""MCP tool: hybrid semantic + keyword search."""

from mcp.server import Server
from ast_tools.database import get_connection
from ast_tools.embeddings import generate_embedding, search_similar
from typing import Optional

def hybrid_search(conn: sqlite3.Connection, query: str, k: int = 10, kind: Optional[str] = None) -> list[dict]:
    """Hybrid search: FTS5 + vector with RRF fusion."""
    
    # 1. Vector search
    query_emb = generate_embedding(query)
    vec_results = search_similar(conn, query_emb, k=k*2)
    
    # 2. FTS5 keyword search
    fts_sql = """
        SELECT s.rowid, bm25(symbols_fts) as score
        FROM symbols_fts
        WHERE symbols_fts MATCH ?
    """
    params = [query]
    if kind:
        fts_sql += " AND s.kind = ?"
        params.append(kind)
    fts_sql += " LIMIT ?"
    params.append(k * 2)
    
    fts_results = conn.execute(fts_sql, params).fetchall()
    
    # 3. Reciprocal Rank Fusion
    fused_scores = {}
    for i, (symbol_id, _) in enumerate(vec_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + 1.5)
    for row in fts_results:
        symbol_id = str(row['rowid'])  # FTS5 returns rowid, need to map
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (row['score'] + 1 + 1.5)
    
    # 4. Sort by fused score
    top_k = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    
    # 5. Fetch full symbol details
    symbols = []
    for symbol_id, _ in top_k:
        symbol = conn.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,)).fetchone()
        if symbol:
            symbols.append(dict(symbol))
    
    return symbols

@mcp.tool()
async def semantic_search(query: str, k: int = 10, kind: Optional[str] = None) -> str:
    """Search symbols by semantic similarity (meaning) + keyword matching."""
    conn = get_connection()
    results = hybrid_search(conn, query, k, kind)
    return json.dumps(results, indent=2)
```

**Test:** `tests/tools/test_semantic_search.py::test_semantic_search_basic`, `test_hybrid_ranking`

---

### Task 10.2: Register Tool in Server

**File:** `src/ast_tools_server.py` (PATCH)

**Add to tool list:**
```python
@mcp.tool()
async def semantic_search(query: str, k: int = 10, kind: Optional[str] = None) -> str:
    """Search symbols by semantic similarity (meaning) + keyword matching."""
    ...
```

**Update `list_tools()`:** Add `semantic_search` to registry

---

## Phase 11: Incremental Embedding

### Task 11.1: Patch Extractor

**File:** `src/ast_tools/indexer/extractor.py` (PATCH)

**Add embedding generation to symbol creation:**
```python
from ast_tools.embeddings import generate_embedding

def create_symbol(...):
    symbol = Symbol(...)
    
    # Generate embedding (docstring + signature)
    embedding_text = f"{symbol.signature or ''} {symbol.docstring or ''}".strip()
    if embedding_text:
        symbol.embedding = generate_embedding(embedding_text)
    
    return symbol
```

---

### Task 11.2: Patch Cache

**File:** `src/ast_tools/indexer/cache.py` (PATCH)

**Add embedding hash tracking:**
```python
# In file_cache table, add embedding_hash column
# Check: if docstring_hash unchanged, skip embedding generation
```

---

## Phase 12: Batch Backfill

### Task 12.1: Add --embeddings Flag to refresh_index

**File:** `src/ast_tools/tools/refresh_index.py` (PATCH)

**Add CLI arg:**
```python
@click.option('--embeddings', is_flag=True, help='Generate embeddings for all symbols')
```

**Implement backfill:**
```python
if embeddings:
    model = get_model()
    symbols = conn.execute("SELECT id, signature, docstring FROM symbols").fetchall()
    
    batch = []
    for symbol in symbols:
        text = f"{symbol['signature'] or ''} {symbol['docstring'] or ''}".strip()
        if text:
            emb = generate_embedding(text, model)
            batch.append((symbol['id'], emb))
        
        if len(batch) >= 100:
            insert_embeddings_batch(conn, batch)
            batch = []
    
    if batch:
        insert_embeddings_batch(conn, batch)
```

---

## Phase 13: Tests

### Task 13.1: Create Test Files

**Files:**
- `tests/embeddings/test_model.py` (8 tests)
- `tests/embeddings/test_store.py` (10 tests)
- `tests/tools/test_semantic_search.py` (12 tests)

**Test patterns:**
- Model loading, CPU inference
- sqlite-vec insert/search
- Hybrid search ranking validation
- Incremental embedding (changed docstring → re-embed)

---

## Phase 14-17: Audit, Lint, Docs, Commit

Follow standard plan-and-audit workflow:
1. Forward + Reverse audits (parallel dispatch)
2. Synthesis + sign-off
3. Adversarial audit (security, edge cases)
4. Ruff lint + dead code removal
5. Phase 2 report
6. Commit all phases, push to master

---

## Dependencies Graph

```
Phase 6 (Install) → Phase 7 (Schema) → Phase 9 (Store) → Phase 10 (Search Tool)
                                    → Phase 8 (Model) ↗
                                    → Phase 11 (Incremental)
                                    → Phase 12 (Backfill)
                                    → Phase 13 (Tests)
```

---

**Next:** Phase 3-5 (Audits + Synthesis) → Phase 6 (Implementation kickoff)