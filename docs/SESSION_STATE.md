# Session State — 2026-07-05

## Active Project: rw-ast-tools

**Branch:** master  
**Last commit:** `2f74938` — test: 39 tests for agent_integration + config  
**Working tree:** Clean  
**Total tests:** 770 (731 existing + 39 new)  

---

## Status

### Completed This Session

**Server Architecture Redesign — 10 phases, 7 commits:**

- **P1** `agent_integration/` package — 4 standalone modules with zero Hermes dependency
- **P2** 4 new MCP tools: `context_inject` (real impl), `token_status`, `validate_usage`
- **P3** Config system — CLI flags > env vars > config file > defaults
- **P4** Timeout mode — stdio + idle TTL shutdown
- **P5** Daemon mode — persistent stdio + watchdog + systemd unit
- **P6** Watchdog (`CodebaseWatcher`) + MetricsStore (time-series SQLite)
- **P7** Remote mode stub — legacy HTTP fallback
- **P8** Unified `rw-ast-tools` Hermes plugin — replaces 3 old plugins
- **P9** 39 new tests (all passing)
- **P10** Spec, ADR, synthesis, plan, completion report

### Hermes Plugin Migration

- Old plugins (`ast-tools-context`, `ast-tools-tokens`, `ast-tools-codebase-index`) **disabled**
- New `rw-ast-tools` plugin **enabled** in `~/.hermes/config.yaml`
- Plugin dirs remain in `hermes-plugins/` for rollback reference

### Next

- Remote mode (Streamable HTTP) — needs MCP v2 SDK testing
- Daemon mode systemd installation guide
- PyPI v0.1.0 tag already pushed (waiting for CI)

---

## Key Files Created

| Path | Purpose |
|------|---------|
| `src/ast_tools/agent_integration/` | 4 standalone modules |
| `src/ast_tools/server_config.py` | Config loader |
| `src/ast_tools/watchdog/monitor.py` | File watcher |
| `src/ast_tools/watchdog/metrics_store.py` | Time-series metrics |
| `deploy/rw-ast-tools.service` | systemd unit |
| `hermes-plugins/rw-ast-tools/` | Thin Hermes plugin |
| `docs/specs/server-architecture-redesign-v1.md` | SPEC |
| `docs/adrs/0012-server-architecture-multi-mode.md` | ADR |
| `docs/reports/server-architecture-completion.md` | Completion report |
| `tests/test_agent_integration/` | 4 test files (39 tests) |