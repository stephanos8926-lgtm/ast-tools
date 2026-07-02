# AST-Tools Changelog

All notable changes to the AST-Tools MCP server.

## [v0.1.1-dev] — 2026-08 (In Development)

### 🚀 New Features

#### Phase 8.1-8.3: Incremental Indexing (Symbol-Level Diff)
- **Symbol-level diff engine** (`src/ast_tools/indexer/diff.py`, 183 lines)
  - `(file_path, qualified_name)` match key for accurate symbol tracking
  - Classifies symbols as: added, removed, modified, or unchanged
  - Preserves IDs, edges, and embeddings for unchanged symbols during reindex
- **Incremental `refresh_index`** — default mode now only reindexes changed files
  - SHA256 content hashing detects actual file changes
  - Immutable symbols skipped entirely (zero-copy)
- **Database helpers**: `get_symbols_by_file`, `delete_symbol_cascade`, `update_symbol_fields`
- **30 new tests** (20 diff + 10 incremental)
- **Pitfall captured**: `database_context()` does NOT auto-commit — must call `conn.commit()` explicitly

#### Documentation Cleanup Phase
- Consolidated 61 markdown files → 37 active + 21 archived
- All audit reports consolidated into `docs/AUDITS_HISTORY.md`
- All specifications consolidated into `docs/SPECS_HISTORY.md`
- All implementation plans consolidated into `docs/PLANS_HISTORY.md`
- All reports consolidated into `docs/REPORTS_HISTORY.md`
- Moved session-specific files to `docs/archive/`

### 🔧 Fixes
- `ast_capsule` parameter mismatches for tool integrations
- External review: caller/callee contract drift (Fixes A-E)
- E2E tests: add `project_path` to all tool calls
- FK cascade for edge table deletions

### 📊 Statistics
| Metric | Value |
|--------|-------|
| **Tools** | 43 registered |
| **Source files** | 69 |
| **Tests** | 461+ (varies by environment) |
| **Test files** | 33 |
| **CLI commands** | 11 |
| **Schema** | v5 |

---

## [v0.1.0] — 2026-07-26

### 🚀 New Features

#### Hermes Plugin Integration (P0 Complete)
- **ast-tools-context plugin** (`~/.hermes/plugins/ast-tools-context/`)
  - `on_session_start` hook: Injects compact 200-token AST-tools index at session start
  - `pre_llm_call` hook: Injects full reference (~1000-1500 tokens) on AST-related queries
  - Keyword-triggered context injection for "ast_grep", "structural", "refactor", etc.
  
- **ast-tools-tokens plugin** (`~/.hermes/plugins/ast-tools-tokens/`)
  - `post_tool_call` hook: Tracks token usage for AST-tools results
  - Context pressure warnings at 80% of compression threshold
  - Error correction database with behavioral training for 4 tools:
    - `ast_edit`: Operation syntax guidance, dry_run reminders
    - `semantic_search`: Query tuning, filter optimization
    - `ast_grep`: Metavariable syntax ($VAR vs $$$VAR)
    - `impact_analysis`: Symbol lookup workflow
  
- **verification-gate plugin** (`~/.hermes/plugins/verification-gate/`)
  - Cross-project quality gate (not AST-tools-specific)
  - `on_session_start` hook: Injects verification-before-completion ritual
  - Enforces: "Never trust docs over source code" principle

#### Tool Enhancements
- **semantic_search** enriched parameters:
  - `inject_context: bool = True` (default) — Auto-inject formatted markdown context
  - `token_budget: int = 4096` (default) — Respect model context window
  - `diversity_limit: int = 3` (default) — Max symbols per file
  - Returns `context_injection` metadata: tokens_used, budget_remaining, diversity_applied

### 📚 Documentation
- **TROUBLESHOOTING.md** (11.7KB) — Comprehensive troubleshooting guide:
  - Common issues table with quick fixes
  - Fake-done pattern detection (stubs, TODOs, hardcoded returns, unwired features)
  - Verification ritual (4-step: identify → run → check → confirm)
  - Plugin debugging procedures
  - Performance tuning (indexing speed, query optimization)
  - Rollback procedures

- **INSTALL.md** (hermes-plugins/) — Plugin installation guide:
  - Installation steps for AST-tools plugins
  - Plugin loading verification
  - Hook registration reference
  - Security notes and rollback procedures

- **PHASE10A_SYNTHESIS.md** — Correction note added:
  - `code_validate_syntax` ✅ DONE (704 lines, 62 tests, registered line 91)
  - `repo_skeleton` ❌ NOT STARTED (Phase 10A remaining)
  - `file_related_suggest` ❌ NOT STARTED (Phase 10A remaining)
  - Lesson: "Never trust docs over source code — verify with git log + ls + pytest"

### 🔧 Technical Details
- Plugin architecture: Hooks loaded dynamically on Hermes session start (no gateway restart required)
- Error correction: Scoped to AST-tools failures only (zero perf penalty for other tools)
- Token budgets by model:
  - Default (4K context): 1K AST-tools budget (25%)
  - GPT-4o/Claude-3.5 (8K context): 2K budget
  - Gemini-1.5-Pro (32K context): 8K budget

---

## [v0.1.0] — 2026-07-24

### 🎉 Launch Release — 29 MCP Tools

**Schema Version:** v5 (enriched with callgraph + dependency metrics)

#### Core Tools (11)

1. **ast_grep** — Structural code search using AST patterns
   - Supports: Python, JS/TS, Rust, Go, Java, C/C++, +20 languages
   - Metavariables: `$VAR` (single node), `$$$VAR` (multiple nodes)
   
2. **ast_read** — API surface extraction
   - Returns: Imports, classes, functions, variables with line numbers
   - Optional: `include_private=True`, `include_imports=True`
   
3. **ast_edit** — Surgical AST-based modifications (libcst)
   - Operations: `replace_node`, `insert_after`, `insert_before`, `remove_node`,
                `rename_function`, `add_parameter`, `change_signature`
   - Always use `dry_run=true` for preview!
   
4. **structural_analysis** — Comprehensive code analysis
   - Types: `callers`, `callees`, `type_hierarchy`, `references`, `dependencies`
   
5. **impact_analysis** — Change impact assessment
   - Returns: Direct + transitive dependents, test files, risk assessment
   - **Mandatory before public API changes**
   
6. **module_imports** — Import dependency analysis
   - Fan-in: What imports FROM target module
   - Fan-out: What target module imports
   - Circular dependency detection
   - Import lines with file/line context
   
7. **find_references** — Cross-file symbol usage search
   - Use before renaming/removing any symbol
   
8. **codebase_summary** — High-level architecture overview (<500 tokens)
   
9. **project_info** — Project intelligence manifest
   - Languages, frameworks, structure, dependencies
   
10. **ast_generate_stub** — Generate .pyi stub files from Python source
   
11. **ast_refactor_extract_interface** — Extract ABC/Protocol from class

#### Phase 9 Additions (5 New Tools)

12. **callgraph_edges** — Materialized view for fast caller/callee lookups
    - `view="materialized"` for performance
    
13. **dependency_metrics** — SPOF detection + centrality scoring
    - Metrics: fan_in, fan_out, spof_score, instability, PageRank centrality
    
14. **embedding_similarity** — Semantic code clone detection
    - Pre-computed cosine similarities
    - `top_k=10`, `min_score=0.7`
    
15. **knn_graph** — Similarity-based code navigation
    - k-nearest-neighbor edges
    - "Find code like this" queries
    
16. **code_validate_syntax** — Multi-language syntax validation ✅ DONE
    - Languages: Python (ast.parse), SQL (sqlparse), Shell (bash -n),
                JS (node --check), TS (tsc --noEmit), Rust (rustc --emit=metadata),
                Go (go build -o /dev/null)
    - 704 lines, 62 tests passing
    - Optional `sqlparse` dependency

#### Curator Tools (5)

17-21. **Curator daemon** tools for index management:
- `curator_status` — Daemon health + last consolidation
- `curator_consolidate` — Manual consolidation trigger
- `curator_orient` — High-level topic extraction
- `curator_gather` — Evidence collection for topics
- `curator_prune` — Stale memory removal

#### Dependency Analysis Tools (5)

22-26. **Advanced dependency tools**:
- `dependency_fan_in` — What depends on this symbol
- `dependency_fan_out` — What this symbol depends on
- `dependency_sPOF` — Single point of failure detection
- `dependency_instability` — Martin's instability metric
- `dependency_centralty` — PageRank-based centrality

#### Search & Discovery (3)

27. **semantic_search** — 6-factor RRF fusion (Phase 8)
    - Semantic similarity (40%)
    - Recency (15%)
    - Usage frequency (15%)
    - Kind relevance (10%)
    - Proximity (10%)
    - Callgraph centrality (10%)
    - Hermes plugins: `inject_context=True`, `token_budget=4096`, `diversity_limit=3`

28. **search_symbols** — FTS5 full-text symbol search

29. **find_symbol_definition** — Find symbol by qualified name ("module.func")

### 🏗️ Architecture (Phase 9)

**Schema v5 Enrichments:**
- `dependency_metrics` table — fan_in, fan_out, spof_score, instability, PageRank
- `embedding_similarity` table — Pre-computed cosine similarities
- `knn_graph` table — k-nearest-neighbor edges
- `audit_log` table — Provenance tracking for compliance
- `callgraph_edges` materialized view — Fast traversal

**Triggers:**
- `embedding_similarity_auto_update` — Maintains similarities on symbol changes
- `knn_graph_auto_update` — Maintains KNN edges on symbol changes

**Indexes (8 new):**
- Composite indexes for hybrid search, callgraph traversal, similarity joins

### 📊 Statistics

**Lines Added:** 18,273 across 98 files  
**Schema Version:** v4 → v5  
**Tests:** 304 passing (114 core + 18 database + 42 context + 130 other)  
**Server Size:** 445 lines (reduced from 1,348 via Phase 0-5 refactoring, -67%)

### 🔧 Technical Improvements

- **Hatchling build system** (migrated from setuptools)
- **pyproject.toml** with dev deps, ruff config, coverage config
- **.pre-commit-config.yaml** with ruff, trailing-whitespace, end-of-file-fixer
- **uv package manager** support
- **GitHub Actions CI/CD** workflow (build, test, lint)
- **ruff linting** configured (I001, SIM105, ARG*, B023, RUF*)

### 📖 Documentation

- **README.md** — Updated with Phase 8-9 features, semantic_search usage
- **AST_EDIT_OPERATIONS.md** — Full reference for ast_edit operations
- **MARKET_ANALYSIS_2026.md** — $50-100M market (2026) → $500M-1.5B (2031)
- **PHASE9_COMPLETE.md** — 6-wave completion report
- **PHASE_SUMMARIES.md** — Phases 0-5 refactoring summaries
- **PLUGIN_ENHANCEMENTS_SPEC.md** — Hermes plugin technical spec
- **PLUGIN_IMPLEMENTATION_PLAN.md** — Step-by-step implementation guide

### 🚀 Launch Readiness

**Target Date:** 2026-08-01  
**Status:** ✅ READY (43 tools, 461+ tests, plugins complete, docs updated)

**Tool count:** 29→43 tools (core 11 + Phase 9 additions + curator + dependency + search + LSP + context + code validation + TS editing)
**Pending (v0.1.1):**
- `repo_skeleton` — Project type detection + dependency inference + ASCII tree
- `file_related_suggest` — Test file suggestion + sibling detection + call graph integration

---

## [v0.0.1] — 2026-06-01

### Initial Release

**Tools:** 11 core tools  
**Schema:** v1 (basic symbols + embeddings)  
**Tests:** 79 passing  
**Server:** Monolithic 1,348-line `ast_tools_server.py`

**Features:**
- Basic AST parsing with tree-sitter
- FTS5 full-text search
- sqlite-vec vector search
- Simple symbol extraction (functions, classes, methods)
- No callgraph, no dependency metrics, no Hermes plugins

---

## Upcoming (v0.2.1 — Planned)

### Tools
- **repo_skeleton** — Project scaffolding analysis
  - Project type detection (Python, Node, Rust, Go, etc.)
  - Dependency inference from pyproject.toml, package.json, Cargo.toml, go.mod
  - ASCII directory tree generation
  
- **file_related_suggest** — "Files related to X" suggestions
  - Test file pattern matching (test_*.py, *_test.py)
  - Import relationship detection (reuse module_imports)
  - Sibling detection (same directory, similar name)
  - Call graph integration (callers/callees)
  - Confidence scoring + ranking

### Timeline
- **Estimate:** 4-6 days development
- **Decision:** Launch v0.2.0 with 29 tools on 2026-08-01, add these in v0.2.1

---

## Version History Summary

| Version | Date | Tools | Tests | Schema | Key Features |
|---------|------|-------|-------|--------|--------------|
| v0.1.1-dev | 2026-08 | 43 | 461+ | v5 | Incremental indexing, doc cleanup, audit fixes |
| v0.1.0 | 2026-07-26 | 43 | 461+ | v5 | Hermes plugins, error correction, verification gate |
| v0.0.1 | 2026-06-01 | 11 | 79 | v1 | Initial release: basic AST + FTS5 + vector search |

---

*Generated from PHASE9_COMPLETE.md, PHASE_SUMMARIES.md, PLUGIN_IMPLEMENTATION_PLAN.md, and session state on 2026-07-26.*