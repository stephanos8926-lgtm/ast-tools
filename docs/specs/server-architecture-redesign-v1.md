# SPEC: rw-ast-tools Server Architecture Redesign

> **Version:** v1  
> **Date:** 2026-07-05  
> **Author:** Lucien  
> **Status:** Draft  

---

## 1. Problem Statement

The rw-ast-tools MCP server currently has three architectural problems:

### 1.1 Hermes-Locked Hooks
Three Hermes plugins (`ast-tools-context`, `ast-tools-tokens`, `ast-tools-codebase-index`) bind critical functionality to Hermes Agent's plugin/hook system. Other agents (FORGE, Claude Code, Cursor, etc.) cannot use context injection, token tracking, or session intelligence because these only exist as Hermes hooks.

### 1.2 Ephemeral Server Lifecycle
The MCP server is launched per-connection via stdio transport. Every tool call on a cold server incurs a startup penalty (~0.5-2s). The server cannot maintain state between connections, and there's no mechanism for persistent background tasks (index watching, metric collection).

### 1.3 No Multi-Transport Support
Only stdio transport is supported. No HTTP/SSE for remote access, no persistent daemon mode, no configuration flexibility.

---

## 2. Solution Architecture

### 2.1 Three-Server-Mode Design

```python
# Transport selection (in priority order):
# 1. --mode CLI flag          highest priority
# 2. AST_TOOLS_MODE env var   runtime override
# 3. config.yaml setting      default

MODE_OPTIONS = Literal["timeout", "daemon", "remote"]

# Default mode: "timeout" (stdio, idle-timeout based)
# Daemon mode: systemd user service, Unix socket
# Remote mode: Streamable HTTP with auth
```

| Mode | Transport | Lifecycle | Use Case |
|------|-----------|-----------|----------|
| **timeout** (default) | stdio | Per-connection, idle TTL | Desktop CLI agents (Claude Code, Codex) |
| **daemon** | stdio over Unix socket | systemd service | Multi-agent workstations, persistent index |
| **remote** | Streamable HTTP | systemd service + auth | Server deployment, multi-machine mesh |

### 2.2 Module Extraction: `ast_tools.agent_integration`

Move Hermes hook logic into the rw-ast-tools package as standalone, importable modules:

```
src/ast_tools/agent_integration/
├── __init__.py              # Public API
├── context_builder.py       # Build context blocks from queries (was pre_llm_call hook)
├── token_tracker.py         # Token budget tracking + pressure warnings (was token plugin)
├── error_correction.py      # Common tool usage error detection (was error correction)
└── session_intel.py         # Session intelligence + metrics (was on_session_end hook)
```

**Each module:** Zero Hermes dependency. Pure functions. Testable with pytest.

**The `context_inject` MCP tool** (`tools/context_tools.py`) becomes a real implementation calling `agent_integration.context_builder.build_context()`.

### 2.3 Thin Hermes Plugin (Replacement)

Replace 3 plugins → 1 plugin (`rw-ast-tools`) that imports from `ast_tools.agent_integration`:

```
~/.hermes/plugins/rw-ast-tools/
├── plugin.yaml
└── __init__.py          # 50 lines, just wiring
```

```python
def register(ctx):
    from ast_tools.agent_integration import context_builder
    ctx.register_hook("pre_llm_call", lambda **kw: 
        {"context": context_builder.build_context(kw["user_message"])})
    # ... same pattern for other hooks
```

### 2.4 Agent-Facing MCP Tools

New tools that were previously only accessible via hooks:

| Tool | Source | What it does |
|------|--------|-------------|
| `context_inject` | Was Hermes hook | Returns formatted AST-tools context block for a query |
| `token_status` | Was Hermes tracker | Returns current token usage and budget pressure |
| `validate_usage` | Was error correction | Pre-validates a tool call against known error patterns |
| `session_intel` | Was on_session_end hook | Returns codebase intelligence snapshot |
| `index_watch` (enhanced) | Was codebase-index plugin | Manage file watcher for auto-indexing |

### 2.5 Config System

```
~/.config/rw-ast-tools/config.yaml          # User config
-- OR --
$PROJECT_ROOT/.ast-tools/config.yaml        # Per-project config
```

```yaml
server:
  mode: "timeout"             # timeout | daemon | remote
  timeout_seconds: 900        # Idle TTL for timeout mode (default 15min)
  
daemon:
  socket_path: "~/.cache/rw-ast-tools/server.sock"
  watchdogs: true             # Enable per-codebase watcher threads
  max_codebases: 10
  
remote:
  host: "127.0.0.1"
  port: 8100
  auth_token: ""              # Empty = no auth (local only)
  tls_cert: ""
  tls_key: ""

watchdog:
  enabled: true
  debounce_ms: 100
  auto_index: true
  metrics_ttl_hours: 168      # 7 days of metric snapshots
```

### 2.6 CLI + Env Overrides

```bash
# Mode override (highest priority)
ast-tools-server --mode daemon
ast-tools-server --mode remote --port 8100 --auth-token "sk-..."

# Env var (medium priority)
AST_TOOLS_MODE=daemon ast-tools-server

# Config file (lowest priority — used when nothing else set)
```

### 2.7 systemd Service (Daemon Mode)

```
~/.config/systemd/user/rw-ast-tools.service
```

```ini
[Unit]
Description=rw-ast-tools MCP Server (Persistent Daemon)
Documentation=https://github.com/stephanos8926-lgtm/ast-tools

[Service]
Type=simple
ExecStart=%h/.local/bin/ast-tools-server --mode daemon
Restart=on-failure
RestartSec=5
WatchdogSec=120
StartLimitBurst=5
StartLimitIntervalSec=300
MemoryMax=1G

[Install]
WantedBy=default.target
```

### 2.8 Watchdog Companion (Daemon Mode Only)

When `server.mode=daemon` and `watchdog.enabled=true`:

- Single `watchdog.observer` thread with routing dispatch
- Per-codebase state tracked as data (not threads)
- Metrics snapshots to SQLite time-series table
- Only active in persistent daemon mode (not timeout/remote)

---

## 3. File Manifest

### New Files

| File | Purpose |
|------|---------|
| `src/ast_tools/agent_integration/__init__.py` | Public API exports |
| `src/ast_tools/agent_integration/context_builder.py` | Context block builder (extracted from Hermes plugin) |
| `src/ast_tools/agent_integration/token_tracker.py` | Token budget tracking |
| `src/ast_tools/agent_integration/error_correction.py` | Common error pattern detection |
| `src/ast_tools/agent_integration/session_intel.py` | Codebase intelligence |
| `src/ast_tools/server/modes/__init__.py` | Mode router |
| `src/ast_tools/server/modes/timeout.py` | Stdio + idle TTL mode |
| `src/ast_tools/server/modes/daemon.py` | Unix socket daemon |
| `src/ast_tools/server/modes/remote.py` | Streamable HTTP server |
| `src/ast_tools/config.py` | Config loader (file + env + CLI) |
| `src/ast_tools/watchdog/monitor.py` | Inotify-based auto-indexer |
| `src/ast_tools/watchdog/metrics_store.py` | Time-series SQLite store |
| `~/.hermes/plugins/rw-ast-tools/plugin.yaml` | New thin plugin |
| `~/.hermes/plugins/rw-ast-tools/__init__.py` | Plugin wiring |
| `~/.config/systemd/user/rw-ast-tools.service` | systemd unit |
| `tests/test_agent_integration/` | Tests for extracted modules |
| `tests/test_server_modes/` | Tests for mode-specific behavior |
| `tests/test_config.py` | Config loading tests |
| `tests/test_watchdog/` | Watchdog + metrics tests |

### Modified Files

| File | Change |
|------|--------|
| `src/ast_tools/_server.py` | Add mode router, config loader, CLI arg parsing |
| `src/ast_tools/tools/context_tools.py` | Full implementation (was placeholder) |
| `src/ast_tools/tools/__init__.py` | Register new tools |
| `src/ast_tools/cli.py` | Add `--mode` / `--port` / `--auth-token` flags |
| `pyproject.toml` | Add `uvicorn` dep, `[project.scripts]` entry for `ast-tools-server` |
| `hermes-plugins/` | Remove 3 old plugins, add 1 new |

### Deleted Files

| File | Reason |
|------|--------|
| `hermes-plugins/ast-tools-context/` | Replaced by rw-ast-tools plugin |
| `hermes-plugins/ast-tools-tokens/` | Replaced by rw-ast-tools plugin |
| `hermes-plugins/ast-tools-codebase-index/` | Replaced by rw-ast-tools plugin |

---

## 4. Dependencies

| Dependency | Version | For |
|-----------|---------|-----|
| `uvicorn` | ≥0.30 | HTTP server for remote mode |
| `watchdog` | ≥4.0 | File watcher for daemon mode |

Existing deps unchanged: `mcp>=1.0`, `anyio>=4.0`, `sqlite-vec>=0.1.0`, `sentence-transformers>=2.2.0`

---

## 5. Acceptance Criteria

- [ ] `ast_tools.agent_integration.*` modules are pure functions with no Hermes dependency
- [ ] All 3 Hermes plugins replaced by single `rw-ast-tools` thin plugin
- [ ] Hermes retains EXACT same functionality after plugin swap
- [ ] Server starts in 3 modes via `--mode` CLI flag
- [ ] Mode selectable via `AST_TOOLS_MODE` env var
- [ ] Config file at `~/.config/rw-ast-tools/config.yaml`
- [ ] Timeout mode: server exits after N seconds idle
- [ ] Daemon mode: systemd service, auto-restart on crash
- [ ] Daemon mode: watchdog auto-indexes codebases in background
- [ ] Daemon mode: metrics snapshots collected per codebase
- [ ] Remote mode: Streamable HTTP with optional bearer auth
- [ ] `context_inject` MCP tool fully implemented (not placeholder)
- [ ] `token_status` MCP tool added
- [ ] 731+ existing tests continue to pass
- [ ] New tests for agent_integration, server modes, config
- [ ] FORGE agent can add rw-ast-tools as MCP server and use all 63+ tools
- [ ] Old plugins disabled, new plugin registered and verified

---

## 6. Rollback Plan

| Issue | Rollback |
|-------|----------|
| New plugin breaks hooks | Re-enable old plugins, disable new |
| Server mode change breaks client | Default to timeout mode (preserves current behavior) |
| Config parsing error | Fallback to hardcoded defaults |
| Watchdog consumes too much RAM | Disable watchdog in config |
| Remote mode auth broken | Modes are independent — remote mode fails, timeout/daemon unaffected |