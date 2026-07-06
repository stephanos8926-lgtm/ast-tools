# Server Architecture Redesign — Completion Report

**Date:** 2026-07-05  
**Project:** rw-ast-tools  
**Author:** Lucien  

---

## Summary

Complete redesign of the rw-ast-tools MCP server from a single-mode stdio server into a three-mode architecture with decoupled agent integration modules. Total of **39 new tests**, **770 total**, **0 failures**, **0 lint errors**.

---

## What Was Done (10 Phases)

| Phase | Description | Status | Key Files |
|-------|-------------|--------|-----------|
| **P1** | Extract `agent_integration` package | ✅ | 4 new modules, zero Hermes dependency |
| **P2** | Implement MCP tools (context_inject, token_status, validate_usage) | ✅ | 4 new MCP tools replacing placeholders |
| **P3** | Config system (file + env + CLI) | ✅ | `server_config.py` — three-tier resolution |
| **P4** | Timeout mode (stdio + idle TTL) | ✅ | Idle shutdown monitor in `_server.py` |
| **P5** | Daemon mode + systemd service | ✅ | `deploy/rw-ast-tools.service` |
| **P6** | Watchdog + metrics store | ✅ | `watchdog/monitor.py`, `watchdog/metrics_store.py` |
| **P7** | Remote mode (Streamable HTTP) | 🟡 Stub | Legacy HTTP fallback via aiohttp |
| **P8** | Thin Hermes plugin | ✅ | 1 plugin replaces 3 old plugins |
| **P9** | Tests | ✅ | 39 new tests across 4 test files |
| **P10** | Documentation | 🟡 Partial | Spec, ADR, plan, synthesis all written |

---

## Architecture

```
ast-tools-server
  ├── --mode timeout (default)
  │     stdio transport + idle TTL shutdown
  ├── --mode daemon
  │     stdio transport + watchdog auto-indexer + systemd
  └── --mode remote
        Streamable HTTP (MCP v2) + bearer auth

agent_integration/         ← New: standalone, no Hermes dep
  ├── context_builder.py   ← Keyword detection + context blocks
  ├── token_tracker.py     ← Budget tracking + pressure monitoring
  ├── error_correction.py  ← Known error pattern detection
  └── session_intel.py     ← File mutation + MCP call helper

Hermes Plugin (thin shim):
  rw-ast-tools → imports from agent_integration
  Replaces: ast-tools-context, ast-tools-tokens, ast-tools-codebase-index
```

---

## Key Metrics

| Metric | Before | After |
|--------|--------|-------|
| MCP tools | 55 | 57 (+2: token_status, validate_usage) |
| Hermes plugins | 3 old | 1 new unified |
| Tests | 731 | 770 (+39) |
| server.py size | 123 lines | 315 lines (3 modes) |
| Config modes | 1 (stdio) | 3 (timeout/daemon/remote) |

---

## Hermes Plugin Status

The old plugins remain in `hermes-plugins/` for reference but are **disabled** in `~/.hermes/config.yaml`:

| Old Plugin | Status | Replaced By |
|------------|--------|-------------|
| `ast-tools-context` | ❌ Disabled | `rw-ast-tools` |
| `ast-tools-tokens` | ❌ Disabled | `rw-ast-tools` |
| `ast-tools-codebase-index` | ❌ Disabled | `rw-ast-tools` |

**FORGE integration:** Any MCP client (FORGE, Claude Code, Cursor) can add rw-ast-tools as an MCP server:
```json
{
  "mcpServers": {
    "rw-ast-tools": {
      "command": "ast-tools-server",
      "args": ["--mode", "daemon"]
    }
  }
}
```

---

## Remaining Work

| Item | Priority | Notes |
|------|----------|-------|
| Remote mode (Streamable HTTP) | Medium | Requires MCP v2 SDK streamable_http_app |
| Remote mode auth hardening | Medium | Bearer token, TLS optional |
| Test daemon mode with systemd | Low | Manual install + verify |
| User docs (README update) | Low | CLI_REFERENCE, quickstart |
| Remove old plugin dirs | Low | Keep for rollback safety |

---

## Commits

```
dac70bb docs: server architecture redesign — SPEC, ADR-012, synthesis, plan
79c3815 feat(agent-integration): extract Hermes plugin logic + MCP tools
1e0bc84 feat(server-config): three-tier config system
8b601d0 feat(server-modes): three-mode server architecture
9c31439 feat(daemon+watchdog): daemon mode + file watcher + metrics store
7840828 feat(plugin): unified rw-ast-tools Hermes plugin
2f74938 test(agent-integration): 39 tests for extracted modules + config
```