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

### 🟡 IN PROGRESS (Active)

| Task ID | Title | Started | Assignee | Notes |
|---------|-------|---------|----------|-------|

### ✅ DONE

| Task ID | Title | Completed | Verified |
|---------|-------|-----------|----------|
| SEC-01 | FTS5 SQL Injection Fix | 2026-06-29 | ✅ 402 tests pass |
| SEC-02 | Path Traversal Validation | 2026-06-29 | ✅ 29 security tests pass |
| SEC-03 | Recursion Limits | 2026-06-29 | ✅ Tests pass |
| SEC-04 | Consistent Path Validation | 2026-06-29 | ✅ 402 tests pass |
| SEC-05 | Error Message Sanitization | 2026-06-29 | ✅ 402 tests pass |
| SEC-06 | Input Limits & DoS Protection | 2026-06-29 | ✅ 402 tests pass |

---

## 🎯 Phase 0 Complete! ✅

**All 6 security tasks complete. All 402 tests pass.**

---

## 📊 Phase 0 Summary

| Task | Effort | Status |
|------|--------|--------|
| SEC-01: FTS5 SQL Injection Fix | 2h | ✅ Done |
| SEC-02: Path Traversal Validation | 3h | ✅ Done |
| SEC-03: Recursion Limits | 2h | ✅ Done |
| SEC-04: Consistent Path Validation | 4h | ✅ Done |
| SEC-05: Error Message Sanitization | 2h | ✅ Done |
| SEC-06: Input Limits & DoS Protection | 2h | ✅ Done |
| **Total** | **15h** | **100% Complete** |

---

## 🎯 Acceptance Criteria (Phase 0 Complete)

- [x] All 6 security tasks done
- [x] Security test suite passes (injection, traversal, DoS)
- [x] No path traversal possible via any tool
- [x] SQL injection impossible via FTS5
- [x] Recursion bounded (tested with deep nesting)
- [x] Error messages safe (no schema leakage)
- [x] All limits enforced

---

## 🔄 Ready for Phase 1

**Phase 1: Dead Code Enhancements** (25h) — Reduce false positives from 40% to <20%

- [ ] Polymorphism tracking (use `implements_detector.py`)
- [ ] Framework decorator detection (Flask, FastAPI, Celery, Click)
- [ ] Entry point detection (`__main__.py`, Click groups, etc.)
- [ ] Orphan cluster detection (SCC algorithm)
- [ ] `__all__` exports check
- [ ] Confidence scoring (high/medium/low)
- [ ] Database-based "deep scan" mode (optional)

---

*Phase 0 Complete: 2026-06-29 | All 6 security tasks done | 402/402 tests passing*