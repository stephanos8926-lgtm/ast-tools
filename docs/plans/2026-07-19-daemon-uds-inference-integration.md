# ast-tools Daemon + RW_InferenceEngine Integration — Implementation Plan

> **For Hermes:** Execute tasks in order. Each task verified before next.

**Goal:** Unify ast-tools architecture: systemd-daemon owned process serving via Unix socket, both workstation + dev VM consuming a **single RW_InferenceEngine pod on dev VM**.

**Architecture:** One persistent `ast-tools-server --mode daemon` per machine, listening on a Unix domain socket. Hermes connects via `socat - UNIX-CONNECT:`. Watchdog + indexer + embedding model stay warm across sessions. Both machines consume RW_InferenceEngine at `http://100.109.15.31:8300` (embedded in a podman container on dev VM).

**Mode:** LOW (1 file modified, config changes, well-understood pattern)

**Phase 0 — Research:** ✅ Done (see conversation above: FGP benchmarks, Dik Rana v4, mcp2cli, Brooks McMillin, Linux IPC benchmarks)

---

## File Manifest

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/_server.py:195-229` | Modify — replace stdio with UDS sockets | 35→~55 |
| `deploy/rw-ast-tools.service` | Verify — already correct (socket path, foreground flag) | 24 |
| `deploy/install-daemon.sh` | Verify — already correct after previous edits | 116 |
| `~/.hermes/config.yaml` (workstation) | Modify — switch mcp_servers.ast-tools to socat | ~5 lines |
| `~/.hermes/config.yaml` (dev VM via SSH) | Create — add ast-tools mcp config | ~5 lines |
| `~/.config/rw-ast-tools/config.yaml` (both) | Verify — socket_path, watch_paths, embedding_provider | 14 |
| `/etc/caddy/Caddyfile` on srv1 | Modify — remove `ast.rapidwebs.org` block | ~5 lines |

---

## Task 1: Add Unix socket listener to daemon mode

**Objective:** Replace stdio transport in `_run_daemon_mode` with a Unix domain socket server that accepts NDJSON MCP messages.

**Files:**
- Modify: `src/ast_tools/_server.py:195-229`

**Step 1: Replace `_run_daemon_mode` with UDS implementation**

Replace lines 192-229:
```python
# ─── Mode: Daemon (Unix socket) ─────────────────────────────────────────

async def _run_daemon_mode(config: dict[str, Any]) -> None:
    """Run server in daemon mode — persistent Unix socket with watchdog.

    Listens on a Unix domain socket (NDJSON framing), accepts MCP JSON-RPC
    from multiple clients simultaneously, and maintains the index hot across
    sessions. systemd manages the process lifecycle.
    """
    socket_path = os.path.expanduser(config["daemon"]["socket_path"])
    logger.info("Starting daemon mode (socket: %s)", socket_path)

    # Clean up stale socket from previous run
    if os.path.exists(socket_path):
        os.unlink(socket_path)

    # Start watchdog for multiple paths
    from ast_tools.watchdog.monitor import CodebaseWatcher

    watcher = CodebaseWatcher(config)
    if watcher.enabled:
        try:
            watch_paths = config["daemon"].get("watch_paths", [])
            if not watch_paths:
                watch_paths = [os.getcwd()]
                logger.info("No watch_paths configured, using CWD: %s", watch_paths[0])
            for path in watch_paths:
                msg = watcher.start(path)
                logger.info("Watchdog: %s", msg)
        except Exception as e:
            logger.warning("Watchdog failed to start: %s", e)

    # Run server on Unix domain socket (NDJSON line protocol)
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(socket_path)
    server_sock.listen(5)
    os.chmod(socket_path, 0o600)  # Owner-only access

    logger.info("Daemon listening on %s", socket_path)

    async def handle_client(reader, writer):
        """Handle one MCP client connection over the socket."""
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                request = json.loads(line.decode("utf-8").strip())
                method = request.get("method")
                req_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "rw-ast-tools", "version": "0.2.0"},
                        },
                    }
                elif method == "tools/list":
                    from ast_tools.tools import list_tools
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"tools": list_tools()},
                    }
                elif method == "tools/call":
                    from ast_tools.tools import get_tool_handler
                    params = request.get("params", {})
                    name = params.get("name")
                    arguments = params.get("arguments", {})
                    handler = get_tool_handler(name)
                    result = await anyio.to_thread.run_sync(handler, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }

                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
        except Exception as e:
            logger.error("Client handler error: %s", e)
        finally:
            writer.close()
            await writer.wait_closed()

    async def accept_loop():
        """Accept client connections on the Unix socket."""
        loop = asyncio.get_event_loop()
        while True:
            client_reader, client_writer = await asyncio.open_unix_connection(
                sock=server_sock
            )
            # Handle in background — concurrent clients
            asyncio.create_task(handle_client(client_reader, client_writer))

    try:
        await accept_loop()
    finally:
        server_sock.close()
        if os.path.exists(socket_path):
            os.unlink(socket_path)
```

**Step 2: Add import for `socket` and `asyncio` at top of file**

```python
import socket
import asyncio as asyncio_mod  # alias to avoid conflict with anyio
```

**Step 3: Verify the daemon starts and accepts connections**

```bash
cd ~/Workspaces/ast-tools && source .venv/bin/activate
python3 src/ast_tools/_server.py --mode daemon --socket-path /tmp/test-ast-daemon.sock --foreground &
sleep 2
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | socat - UNIX-CONNECT:/tmp/test-ast-daemon.sock
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | socat - UNIX-CONNECT:/tmp/test-ast-daemon.sock
kill %1
```

Expected: initialize returns protocol version, tools/list returns tool count > 50.

**Step 4: Run targeted tests**

```bash
cd ~/Workspaces/ast-tools && source .venv/bin/activate
python3 -m pytest tests/test_cli.py -q --tb=short
```

Expected: 22 passed.

---

## Task 2: Switch workstation Hermes to consume via socket

**Objective:** Change `mcp_servers.ast-tools` in `~/.hermes/config.yaml` from stdio launch to Unix socket connection.

**Files:**
- Modify: `~/.hermes/config.yaml` (the `mcp_servers.ast-tools` block)

**Step 1: Replace the ast-tools mcp_servers entry**

Find:
```yaml
mcp_servers:
  ast-tools:
    args:
      - /home/sysop/Workspaces/ast-tools/src/ast_tools/_server.py
      - --mode
      - daemon
    command: /home/sysop/Workspaces/ast-tools/.venv/bin/python3
    connect_timeout: 60
    timeout: 120
    env:
      AST_TOOLS_DISCOVERY_MODE: 'true'
```

Replace with:
```yaml
mcp_servers:
  ast-tools:
    command: socat
    args:
      - "-"
      - "UNIX-CONNECT:/home/sysop/.cache/rw-ast-tools/server.sock"
    connect_timeout: 10
    timeout: 120
```

**Step 2: Verify Hermes can reach daemon after config reload**

After Hermes restarts: call `search_tools(query="codebase summary")` to confirm ast-tools tools respond.

---

## Task 3: Install + configure daemon on dev VM

**Objective:** Copy the systemd service + config to dev VM, point embedding provider at localhost RW_InferenceEngine, start daemon.

**Files:**
- Create: `~/.config/rw-ast-tools/config.yaml` on dev VM
- Copy: `~/.config/systemd/user/rw-ast-tools.service` from workstation template (adjusted for dev paths)

**Step 1: Create config on dev VM**

```bash
ssh dev "mkdir -p ~/.config/rw-ast-tools ~/.cache/rw-ast-tools"
ssh dev "cat > ~/.config/rw-ast-tools/config.yaml << 'EOF'
server:
  mode: daemon
  timeout_seconds: 900

daemon:
  socket_path: /home/sysop/.cache/rw-ast-tools/server.sock
  watchdogs: true
  max_codebases: 10
  watch_paths:
    - /home/sysop/Workspaces

embedding:
  provider: remote
  remote_url: http://127.0.0.1:8300

watchdog:
  enabled: true
  debounce_ms: 100
  auto_index: true
  metrics_ttl_hours: 168
EOF"
```

**Step 2: Install systemd service on dev VM**

```bash
ssh dev "mkdir -p ~/.config/systemd/user"
scp ~/Workspaces/ast-tools/deploy/rw-ast-tools.service dev:~/.config/systemd/user/
ssh dev "systemctl --user daemon-reload && systemctl --user enable --now rw-ast-tools"
```

**Step 3: Verify daemon is running on dev**

```bash
ssh dev "systemctl --user status rw-ast-tools --no-pager -l"
ssh dev "echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}' | socat - UNIX-CONNECT:/home/sysop/.cache/rw-ast-tools/server.sock | head -c 200"
```

Expected: Active (running), tools/list returns JSON.

---

## Task 4: Clean up dead infrastructure

**Objective:** Remove the Caddy `ast.rapidwebs.org` proxy block. Remove ast-tools HTTP remote mode container/service remnants if any.

**Step 1: Remove Caddy ast.rapidwebs.org block**

```bash
ssh srv1 "cd /etc/caddy && cp Caddyfile Caddyfile.bak.$(date +%Y%m%d)"
ssh srv1 "sed -i '/ast\.rapidwebs\.org/,/}/d' /etc/caddy/Caddyfile"
ssh srv1 "systemctl reload caddy"
```

**Step 2: Verify Caddy reloaded clean**

```bash
ssh srv1 "systemctl status caddy --no-pager | head -5"
ssh srv1 "curl -sS -o /dev/null -w '%{http_code}' http://ast.rapidwebs.org/ 2>&1"
```

Expected: Caddy active, ast.rapidwebs.org returns 404 or connection refused (DNS still resolves but no backend).

---

## Task 5: Verify end-to-end pipeline

**Step 1: Verify workstation daemon → RW_InferenceEngine → embedding works**

```bash
curl -sS -m 5 http://100.109.15.31:8300/health
```

Expected: `{"status":"ready","models_loaded":true}`

**Step 2: Verify daemon semantic_search works end-to-end**

Via Hermes after config reload: call `semantic_search(query="authentication", project_root="/home/sysop/Workspaces/ast-tools")`

Expected: Returns symbol results with relevance scores.

**Step 3: Verify dev daemon → RW_InferenceEngine works**

```bash
ssh dev "curl -sS -m 5 http://127.0.0.1:8300/health"
```

Expected: `{"status":"ready"}`

---

## Rollback Plan

Each task is reversible:
- Task 1: Revert `_server.py` to original stdio mode (git checkout)
- Task 2: Restore `~/.hermes/config.yaml` from current state (copy kept before edit)
- Task 3: `ssh dev "systemctl --user stop rw-ast-tools && systemctl --user disable rw-ast-tools"`
- Task 4: Restore Caddyfile from `.bak` copy `ssh srv1 "cp Caddyfile.bak.$(date +%Y%m%d) Caddyfile && systemctl reload caddy"`

---

## Verification Checklist

- [ ] Daemon listens on Unix socket (socat probe returns valid JSON-RPC)
- [ ] Workstation Hermes can call ast-tools tools via socket
- [ ] Dev VM daemon running via systemd
- [ ] Both daemons consume RW_InferenceEngine at `http://100.109.15.31:8300`
- [ ] RW_InferenceEngine health check returns `models_loaded: true`
- [ ] Caddy `ast.rapidwebs.org` route removed
- [ ] All 22 CLI tests pass
- [ ] SOUL.md updated with new architecture facts