# ast-tools

Structural code analysis and editing MCP server — 43 tools for Python, TypeScript, JavaScript, Rust, Go, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, and more.

## Overview

**ast-tools** provides 43 production-ready tools across 7 categories:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Core AST** | 8 | Structural search, read, edit, query, capsule, stub gen, interface extraction |
| **Project Intelligence** | 3 | Codebase summary, project info, impact analysis |
| **Symbol Search** | 5 | FTS5 full-text, semantic hybrid, find-by-name, list symbols, index status |
| **Structural Analysis** | 5 | Call graphs, type hierarchies, references, imports, dependency chains |
| **Dependency Analysis** | 5 | Fan-in/out, circular deps, external deps, dead code (basic + enhanced), API surface diff |
| **Index Management** | 4 | Refresh, reindex path, watch add, watch status |
| **LSP Integration** | 8 | Go-to-def, references, hover, symbols, call hierarchy (in/out), server check, langs |
| **Context Injection** | 2 | Inject relevant context, context status |
| **Code Validation** | 1 | Multi-language syntax validation (10+ languages) |
| **TypeScript Editing** | 1 | Structural TS/JS/TSX/JSX editing via tree-sitter |
| **Curator** | 3 | Automated code review, review summary, daemon status |

> **v0.1.0** — 43 MCP tools · 307+ tests · Schema v5 · MIT License

---

## Installation

```bash
# Clone
git clone https://github.com/your-org/ast-tools.git
cd ast-tools

# Production install (uv)
uv pip install -e .

# Development install
uv sync --all-extras
```

### MCP Server Configuration

Add to your Hermes config (`~/.hermes/config.yaml`):

```yaml
mcp_servers:
  ast-tools:
    command: ["python3", "-m", "ast_tools_server"]
    cwd: "/path/to/ast-tools"
```

### CLI

All 43 tools are accessible via the `ast` CLI:

```bash
ast search "authentication handler"        # Semantic search
ast navigate UserController                # Go to definition
ast blast-radius src/auth.py:42            # Impact analysis
ast find-dead --format json                 # Dead code detection
ast summary --format markdown               # Codebase overview
```

---

## Core Tools (Top 10)

### 1. `ast_grep` — Structural Pattern Search

Search code using AST patterns, not regex. Understands syntax tree structure.

```json
{
  "pattern": "def $FUNC($$$ARGS)",
  "lang": "python",
  "path": "src/",
  "limit": 10
}
```

### 2. `ast_read` — Extract File Structure

Get a file's complete API surface before editing.

```json
{
  "file": "src/auth/middleware.py",
  "include_private": true,
  "include_imports": true
}
```

### 3. `ast_edit` — Surgical AST Modifications

Precise edits using libcst (Python-only). Operations: `replace_node`, `insert_after`, `insert_before`, `remove_node`, `rename_function`, `add_parameter`, `change_signature`.

⚠️ **Always use `dry_run: true` first.**

### 4. `semantic_search` — Search by Meaning

Hybrid FTS5 + vector search with 6-factor Reciprocal Rank Fusion:
- Semantic similarity (40%) — Cosine distance
- Recency (15%) — Git timestamp decay
- Usage frequency (15%) — Access patterns
- Kind relevance (10%) — Function/class boosting
- Proximity (10%) — Distance from entry points
- Callgraph centrality (10%) — PageRank score

```json
{
  "query": "websocket session authentication",
  "k": 10,
  "inject_context": true,
  "token_budget": 4096,
  "diversity_limit": 3
}
```

### 5. `structural_analysis` — Code Intelligence

Call graphs, type hierarchies, references, and module dependencies. `analysis_type`: `callers`, `callees`, `type_hierarchy`, `references`, `dependencies`.

### 6. `impact_analysis` — Change Risk Assessment

**Mandatory before public API changes.** Returns direct + transitive dependents, affected test files, risk level.

### 7. `find_references` — Cross-file Symbol Usage

Use before renaming or removing any symbol.

### 8. `module_imports` — Fan-in/Fan-out Analysis

Module-level import analysis with circular dependency detection.

### 9. `code_validate_syntax` — Multi-Language Validation

Supports Python (ast), SQL (sqlparse), Shell (bash -n), JS (node --check), TS (tsc --noEmit), Rust (rustc), Go (go build), plus tree-sitter for C/C++/C#.

### 10. `ts_edit` — TypeScript/JS Structural Editing

Tree-sitter backed editing for `.ts`, `.tsx`, `.js`, `.jsx`. Operations: `rename_identifier`, `add_parameter`, `replace_node`.

---

## Language Support

| Language | Search | Edit | Analyze | Validate |
|----------|--------|------|---------|----------|
| Python | ✅ | ✅ libcst | ✅ | ✅ ast.parse |
| TypeScript | ✅ | ✅ tree-sitter | ✅ | ✅ tsc --noEmit |
| JavaScript | ✅ | ✅ tree-sitter | ✅ | ✅ node --check |
| Rust | ✅ | ❌ | ✅ | ✅ rustc |
| Go | ✅ | ❌ | ✅ | ✅ go build |
| Java | ✅ | ❌ | ✅ | ❌ |
| C/C++ | ✅ | ❌ | ✅ | ✅ tree-sitter |
| C# | ✅ | ❌ | ✅ | ✅ tree-sitter |
| Ruby/PHP/Swift/Kotlin | ✅ | ❌ | ✅ | ❌ |

---

## Project Structure

```
ast-tools/
├── src/
│   └── ast_tools/
│       ├── __init__.py              # Package init
│       ├── cli.py                   # CLI entry point (11 commands)
│       ├── lsp_client.py            # LSP protocol client
│       ├── types.py                 # Shared type definitions
│       ├── tools/                   # 43 tool implementations
│       │   ├── __init__.py          # Tool registry + schemas
│       │   ├── ast_grep.py          # Structural pattern search
│       │   ├── ast_edit.py          # Surgical AST edits (libcst)
│       │   ├── ast_read.py          # API surface extraction
│       │   ├── ast_query.py         # Smart router (recommends tools)
│       │   ├── ast_capsule.py       # One-call symbol dossier
│       │   ├── ast_generate_stub.py # .pyi stub generation
│       │   ├── ast_refactor_extract_interface.py # ABC/Protocol extraction
│       │   ├── structural_analysis.py # Call graphs, hierarchies
│       │   ├── impact_analysis.py   # Change risk assessment
│       │   ├── find_references.py   # Cross-file symbol search
│       │   ├── module_imports.py    # Fan-in/fan-out analysis
│       │   ├── codebase_summary.py  # Architecture overview
│       │   ├── project_info.py      # Project manifest
│       │   ├── semantic_search.py   # Hybrid vector+FTS5 search
│       │   ├── search_symbols.py    # FTS5 symbol search
│       │   ├── find_symbol_definition.py # Qualified name lookup
│       │   ├── list_symbols.py      # Symbol listing
│       │   ├── index_status.py      # Index statistics
│       │   ├── refresh_index.py     # Index/re-index project
│       │   ├── code_validate.py     # Multi-language validation
│       │   ├── ts_edit.py           # TypeScript structural editing
│       │   ├── enhanced_dead_code.py # Dead code with 6 FP reductions
│       │   ├── dependency.py        # Dependency analysis tools
│       │   ├── dependency_tools.py  # Advanced dependency tools
│       │   ├── curator.py           # Curator review tools
│       │   ├── lsp_tools.py         # LSP integration tools
│       │   ├── context_tools.py     # Context injection tools
│       │   ├── watcher.py           # File watcher tools
│       │   └── dynamic_schemas.py   # Dynamic schema generation
│       ├── database/
│       │   ├── __init__.py          # Database package
│       │   ├── connection.py        # Connection management
│       │   ├── schema.py            # Schema v5 (symbols, embeddings, edges, metrics, audit)
│       │   ├── queries.py           # Database queries
│       │   └── migrations/          # Schema migrations
│       ├── embeddings/
│       │   ├── model.py             # Sentence transformers (384-dim)
│       │   └── store.py             # Embedding storage + retrieval
│       ├── indexer/
│       │   ├── parser.py            # Tree-sitter parsing
│       │   ├── extractor.py         # Symbol extraction
│       │   ├── diff.py              # Symbol-level diff engine
│       │   ├── dependency_metrics.py # SPOF, centrality metrics
│       │   ├── knn_builder.py       # K-nearest-neighbor graph
│       │   ├── implements_detector.py # Interface implementation detection
│       │   └── cache.py             # Cache management
│       ├── context/
│       │   ├── injector.py          # Context injection
│       │   ├── formatters.py        # Output formatters
│       │   └── history.py           # Query history
│       ├── curator/
│       │   └── daemon.py            # Curator daemon
│       ├── watcher/
│       │   └── daemon.py            # File watcher daemon (watchdog)
│       └── utils/
│           ├── file_utils.py        # File operations
│           ├── impact.py            # Impact analysis utilities
│           ├── security.py          # Path validation, injection prevention
│           ├── secret_sanitizer.py  # API key/password detection
│           └── annotations.py       # Type annotation utilities
├── tests/
│   ├── conftest.py
│   ├── test_e2e.py
│   ├── test_cli.py
│   ├── test_diff.py
│   ├── test_incremental_index.py
│   ├── test_enhanced_dead_code.py
│   ├── test_security.py
│   ├── test_phase3_polish.py
│   ├── test_project_tools.py
│   ├── database/                    # DB schema, queries, migrations
│   ├── embeddings/                  # Embedding model & store
│   ├── context/                     # Context injection tests
│   ├── curator/                     # Curator tests
│   ├── tools/                       # Tool-specific tests
│   ├── indexer/                     # Parser, extractor tests
│   └── watcher/                     # Daemon tests
├── docs/                            # Full documentation
└── pyproject.toml
```

---

## Semantic Database

**Schema v5** — SQLite + sqlite-vec with 6-factor hybrid search:

- **Symbols table** — All extracted functions, classes, methods, variables
- **Embeddings table** — 384-dim vectors (all-MiniLM-L6-v2)
- **Edges table** — Caller/callee relationships
- **Dependency metrics** — fan_in, fan_out, SPOF score, instability, PageRank
- **Embedding similarity** — Pre-computed cosine similarities
- **KNN graph** — k-nearest-neighbor edges for similarity traversal
- **Audit log** — Provenance tracking

**Performance:**
- FTS5 queries: <10ms
- Vector search: <50ms (CPU)
- Hybrid fusion: <100ms total
- Indexing: ~10K symbols/min

---

## Hermes Plugins

3 Hermes plugins for seamless integration:

| Plugin | Hooks | Behavior |
|--------|-------|----------|
| `ast-tools-context` | `pre_llm_call`, `on_session_start` | Injects tool docs on code queries, "did you mean?" corrections |
| `ast-tools-tokens` | `pre_llm_call`, `post_tool_call` | Token budget tracking, 50%/80% pressure alerts |
| `ast-tools-project-context` | `pre_llm_call` | Injects actual project code context via semantic_search |

---

## Development

```bash
# Run tests (307+ passing)
pytest tests/ -v

# Lint
ruff check src/ tests/

# Build package
uv build
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/AST_TOOLS_QUICKSTART.md` | User guide & workflows |
| `docs/CLI_REFERENCE.md` | Complete CLI reference |
| `docs/ENHANCED_DEAD_CODE.md` | Dead code detection guide |
| `docs/TROUBLESHOOTING.md` | Common issues & fixes |
| `docs/USAGE_RULES.md` | Usage rules & boundaries |
| `docs/SCOPE.md` | Project scope & guidelines |
| `docs/MARKET_ANALYSIS_2026.md` | Competitive landscape |
| `docs/DOCUMENTATION_INDEX.md` | Full doc navigation |
| `docs/roadmap/ROADMAP.md` | Ecosystem roadmap |
| `CHANGELOG.md` | Version history |

---

## License

MIT — RapidWebs Enterprise, LLC

## Contact

Steven Albert Page <steven@rapidwebs.io>