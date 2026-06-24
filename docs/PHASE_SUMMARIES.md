# ast-tools — Phase Summaries (0-5)

**Refactoring Complete:** 2026-07-23  
**Total Commits:** 6  
**Tests:** 114 passing  
**Server Reduction:** 1,348 → 445 lines (-67%)

---

## Phase 0 — Initial State

**Commit:** 826a0fa  
**Status:** Monolithic server, all tools in one file

**Before:**
- `src/ast_tools_server.py`: 1,348 lines
- All 11 tool implementations inline
- No package structure
- No tests

**Goal:** Extract tools into modular package structure.

---

## Phase 1 — Extract Core Trio (ast_grep, ast_edit, ast_read)

**Commit:** 445d64f  
**Date:** 2026-07-23

**Extracted:**
- `src/ast_tools/tools/ast_grep.py` — Structural search (ast-grep CLI)
- `src/ast_tools/tools/ast_edit.py` — Surgical edits (libcst)
- `src/ast_tools/tools/ast_read.py` — API surface extraction
- `src/ast_tools/tools/__init__.py` — Registry system

**Changes:**
- Created `TOOL_REGISTRY` dict + `register_tool()` decorator
- Server imports from new locations
- Updated test imports

**Result:** 3 tools extracted, registry pattern established.

---

## Phase 2 — Extract structural_analysis

**Commit:** 884c16b  
**Date:** 2026-07-23

**Extracted:**
- `src/ast_tools/tools/structural_analysis.py` — Call graphs, type hierarchies, refs, deps

**Dependencies:**
- Created `src/ast_tools/utils/file_utils.py` — `find_python_files`, `is_test_file`, `file_to_module`, `filter_top_level`
- Uses `jedi` for semantic analysis

**Gotcha:** Missing `_find_python_files` helper — added wrapper function.

**Tests:** All passing after fix.

---

## Phase 3 — Extract impact_analysis + find_references

**Commit:** 09ed96b  
**Date:** 2026-07-23

**Extracted:**
- `src/ast_tools/tools/find_references.py` — Cross-file symbol usage
- `src/ast_tools/tools/impact_analysis.py` — Change impact + risk assessment

**Dependencies:**
- Created `src/ast_tools/utils/impact.py` — `build_reverse_deps`, `get_transitive_deps`, `classify_risk`

**Pattern Established:**
- Extract tool → create utils → fix tests → commit

**Tests:** 114 total, all passing.

---

## Phase 4 — Extract module_imports

**Commit:** ee53c43  
**Date:** 2026-07-23

**Extracted:**
- `src/ast_tools/tools/module_imports.py` — Fan-in/fan-out import analysis

**Features:**
- Parses Python files with `ast` module
- Builds import graph
- Detects circular dependencies
- Returns detailed import lines with file/line context

**Tests:** Added to `test_project_tools.py`.

---

## Phase 5 — Server Cleanup + Integration

**Commit:** a45d137 (HEAD)  
**Date:** 2026-07-23

**Completed:**
- Removed 586 lines of duplicate tool handlers from server
- Server now ONLY contains:
  - Tool schema definitions (11 tools)
  - Dispatcher (`call_tool()` function)
- Removed unused imports: `ast`, `libcst`, `os`, `subprocess`, `pathlib`
- Fixed all test imports to use `ast_tools.tools.*`
- Cleaned up trailing comments

**Final Server:** 445 lines (was 1,348)

**Net Diff:**
- Lines added: 30
- Lines removed: 939
- Net: -909 lines (-67%)

**Tests:** 114/114 passing ✅

---

## Summary Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Server lines | 1,348 | 445 | -67% |
| Tool files | 1 (monolith) | 13 (modular) | +12 |
| Test files | 0 | 4 | +4 |
| Tests | 0 | 114 | +114 |
| Utils | 0 | 2 | +2 |
| Commits | 1 | 6 | +5 |

---

## Lessons Learned

### What Worked

1. **Incremental extraction** — One tool at a time, test after each
2. **Registry pattern** — Clean separation, easy to extend
3. **Test-driven** — Caught issues immediately
4. **Shared utils** — No duplication

### Pitfalls

1. **Circular imports** — Map before extracting
2. **Missing helpers** — Check dependencies first
3. **Test imports** — Update as you go
4. **Unused imports** — Clean up at end
5. **Hermes `patch` tool** — Requires `path=`, not `file=`

### Established Pattern

```
1. Identify tool boundary
2. Check dependencies (helpers, utils)
3. Create new file in src/ast_tools/tools/
4. Implement with @register_tool()
5. Update server (remove old, import new)
6. Fix test imports
7. Run pytest — all must pass
8. Commit
```

---

**End of Phase Summaries**