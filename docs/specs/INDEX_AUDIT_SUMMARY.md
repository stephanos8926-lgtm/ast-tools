# Index Consolidation: Audit Summary

## Verified Findings

### Database fragmentation: 3 physical files
1. `~/.ast-tools/cache/codebase.db` — Main index (symbols, edges, embeddings, KG, co_change)
2. `~/.cache/rw-ast-tools/metrics.db` — Watchdog time-series snapshots (separate!)
3. `~/.ast-tools/index.db` — Curator uses a DIFFERENT file (WRONG!)

### DB path references: 26 hardcoded across 11 files
```
src/ast_tools/config/loader.py
src/ast_tools/curator/daemon.py
src/ast_tools/curator/doctor.py
src/ast_tools/curator/setup_wizard.py
src/ast_tools/curator/vacuum.py
src/ast_tools/database/connection.py     ← has get_db_path() but 10 others DON'T use it
src/ast_tools/tools/co_change.py         ← duplicates get_db_path() logic
src/ast_tools/tools/knowledge_graph.py   ← hardcodes Path.home() / ...
src/ast_tools/tools/project_registry.py  ← uses WRONG path
src/ast_tools/tools/spectral.py          ← uses 3 COMPLETELY DIFFERENT paths
src/ast_tools/watchdog/metrics_store.py   ← separate metrics.db
```

### Critical fixes needed:
1. **spectral.py**: Uses `ast_tools.db` in 3 locations — completely disjoint from codebase.db
2. **curator**: Uses `index.db` — unaware of symbols already in codebase.db
3. **metrics.db**: Totally separate — no atomic coupling with symbol index

### CLI gap:
- No `ast-tools index` command — have `refresh_index` (MCP), `reindex_path` (watcher), `project_add` (registry)
- But no unified "reindex everything" CLI command

### Next:
- Phase 1 implementation per ~/Workspaces/ast-tools/docs/specs/INDEX_CONSOLIDATION.md