# Phase 5: Knowledge Graph — Test Completion Plan

**Mode:** MEDIUM (subagent-driven development, parallel dispatch)
**Date:** 2026-07-02

## What Exists (Already Implemented)
- `src/ast_tools/kg/graph_engine.py` — 311 lines, all 6 methods: `get_neighborhood`, `shortest_path`, `get_centrality_hotspots`, `get_clusters`, `bfs`, `_reconstruct`
- `src/ast_tools/tools/knowledge_graph.py` — 306 lines, 3 MCP tools: `kg_query`, `kg_shortest_path`, `kg_neighborhood`
- `src/ast_tools/tools/__init__.py` — All 3 registered with input schemas
- `tests/tools/test_knowledge_graph.py` — 7 tests (weak, timeout on real DB calls)

## What's Missing (This Sprint)
- `tests/kg/__init__.py` — Empty package init
- `tests/kg/test_graph_engine.py` — Comprehensive unit tests for GraphEngine
- Expand `tests/tools/test_knowledge_graph.py` — Fix timeouts, add real integration tests

## Task Breakdown

### Task A: GraphEngine Unit Tests (`tests/kg/test_graph_engine.py`)
Target: 35-45 test methods
- Test DB setup helper (in-memory SQLite with symbols + edges + dependency_metrics)
- `get_neighborhood`: 1-hop, 2-hop, max_nodes limit, max_depth limit, disconnected symbol
- `shortest_path`: direct neighbors, multi-hop, bidirectional, no-path, same node
- `get_centrality_hotspots`: returns top-N, ordering, handles empty
- `get_clusters`: 2-node cluster, 3-node+ cluster, min_size filter, no edges yields empty
- `bfs`: depth_limit=1, depth_limit=3, respects visited set (cycles)
- Edge cases: non-existent symbol ID, empty database, single node with self-referencing edge

### Task B: Knowledge Graph MCP Tool Tests (`tests/tools/test_knowledge_graph.py`)
Target: 15-20 test methods
- Fix existing tests to use tmp_path DB instead of real DB (eliminate timeouts)
- `kg_neighborhood`: symbol not found, found with results, found with no edges
- `kg_shortest_path`: both symbols not found, one not found, path exists, no path
- `kg_query`: complete flow, empty results, query_with_no_results
- Tool registration: all 3 registered, schemas parseable

## Acceptance Criteria
- [ ] `tests/kg/__init__.py` exists (empty)
- [ ] `tests/kg/test_graph_engine.py` has 35-45 tests, all passing
- [ ] `tests/tools/test_knowledge_graph.py` has 15-20 tests, all passing
- [ ] Combined total >= 60 tests
- [ ] All tests run in <30s (in-memory DB, no real deps)
- [ ] No regressions in existing test suite
