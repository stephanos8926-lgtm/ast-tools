# ADR-002: Data Lifecycle Architecture

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools creates and manages persistent state (SQLite database, embedding models, temporary indexes). Without lifecycle management, this data accumulates unboundedly — stale symbols, orphaned embeddings, and bloated databases degrade performance over time.

## Decision

Adopt a **five-stage lifecycle model** for all persistent data:

```
INIT → MAINTAIN → CURATE → VACUUM → CLEANUP
                ↓                        ↓
            (recurring)          UNINSTALL (terminal)
```

### Stage Details

#### 1. INIT (setup wizard)
- Interactive first-time setup
- Schema initialization (run migrations)
- Embedding model download (if needed)
- Initial codebase index
- Config file creation with defaults

#### 2. MAINTAIN (doctor command)
- Database integrity check (`PRAGMA integrity_check`)
- Embedding model availability
- Index consistency (no dangling references)
- Configuration validation
- Dependency checks (tree-sitter grammars, etc.)
- Returns health score (0-100)

#### 3. CURATE (daemon + commands)
- **Pruning:** Remove symbols/files that no longer exist in the workspace
- **Deduplication:** Content-hash comparison, merge identical symbols
- **PII redaction:** Scan for emails, API keys, paths in symbol names/docs — redact or flag
- **Staleness detection:** Symbols untouched for >N days get demoted in search ranking
- **Orphan cleanup:** Embeddings without parent symbols, edges without endpoints

#### 4. VACUUM (space reclamation)
- SQLite `VACUUM` + `REINDEX`
- Temporary file cleanup (`cache/tmp/`)
- Old log rotation (>30 days)
- Shrink embedding model cache (remove unused variants)

#### 5. CLEANUP / UNINSTALL (terminal)
- Remove all config, cache, logs, backups under `~/.ast-tools/`
- Optional: preserve config only for reinstall
- Systemd service removal
- Hermes plugin config cleanup

### Trigger Model

| Trigger | Action | Automation |
|---------|--------|------------|
| First install | INIT | Interactive wizard |
| `ast-tools doctor` | MAINTAIN | On-demand |
| Daily cron | CURATE | Optional (configurable) |
| Weekly cron | VACUUM | Optional (configurable) |
| `ast-tools uninstall` | CLEANUP | Confirmation-only |

### Consequences

- Positive: Database never grows unbounded
- Positive: Consistent lifecycle across all data types
- Positive: Doctor gives users confidence in their deployment
- Negative: Additional code to maintain (6 new commands)
- Negative: Daemon adds complexity for scheduled curation

## Alternatives Considered

1. **No lifecycle management**: Rejected — database bloat is a real problem at scale
2. **Git LFS-style automatic pruning**: Rejected — user should control when curation happens
3. **PostgreSQL instead of SQLite for easier maintenance**: Rejected — SQLite simplicity outweighs maintenance gains for single-machine deployments