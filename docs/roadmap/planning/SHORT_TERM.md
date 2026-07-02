# Short-Term Plan — Next 4 Weeks (Phases 0-1)

> **Focus:** Foundation, Configuration, Data Lifecycle, Operations  
> **Timeline:** 3 weeks Phase 0 + 2 weeks Phase 1 (can overlap 1 week)  
> **Total:** ~4 weeks

---

## Week 1-2: Phase 0 — Foundation & Configuration

### Deliverables
- [ ] `~/.ast-tools/` config directory with XDG support
- [ ] `~/.ast-tools/config/tokens.yaml` with JSON Schema validation
- [ ] Logging framework with rotation
- [ ] Audit log for destructive operations
- [ ] SKILL.md cross-platform bundle (Hermes, Claude Code, generic)
- [ ] ast-tools-tokens plugin updated to read tokens.yaml
- [ ] Config file validation command

### Tasks
1. **Config directory module** — `src/ast_tools/config/` with loader, validation, schema
2. **tokens.yaml schema** — Define: per-tool budgets, model context lengths, compression/warning thresholds
3. **Logging setup** — Structured JSON logging, log rotation (size+time based), `logs/` directory
4. **Audit trail** — All destructive ops logged to `audit.log` with timestamp, action, user, params
5. **Plugin update** — `ast-tools-tokens` reads from `~/.ast-tools/config/tokens.yaml` instead of hardcoded values, falls back to defaults
6. **SKILL.md bundle** — Platform-agnostic skill files documenting all 43 tools, install + usage instructions
7. **Config validation** — `ast-tools config validate` command

### Dependencies
- ADR-001 (Config Directory Structure) — finalized
- `src/ast_tools/utils/` — needs config loader module

### Risk
- Config file migration from `~/.cache/ast-tools/` may have edge cases
- Plugin backwards compatibility with hardcoded values during transition

---

## Week 3-4: Phase 1 — Data Lifecycle & Operations

### Deliverables
- [ ] Setup wizard (interactive + `--non-interactive` mode)
- [ ] Doctor command with health score
- [ ] Vacuum command
- [ ] Curation daemon with scheduled execution
- [ ] PII redaction in curator
- [ ] Cleanup command
- [ ] Hermes plugin maintenance (project-context plugin)

### Tasks
1. **Setup wizard** — `ast-tools init`: detect env, create config, download model, create initial index
2. **Doctor command** — `ast-tools doctor`: check db integrity, model presence, index consistency, config validity, dependency availability, output health score
3. **Vacuum command** — `ast-tools vacuum`: SQLite VACUUM + REINDEX, temp file cleanup, old log rotation
4. **Curator daemon** — `ast-tools curator`: prune stale symbols, dedup, cleanup orphans. Configurable schedule (cron expression). `ast-tools curator run` for one-shot execution
5. **PII redaction** — Add to curator: scan symbol names/comments for emails, API keys, tokens, file paths. Configurable action (redact/flag/remove)
6. **Cleanup command** — `ast-tools cleanup`: `cache/tmp/`, stale model variants, expired caches
7. **Plugin maintenance** — Update ast-tools-context to reference tokens.yaml thresholds. Create ast-tools-project-context plugin (injects project metadata on session start)

### Dependencies
- Phase 0 (config directory, logging, audit)
- ADR-002 (Data Lifecycle Architecture) — finalized

### Risk
- Model download can fail (large file, network interruption) — need resume support
- Curator daemon must not conflict with concurrent index operations (locking)

---

## Immediate Next Steps (Day 1-3)

1. Write Phase 0 draft implementation doc
2. Run forward + reverse + adversarial audits on Phase 0 draft
3. Finalize Phase 0 document
4. Begin Phase 0 implementation (config directory module first)
5. Begin Phase 1 draft and audit in parallel with Phase 0 implementation

## Key Decisions Needed

- [ ] Approve ADR-001 (Config Directory Structure)
- [ ] Approve ADR-002 (Data Lifecycle Architecture)
- [ ] Approve tokens.yaml schema design (per-tool budgets)
- [ ] Model download strategy: bundled vs download-on-init