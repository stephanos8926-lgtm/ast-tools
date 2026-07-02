# ADR-001: Config Directory Structure

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools needs a standardized configuration directory for all user-facing settings, cache data, and logs. Currently, configuration is scattered — Hermes plugin config lives in `~/.hermes/plugins/`, the database lives in `~/.cache/ast-tools/`, and the tokens plugin has hardcoded values.

## Decision

Adopt `~/.ast-tools/` as the canonical configuration directory with the following structure:

```
~/.ast-tools/
├── config/
│   ├── tokens.yaml          # Token budgets, context lengths, thresholds
│   ├── server.yaml          # MCP server settings (host, port, log level)
│   └── mcp.yaml             # MCP protocol settings (transport, timeouts)
├── cache/
│   ├── codebase.db          # SQLite database (indexes + embeddings)
│   ├── models/              # Downloaded embedding models
│   └── tmp/                 # Temporary working files
├── logs/
│   ├── ast-tools.log        # Main application log
│   └── audit.log            # Audit trail for destructive operations
└── backups/                 # Backup archives (created by backup command)
```

### Design Principles

1. **XDG Base Directory compliant** — Respect `$XDG_CONFIG_HOME`, `$XDG_CACHE_HOME`, `$XDG_DATA_HOME` when set. Fall back to `~/.ast-tools/`.
2. **Environment override** — `$AST_TOOLS_HOME` overrides the base directory entirely.
3. **Self-contained** — All data lives under this directory. `rm -rf ~/.ast-tools/` is a valid uninstall.
4. **Git-ignorable** — The config directory is NEVER committed to a project repo.

### File Format

All config files use YAML with JSON Schema validation on load. Invalid files produce clear error messages with file:line references.

### Consequences

- Positive: Single source of truth for configuration
- Positive: Easy backup/restore (one directory)
- Positive: Clear uninstall boundary
- Negative: Existing `~/.cache/ast-tools/` data must be migrated
- Negative: Hermes plugin config currently in `~/.hermes/plugins/` must adapt

## Alternatives Considered

1. **Single config file**: Rejected — separate concerns need separate files
2. **INI format**: Rejected — YAML supports complex nesting for multi-server config
3. **Database-only**: Rejected — config files must be human-editable without CLI tools