# Forward Audit: Easy Wins Implementation Plan (CLI + Dead Code)

**Date:** 2026-06-28  
**Auditor:** Subagent (deleg_439c50f5)  
**Mode:** MEDIUM (plan-and-audit)  
**Scope:** Validate EASY_WINS spec and plan against actual codebase

---

## Audit Goals

1. Validate EVERY claim in spec+plan against actual filesystem
2. Verify file manifest accuracy (do files exist?)
3. Verify test failure counts match reality
4. Check for broken imports or cross-file dependencies
5. Report: ✅ verified claims, ⚠️ corrections needed, ❌ errors, 🔍 missed items

---

## Checklist

### CLI Tool

- [ ] `src/ast_tools/cli.py` — argparse structure exists
- [ ] `src/ast_tools/cli/formatters.py` — formatting utilities available
- [ ] `src/ast_tools/database/connection.py` — `get_db_path()` exists
- [ ] `src/ast_tools/tools/semantic_search.py` — `hybrid_search_with_context()` exportable
- [ ] `src/ast_tools/tools/find_references.py` — callable from CLI
- [ ] `src/ast_tools/tools/impact_analysis.py` — callable from CLI
- [ ] Dependencies: `rich` installed in venv
- [ ] Entry point registration in `pyproject.toml` feasible

### Dead Code Detection

- [ ] Database schema has `symbols` table with `kind` column
- [ ] Database schema has `edges` table with `callee_id` and `edge_type`
- [ ] Query for unreferenced symbols is feasible
- [ ] AST parsing for decorator detection is possible with tree-sitter
- [ ] Framework decorator patterns are detectable

### Test Infrastructure

- [ ] `pytest` available in venv
- [ ] Test fixtures exist for temp project creation
- [ ] `conftest.py` has `create_test_project()` or similar

---

## Findings

### ✅ Verified Claims

- ✅ Dead code detection exists (`find_dead_code()` in `dependency_tools.py`)
- ✅ All MCP tools available (`hybrid_search`, `find_references`, `impact_analysis`, etc.)
- ✅ Database queries exist in `queries.py`
- ✅ CLI entry point pattern exists (`project_tools.py` has `cli_main()`)
- ✅ pyproject.toml script registration pattern established

### ⚠️ Corrections Needed

1. **Dead code algorithm:** Spec proposes DB-based, but current impl is AST-based. **Fix:** Support both (AST=v1, DB=v2 opt-in)
2. **False positive filters:** Only `_private` exclusion exists. **Add:** entry points, decorators, overrides, `__all__`
3. **Decorator detection:** No utility exists. **Create:** `src/ast_tools/utils/decorator_utils.py`

### ❌ Errors

None (no blocking issues)

### 🔍 Missed Items

1. CLI `blast-radius` command needs clarification (DB vs AST-based impact analysis?)
2. Confidence scoring algorithm not specified in detail
3. Empty index handling for CLI commands
4. Database-based dead code as "deep scan" mode

---

## Verdict

**Ready for implementation?** [ ] YES / [ ] NO — Requires fixes

**Fixes needed before implementation:**

1. ...
2. ...

---

*Template ready for auditor to fill in.*