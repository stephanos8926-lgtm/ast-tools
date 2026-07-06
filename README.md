# rw-ast-tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-770%20passing-brightgreen.svg)](https://github.com/stephanos8926-lgtm/ast-tools)
[![MCP](https://img.shields.io/badge/MCP-server-7C3AED.svg)](https://modelcontextprotocol.io)

Structural code analysis and editing MCP server — **57 tools** for Python, TypeScript, JavaScript, Rust, Go, Java, C, C++, and more.

**rw-ast-tools** gives LLMs the ability to search, read, edit, and analyze code structurally, not as text. Built on tree-sitter parsing for accuracy across 20+ languages, with a hybrid semantic + keyword search engine powered by sqlite-vec.

## Features

- **57 MCP tools** across 13 categories — structural search, semantic analysis, code editing, dependency analysis, class hierarchy, blast radius, knowledge graphs, co-change analysis, and more
- **Three server modes** — `timeout` (stdio + idle TTL, default), `daemon` (systemd + file watcher), `remote` (Streamable HTTP + auth)
- **Agent-agnostic integration** — `ast_tools.agent_integration` package has zero Hermes dependency. Use with FORGE, Claude Code, Cursor, or any MCP client
- **Hybrid search**: True 6-factor RRF fusion — FTS5 keyword + vector semantic + recency + usage frequency + symbol kind + callgraph centrality
- **Multi-language**: 20+ languages via tree-sitter with full structural awareness
- **Incremental indexing**: SHA256 content-hash based, symbol-level diff — reindex in milliseconds
- **Watchdog auto-indexer**: Inotify-based file watcher for live codebase updates
- **Metrics store**: Time-series SQLite for codebase growth tracking
- **CLI**: 11 commands for terminal-first workflows
- **Schema v5**: symbols, embeddings, edges, dependency metrics, KNN graph, audit log

## Quick Start

```bash
git clone https://github.com/stephanos8926-lgtm/ast-tools.git
cd ast-tools
uv sync --all-extras
```

### MCP Server Configuration

**Any MCP client** (Hermes, FORGE, Claude Code):

```json
{
  "mcpServers": {
    "rw-ast-tools": {
      "command": "ast-tools-server",
      "args": ["--mode", "timeout"]
    }
  }
}
```

### Server Modes

| Mode | Flag | Transport | Lifecycle | Use Case |
|------|------|-----------|-----------|----------|
| `timeout` (default) | `--mode timeout` | stdio | Per-connection, idle TTL | Desktop CLI agents |
| `daemon` | `--mode daemon` | stdio + systemd | Persistent, auto-restart | Multi-agent workstations |
| `remote` | `--mode remote` | HTTP | Persistent, auth | Server deployment |

Override via env var: `AST_TOOLS_MODE=daemon ast-tools-server`

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
| **Agent Integration** | 4 | Context inject, context status, token status, validate usage |
| **Code Validation** | 1 | Multi-language syntax validation |
| **Knowledge Graph** | 3 | KG query, shortest path, neighborhood |
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
rw-ast-tools/
├── src/
│   └── ast_tools/
│       ├── agent_integration/   # Standalone modules (zero Hermes dep)
│       ├── tools/               # All 57 tool implementations
│       ├── watchdog/            # File watcher + metrics store
│       ├── kg/                  # Knowledge graph engine
│       ├── cochange/            # Co-change analysis
│       ├── database/            # Schema v5
│       ├── embeddings/          # 384-dim vector embeddings
│       ├── indexer/             # Symbol extraction, diff engine
│       ├── context/             # Context injection (6-factor RRF)
│       ├── watcher/             # File watcher daemon
│       ├── curator/             # Automated index curation
│       ├── utils/               # Security, file ops
│       ├── _server.py           # 3-mode MCP server
│       ├── server_config.py     # Config (CLI/env/file)
│       └── cli.py               # CLI commands
├── tests/                       # 770 tests passing
├── docs/                        # Full documentation
├── hermes-plugins/rw-ast-tools/ # Unified Hermes plugin
├── deploy/                      # systemd service files
└── CHANGELOG.md                 # Release changelog
```

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/AST_TOOLS_QUICKSTART.md` | User guide & workflows |
| `docs/CLI_REFERENCE.md` | Complete CLI reference |
| `docs/TROUBLESHOOTING.md` | Common issues & fixes |
| `docs/DOCUMENTATION_INDEX.md` | Full documentation index |
| `docs/reports/server-architecture-completion.md` | 3-mode server architecture report |
| `docs/specs/server-architecture-redesign-v1.md` | Architecture specification |
| `docs/adrs/0012-server-architecture-multi-mode.md` | Architecture decision record |
| `SETUP_INSTRUCTIONS.md` | Installation guide |

## License

MIT — RapidWebs Enterprise, LLC

## Contact

Steven Page — <steven@rapidwebs.io>

---

<sup>Part of the [RapidWebs Enterprise](https://rapidwebs.io) ecosystem.</sup>