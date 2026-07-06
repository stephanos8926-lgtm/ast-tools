# ADR-012: Multi-Mode Server Architecture

**Status:** Proposed  
**Date:** 2026-07-05  
**Author:** Lucien  

## Context

The rw-ast-tools MCP server has three architectural constraints that limit its utility:

1. **Hermes-locked plugins** — Core capabilities (context injection, token tracking, session intelligence) are implemented as Hermes hooks and inaccessible to other agents
2. **Ephemeral lifecycle** — Server starts/stops per connection, wasting resources on cold starts and preventing persistent state
3. **Single transport** — Only stdio, no HTTP/SSE for remote access or multi-client scenarios

## Decision

Adopt a **three-mode server architecture** with configurable transport and lifecycle:

### Modes

| Mode | Transport | Lifecycle | Primary Use |
|------|-----------|-----------|-------------|
| `timeout` (default) | stdio | Per-connection with idle TTL | Desktop agents (Claude Code, Codex) |
| `daemon` | Unix socket via systemd | Persistent, auto-restart | Multi-agent workstations |
| `remote` | Streamable HTTP | Persistent, secured | Server deployment, cross-machine |

### Architectural Decoupling

Extract Hermes plugin logic into `ast_tools.agent_integration.*` — pure functions importable by any framework. The Hermes plugin becomes a ~50-line thin shim.

## Consequences

**Positive:**
- FORGE, Claude Code, Cursor can all use rw-ast-tools as a standard MCP server
- Persistent daemon eliminates cold-start latency
- Remote mode enables server-side deployment
- Watchdog auto-indexing only in daemon mode (no wasted resources)
- Backward compatible — timeout mode preserves current behavior

**Negative:**
- Increased complexity from 1 mode to 3
- Need to manage systemd service lifecycle
- Daemon mode requires ~130MB for embedding model in RAM
- Auth infrastructure needed for remote mode

**Neutral:**
- Hermes plugin becomes thinner but requires migration
- Watchdog disabled by default (only daemon mode)
- Config system adds operational surface area

## Alternatives Considered

1. **Single daemon mode only** — Rejected: breaks backward compatibility for desktop agents
2. **HTTP-only with supergateway** — Rejected: adds external dependency, less control
3. **Keep Hermes hooks + add MCP tools** — Rejected: doesn't solve the agent-lock problem
4. **Remain single-transport (stdio only)** — Rejected: `streamable-http` is the MCP spec's recommended transport for 2026+

## References

- MCP Spec 2025-06-18: Streamable HTTP is recommended transport
- MCP Python SDK v2: Native `mcp.run(transport="streamable-http")` support
- `mcp-stdio-bridge`, `MCP-Starter-Kit`, `local-mcp-server` — reference implementations using dual-transport architecture
- "MCP in Production" (ilirivezaj.com): systemd user services with WatchdogSec for MCP servers