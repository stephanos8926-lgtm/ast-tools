# ast-tools Index Consolidation Audit & Spec

**Date:** 2026-07-19
**Author:** Lucien + Steven Page
**Status:** For Review

---

## Part 1: Formal Audit — All Indexing Layers

### 1.1 Current State — Fragmented Indexes

| # | Index Name | Database File | Tables/Structures | Created By | Purpose |
|---|---|---|---|---|---|
| **A** | **Core Symbol Index** | `~/.ast-tools/cache/codebase.db` | `symbols`, `edges`, `file_cache`, `symbols_fts`, `symbols_vec`, `dependency_metrics`, `embedding_similarity`, `knn_graph`, `audit_log` | `refresh_index()` | AST parsing → symbols, edges, embeddings |
| **B** | **Co-Change Index** | `~/.ast-tools/cache/codebase.db` | `co_change_pairs`, `churn_metrics` | `GitMiner.mine_pairs()` | Git history → file change patterns |
| **C** | **Knowledge Graph** | `~/.ast-tools/cache/codebase.db` | Reads from `symbols` + `edges` + `dependency_metrics` | `GraphEngine` | BFS/DFS traversal over existing tables |
| **D** | **Watchdog Metrics** | `~/.cache/rw-ast-tools/metrics.db` | `codebase_snapshots` (time-series) | `MetricsStore` | Periodic codebase stat snapshots |
| **E** | **Curator State** | `.{project}/.ast-tools/index.db` | `LLmCurator.daily_audit()` reads codebase.db | `LLmCurator` | Index health, staleness, auto-fix |
| **F** | **Project Registry** | `~/.config/rw-ast-tools/config.yaml` | YAML list of projects | `project_registry` tools | Project → path mapping |
| **G** | **Semantic DB (FORGE)** | External system | Separate codebase | `semantic-db` skill | Legacy research DB |

### 1.2 Critical Findings

#### ✅ Same DB = Good
- **A, B, C** all live in `codebase.db` — already unified
- **B** (co_change) stores tables inside codebase.db: correct
- **C** (knowledge graph) is pure read-only views over A: correct

#### ❌ Separate DB Issues
- **D** (`metrics.db`): Time-series snapshots split from main index → no atomic relationship between symbols and their metrics history
- **E** (curator `index.db`): Uses DIFFERENT path from codebase.db — causes stale backup/audit mismatches
- **F** (project registry): YAML config, not a DB — fragile, no ACID, hard to sync across machines

#### ❌ Multiple `db_path` References (DRY violation)
```
codebase.db referenced in:
- database/connection.py    → DEFAULT_DB_PATH = get_cache_dir() / "codebase.db"
- tools/co_change.py        → get_cache_dir() / "codebase.db"          (duplicate!)
- tools/knowledge_graph.py  → Path.home() / ".cache" / "ast-tools" / "codebase.db" (duplicate!)
- curator/daemon.py          → AST_TOOLS_DIR / "cache" / "codebase.db"   (duplicate!)
- curator/doctor.py          → AST_TOOLS_DIR / "cache" / "codebase.db"   (duplicate!)
- curator/vacuum.py          → AST_TOOLS_DIR / "cache" / "codebase.db"   (duplicate!)
- curator/setup_wizard.py    → config_dir / "cache" / "codebase.db"      (duplicate!)
- project_registry.py        → Path(path) / ".ast-tools" / "cache" / "codebase.db" (WRONG path!)
- tools/spectral.py          → project_root / ".db" / "ast_tools.db"      (COMPLETELY WRONG path!)
```

#### ❌ `spectral.py` Uses DIFFERENT Database Pattern
```python
project_root / ".db" / "ast_tools.db"   # L1751
project_root / "ast_tools.db"           # L1752
project_root / "index" / "ast_tools.db"  # L1753
```
**Three different databases** — none of which are codebase.db.

#### ❌ `curator/daemon.py` Uses DIFFERENT Path
```python
self.db_path = self.project_root / ".ast-tools" / "index.db"  # Line 99
```
This is **index.db**, NOT codebase.db. So the curator operates on a completely different database from the indexer.

### 1.3 Summary: Source of Truth Breakdown

```
                    ┌─────────────────────────────┐
                    │     "THE INDEX" (vague)      │
                    └──────────┬──────────────────┘
                               │
         ┌─────────────────────┼──────────────────────┐
         │                     │                      │
    ┌────▼─────┐        ┌──────▼──────┐        ┌──────▼──────┐
    │codebase.db│        │  metrics.db │        │  index.db   │
    │(main)     │        │(time-series)│        │(curator)    │
    │symbols    │        │logically    │        │DIFFERENT    │
    │edges      │        │SHOULD be in │        │DATABASE!    │
    │co_change  │        │codebase.db  │        │             │
    │embeddings │        │             │        │             │
    │KG (views) │        │             │        │             │
    └───────────┘        └─────────────┘        └─────────────┘
```

**We have 3 separate databases when we should have ONE.** The knowledge graph is fine (views over codebase.db), but metrics.db and index.db are separate physical files.

---

## Part 2: Industry Research — How Others Solved It

### Key patterns from the research:

#### Pattern 1: Single SQLite = All Layers (Codebase-Memory, Codeintel)
- Codebase-Memory: "All state lives in a single SQLite file" — symbols, edges, call graph, communities, all in one DB
- Codeintel: "Durable control-plane state belongs in PostgreSQL. Graph state belongs in NebulaGraph." — but they're a multi-tenant SaaS, not a local tool

#### Pattern 2: Single Graph DB = All Backends (Code Atlas, Prometheus)
- Code Atlas: Memgraph (graph + vector + BM25, single backend)
- Prometheus: Neo4j (single graph DB for AST + text + file hierarchy)

#### Pattern 3: Multi-DB = Valid for SCALE (engineering-support-system)
- Uses Qdrant + Neo4j as "triangulated truth" — but this is a multi-component system, not a code index

#### Pattern 4: Tiered Pipeline, Single DB (Lore)
- Lore: All stages (SCIP → LSP → Import → Embed) write to ONE SQLite DB. Time-series (git history) is in the same DB
- Key insight: **tiered pipeline, but single output database**

### Best Match for ast-tools:

**The Codebase-Memory + Lore pattern** fits our scale perfectly:
- Single SQLite file for ALL indexing data
- Tiered pipeline (parse → extract → resolve → enrich → embed)
- But ALL stages write to the same DB
- Background watcher uses inotify + content hash → incremental reindex
- **ONE `reindex` call triggers all stages sequentially, in a single transaction**

---

## Part 3: Recommended Architecture — The Unified Index

### 3.1 Target State

```
┌─────────────────────────────────────────────────────────────┐
│                   ~/.ast-tools/cache/codebase.db             │
│                    (ONE SOURCE OF TRUTH)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌──────────────────┐  ┌──────────────────────┐             │
│ │ SYMBOL LAYER     │  │ EMBEDDING LAYER      │             │
│ │ - symbols        │  │ - symbols_vec        │             │
│ │ - edges          │  │ - embedding_similarity│            │
│ │ - symbols_fts    │  │ - knn_graph          │             │
│ │ - file_cache     │  │ - embedding_model_v  │             │
│ └──────────────────┘  └──────────────────────┘             │
│                                                             │
│ ┌──────────────────┐  ┌──────────────────────┐             │
│ │ RELATION LAYER   │  │ ANALYTICS LAYER      │             │
│ │ - edges          │  │ - dependency_metrics │             │
│ │ - co_change_pair │  │ - churn_metrics      │             │
│ │ - callgraph_edges│  │ - codebase_snapshots │             │
│ └──────────────────┘  └──────────────────────┘             │
│                                                             │
│ ┌──────────────────┐  ┌──────────────────────┐             │
│ │ GOVERNANCE LAYER │  │ PROJECT REGISTRY     │             │
│ │ - audit_log      │  │ - projects           │             │
│ │ - schema_version │  │ - project_watch      │             │
│ └──────────────────┘  └──────────────────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Consolidation Tasks

#### P0: Merge `metrics.db` → `codebase.db`
- Move `codebase_snapshots` table into codebase.db
- Migrate existing data from `~/.cache/rw-ast-tools/metrics.db`
- Remove `MetricsStore` class — use schema.py tables
- Add schema migration v6

#### P0: Fix curator path
- Change `LLmCurator.__init__` from `index.db` → `codebase.db`
- Remove hardcoded `AST_TOOLS_DIR / "cache" / "codebase.db"` references (8+ places)
- All code must use `get_db_path()` from database/connection.py

#### P0: Fix spectral.py database path
- `spectral.py` uses `project_root / ".db" / "ast_tools.db"` — completely wrong
- Should use standard `get_db_path()` or accept a `db_path` parameter
- Currently spectral clustering WRITES TO A DIFFERENT DB than everything else

#### P1: Single Source of Truth for db_path
- Add `/codebase.db` as the canonical path referenced by ONE function: `get_db_path()`
- Remove all 8+ hardcoded `.db` path references across codebase
- Add `ast_tools.database.connection.get_unified_db_path(project_root)` for project-scoped indices

#### P1: Unified `reindex` pipeline
- One `reindex` call triggers all stages atomically:
  1. Parse files → symbols + edges (existing)
  2. Diff old → incremental update (existing)
  3. Generate embeddings for new/modified (existing)
  4. Build KNN graph (existing, separate)
  5. Compute dependency metrics (existing, separate)
  6. Mine co-change from git (existing, separate call)
  7. Record codebase snapshot to metrics layer
- **Single transaction, single DB, single call**

#### P2: Project registry → DB table
- Migrate from `~/.config/rw-ast-tools/config.yaml` to `projects` table in codebase.db
- ACID operations, atomic project_add/project_remove
- sync across multi-project DB (cross-project query becomes SQL JOIN)

### 3.3 Schema Migration v6

```sql
-- v6: Index Consolidation

-- Move metrics snapshots into unified DB
CREATE TABLE IF NOT EXISTS codebase_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codebase_id TEXT NOT NULL,
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    files INTEGER DEFAULT 0,
    loc INTEGER DEFAULT 0,
    functions INTEGER DEFAULT 0,
    classes INTEGER DEFAULT 0,
    deps INTEGER DEFAULT 0,
    size_bytes INTEGER DEFAULT 0,
    commits_since_last INTEGER DEFAULT 0,
    new_files INTEGER DEFAULT 0,
    deleted_files INTEGER DEFAULT 0,
    inserted_lines INTEGER DEFAULT 0,
    deleted_lines INTEGER DEFAULT 0
);

-- Projects table (migrate from YAML)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL,
    auto_watch INTEGER DEFAULT 1,
    last_indexed_at TEXT,
    symbol_count INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    index_state TEXT DEFAULT 'pending',  -- pending, indexing, ready, stale
    watch_pair_ids TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(root_path);
CREATE INDEX IF NOT EXISTS idx_projects_state ON projects(index_state);

-- Index for snapshot history
CREATE INDEX IF NOT EXISTS idx_snapshots_cb_ts ON codebase_snapshots(codebase_id, ts);
```

### 3.4 New Unified Reindex API

```python
def reindex_all(project_path: str, force: bool = False) -> dict:
    """
    Reindex ALL layers for a project in a single transaction.
    
    Stages (all within one BEGIN/COMMIT):
    1. File scan → AST parse → symbols/edges
    2. Incremental diff → update symbols (preserve IDs for unchanged)
    3. Generate embeddings for new/modified symbols
    4. Build KNN graph
    5. Compute dependency metrics
    6. Mine co-change pairs
    7. Record snapshot to metricsStore
    8. Update project registry state
    
    Returns: Unified statistics dict with per-layer counts.
    """
```

### 3.5 CLI Tool Surface

```bash
# One command reindexes everything
ast-tools index                # reindex current project (all layers)
ast-tools index --path /path   # reindex another project
ast-tools index --force        # full rebuild (skip incremental diff)
ast-tools index --watch        # start daemon watching all projects

# Project management (in DB now)
ast-tools project add /path
ast-tools project remove /path
ast-tools project list
ast-tools project info /path

# Index queries (read from unified DB)
ast-tools index status         # current state of all projects
ast-tools index stats          # symbol/edge/embedding counts
ast-tools index health         # stale files, missing embeddings, etc.
```

---

## Part 4: Implementation Plan

### Phase 1: Audit + Path Convergence (1 day)
- [ ] Find ALL hardcoded `.db` paths → consolidate to `get_db_path()`
- [ ] Fix `spectral.py` database path bug
- [ ] Fix `curator/daemon.py` index.db → codebase.db
- [ ] Fix `project_registry.py` `.ast-tools/cache/codebase.db` path

### Phase 2: Schema Migration v6 (1 day)
- [ ] Add `codebase_snapshots` table to codebase.db
- [ ] Add `projects` table to codebase.db
- [ ] Write migration data script (metrics.db → codebase.db, YAML → projects table)
- [ ] Write migration tests

### Phase 3: Unified reindex Pipeline (1 day)
- [ ] Create `indexer/pipeline.py` → `reindex_all()` wraps all stages
- [ ] Wire to CLI (`ast-tools index`)
- [ ] Write integration tests

### Phase 4: Cleanup (1 day)
- [ ] Remove `MetricsStore` class
- [ ] Delete `~/.cache/rw-ast-tools/metrics.db` (after migration)
- [ ] Update all docs
- [ ] Release v0.3.0