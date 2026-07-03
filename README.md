# ast-tools

Structural code analysis and editing MCP server — 55 tools for Python, TypeScript, JavaScript, Rust, Go, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, and more.

## Features

- **55 MCP tools** across 12 categories — structural search, semantic analysis, code editing, dependency analysis, class hierarchy, blast radius, knowledge graphs, co-change analysis, and more
- **Hybrid search**: 6-factor semantic + keyword fusion (RRF) via sqlite-vec
- **Multi-language**: 20+ languages via tree-sitter
- **Incremental indexing**: SHA256 content-hash based, symbol-level diff
- **Hermes plugins**: 3 auto-injecting plugins for context, tokens, and codebase indexing
- **CLI**: 11 commands for terminal-first workflows

## Quick Start

```bash
git clone https://github.com/stephanos8926-lgtm/ast-tools.git
cd ast-tools
uv pip install -e .
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

## Tool Categories

| Category | Count | Tools |
|----------|-------|-------|
| **Core AST** | 8 | Structural search, read, edit, query, capsule, stub gen, interface extraction, TS editing |
| **Project Intelligence** | 3 | Codebase summary, project info, impact analysis |
| **Symbol Search** | 5 | FTS5, semantic hybrid, find-by-name, list symbols, index status |
| **Structural Analysis** | 5 | Call graphs, type hierarchies, references, imports, dependency chains |
| **Dependency Analysis** | 5 | Fan-in/out, circular deps, external deps, dead code, API diff |
| **Index Management** | 4 | Refresh, reindex path, watch add, watch status |
| **LSP Integration** | 8 | Go-to-def, references, hover, symbols, call hierarchy, server check |
| **Context Injection** | 2 | Inject context, context status |
| **Code Validation** | 1 | Multi-language syntax (10+ languages) |
| **Knowledge Graph** | 3 | KG query, shortest path, neighborhood |
| **Co-Change Analysis** | 4 | Predict, hotspots, history, diff |
| **Phase 10** | 7 | Transitive deps, class hierarchy, blast radius v2, repo skeleton, file related |

## CLI

```bash
ast search "authentication handler"     # Semantic search
ast blast-radius src/auth.py:42         # Impact analysis
ast find-dead --format json              # Dead code detection
ast callers process_payment              # Call graph
ast deps src/api/handlers.py            # Import analysis
```

## Architecture

```
ast-tools/
├── src/
│   └── ast_tools/
│       ├── tools/              # All 55 tool implementations
│       ├── kg/                 # Knowledge graph engine
│       ├── cochange/           # Co-change analysis (GitMiner)
│       ├── database/           # Schema v5 (symbols, embeddings, edges, metrics, KNN, audit)
│       ├── embeddings/         # 384-dim vector embeddings
│       ├── indexer/            # Symbol extraction, diff engine, KNN builder
│       ├── context/            # Context injection (6-factor RRF)
│       ├── curator/            # Automated index curation
│       ├── watcher/            # File watcher daemon
│       └── utils/              # Security, file ops, annotations
├── tests/                      # 51 test files
├── docs/                       # Full documentation
└── hermes-plugins/             # 3 Hermes integration plugins
```

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/AST_TOOLS_QUICKSTART.md` | User guide & workflows |
| `docs/CLI_REFERENCE.md` | Complete CLI reference |
| `docs/ENHANCED_DEAD_CODE.md` | Dead code detection guide |
| `docs/TROUBLESHOOTING.md` | Common issues & fixes |
| `docs/SESSION_STATE.md` | Project state & phase tracking |

## License

MIT — RapidWebs Enterprise, LLC

## Contact

Steven Albert Page <steven@rapidwebs.io>