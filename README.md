# rw-ast-tools

**Structural Code Analysis & Editing MCP Server** — 77 tools for AST-based code intelligence, semantic search, and surgical Python/TypeScript editing.

[![Tests](https://img.shields.io/badge/tests-943%20passing-brightgreen)](https://github.com/rapidwebs/rw-ast-tools/actions)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)

---

## 🎯 What It Does

rw-ast-tools is an MCP (Model Context Protocol) server that gives LLMs **structural code intelligence** — not just text search, but understanding of code as Abstract Syntax Trees:

| Capability | Tools |
|------------|-------|
| **Structural Search** | `ast_grep` — pattern-match on AST nodes across 8 languages |
| **Code Reading** | `ast_read` — extract API surface (classes, functions, imports, line numbers) |
| **Surgical Editing** | `ast_edit` — libcst-powered edits (rename, add params, replace nodes) |
| **Semantic Search** | `semantic_search` — hybrid vector + FTS5, finds code by *meaning* |
| **Impact Analysis** | `impact_analysis`, `blast_radius_v2` — what breaks if you change X? |
| **Code Intelligence** | `find_references`, `module_imports`, `circular_dependencies`, `class_hierarchy` |
| **LSP Integration** | 11 LSP tools: definition, references, hover, completion, rename, diagnostics, code actions |
| **Knowledge Graph** | `kg_query`, `kg_shortest_path`, `kg_neighborhood` — natural language graph traversal |
| **Dead Code** | `dead_code_enhanced` — 6 FP reduction strategies (>40% → <20%) |
| **Syntax Validation** | `code_validate_syntax` — 10 languages via compilers + tree-sitter |
| **Auto-Fix** | `fix_code`, `fix_check` — multi-language convergent fix pipeline |
| **Tool Discovery** | `search_tools`, `call_tool`, `tool_info`, `tool_usage_stats` — dynamic tool lookup |

---

## 🚀 Quick Start

### Install

```bash
git clone https://github.com/rapidwebs/rw-ast-tools
cd rw-ast-tools
uv venv && source .venv/bin/activate
uv pip install -e .
```

### Run MCP Server

```bash
# Daemon mode (persistent, systemd-managed) — RECOMMENDED
ast-tools --mode daemon

# Or timeout mode (default, stdio with idle timeout)
ast-tools
```

### Hermes Integration

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  ast-tools:
    command: socat
    args:
      - "-"
      - "UNIX-CONNECT:/home/user/.cache/rw-ast-tools/server.sock"
    connect_timeout: 10
    timeout: 120
```

Daemon setup:
```bash
# Install systemd user service
cp deploy/rw-ast-tools.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rw-ast-tools
```

The daemon auto-starts via systemd and Hermes connects via socat bridge. No per-session cold start — the daemon is always ready.

---

## 🧰 All 77 Tools

### Core AST (8)
| Tool | Description |
|------|-------------|
| `ast_grep` | Structural search with AST patterns (Python, JS, TS, Rust, Go, Java, C++, C#) |
| `ast_read` | Extract API surface — classes, functions, imports, line numbers |
| `ast_edit` | Surgical edits via libcst — **always `dry_run=true` first!** |
| `ast_generate_stub` | Generate `.pyi` stub files or interface summaries |
| `ast_refactor_extract_interface` | Extract ABC/Protocol from a class |
| `ast_capsule` | Export code as self-contained capsule with dependencies |
| `ast_query` | Smart router — describe intent, auto-selects best tool |
| `ts_edit` | TypeScript/TSX structural editing (tree-sitter) |

### Analysis & Impact (14)
| Tool | Description |
|------|-------------|
| `structural_analysis` | Call graphs, type hierarchies, references, dependencies |
| `impact_analysis` | **Before refactoring** — affected files + risk assessment |
| `blast_radius_v2` | Unified blast radius (imports + hierarchy + call graph) |
| `module_imports` | Fan-in/fan-out import graph, circular dependency detection |
| `find_references` | All usages of a symbol across the codebase |
| `transitive_dependents` | Full transitive dependency chain |
| `class_hierarchy` | MRO, bases, subclasses, method categories |
| `circular_dependencies` | Detect circular imports |
| `dependency_chain` | Trace dependency paths end-to-end |
| `external_dependencies` | Find third-party imports |
| `api_surface_diff` | Compare API surfaces between versions |
| `co_change_predict` | Files that tend to change with a given file |
| `co_change_hotspots` | Top-N riskiest files by churn × coupling |
| `co_change_diff` | Symbols at risk when changing a symbol |

### Knowledge Graph (3)
| Tool | Description |
|------|-------------|
| `kg_query` | Natural language graph traversal |
| `kg_shortest_path` | Shortest path between two symbols |
| `kg_neighborhood` | All symbols within N hops |

### Semantic Search & Index (8)
| Tool | Description |
|------|-------------|
| `semantic_search` | Vector + FTS5 hybrid — search by **meaning** |
| `search_symbols` | FTS5 keyword search |
| `find_symbol_definition` | Lookup by qualified name |
| `list_symbols` | All symbols in a file |
| `refresh_index` | Incremental indexing (SHA256 content hashing) |
| `index_status` | Symbols, files, embeddings count |
| `reindex_path` | Per-file reindex |
| `watch_add` / `watch_status` | Auto-index watcher daemon |

### Dead Code & Quality (4)
| Tool | Description |
|------|-------------|
| `dead_code_detection` | Basic unused code detection |
| `dead_code_enhanced` | **6 FP reductions** — confidence scoring, framework decorators, entry points, SCC, `__all__`, polymorphism |
| `code_validate_syntax` | 10 languages: Python, SQL, Shell, JS, TS, Rust, Go (compilers) + C, C++, C# (tree-sitter) |
| `fix_code` / `fix_check` | Multi-language auto-fix pipeline (SAFE/UNSAFE/DISPLAY) |

### LSP Code Intelligence (11)
| Tool | Description |
|------|-------------|
| `lsp_definition` | Go to definition |
| `lsp_references` | Find all references |
| `lsp_hover` | Type signature + docs |
| `lsp_symbols` | All symbols in file |
| `lsp_diagnostics` | Errors/warnings from LSP |
| `lsp_format` | Format code |
| `lsp_code_actions` | Quick fixes & refactorings |
| `lsp_rename` | Workspace-wide rename |
| `lsp_signature_help` | Function signature at call site |
| `lsp_completion` / `lsp_completion_detail` | Code completion |
| `lsp_available_languages` / `lsp_check_server` | Server management |

### Meta & Discovery (5)
| Tool | Description |
|------|-------------|
| `search_tools` | Semantic search across all 77 tool descriptions |
| `call_tool` | Execute tool by name with validated params |
| `tool_info` | Full schema, category, usage stats for any tool |
| `tool_usage_stats` | Call counts, error rates, latency, ranking boosts |
| `context_inject` / `context_status` / `token_status` / `validate_usage` | Context injection system |

### Embedding Models (4)
| Tool | Description |
|------|-------------|
| `switch_embedding_model` | Hot-swap embedding model |
| `list_embedding_models` | Available models |
| `get_embedding_model_info` | Model details |
| `rerank_results` | Cross-encoder reranking |

### Curator (3)
| Tool | Description |
|------|-------------|
| `curator_audit` | Automated code review |
| `curator_summary` | Review summary |
| `curator_status` | Curator system status |

---

## 🔧 Common Workflows

### Before Making Changes (MANDATORY)
```bash
# 1. Orient to project
ast-tools codebase_summary

# 2. Read target file structure
ast-tools ast_read --file src/auth/middleware.py

# 3. Check what calls it (impact)
ast-tools impact_analysis --target src/auth/middleware.py

# 4. Check imports (if splitting module)
ast-tools module_imports --module src.auth.middleware
```

### Find Code by Meaning
```bash
# "Where is the websocket handler?"
ast-tools semantic_search --query "websocket handler" --k 5

# "How does error retry work?"
ast-tools semantic_search --query "exponential backoff retry" --k 10
```

### Refactor Large Module → Subpackage
```bash
# 1. Map all imports
ast-tools structural_analysis --analysis-type dependencies --file src/large_module.py

# 2. Check circular deps
ast-tools module_imports --module large_module

# 3. Extract to subpackage (create __init__.py with __all__)
# 4. Run tests AFTER EACH extraction
```

### Dead Code Cleanup
```bash
# High-confidence dead code only
ast-tools dead_code_enhanced --format json | jq '.dead_functions[] | select(.confidence=="high")'
```

---

## 📦 Server Modes

| Mode | Transport | Use Case |
|------|-----------|----------|
| `daemon` (default) | **Unix domain socket** (systemd) | **Persistent, production** — recommended for Hermes |
| `timeout` | stdio + idle timeout | Interactive, short sessions |
| `remote` | Streamable HTTP + bearer auth | Remote container access |

**Daemon mode** (used by Hermes):
```bash
# systemd-managed (production)
systemctl --user enable --now rw-ast-tools

# Or manually:
ast-tools --mode daemon

# Via socat from Hermes:
socat - UNIX-CONNECT:/home/user/.cache/rw-ast-tools/server.sock
```

The daemon listens on a Unix domain socket using NDJSON line protocol. Multiple clients (Hermes, subagents, CLI) share the same daemon — no per-session cold start overhead (~10-16s saved per Hermes session).

### Multi-Project Watching in Daemon Mode

Daemon mode can monitor multiple projects simultaneously (saves resources vs running multiple instances). Configure via:

1. **Config file** (`~/.config/rw-ast-tools/config.yaml`):
```yaml
daemon:
  watchdogs: true
  watch_paths:
    - "/home/user/Workspaces/project-a"
    - "/home/user/Workspaces/project-b"
    - "/home/user/Workspaces/project-c"
```

2. **Environment variable** (comma-separated):
```bash
AST_TOOLS_DAEMON_WATCH_PATHS="/home/user/Workspaces/project-a,/home/user/Workspaces/project-b" ast-tools --mode daemon
```

3. **CLI** (coming soon): `ast-tools --mode daemon --watch-paths /path/a,/path/b`

If no paths configured, defaults to CWD.

---
---

## 🔌 Hermes Plugin: `rw-ast-tools`

Unified plugin replacing 3 old plugins. 4 hooks:

| Hook | Purpose |
|------|---------|
| `pre_llm_call` | Injects project-specific context via `semantic_search` + quick reference + typo corrections |
| `on_session_start` | Compact 200-token tool index |
| `post_tool_call` | Token tracking + error correction for common mistakes |
| `on_session_end` | Session intelligence (modified files + codebase summary) |

**Key improvement**: `pre_llm_call` now calls `semantic_search(query, inject_context=True)` — returns **actual project symbols** (signatures, docstrings, file paths) instead of generic tool docs.

---

## 🏗️ Architecture

```
rw-ast-tools/
├── src/ast_tools/
│   ├── _server.py              # MCP server entry (3 modes)
│   ├── server_config.py        # Unified config: CLI > env > file > defaults
│   ├── config/unified.py       # Pydantic config with validation
│   ├── tools/                  # 77 MCP tools (auto-registered)
│   │   ├── semantic_search.py  # Hybrid vector + FTS5 (6-factor RRF)
│   │   ├── ast_edit.py         # libcst surgical editing
│   │   ├── ast_grep.py         # Tree-sitter structural search
│   │   ├── lsp_tools.py        # 11 LSP tools
│   │   ├── dynamic_schemas.py  # generate_quick_reference(), find_similar_tool()
│   │   └── ... (70 more)
│   ├── database/               # SQLite + sqlite-vec (384-dim)
│   │   ├── connection.py       # Persistent pool + thread-pool fallback
│   │   ├── schema.py           # Schema v5, migrations
│   │   └── queries.py          # Symbol CRUD, vector KNN
│   ├── indexer/                # Incremental indexing
│   │   ├── extractor.py        # Tree-sitter + libcst extraction
│   │   ├── diff.py             # Symbol-level diff (added/removed/modified)
│   │   └── daemon.py           # Watchdog watcher (100ms debounce)
│   ├── embeddings/             # SentenceTransformers + provider abstraction
│   ├── reranker/               # Cross-encoder (ms-marco-MiniLM-L-6-v2)
│   ├── lsp_client.py           # Persistent LSP cache, ref counting
│   ├── agent_integration/      # Zero-Hermes-dependency modules
│   │   ├── context_builder.py  # build_ast_tools_context, detect_ast_query
│   │   ├── token_tracker.py    # TokenTracker, ContextPressureMonitor
│   │   ├── error_correction.py # Common tool error detection
│   │   └── session_intel.py    # Mutation tracking, codebase_summary
│   ├── fix/                    # Auto-fix pipeline (C1)
│   │   ├── engine.py           # Convergent fix runner
│   │   └── fixers.py           # Per-language fixers
│   ├── curator/                # Code review automation
│   ├── ts_backend.py           # TypeScript tree-sitter backend
│   └── spectral.py             # Spectral clustering (Nyström, TF-IDF naming)
├── tests/                      # 71 test files, 943 tests
├── docs/
│   ├── portal/                 # Interactive HTML docs (React)
│   ├── AST_TOOLS_QUICKSTART.md
│   ├── CLI_REFERENCE.md
│   └── DOCUMENTATION_INDEX.md
└── plugins/
    └── rw-ast-tools/           # Hermes plugin
```

---

## 📊 Specs

| Metric | Value |
|--------|-------|
| **MCP Tools** | 77 |
| **Source Files** | 134 |
| **Test Files** | 71 |
| **Test Lines** | 8,946 |
| **Tests Passing** | 943 (2 skipped) |
| **Languages (AST)** | Python, JS, TS, TSX, Rust, Go, Java, C++, C, C# |
| **Languages (Syntax Validation)** | 10 (7 compilers + 3 tree-sitter) |
| **Embedding Dim** | 384 (all-MiniLM-L6-v2) |
| **Schema Version** | v5 |
| **License** | MIT |

---

## 🧪 Testing

```bash
# Full suite (2 min)
pytest tests/ -v

# Fast: unit tests only
pytest tests/ -m "not integration" -x

# Specific area
pytest tests/tools/test_semantic_search.py -v
pytest tests/tools/test_lsp_tools.py -v
pytest tests/test_cli.py -v
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `docs/AST_TOOLS_QUICKSTART.md` | 13KB intro + workflows |
| `docs/CLI_REFERENCE.md` | 15KB complete CLI guide (11 commands) |
| `docs/DOCUMENTATION_INDEX.md` | Full index of all docs |
| `docs/portal/` | Interactive HTML docs (React + live search) |

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

**Built by RapidWebs Enterprise** — `ast-tools` is the structural code intelligence layer for the NexusAgent platform.