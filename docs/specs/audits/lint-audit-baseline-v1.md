# Lint Audit — Baseline (Pre-Implementation)

**Date:** 2026-06-28  
**Mode:** MEDIUM (plan-and-audit)  
**Scope:** Existing codebase baseline before CLI + dead code implementation

---

## Command Run

```bash
ruff check src/ast_tools/ --statistics
```

---

## Findings

| Code | Count | Description |
|------|-------|-------------|
| `ARG001` | 4 | Unused function argument |
| `ARG002` | 1 | Unused method argument |
| `ARG005` | 2 | Unused lambda argument |
| **Total** | **7** | All severity: error |

---

## Files with Violations

- `src/ast_tools/lsp_client.py:310` — ARG002 (unused method argument: `file`)
- `src/ast_tools/tools/watcher.py:167,169` — ARG005 (unused lambda argument: `args`)
- Other files — ARG001 (unused function arguments)

---

## Verdict

**Lint baseline: ACCEPTABLE** ✅

- 7 errors total (all unused arguments, not critical)
- No syntax errors
- No import errors
- No security issues from linter
- No dead code from linter (ARG only flags unused params, not unused functions)

**Action before implementation:** Fix these 7 lint errors (2h effort)

**Recommended:**
```bash
ruff check src/ast_tools/ --fix
```

---

*Baseline saved. Will re-run lint after implementation to ensure no new violations.*