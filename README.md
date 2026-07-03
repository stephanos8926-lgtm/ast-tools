# ast-tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-686%20passing-brightgreen.svg)](https://github.com/stephanos8926-lgtm/ast-tools)
[![MCP](https://img.shields.io/badge/MCP-server-7C3AED.svg)](https://modelcontextprotocol.io)

Structural code analysis and editing MCP server — **55 tools** for Python, TypeScript, JavaScript, Rust, Go, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, and more.

**ast-tools** gives LLMs the ability to search, read, edit, and analyze code structurally, not as text. Built on tree-sitter parsing for accuracy across 20+ languages, with a hybrid semantic + keyword search engine powered by sqlite-vec.

## Features

- **55 MCP tools** across 12 categories — structural search, semantic analysis, code editing, dependency analysis, class hierarchy, blast radius, knowledge graphs, co-change analysis, and more
- **Hybrid search**: True 6-factor RRF fusion — FTS5 keyword + vector semantic + recency + usage frequency + symbol kind + callgraph centrality. Fused via Reciprocal Rank Fusion (k=60) for robust multi-dimension ranking. — finds code by meaning, not just name
- **Multi-language**: 20+ languages via tree-sitter with full structural awareness
- **Incremental indexing**: SHA256 content-hash based, symbol-level diff — reindex in milliseconds
- **Hermes plugins**: 3 auto-injecting plugins for context, tokens, and codebase indexing
- **CLI**: 11 commands for terminal-first workflows
- **Schema v5**: symbols, embeddings, edges, dependency metrics, KNN graph, audit log

## Quick Start

```bash
git clone https://github.com/stephanos8926-lgtm/ast-tools.git
cd ast-tools
uv sync --all-extras
```

### MCP Server Configuration

Add to your Hermes config (`~/.hermes/config.yaml`):

```yaml
mcp_servers:
  ast-tools:
    command: /path/to/ast-tools/.venv/bin/python3
    args: [/path/to/ast-tools/src/ast_tools_server.py]
    connect_timeout: 60
```

### Hermes Plugin Installation

```bash
# Install 3 auto-injecting plugins
cp -r hermes-plugins/ast-tools-context ~/.hermes/plugins/
cp -r hermes-plugins/ast-tools-tokens ~/.hermes/plugins/
cp -r hermes-plugins/ast-tools-project-context ~/.hermes/plugins/

# Add to hermes config under plugins.enabled:
  #   - ast-tools-context
  #   - ast-tools-tokens
  #   - ast-tools-project-context
```

See [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) for full setup details.

## Tool Categories

| Category | Count | Tools |
|----------|-------|-------|
| **Core AST** | 8 | Structural search (`ast_grep`), read (`ast_read`), edit (`ast_edit`), query (`ast_query`), capsule (`ast_capsule`), stub gen (`ast_generate_stub`), interface extraction (`ast_refactor_extract_interface`), TS editing (`ts_edit`) |
| **Project Intelligence** | 3 | Codebase summary, project info, impact analysis |
| **Symbol Search** | 5 | FTS5, semantic hybrid (6-factor RRF), find-by-name, list symbols, index status |
| **Structural Analysis** | 5 | Call graphs, type hierarchies, references, module imports, dependency chains |
| **Dependency Analysis** | 6 | Fan-in/out (`module_imports`), circular deps, external deps, dead code (basic + enhanced), API surface diff |
| **Index Management** | 4 | Refresh, reindex path, watch add, watch status |
| **LSP Integration** | 8 | Go-to-def, references, hover, symbols, call hierarchy (in/out), available languages, server check |
| **Context Injection** | 2 | Inject context, context status |
| **Code Validation** | 1 | Multi-language syntax validation (10+ languages) |
| **Knowledge Graph** | 3 | KG query (`kg_query`), shortest path (`kg_shortest_path`), neighborhood (`kg_neighborhood`) |
| **Co-Change Analysis** | 4 | Predict, hotspots, history, diff |
| **Phase 10** | 7 | Transitive deps, class hierarchy (MRO), blast radius v2, repo skeleton, file related, code validate |
| **CLI** | 11 | Commands (`ast search`, `ast blast-radius`, `ast find-dead`, `ast callers`, `ast deps`, etc.) |

## CLI

```bash
ast search "authentication handler"     # Semantic search
ast blast-radius src/auth.py:42         # Impact analysis
ast find-dead --format json              # Dead code detection
ast callers process_payment              # Call graph
ast deps src/api/handlers.py            # Import analysis
```

See [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md) for the complete CLI reference.

## Architecture

```
ast-tools/
├── src/
│   └── ast_tools/
│       ├── tools/              # All 55 tool implementations
│       ├── kg/                 # Knowledge graph engine (Phase 5)
│       ├── cochange/           # Co-change analysis (Phase 6)
│       ├── database/           # Schema v5 (symbols, embeddings, edges, metrics, KNN, audit)
│       ├── embeddings/         # 384-dim vector embeddings via sentence-transformers
│       ├── indexer/            # Symbol extraction, diff engine, KNN builder
│       ├── context/            # Context injection (6-factor RRF)
│       ├── curator/            # Automated index curation
│       ├── watcher/            # File watcher daemon
│       └── utils/              # Security, file ops, annotations
├── tests/                      # 42 test files — 686 tests passing
├── docs/                       # Full documentation (19 active + 21 archived)
├── hermes-plugins/             # 3 Hermes integration plugins
├── .github/                    # Issue/PR templates, 5 CI/CD workflows
├── SUPPORT.md                  # Support channels
├── CONTRIBUTING.md             # Contribution guide
├── CODE_OF_CONDUCT.md          # Community standards
├── SECURITY.md                 # Security policy
└── CHANGELOG.md                # Release changelog
```

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/AST_TOOLS_QUICKSTART.md` | User guide & workflows |
| `docs/CLI_REFERENCE.md` | Complete CLI reference |
| `docs/ENHANCED_DEAD_CODE.md` | Dead code detection guide |
| `docs/TROUBLESHOOTING.md` | Common issues & fixes |
| `docs/SESSION_STATE.md` | Project state & phase tracking |
| `docs/DOCUMENTATION_INDEX.md` | Full documentation index |
| `SUPPORT.md` | Support channels |

## License

MIT — RapidWebs Enterprise, LLC

## Contact

Steven Page — <steven@rapidwebs.io>

---

<sup>Part of the [RapidWebs Enterprise](https://rapidwebs.io) ecosystem.</sup>
