# AST-Tools Changelog

All notable changes to the AST-Tools MCP server.

## [v0.1.2-dev] — 2026-07-03

### ✨ Features
- **True 6-factor RRF**: `semantic_search` now fuses 6 ranking dimensions — FTS5 + vector + recency + usage + kind priority + callgraph centrality via `utils/rrf.py` (Reciprocal Rank Fusion, k=60)
- **ContextInjector fixed**: callgraph factor now reads real `dependency_metrics.centrality` from DB (was hardcoded 0.5 stub)

### 🔧 Fixes
- **ast_tools_server.py**: Restored missing `main()` entry point and `if __name__` block (was accidentally deleted in Phase 5 server cleanup, commit `a45d137`). MCP server was starting, importing all tools, and exiting without serving.
- **GitHub MCP**: Added `GITHUB_TOKEN` env var to MCP server config (was unauthenticated)
- **mcp_discovery_timeout**: Increased from 2.5s to 60s (ast-tools takes ~8s to load)
- **context_file_max_chars**: Fixed quoted string `'250000'` → proper integer `250000`

### 📚 Documentation
- Full documentation audit: all docs now reflect actual 55 tools, 82 source files, 51 test files
- SESSION_STATE.md rewritten with accurate phase completion status
- DOCUMENTATION_INDEX.md updated with correct metrics
- README.md tool count corrected (43 → 55), new phase categories added
- Global state file updated

---

## [v0.1.1-dev] — 2026-07-02

### 🚀 New Features

#### Phase 5: Knowledge Graph
- **GraphEngine** class (`src/ast_tools/kg/graph_engine.py`, 311 lines)
  - `get_neighborhood()` — BFS-based neighborhood traversal
  - `shortest_path()` — Bidirectional BFS for shortest paths
  - `centrality()` — Degree centrality scoring
  - `clusters()` — Connected components detection
- **3 MCP tools**: `kg_query`, `kg_shortest_path`, `kg_neighborhood`
- **35 tests**, 0 failures, 19s runtime

#### Phase 6: Co-Change Analysis
- **GitMiner** (`src/ast_tools/cochange/git_miner.py`, 324 lines)
  - Parses `git log --numstat` for co-change pairs
  - Computes: frequency, coupling score, avg gap, churn metrics
- **Hotspot detector** (`src/ast_tools/cochange/hotspot.py`)
  - Combines churn × coupling for high-risk file detection
- **4 MCP tools**: `co_change_predict`, `co_change_hotspots`, `co_change_history`, `co_change_diff`
- **35 tests**, 0 failures, 14.5s runtime

#### Phase 10A (Completion)
- **repo_skeleton** (`src/ast_tools/tools/repo_skeleton.py`, 359 lines)
  - Project type detection (Python, Node, Rust, Go, etc.)
  - Dependency inference from pyproject.toml, package.json, etc.
  - ASCII directory tree generation
  - **48 tests**, ~2s runtime (was 15s+ timeout)
- **file_related_suggest** (`src/ast_tools/tools/file_related.py`, 435 lines)
  - Test file pattern matching (`test_*.py`, `*_test.py`)
  - Import relationship detection
  - Sibling detection + call graph integration
  - **18 tests**, ~0.2s runtime (was infinite timeout)

#### Phase 10.1: Transitive Import Resolution
- **transitive_dependents** tool — "what breaks if I change X?"
  - BFS-based transitive dependency chain with depth tracking
  - Direction: dependents (who imports this) or dependencies (what this imports)
  - Risk classification: none/low/medium/high
- Extracted `_build_import_graph()` reusable function
- Wired live graph into `impact_analysis.py` (replaced stale JSON file)
- **11 tests**, **53 tools at this point**

#### Phase 10.2: Class Hierarchy Analysis
- **class_hierarchy** tool (`src/ast_tools/tools/class_hierarchy.py`, 625 lines)
  - AST-based inheritance analysis (no runtime imports)
  - C3 linearization (MRO) computation
  - Method categorization: own, inherited, overrides
  - Interface detection: ABC/Protocol

#### Phase 10.3: Blast Radius v2
- **blast_radius_v2** tool (`src/ast_tools/tools/blast_radius_v2.py`)
  - Unified impact analysis: import graph + class hierarchy + call graph
  - Confidence scoring per analysis axis
  - Combined risk aggregation
  - CLI: `ast blast-radius`

### 🔧 Bug Fixes
- **`file_related_suggest`**: Fixed `UnicodeDecodeError` crash on binary/non-UTF8 files
- **`file_related_suggest`**: Fixed indentation bug causing `NoneType` crash
- **`repo_skeleton`**: Fixed param name mismatch (`root_path` vs `path`)
- **`repo_skeleton`**: Added missing `files` key to output
- **`repo_skeleton`**: Added `.git`, `.venv`, `.eggs`, `node_modules` to exclusion list

### ⚡ Performance
- **AST Pattern Cache**: LRU cache for AST pattern compilation (commits `1b7a4ad`, `143e17e`)
- **Connection Caching**: Per-thread connection pool via `threading.local()` (commit `9c3cd64`)
- **Parallel Tests**: pytest-xdist with `-n auto --dist worksteal` (commit `6187f84`)
- **`file_related_suggest`**: Replaced `rglob()` with `os.walk()` — timeout fixed: ∞ → ~0.2s
- **`repo_skeleton`**: File count cap + expanded skip dirs — timeout fixed: 15s+ → ~2s

### 📚 Documentation
- Added `LICENSE` (MIT)
- Added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- Added `Dockerfile`, `.gitignore`, PR template
- Added CI/CD workflows: release, security-audit, CI, codeql, pylint, pyre, summary
- CHANGELOG updated with all Phase 5-10.3 features

### 📊 Statistics
| Metric | Value |
|--------|-------|
| **MCP Tools** | 55 |
| **Source files** | 82 |
| **Test files** | 51 |
| **OSS docs** | 11 files |
| **CI/CD workflows** | 8 |
| **Schema** | v5 |

---

## [v0.1.0] — 2026-07-26

### 🚀 New Features

#### Hermes Plugin Integration (P0 Complete)
- **ast-tools-context plugin** (`~/.hermes/plugins/ast-tools-context/`)
  - `on_session_start` hook: Injects compact 200-token AST-tools index at session start
  - `pre_llm_call` hook: Injects full reference (~1000-1500 tokens) on AST-related queries
  
- **ast-tools-tokens plugin** (`~/.hermes/plugins/ast-tools-tokens/`)
  - `post_tool_call` hook: Tracks token usage for AST-tools results
  - Context pressure warnings at 80% of compression threshold
  - Error correction database for 4 tools

- **verification-gate plugin** (`~/.hermes/plugins/verification-gate/`)
  - Cross-project quality gate
  - `on_session_start` hook: Injects verification-before-completion ritual

#### Tool Enhancements
- **semantic_search** enriched parameters:
  - `inject_context: bool = True` (default)
  - `token_budget: int = 4096` (default)
  - `diversity_limit: int = 3` (default)

### 📚 Documentation
- **TROUBLESHOOTING.md** (11.7KB) — Comprehensive troubleshooting guide
- **INSTALL.md** (hermes-plugins/) — Plugin installation guide

---

## [v0.0.1] — 2026-06-01

### Initial Release

**Tools:** 11 core tools  
**Schema:** v1 (basic symbols + embeddings)  
**Tests:** 79 passing  
**Server:** Monolithic 1,348-line `ast_tools_server.py`

## Version History Summary

| Version | Date | Tools | Tests | Schema | Key Features |
|---------|------|-------|-------|--------|--------------|
| v0.1.2-dev | 2026-07-03 | 55 | 51 files | v5 | Documentation audit, MCP fix, all Phase 5-10.3 |
| v0.1.1-dev | 2026-07-02 | 55 | 51 files | v5 | Phases 5, 6, 10.1, 10.2, 10.3, perf |
| v0.1.0 | 2026-07-26 | 43 | 461+ | v5 | Hermes plugins, error correction, verification gate |
| v0.0.1 | 2026-06-01 | 11 | 79 | v1 | Initial release: basic AST + FTS5 + vector search |