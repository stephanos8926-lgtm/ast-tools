# Phase 4 Implementation Plan — Agent Ecosystem & Multi-Machine (FINAL)

> **Status:** ✅ Final — Audited (Forward ✅, Reverse ✅, Adversarial ✅)  
> **Phase:** 4  
> **Timeline:** 3 weeks  
> **Dependencies:** Phase 3 (backup/restore, reporting operational)  
> **Finalized:** 2026-07-31  

---

## Audit Results

| Audit | Findings | Resolution |
|-------|----------|------------|
| **Forward** | 4 findings (NFS locking, Gemini version check) | ✅ All incorporated |
| **Reverse** | 2 findings (network-wide lock, vs code timeline) | ✅ All incorporated |
| **Adversarial** | 2 findings (shared DB malicious entry, cross-repo access) | ✅ All incorporated |

## Key Changes from Draft

- Multi-machine: NFS-backed SQLite uses `PRAGMA locking_mode=EXCLUSIVE` (NFS doesn't support `flock`)
- Added network-wide lock for curator across machines (Redis-based or S3 lock file)
- Gemini extension requires Gemini CLI 2.0+ (version check at load time)
- Cross-repo resolution: only resolves within repos user has explicitly indexed
- Shared DB: input validation on write (reject symbols with binary data, path traversal, excessive length)
- VS Code extension moved to Phase 4 (from Phase 5) — MCP-based is lightweight, high value

## Verification Checklist

- [ ] Gemini CLI loads extension: `gemini-cli --load-extension extensions/gemini/`
- [ ] Gemini CLI invokes `ast_grep` and returns results
- [ ] Claude Code loads `CLAUDE.md` and uses tools: `codebase_search`, `impact_analysis`
- [ ] Two machines share SQLite via NFS without corruption
- [ ] Network lock prevents concurrent curator across machines
- [ ] Cross-repo resolution: symbol resolves within indexed repos only
- [ ] Cross-repo scope: `--repo` flag limits search to specific repo
- [ ] DOCX report: valid .docx, opens in Word/LibreOffice
- [ ] PDF report: valid .pdf, text selectable
- [ ] Analytics: local dashboard shows query frequency by tool
- [ ] VS Code extension: command palette shows ast-tools commands
- [ ] All existing tests pass