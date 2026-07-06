# Session State — 2026-07-06

## Active Project: rw-ast-tools

**Branch:** master
**Last commit:** `0c738e8` — deploy: add systemd daemon install guide + automated installer
**Tag:** `v0.2.0` — remote mode (Streamable HTTP) with unit tests
**Working tree:** Clean
**Total tests:** 770

---

## Status

### Completed This Session (2026-07-06)

**Remote Mode — Streamable HTTP (v0.2.0):**
- `_run_remote_mode()` implemented using `StreamableHTTPSessionManager` + `StreamableHTTPASGIApp`
- Works with MCP Python SDK v1.27.2 (FastMCP internals)
- Port conflict handled via `RuntimeError` propagation (no fallback)
- Bearer auth deferred to reverse proxy layer
- Unit tests: 6 passing (config, CLI args, env vars, legacy fallback)
- Integration tests: skipped by default (manual run only)

**Daemon Mode Systemd Guide:**
- `deploy/README.md` — complete install guide
- `deploy/install-daemon.sh` — automated installer
- `deploy/rw-ast-tools.service` — hardened systemd unit

**Documentation Audit (from 2026-07-05):**
- All docs updated to reflect v0.1.0 (57 tools, 770 tests, 3 server modes)
- Hermes plugin docs updated to unified `rw-ast-tools` plugin

### PyPI Releases
| Version | Tag | Status | Notes |
|---------|-----|--------|-------|
| 0.1.0 | `v0.1.0` | ✅ Published | 3-mode server, unified plugin, 770 tests |
| 0.2.0 | `v0.2.0` | ✅ Published | Remote mode (Streamable HTTP), unit tests |

---

## Key Files Created/Modified (2026-07-06)

| Path | Purpose |
|------|---------|
| `src/ast_tools/_server.py` | Remote mode `_run_remote_mode()` + SystemExit handling |
| `tests/test_remote_mode.py` | 4 unit tests + 2 integration tests (skipped) |
| `deploy/README.md` | Systemd daemon install guide |
| `deploy/install-daemon.sh` | Automated installer |
| `pyproject.toml` | Removed duplicate `integration` marker |

---

## Next

- [ ] CI: Lint failures in `tests/watcher/test_daemon.py` (pre-existing, not from this work)
- [ ] Daemon mode: verify `install-daemon.sh` on clean machine
- [ ] Phase C: Auto-fix pipeline (planned, not specced)
- [ ] Phase D: Launch pipeline (marketing, docs site)