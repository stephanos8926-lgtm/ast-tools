# Kanban Board — Phase 0: Security Hardening

**Created:** 2026-06-29  
**Project:** ast-tools  
**Phase:** 0 - Security Hardening (15h)  
**Goal:** Fix 8 critical issues before any feature work

---

## 📋 Board

### 🔴 TODO (Not Started)

| Task ID | Title | Effort | Priority | Description |
|---------|-------|--------|----------|-------------|
| SEC-04 | Consistent Path Validation | 4h | 🟠 P1 | Apply `is_relative_to()` to ALL file operations (cache, refresh, etc.) |
| SEC-05 | Error Message Sanitization | 2h | 🟠 P1 | Generic user errors, detailed logging separate |
| SEC-06 | Input Limits & DoS Protection | 2h | 🟠 P1 | Cap query length (500), limit (1000), timeout (30s) |

### 🟡 IN PROGRESS (Active)

| Task ID | Title | Started | Assignee | Notes |
|---------|-------|---------|----------|-------|

### ✅ DONE

| Task ID | Title | Completed | Verified |
|---------|-------|-----------|----------|
| SEC-01 | FTS5 SQL Injection Fix | 2026-06-29 | ✅ Tests pass |
| SEC-02 | Path Traversal Validation | 2026-06-29 | ✅ Tests pass (29/29) |
| SEC-03 | Recursion Limits | 2026-06-29 | ✅ Tests pass |

---

## 📝 Remaining Task Details

### SEC-04: Consistent Path Validation (4h) 🟠 P1 **NEXT**
**Files:** `cache.py`, `refresh_index.py`, `ast_edit.py`, `ast_read.py`, `ast_generate_stub.py`, `ast_refactor_extract_interface.py`
- [ ] Audit all file operations for path operations for path validation
- [ ] Apply `is_relative_to(project_path)` consistently  
- [ ] Reject (not just log) traversal attempts
- [ ] Use new `validate_project_path()` from security.py where applicable

### SEC-05: Error Message Sanitization (2h) 🟠 P1
**Files:** All tools returning errors
- [ ] Generic user-facing messages
- [ ] Detailed errors logged separately
- [ ] No schema/file paths in user output

### SEC-06: Input Limits & DoS Protection (2h) 🟠 P1
**Files:** CLI args, tool parameters
- [ ] Query length max 500 (already in sanitize_fts5_query)
- [ ] Result limit max 1000
- [ ] Timeout 30s for long ops

---

## 🎯 Acceptance Criteria (Phase 0 Complete)

- [ ] All 6 security tasks done
- [ ] Security test suite passes (injection, traversal, DoS)
- [ ] No path traversal possible via any tool
- [ ] SQL injection impossible via FTS5
- [ ] Recursion bounded (tested with 10000-level nesting)
- [ ] Error messages safe (no schema leakage)
- [ ] All limits enforced

---

## 🔄 Workflow

1. **Claim task** → Move to IN PROGRESS
2. **Implement** → Write tests first (TDD), then code
3. **Verify** → Run security tests + full suite
4. **Complete** → Move to DONE
5. **Next task** → Claim from TODO

---

*Updated: 2026-06-29 | SEC-01, SEC-02, SEC-03 Complete | Next: SEC-04 (Consistent Path Validation)*