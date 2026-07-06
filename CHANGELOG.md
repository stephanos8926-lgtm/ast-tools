# rw-ast-tools Changelog

All notable changes to the rw-ast-tools MCP server.

## [v0.1.0] — 2026-07-05

### ✨ Features
- **Three server modes**: timeout (default), daemon, remote
- **Unified Hermes plugin**: `rw-ast-tools` replaces 3 old plugins
- **Agent integration package**: `ast_tools.agent_integration` — zero Hermes dependency
- **New MCP tools**: `context_inject`, `context_status`, `token_status`, `validate_usage`, `session_intel`, `index_watch`
- **Watchdog auto-indexer** (daemon mode only)
- **Metrics store** with time-series SQLite
- **systemd service** for persistent daemon mode
- **Streamable HTTP** support for remote mode
- **Config system**: CLI > env > file > defaults

### 🔧 Fixes
- **ast_tools_server.py**: Restored missing `main()` entry point (was accidentally deleted in Phase 5 server cleanup)
- **GitHub MCP**: Added `GITHUB_TOKEN` env var to MCP server config (was unauthenticated)
- **mcp_discovery_timeout**: Increased from 2.5s to 60s (ast-tools takes ~8s to load)
- **context_file_max_chars**: Fixed quoted string `'250000'` → proper integer `250000`

### 📚 Documentation
- Full documentation audit: all docs reflect actual 57 tools, 770 tests
- SESSION_STATE.md rewritten with accurate phase completion status
- DOCUMENTATION_INDEX.md updated with correct metrics
- README.md tool count corrected (55 → 57), new phase categories added
- Global state file updated

---

## [v0.0.1] — 2026-06-01

### Initial Release

**Tools:** 11 core tools  
**Schema:** v1 (basic symbols + embeddings)  
**Tests:** 79 passing  
**Server:** Monolithic 1,348-line `ast_tools_server.py`