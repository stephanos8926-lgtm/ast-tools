# Changelog

All notable changes to rw-ast-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---
## [v0.2.2] — 2026-07-19

### ✨ New Features
- **Unix Domain Socket transport** — daemon mode now listens on a Unix domain socket instead of stdio. Uses NDJSON line protocol over UDS. Enables persistent multi-client daemon (shared by Hermes + subagents + CLI).
- **systemd user service** on BOTH machines — `rw-ast-tools.service` manages daemon lifecycle (auto-restart, 1G limit, watchdog). Same service file on workstation and dev VM.
- **Symmetric multi-machine deployment** — both machines use identical config layout:
  - `~/.config/rw-ast-tools/config.yaml` — daemon config
  - `~/.cache/rw-ast-tools/server.sock` — UDS socket
  - `socat - UNIX-CONNECT:server.sock` — Hermes MCP bridge
- **RW_InferenceEngine integration** — both machines share embedding provider at `100.109.15.31:8300` (dev VM). Workstation uses remote mode.
- **Worker Hermes on dev VM configured** — dev VM's Hermes agent now uses ast-tools via socat bridge, same as workstation.

### 🐛 Bug Fixes
- **Socket-first startup** — UDS socket created BEFORE watchdog init (watchdog scan can block 30+ seconds). Daemon immediately reachable after systemd start.
- **Graceful client disconnect** — `ConnectionResetError`/`BrokenPipeError` caught silently instead of spamming error log.
- **tools/list timeouts** — response closes cleanly after one NDJSON line (was hanging waiting for implicit EOF).

### 🔧 Improvements
- Socket permissions: `chmod 0o600` (owner-only)
- Stale socket cleanup on startup
- `os.path.expanduser()` on configured socket_path
- Watchdog monitors `~/Workspaces/ast-tools` and `~/Workspaces/NexusAgent` on workstation

### 📚 Documentation
- Updated: 77 tools, schema v5, 943 tests
- New daemon mode docs with systemd + socat bridge
- Multi-machine symmetric deployment documentation
- Removed stale `ast.rapidwebs.org` Caddy proxy references

### 💥 Breaking Changes
- **Hermes MCP config updated** — old: `python3 _server.py --mode daemon` stdio subprocess. New: `socat - UNIX-CONNECT:/path/to/server.sock`
- **No more `ast.rapidwebs.org`** — port 8400 remote mode proxy removed. Use local UDS daemon or direct dev VM socket.

---

## [v0.2.1] — 2026-07-18

### 🐛 Bug Fixes & Code Quality
- **Fixed 307 lint issues** across codebase (ruff --fix): removed unused variables, simplified nested conditionals, removed whitespace issues, fixed docstring character ambiguities (× → x, – → -)
- **Eliminated duplicate set items** in `spectral.py` (static, void, default, None duplicates)
- **Fixed missing newline at EOF** in `switch_model.py`
- **All 943 tests passing** (2 skipped, 398 warnings — mostly pytest deprecation warnings)

### 🔧 Plugin Improvements
- **rw-ast-tools Hermes plugin** updated:
  - `pre_llm_call` hook now calls `semantic_search` via MCP stdio for **project-specific context** (actual code symbols, not generic docs)
  - Added **typo correction** ("Did you mean?") using `find_similar_tool()` from `dynamic_schemas.py`
  - Replaced static ~1000-token docs with compact **300-token quick reference** from `generate_quick_reference()`
  - Fixed `on_session_end` to pass `conversation_history` to `extract_modified_files()`

### 📦 Configuration
- **Hermes config**: `ast-tools` MCP server now runs in `--mode daemon` (persistent, systemd-managed) instead of `--mode timeout`
- Requires gateway restart: `systemctl --user restart hermes-gateway` (from outside gateway process)

### 📚 Documentation
- Updated tool count references: **77 tools** (was 55/57 in various docs)
- README.md refreshed with current feature list, architecture, and tool categories
- All doc files now reflect actual schema v5, 943 tests, 77 tools

---

## [v0.2.0] — 2026-07-13

### ✨ New Features
- **Interactive HTML Documentation Portal** (`docs/portal/`): React-based interactive docs with live search, tool filtering, and mermaid diagram rendering
- **Tool Discovery System (Phase A-D)**: 4 new meta-tools — `search_tools`, `call_tool`, `tool_info`, `tool_usage_stats` — for dynamic tool discovery and usage analytics
- **Spectral Clustering (P3)**: TF-IDF cluster naming, multi-resolution clustering, parallel graph construction, incremental Laplacian, Nyström approximation
- **LSP Phase 2**: Persistent LSP client cache, true diagnostics tracking, code actions, rename symbol, signature help, code completion, apply format

### 🔧 Improvements
- Added missing tool categories: `context_tools` + `tool_usage_stats` to tool registry
- Dynamic tool schemas: `generate_quick_reference()` builds markdown from registered schemas
- "Did you mean?" typo correction: `find_similar_tool()` uses difflib for tool name suggestions
- LSP client improvements: reference counting, window/logMessage handling, full capability registration

### 🐛 Fixes
- Fixed LSP command name in config (`vscode` extension)
- Relocated `ts_backend` into package, renamed `types` → `symbols` to avoid Python 3.14 stdlib conflict
- Pointed remote inference defaults to `rw-server:8300`

### 📚 Documentation
- `docs/portal/`: Interactive HTML documentation portal
- `docs/AST_TOOLS_QUICKSTART.md`: User guide & workflows
- `docs/CLI_REFERENCE.md`: Complete 11-command CLI reference
- `docs/DOCUMENTATION_INDEX.md`: Full documentation index

---

## [v0.1.1] — 2026-07-02

### ✨ New Features
- **Wave 2 Core Infrastructure**: Persistent aiosqlite connection pool with graceful fallback to thread pool when aiosqlite unavailable (externally-managed-environment)
- **Security Sprint (P0)**: Path traversal validation across 5 tools, graceful degradation for missing `project_path`
- **Enhanced Dead Code Detection**: 6 false-positive reduction strategies (>40% → <20% FP rate)
  - Polymorphism tracking via `ImplementsDetector`
  - Framework decorator detection (20+ decorators: Flask, FastAPI, Celery, Click, Django, Pytest)
  - Entry point analysis with call graph tracing
  - Tarjan's SCC algorithm for circular dead code
  - `__all__` exports check
  - Confidence scoring (High/Medium/Low with `alive_signals`)

### 🔧 Improvements
- Multi-machine deployment with `uv` venv pattern (bypasses PEP 668)
- Incremental indexing: SHA256 content hashing, symbol-level diff engine
- Watcher daemon: inotify-based, 100ms debounce, thread-safe queue
- 6-factor RRF fusion: semantic (40%), recency (15%), usage (15%), kind (10%), proximity (10%), callgraph centrality (10%)

### 🐛 Fixes
- MCP server troubleshooting: ModuleNotFoundError when using system Python vs venv
- Path traversal validation: handle missing `project_path` gracefully
- Test fixture discipline: all test calls updated for new params

---

## [v0.1.0] — 2026-06-01

### Initial Release
- **11 core tools**: `ast_grep`, `ast_read`, `ast_edit`, `ast_generate_stub`, `ast_refactor_extract_interface`, `ast_capsule`, `ast_query`, `semantic_search`, `search_symbols`, `find_symbol_definition`, `list_symbols`
- **Schema v1**: Basic symbols + embeddings (384-dim all-MiniLM-L6-v2)
- **79 tests** passing
- **Monolithic server**: 1,348-line `ast_tools_server.py`
- **MIT License**