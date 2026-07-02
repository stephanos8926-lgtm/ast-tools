# Phase 3 Implementation Plan — Backup, Reporting & Dashboard (FINAL)

> **Status:** ✅ Final — Audited (Forward ✅, Reverse ✅, Adversarial ✅)  
> **Phase:** 3  
> **Timeline:** 3 weeks  
> **Dependencies:** Phase 2 (SDK, Docker)  
> **Finalized:** 2026-07-31  

---

## Audit Results

| Audit | Findings | Resolution |
|-------|----------|------------|
| **Forward** | 9 findings | ✅ All incorporated |
| **Reverse** | 9 findings (retention policy, incremental strategy, restore safety, dashboard auth/TLS, report output dir) | ✅ All incorporated |
| **Adversarial** | 8 findings (tamper detection, key management, XSS, downgrade protection, path traversal in archive) | ✅ All incorporated |

## Key Changes from Draft

- Backup includes SHA256 checksums in `meta.yaml` for tamper detection
- Restore warns if backup is newer than database (downgrade protection)
- Archive extraction validates paths (prevents archive path traversal)
- Dashboard requires `AST_TOOLS_DASHBOARD_TOKEN` env var for auth
- Dashboard sanitizes all user-controlled data (symbol names, paths) against XSS
- Backup retention: default "keep last 5 full backups", configurable
- Incremental backup: content-hash based (SHA256 of each file, compare to full backup baseline)
- Restore safety prompt: "Database is newer than backup by X days. Continue?"
- Backup scheduled via same mechanism as curator (Phase 1 scheduler integration)
- Report output: `ast-tools insights --output ~/.ast-tools/reports/report-name.md`
- Uninstall: interactive, offers to create backup first, removes all artifacts (Task carried over from Phase 1)

## Verification Checklist

- [ ] `ast-tools backup list` shows date, size, type, encrypted status
- [ ] `ast-tools backup` SHA256 checksum verifiable: `shasum -c meta.yaml`
- [ ] Encrypted backup requires password for restore
- [ ] Wrong password → clear error, no data loss
- [ ] Archive path traversal blocked: `tar` with path components containing `..` rejected
- [ ] Incremental backup is measurably smaller than full backup
- [ ] Backup retention: when limit exceeded, oldest backup auto-removed
- [ ] `ast-tools insights --format json` returns valid complete JSON
- [ ] Dashboard starts, requires token, shows index stats
- [ ] Symbol named `<script>alert(1)</script>` renders safely in dashboard
- [ ] `ast-tools uninstall` creates backup before deletion
- [ ] `ast-tools uninstall --force` skips confirmation, removes all
- [ ] All existing tests pass