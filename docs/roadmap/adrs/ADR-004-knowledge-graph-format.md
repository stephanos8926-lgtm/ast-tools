# ADR-004: Knowledge Graph Storage Format

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools currently has `knn_builder.py` that builds a KNN graph from embedding vectors. This provides "nearest neighbors" queries but isn't a full knowledge graph — it lacks typed edges, graph traversal APIs, and cross-repository capabilities.

## Decision

Extend the existing SQLite schema to support a **lightweight property graph** using the existing `edges` table as the foundation:

### Schema Extension

```sql
-- Extend existing edges table (already has source_id, target_id, edge_type)
ALTER TABLE edges ADD COLUMN weight REAL DEFAULT 1.0;
ALTER TABLE edges ADD COLUMN metadata TEXT;  -- JSON blob for custom attributes
ALTER TABLE edges ADD COLUMN created_at TEXT DEFAULT (datetime('now'));

-- New: Graph traversal index
CREATE INDEX idx_edges_source_type ON edges(source_id, edge_type);
CREATE INDEX idx_edges_target_type ON edges(target_id, edge_type);

-- New: Symbol clusters for concept extraction
CREATE TABLE IF NOT EXISTS symbol_clusters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- New: Cluster membership (many-to-many)
CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id INTEGER NOT NULL REFERENCES symbol_clusters(id) ON DELETE CASCADE,
    symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (cluster_id, symbol_id)
);
```

### Edge Types

| Edge Type | Source | Target | Description |
|-----------|--------|--------|-------------|
| `imports` | Module | Module | Import dependency |
| `calls` | Function | Function | Call graph edge |
| `inherits` | Class | Class | Inheritance relationship |
| `implements` | Class | Protocol/ABC | Interface implementation |
| `references` | Any | Any | Cross-file reference |
| `contains` | Module | Symbol | Containment hierarchy |
| `similar` | Symbol | Symbol | Semantic similarity (KNN) |
| `co-occurs` | Symbol | Symbol | Frequently imported together |

### Query API

```python
# Proposed SDK methods
kg.neighbors(symbol_id, edge_types=["calls", "imports"], max_depth=2)
kg.path(source_id, target_id, max_length=5)
kg.cluster(symbol_id)  # Returns cluster memberships
kg.concept(codebase_path)  # High-level "what does this do?"
```

### Consequences

- Positive: Extends existing schema — no new database needed
- Positive: SQL + Python for querying — no graph database dependency
- Positive: Fits within the existing SQLite backup/restore flow
- Negative: Not suitable for >10M symbols (graph traversal in SQLite is slow at scale)
- Negative: No graph query language (Cypher/SPARQL) — Python API only

## Alternatives Considered

1. **Dedicated graph database (Neo4j/ArangoDB)**: Rejected — adds deployment complexity; overkill for single-machine
2. **NetworkX in-memory**: Rejected — doesn't persist; memory-bound
3. **RDF/SPARQL store**: Rejected — too heavyweight for a developer tool