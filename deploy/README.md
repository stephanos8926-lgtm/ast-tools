# rw-ast-tools — Systemd Daemon Install Guide

## Overview

The **daemon mode** runs `ast-tools-server` as a persistent systemd user service with:
- Auto-restart on failure
- Watchdog auto-indexer (file watcher for live codebase updates)
- Metrics store (time-series SQLite for codebase growth tracking)
- Unix socket for fast local communication

## Prerequisites

- **Linux** with systemd (tested on Ubuntu 22.04+, Debian 12+)
- **Python 3.10+** installed
- **rw-ast-tools** installed via PyPI or from source

```bash
# Option 1: Install from PyPI (recommended)
uv tool install rw-ast-tools

# Option 2: Install from source
cd ~/Workspaces/ast-tools
uv sync --all-extras
uv build
uv tool install dist/*.whl
```

Verify installation:
```bash
ast-tools-server --version
# Should output: rw-ast-tools 0.1.0
```

## Quick Install (Automated)

```bash
cd ~/Workspaces/ast-tools/deploy
./install-daemon.sh
```

This script:
1. Copies the service unit to `~/.config/systemd/user/`
2. Creates required directories
3. Reloads systemd
4. Enables and starts the service

## Manual Install (Step-by-Step)

### 1. Copy the service unit

```bash
mkdir -p ~/.config/systemd/user
cp ~/Workspaces/ast-tools/deploy/rw-ast-tools.service ~/.config/systemd/user/
```

### 2. Create required directories

```bash
mkdir -p ~/.cache/rw-ast-tools ~/.config/rw-ast-tools
```

### 3. Create user config (optional)

```bash
cat > ~/.config/rw-ast-tools/config.yaml << 'EOF'
server:
  mode: "daemon"
  timeout_seconds: 900

daemon:
  socket_path: "~/.cache/rw-ast-tools/server.sock"
  watchdogs: true
  max_codebases: 10

watchdog:
  enabled: true
  debounce_ms: 100
  auto_index: true
  metrics_ttl_hours: 168  # 7 days
EOF
```

### 4. Reload and enable

```bash
systemctl --user daemon-reload
systemctl --user enable --now rw-ast-tools
```

### 5. Verify status

```bash
systemctl --user status rw-ast-tools
```

Expected output:
```
● rw-ast-tools.service - rw-ast-tools MCP Server (Persistent Daemon)
   Loaded: loaded (/home/user/.config/systemd/user/rw-ast-tools.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2026-07-06 08:15:23 UTC; 5s ago
   Docs: https://github.com/stephanos8926-lgtm/ast-tools
 Main PID: 12345 (ast-tools-server)
    Tasks: 12 (limit: 4915)
   Memory: 45.2M (max: 1.0G)
   CGroup: /user.slice/user-1000.slice/user@1000.service/rw-ast-tools.service
           └─12345 /home/user/.local/bin/ast-tools-server --mode daemon --foreground
```

## Using the Daemon

### As MCP Server (stdio over Unix socket)

Add to your MCP client config (Hermes, FORGE, Claude Code, etc.):

```json
{
  "mcpServers": {
    "rw-ast-tools": {
      "command": "socat",
      "args": ["-", "UNIX-CONNECT:~/.cache/rw-ast-tools/server.sock"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Or use the native MCP client support if available.

### Via CLI (connect to running daemon)

```bash
# Connect to daemon and run a command
ast search "authentication handler" --project-root /path/to/project
```

### Watchdog Features

The watchdog automatically:
- **Watches** `~/.cache/rw-ast-tools/` for codebase changes
- **Re-indexes** modified files within 100ms debounce
- **Records metrics** (symbol counts, file sizes, churn) to SQLite

Check watchdog status:
```bash
# From an MCP client
mcp_ast_tools_watch_status
# Expected: {"status": "running", "paths": ["/path/to/project"], "debounce_ms": 100}
```

## Configuration Reference

### Server Config (`~/.config/rw-ast-tools/config.yaml`)

```yaml
server:
  mode: "daemon"              # timeout | daemon | remote
  timeout_seconds: 900        # Idle TTL for timeout mode (15 min)

daemon:
  socket_path: "~/.cache/rw-ast-tools/server.sock"
  watchdogs: true             # Enable per-codebase watcher threads
  max_codebases: 10           # Limit concurrent watched codebases

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

### CLI Overrides

```bash
# Override mode
AST_TOOLS_MODE=daemon ast-tools-server

# Override socket path
ast-tools-server --mode daemon --socket-path /custom/path.sock
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AST_TOOLS_MODE` | Server mode | `timeout` |
| `AST_TOOLS_CONFIG` | Config file path | `~/.config/rw-ast-tools/config.yaml` |
| `AST_TOOLS_SOCKET` | Unix socket path | `~/.cache/rw-ast-tools/server.sock` |

## Troubleshooting

### Service won't start

```bash
# Check logs
journalctl --user -u rw-ast-tools -n 50

# Common issues:
# 1. ast-tools-server not in PATH
#    Fix: Ensure ~/.local/bin is in PATH, or use full path in service unit

# 2. Permission denied on socket
#    Fix: Check ReadWritePaths in service unit matches socket_path

# 3. Config file not found
#    Fix: Create ~/.config/rw-ast-tools/config.yaml or let it use defaults
```

### Daemon not responding

```bash
# Check if process is alive
ps aux | grep ast-tools-server

# Check socket exists
ls -la ~/.cache/rw-ast-tools/server.sock

# Test with socat
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | socat - UNIX-CONNECT:~/.cache/rw-ast-tools/server.sock
```

### Watchdog not indexing

```bash
# Check watchdog status via MCP
mcp_ast_tools_watch_status

# Verify watch_add was called
# Check logs for "File watcher started"

# Manually trigger reindex
mcp_ast_tools_refresh_index project_path="."
```

### High memory usage

The embedding model (~130MB) stays loaded in daemon mode. If memory is constrained:

```yaml
# In config.yaml
daemon:
  watchdogs: true
  max_codebases: 3  # Reduce concurrent codebases

# Or disable watchdog entirely
watchdog:
  enabled: false
```

## Uninstall

```bash
systemctl --user stop rw-ast-tools
systemctl --user disable rw-ast-tools
rm ~/.config/systemd/user/rw-ast-tools.service
systemctl --user daemon-reload
```

## Security Notes

The service unit includes hardening:
- `NoNewPrivileges=true` — prevents privilege escalation
- `ProtectHome=read-only` — home dir read-only
- `ProtectSystem=strict` — system dirs read-only
- `PrivateTmp=true` — private /tmp
- `MemoryMax=1G` — memory limit

Only these paths are writable:
- `~/.cache/rw-ast-tools/` — socket, index DB, metrics
- `~/.config/rw-ast-tools/` — config

## Logs

```bash
# Follow logs
journalctl --user -u rw-ast-tools -f

# Last 100 lines
journalctl --user -u rw-ast-tools -n 100

# Since boot
journalctl --user -u rw-ast-tools -b
```

## Related Files

| File | Purpose |
|------|---------|
| `deploy/rw-ast-tools.service` | systemd unit |
| `deploy/install-daemon.sh` | Automated installer |
| `src/ast_tools/watchdog/monitor.py` | File watcher |
| `src/ast_tools/watchdog/metrics_store.py` | Metrics SQLite |
| `src/ast_tools/server/modes/daemon.py` | Daemon mode implementation |