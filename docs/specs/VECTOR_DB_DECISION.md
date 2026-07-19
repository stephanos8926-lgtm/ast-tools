# ast-tools Vector Database Decision Analysis

**Date:** 2026-07-19
**Authors:** Lucien + Steven Page
**Decision Gate:** Before index consolidation implementation

---

## TL;DR Recommendation

**Stay on sqlite-vec for NOW. Design adapter pattern with pgvector as explicit target. Do NOT migrate to a specialized DB.**

Reason: sqlite-vec just shipped ANN support (rescore + DiskANN + IVF in alpha), our current scale is 7K vectors (dev), migration cost at our current scale is unjustifiable complexity. The adapter pattern future-proofs us.

---

## Section 1: Where We Are Right Now

| Metric | Workstation | Dev Server |
|--------|------------|------------|
| Symbols indexed | 56 | 7,394 |
| Vector embeddings | 0 (not generated) | 0 |
| Database size | ~138KB | ~2MB |
| SQLite version | 3.50.4 | — |
| sqlite-vec loaded | ✅ vec0 extension | — |

**We have zero production vectors.** The `symbols_vec` table exists (schema migration v2), `generate_embeddings=True` flag works on `refresh_index`, but we've never generated embeddings at scale. This means we can make this decision with zero data migration cost.

---

## Section 2: Benchmark Data (What The Numbers Say)

### 2.1 sqlite-vec performance (our current backend)

| Vectors | Dimensions | Query Time | Index | Notes |
|---------|-----------|------------|-------|-------|
| 10K | 384 (MiniLM) | 2-3ms | Brute-force (exact) | SIMD via AVX2/NEON |
| 100K | 384 | 4-12ms | Brute-force | Still exact, sub-15ms |
| 500K | 384 | 20-50ms | Brute-force | Exact; 99% use cases here |
| 1M | 384 | 50-100ms | Brute-force | Linear degradation begins |
| 1M | 128 (SIFT1M) | 17ms | Static mode | Competitive with FAISS (10ms) |
| 1M | 3072 (OpenAI) | 200ms+ | Brute-force | Binary quant: 92% recall @ 4ms |
| 5M+ | any | seconds | Brute-force | Needs ANN |

**sqlite-vec ANN (as of v0.1.10-alpha.1, March 2026):**
- **rescore**: Binary/int8 quantized coarse search → rescore on full float. Still O(N) but on compressed vectors
- **IVF**: Experimental (hidden behind flag), k-means clustering, fast inserts after training
- **DiskANN**: Graph-based, no training required, disk-resident, slow writes to prune

**Key sqlite-vec advantages:**
- Exact nearest-neighbor (100% recall) — no tuning recall vs. latency
- Pure C, zero dependencies, 200KB compiled
- WASM support (browser, edge)
- Single `.db` file portability

### 2.2 pgvector performance (adapter target)

| Vectors | Dimensions | Query Time | Index | Notes |
|---------|-----------|------------|-------|-------|
| 1M | 384 | <10ms | HNSW | Sub-10ms ANN |
| 10M | 768 (Cohere) | ~14ms p99 | HNSW (0.7) | Standard pgvector |
| 50M | 768 | 74ms p99 / 471 QPS | pgvectorscale (DiskANN) | 11.4× Qdrant throughput |
| 100M | 1536 (ada-002) | 58ms p99 @ 20% filter | HNSW | Starts to degrade |

**pgvector + pgvectorscale vs Qdrant (Tiger Data benchmark, 50M vectors @ 99% recall):**

| Metric | pgvector + pgvectorscale | Qdrant |
|--------|--------------------------|--------|
| **QPS** | **471.57** | 41.47 |
| p50 latency | 31.07ms | 30.75ms |
| p95 latency | 60.42ms | **36.73ms** |
| p99 latency | 74.60ms | **38.71ms** |
| Index build | 11.1 hours | 3.3 hours |

Postgres wins **throughput** (11.4×). Qdrant wins **tail latency** (48% better p99) and **index build speed** (3.3× faster).

### 2.3 LanceDB (alternative embedded option)

- Embedded library (like sqlite-vec, no server process)
- HNSW approximate search (ANN built-in)
- Apache Arrow columnar format (Parquet-compatible)
- Python + Rust rewrite (2025: 4× faster than original)
- Multi-modal: raw data + embeddings + metadata in one table
- Best for: read-heavy, batch workloads, Arrow ecosystem
- Weakness: v0.x, smaller ecosystem, no built-in FTS

---

## Section 3: The Adapter Pattern — What Others Did

### Pattern A: AgentOS (TypeScript)
```
SQLite brute-force (0→1K) → HNSW sidecar auto-builds at 1K
  → Postgres + pgvector (500K→10M) via MigrationEngine.migrate()
  → Qdrant (10M→1B+) via MigrationEngine.migrate()
```
**Single StorageAdapter interface** — application code identical across backends.

### Pattern B: Shaktiman (Go, Build Tags)
```go
// Build tags control available backends:
// go build -tags "sqlite_fts5 hnsw" → SQLite + HNSW (local)
// go build -tags "postgres pgvector" → Postgres + pgvector (team)
// go build -tags "postgres qdrant" → PG + Qdrant (cloud)
```
**Config-driven factory** — `vector.backend = "brute_force" | "hnsw" | "qdrant" | "pgvector"`. Validation enforces compatible pairs (Postgres + brute_force = rejected).

### Pattern C: Datus (Python)
```
RelationalAdapter contract → SQLite (default), PostgreSQL (production)
VectorAdapter contract → LanceDB (default), Qdrant, pgvector
```
**Two separate adapter contracts** — relational and vector are independent. `agent.yml` one-line change to switch.

### Pattern D: turbomem / @framers/sql-storage-adapter
```
StorageAdapter interface → PGlite (WASM PG+pgvector), sqlite-vec, Upstash Vector
SqlDialect interface → auto-translates SQL between SQLite and PG
IFullTextSearch interface → FTS5 (SQLite) / tsvector (Postgres)
```
**Feature abstraction layer** — not just storage, but SQL dialect + FTS + BLOB codec all adapt.

---

## Section 4: Decision Matrix

### Option A: Stay sqlite-vec, No Adapter (Current)
| Factor | Score |
|--------|-------|
| Implementation cost | ✅ Zero |
| Local-only user story | ✅ Single file, no daemon |
| Enterprise scaling | ❌ 500K ceiling, no sharding/replication |
| SQL dialect flexibility | ❌ SQLite-only |
| Future migration cost | ❌ Rewrite required |
| ANN support | ✅ Just shipped (alpha) |

### Option B: Migrate to pgvector NOW (Backend Swap)
| Factor | Score |
|--------|-------|
| Implementation cost | ❌ PostgreSQL server requirement |
| Local-only user story | ❌ Breaks single-file simplicity |
| Enterprise scaling | ✅ 50M+ vectors, HNSW, DiskANN |
| SQL dialect | ✅ Rich SQL, JSONB, FTS |
| Future migration cost | ✅ Already at target |
| Dev experience | ❌ Docker/process for local dev |

### Option C: Adapter Pattern + sqlite-vec Default (RECOMMENDED)
| Factor | Score |
|--------|-------|
| Implementation cost | ⚠️ Medium (design contracts, ~1 week) |
| Local-only user story | ✅ Preserved (sqlite-vec default) |
| Enterprise scaling | ✅ Config: `database.backend = "postgres"` |
| SQL dialect | ✅ Abstracted behind contracts |
| Future migration cost | ✅ Zero — swap config line |
| ANN support | ✅ sqlite-vec rescore/IVF/DiskANN + pgvector HNSW |
| Testability | ✅ In-memory SQLite for unit tests |

### Option D: Migrate to Qdrant/LanceDB
| Factor | Score |
|--------|-------|
| Implementation cost | ❌ New service/API |
| Local-only | ❌ Qdrant: Docker; LanceDB: embedded OK |
| Enterprise scaling | ✅ Qdrant: 1B+; LanceDB: 10M+ |
| Relational queries | ❌ Separate store, sync problem |
| Operations | ❌ New service to manage |

### Option E: Dual-Write (sqlite-vec + pgvector simultaneously)
| Factor | Score |
|--------|-------|
| Implementation cost | ❌ High (dual consistency) |
| Migration | ✅ Gradual |
| Complexity | ❌ Two stores to keep in sync |
| Reasoning | Overengineered at our scale |

---

## Section 5: Detailed Wins & Losses for RECOMMENDED Option (C)

### WINS

#### 1. Local-First User Story Preserved (Critical)
```python
# Default: zero config, single file
import ast_tools
# → ~/.ast-tools/cache/codebase.db (SQLite + sqlite-vec)
# → ast-tools index --path /my/project
# → Everything in one database file
```
This is what makes ast-tools competitive against Code Atlas and Lore. The "no Docker, no daemon" story is the differentiation.

#### 2. Enterprise Path Opens
```python
# Enterprise: one config change
# pyproject.toml or ast-tools.yaml:
# [database]
# backend = "postgres"
# connection_string = "postgresql://..."
# [vector]
# backend = "pgvector"
```
Same tools. Same CLI. Same API surface. Different database.

#### 3. Testing Stays Fast
```python
# Unit tests: in-memory SQLite — sub-ms setup
conn = sqlite3.connect(":memory:")
# No Docker container, no port management, no wait-for-it
```

#### 4. SQL Abstraction Wins
- `SqlDialect` translates `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING` across backends
- `IFullTextSearch` bridges FTS5 → tsvector/GIN
- `IVectorStore` wraps sqlite-vec vec0 / pgvector HNSW
- Application code calls `context.execute("FIND_NEAREST", query)` — backend handles the SQL

#### 5. Migration is a Single CLI Command
```bash
ast-tools migrate --from sqlite --to postgres --connection-string "..."
# → Migrates schema, symbols, edges, embeddings, project registry
# → Same call for sqlite→postgres, postgres→postgres (team scale)
```

#### 6. sqlite-vec Just Shipped ANN
As of March-April 2026 (literally weeks ago):
- **rescore** index: binary/int8 quantized coarse search + full rescore
- **IVF** index: experimental, k-means centroids
- **DiskANN** index: graph-based, disk-resident, no training
- This eliminates the "sqlite-vec is brute-force only" argument. At 500K vectors, rescore gives 10× speedup at 92% recall.

### LOSSES

#### 1. Adapter Abstraction Overhead (~1 week dev)
- Need to design contracts: `IDatabaseBackend`, `IVectorBackend`, `ISqlDialect`, `IFullTextSearch`
- Need to implement 2 concrete backends: `SqliteBackend`, `PostgresBackend`
- Need migration tooling
- ~500-800 lines of abstraction code

#### 2. sqlite-vec ANN is Alpha Software
- v0.1.10-alpha.1: rescore, IVF (hidden), DiskANN
- IVF is experimental (behind SQLITE_VEC_EXPERIMENTAL_IVF_ENABLE flag)
- DiskANN has expensive DELETEs (known bug, being fixed)
- pgvector HNSW is production-battle-tested for years

#### 3. Dual Maintenance
- Every new DB feature must work on both backends
- SQL dialect differences will bite (e.g., `json_extract` vs `jsonb`, `INSERT OR IGNORE` vs `ON CONFLICT`)
- Tests must run against both backends

#### 4. Postgres is Heavy for Local Dev
- Local-only users who want pgvector need Docker or a PG install
- This is the fundamental tradeoff the adapter pattern can't eliminate
- But it's opt-in — sqlite-vec remains default

#### 5. No Real-Time Distributed Vector Operations
- Even with Postgres+pgvector, we don't get Qdrant's native sharding or Milvus's GPU indexing
- At 100M+ vectors, pgvector needs pgvectorscale (StreamingDiskANN) which is Timescale-specific
- This is a "cross that bridge when we get there" problem

---

## Section 6: Concrete Architecture

### 6.1 Contracts

```python
# ast_tools/storage/contracts.py

class IDatabaseBackend(Protocol):
    """Relational storage contract."""
    def connect(self) -> Connection: ...
    def execute(self, sql: str, params: dict) -> Cursor: ...
    def transaction(self) -> ContextManager: ...
    @property
    def dialect(self) -> ISqlDialect: ...

class ISqlDialect(Protocol):
    """SQL dialect abstraction."""
    def insert_or_ignore(self, table: str, cols: list[str]) -> str: ...
    def json_extract(self, col: str, path: str) -> str: ...
    def vector_distance(self, col: str, query: str) -> str: ...

class IVectorBackend(Protocol):
    """Vector storage contract."""
    def store_vectors(self, ids: list[str], vectors: list[list[float]]) -> None: ...
    def search(self, query: list[float], k: int, filters: dict | None) -> list[SearchResult]: ...
    def delete_vectors(self, ids: list[str]) -> None: ...
    def count(self) -> int: ...

class IFullTextSearch(Protocol):
    """Full-text search contract."""
    def create_index(self, table: str, columns: list[str]) -> None: ...
    def search(self, query: str, limit: int) -> list[SearchResult]: ...
    def rank_expression(self) -> str: ...
```

### 6.2 Backend Implementations

| Contract | SqliteBackend | PostgresBackend |
|----------|--------------|-----------------|
| `IDatabaseBackend` | `sqlite3.connect` + WAL | `psycopg2` connection pool |
| `ISqlDialect` | `INSERT OR IGNORE`, `json_extract()`, `vec_distance_knn()` | `ON CONFLICT DO NOTHING`, `jsonb`, `<=>` |
| `IVectorBackend` | sqlite-vec `vec0` virtual tables | pgvector `vector(N)` columns + HNSW |
| `IFullTextSearch` | FTS5 virtual tables | tsvector + GIN index |

### 6.3 Configuration

```yaml
# ast-tools.yaml (or pyproject.toml [tool.ast-tools])
[database]
# backend = "sqlite"  # default
# backend = "postgres"
# connection_string = "postgresql://..."

[vector]
# backend = "sqlite-vec"  # default
# backend = "pgvector"
# index_type = "hnsw"  # or "ivfflat", "diskann"

[fulltext]
# backend = "fts5"  # default (SQLite)
# backend = "tsvector"  # PostgreSQL
```

### 6.4 Factory

```python
# ast_tools/storage/factory.py

def create_database(config: AstToolsConfig) -> IDatabaseBackend:
    backend = config.database.backend  # "sqlite" | "postgres"
    if backend == "sqlite":
        return SqliteBackend(config)
    elif backend == "postgres":
        return PostgresBackend(config)
    raise ValueError(f"Unknown backend: {backend}")

def create_vector_store(config: AstToolsConfig, db: IDatabaseBackend) -> IVectorBackend:
    backend = config.vector.backend  # "sqlite-vec" | "pgvector"
    if backend == "sqlite-vec":
        return SqliteVecBackend(db, config)
    elif backend == "pgvector":
        return PgvectorBackend(db, config)
    raise ValueError(f"Unknown backend: {backend}")

# Validation
def validate_config(config: AstToolsConfig) -> list[str]:
    warnings = []
    if config.database.backend == "postgres" and config.vector.backend == "sqlite-vec":
        warnings.append("sqlite-vec with Postgres: vectors stored in separate SQLite file, not in PG")
    if config.database.backend == "sqlite" and config.vector.backend == "pgvector":
        raise ConfigError("pgvector requires PostgreSQL backend")
    return warnings
```

---

## Section 7: Timing — When to Implement

### Phase 1: NOW — Index Consolidation (sqlite-vec only)
- Merge all databases into `codebase.db` (current work)
- Fix spectral.py, curator paths, metrics.db
- **No adapter pattern yet** — stay on sqlite-vec

### Phase 2: AFTER consolidation — Adapter Contracts
- Design and implement `IDatabaseBackend`, `IVectorBackend`, `ISqlDialect`, `IFullTextSearch`
- Implement `SqliteBackend` (wrap existing code)
- All new code writes against contracts, not raw sqlite3

### Phase 3: Postgres Backend (when first enterprise user asks)
- Implement `PostgresBackend`, `PgvectorBackend`, `PostgresDialect`, `PostgresFts`
- Migration tool: `ast-tools migrate`
- Not before someone actually needs it

### Phase 4: Future Options (2027+)
- `QdrantBackend` for billion-vector scale
- `LanceDBBackend` for Arrow/Parquet ecosystem
- `RemoteBackend` for cloud-hosted ast-tools

---

## Section 8: Explicit Anti-Decision

### We are NOT doing:
- ❌ Migrating to pgvector NOW (unnecessary at 7K vectors)
- ❌ Migrating to Qdrant/Pinecone/Weaviate/Milvus (separate service = breaks local-first)
- ❌ Dual-write (sqlite-vec + pgvector simultaneously) (overengineered)
- ❌ Dropping sqlite-vec (local-first is our differentiator)

### We ARE doing:
- ✅ Staying on sqlite-vec as default
- ✅ Designing adapter contracts during index consolidation
- ✅ Building both backends to the same contract
- ✅ Letting configuration choose backend at runtime

---

## Section 9: Key References

1. **sqlite-vec v0.1.10-alpha.1** — ANN support shipped March 2026: rescore + IVF + DiskANN
2. **pgvector vs Qdrant benchmark** — Tiger Data/Timescale: 11.4× throughput for PG, Qdrant wins tail latency
3. **AgentOS 4-tier scaling** — SQLite→HNSW sidecar→PG+pgvector→Qdrant via MigrationEngine
4. **Shaktiman ADR-003** — Build-tag-based adapter registry with config validation
5. **framers/sql-storage-adapter** — Full SqlDialect + IFullTextSearch + IBlobCodec abstraction
6. **"pgvector vs sqlite-vec: You Probably Don't Need Postgres"** — LLBBL Blog 2026: local-first keeps sqlite-vec