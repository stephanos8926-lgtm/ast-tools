# Implementation Plan: Server Architecture Redesign

> **Based on:** `docs/specs/server-architecture-redesign-v1.md`  
> **Mode:** MEDIUM (multi-phase, 5+ files, multiple subsystems)  

---

## Phases

### Phase 1: Extract agent_integration Module

**Objective:** Move Hermes plugin logic into standalone importable modules.

**Files:** Create `src/ast_tools/agent_integration/` with 4 modules.

- `context_builder.py` — port logic from `hermes-plugins/ast-tools-context/__init__.py`
- `token_tracker.py` — port logic from `hermes-plugins/ast-tools-tokens/__init__.py`
- `error_correction.py` — port error pattern dicts
- `session_intel.py` — port `_mcp_call()` + session tracking from codebase-index plugin

**Verification:** `python3 -c "from ast_tools.agent_integration import context_builder; print(context_builder.build_context('ast grep'))"` returns a non-empty string.

---

### Phase 2: Implement MCP Tools

**Objective:** Replace `context_inject` / `context_status` stubs with real implementations; add `token_status`, `validate_usage`, `session_intel`.

**Verification:** New tools appear in `list_tool_names()` output.

---

### Phase 3: Config System

**Objective:** Config file loading + CLI arg parsing + env var overrides for all 3 modes.

**Verification:** `ast-tools-server --mode daemon --help` shows mode options.

---

### Phase 4: Timeout Mode

**Objective:** Add idle timeout to stdio server — exits after N seconds of inactivity.

**Verification:** `ast-tools-server --timeout 5` exits after 5 seconds idle.

---

### Phase 5: Daemon Mode

**Objective:** Unix socket daemon with systemd unit.

**Verification:** `systemctl --user status rw-ast-tools` shows active.

---

### Phase 6: Watchdog + Metrics

**Objective:** Background auto-indexer + time-series metrics store (daemon mode only).

**Verification:** `index_status` shows watched codebases with recent metrics.

---

### Phase 7: Remote Mode

**Objective:** Streamable HTTP server with optional bearer auth.

**Verification:** `curl -X POST http://127.0.0.1:8100/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'` returns tool list.

---

### Phase 8: Hermes Plugin Migration

**Objective:** Replace 3 old plugins with 1 thin `rw-ast-tools` plugin.

**Verification:** Old plugins disabled, new plugin registered, hooks fire correctly.

---

### Phase 9: Tests

**Objective:** Test agent_integration modules, server modes, config loading.

**Verification:** `pytest tests/ -q --tb=short` passes.

---

### Phase 10: Documentation

**Objective:** Update README, CLI_REFERENCE, create systemd setup guide.

**Verification:** All docs reference accurate tool counts and mode options.