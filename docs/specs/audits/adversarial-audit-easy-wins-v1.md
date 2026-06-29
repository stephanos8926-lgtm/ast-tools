# Adversarial Audit Summary — CLI + Dead Code Security

**Date:** 2026-06-28  
**Auditor:** Hermes Agent (Security Analysis)  
**Severity Distribution:** 🔴 CRITICAL: 3 | 🟠 HIGH: 6 | 🟡 MEDIUM: 6 | 🟢 LOW: 3

---

## 🔴 CRITICAL (3 findings)

### C-01: SQL Injection via FTS5 Operators
**File:** `src/ast_tools/database/queries.py:43-47`  
**Exploit:** `ast-tools search "auth OR 1=1"`, `ast-tools search "test NEAR/0 column"`  
**Impact:** Database enumeration, filter bypass, DoS, info leakage  
**Mitigation:** Sanitize FTS5 operators (OR, AND, NEAR, quotes, ^) before query  
**Effort:** 2h

### C-02: Path Traversal in `--path` Argument  
**Exploit:** `ast-tools search "password" --path ../../etc`, `--path ~/.ssh`  
**Impact:** Read arbitrary system files, enumerate directories, discover sensitive configs  
**Mitigation:** Validate path is under allowed roots, block symlinks escaping root, reject `..` patterns  
**Effort:** 3h (CLI security critical!)

### C-03: Unlimited Recursion in Caller Analysis  
**File:** `src/ast_tools/tools/structural_analysis.py:44-76`  
**Exploit:** Deeply nested functions (10000+ levels) → stack overflow  
**Impact:** DoS via crash, memory exhaustion  
**Mitigation:** Add `max_depth=50`, `max_files=100` limits  
**Effort:** 2h

---

## 🟠 HIGH (6 findings)

### H-01: Information Leakage via Error Messages
**Problem:** SQLite errors expose schema details, file paths  
**Exploit:** `ast-tools search "NEAR/invalid"` → error reveals table structure  
**Mitigation:** Generic error messages for users, log details separately  
**Effort:** 2h

### H-02: DoS via Unbounded Query Limits
**Problem:** No limit on `--limit`, query length, result set size  
**Exploit:** `ast-tools search "a" --limit 999999` → memory exhaustion  
**Mitigation:** Hard cap `--limit 1000`, `--query-length 500`, result size limits  
**Effort:** 2h

### H-03: Dead Code Reveals Sensitive Patterns
**Problem:** `find-dead` exposes internal function names, security patterns  
**Exploit:** Enumerate `auth_`, `encrypt_`, `validate_` function names even in private code  
**Mitigation:** Skip files matching `*security*`, `*auth*`, `*crypto*`, `*.env`, `*secret*`  
**Effort:** 3h

### H-04: Race Condition in Concurrent CLI Runs
**Problem:** Multiple `ast-tools` instances share SQLite DB without proper locking  
**Exploit:** Run 10 concurrent `find-dead` commands → DB corruption  
**Mitigation:** `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, use `database_context()`  
**Effort:** 4h

### H-05: Dead Code False Positives → Accidental Deletion
**Problem:** Dynamic dispatch, framework routes flagged as dead (40%+ false positive rate)  
**Risk:** User runs `ast-tools find-dead --format=compact | xargs rm` → deletes working code  
**Mitigation:** Conservative defaults, require `--force` for deletion suggestions, confidence scoring  
**Effort:** Already covered in reverse audit (enhance filtering)

### H-06: Missing Authentication for Remote Usage
**Problem:** CLI could be wrapped in REST API later with no auth  
**Mitigation:** Document that CLI is local-only, add `--allow-remote` flag if ever exposed  
**Effort:** 1h (documentation only for now)

---

## 🟡 MEDIUM (6 findings)

1. **Symbol Name Enumeration** — `ast-tools nav Admin` finds all "Admin" classes even in private modules
2. **Timing Attacks** — Query latency reveals index size/presence of symbols
3. **Configuration File Exposure** — Scans `.git/`, `.env`, `config.yaml` by default
4. **Leftover Debug Code** — Print statements in indexer could leak paths
5. **Subprocess Injection** — If CLI shells out without list args
6. **Cache Poisoning** — No integrity check on cached results

---

## 🟢 LOW (3 findings)

1. **No Rate Limiting** — Could run millions of queries/second
2. **No Audit Logging** — No record of who searched for what
3. **Verbose Mode Leaks** — `--verbose` shows internal paths

---

## CRITICAL MITIGATIONS (MUST IMPLEMENT BEFORE LAUNCH)

| Issue | Mitigation | Effort | Priority |
|-------|------------|--------|----------|
| C-01 SQL Injection | `sanitize_fts5_query()` function | 2h | 🔴 P0 |
| C-02 Path Traversal | `validate_project_path()` with root allowlist | 3h | 🔴 P0 |
| C-03 Unlimited Recursion | `max_depth`, `max_files` limits | 2h | 🔴 P0 |
| H-01 Info Leakage | Generic error messages + separate detailed logging | 2h | 🟠 P1 |
| H-02 DoS Limits | Hard caps on limits, query length, result size | 2h | 🟠 P1 |
| H-04 Race Conditions | WAL mode, busy timeout, `database_context()` | 4h | 🟠 P1 |

**Total critical fix effort:** 15h

---

## Security Checklist (Pre-Launch)

- [ ] C-01: FTS5 sanitization implemented + tested
- [ ] C-02: Path validation with allowlist + symlink checks
- [ ] C-03: Recursion limits enforced (test with 10000-level nesting)
- [ ] H-01: Error messages sanitized (no schema paths in output)
- [ ] H-02: All limits enforced (query length, result count, timeout)
- [ ] H-03: Sensitive file patterns excluded from dead code scan
- [ ] H-04: SQLite WAL mode + busy timeout configured
- [ ] H-05: Confidence scoring for dead code (prevent accidental deletion)
- [ ] Test suite includes security tests (injection, traversal, DoS)

---

*Full audit report: `docs/SECURITY_AUDIT_CLI_DEADCODE_20260628.md` (862 lines, 25KB)*