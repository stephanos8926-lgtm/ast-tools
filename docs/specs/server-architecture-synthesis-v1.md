# SYNTHESIS: Server Architecture Redesign Plan

## Audit Summary

### Forward Audit Results
- **Spec structure**: ✅ Valid. All file paths referenced exist in the codebase
- **Current `_server.py`**: 123 lines, stdio-only, low-level `mcp.server.Server` API (not v2 `MCPServer`)
- **Current `context_tools.py`**: 42 lines, contains stubs/placeholders — perfect extraction anchor
- **Current plugin directory**: 3 plugins in `hermes-plugins/` — confirmed deletable
- **Dependencies**: `mcp>=1.0`, `anyio>=4.0` already present — `uvicorn` needs adding
- **Watchdog**: `watchdog` already in dev deps (`dependency-groups.dev`) — needs promotion to runtime deps

### Key Technical Notes
1. The server uses **`mcp.server.Server`** (low-level) not `MCPServer` v2 — this is the correct low-level API. Streamable HTTP will need the v2 `mcp.run(transport="streamable-http")` but we can integrate it via the `streamable_http_app()` method on the low-level server.
2. `anyio` is already a dependency — perfect for async mode management.
3. No existing CLI arg parsing in `_server.py` — `cli.py` (1375 lines) handles CLI but server entry point is separate. Will enhance both.
4. Plugin migration is purely additive (new module) then subtractive (delete old).

---

## Phase Plan (10 Phases)

| Phase | Description | Files | Dependencies |
|-------|-------------|-------|-------------|
| **P1** | Extract `agent_integration` modules | 5 new files | None |
| **P2** | Implement MCP tools (context_inject, token_status, etc.) | 2 modified | P1 |
| **P3** | Config system (file + env + CLI) | 1 new + 2 modified | None |
| **P4** | Timeout mode (enhance existing stdio) | 1 new + 1 modified | P3 |
| **P5** | Daemon mode (Unix socket, systemd) | 1 new + 2 modified | P3, P4 |
| **P6** | Watchdog + metrics store (daemon only) | 2 new | P5 |
| **P7** | Remote mode (Streamable HTTP) | 1 new + 1 modified | P3, P5 |
| **P8** | Thin Hermes plugin + cleanup | 4 new + 3 deleted | P1-P7 |
| **P9** | Tests | ~5 new test files | P1-P8 |
| **P10** | Documentation + config examples | ~3 files | P1-P9 |