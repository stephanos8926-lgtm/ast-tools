# Phase 10A: repo_skeleton + file_related_suggest — Implementation Plan

**Goal:** Implement 2 new MCP tools for ast-tools structural code intelligence.

**Status:** Archived specs exist in `docs/archive/PHASE10A_SPEC.md` (detailed) and `docs/archive/PHASE10A_PLAN.md` (task breakdown). `code_validate_syntax` already done.

**Both tools are independent** — different files, no shared dependencies → **parallel dispatch**.

---

## Tool 1: `repo_skeleton`

**Objective:** Intelligent project skeleton with type detection, key file identification, dependency graph, ASCII tree.

**Files:**
- Create: `src/ast_tools/tools/repo_skeleton.py` (~250 lines)
- Create: `tests/tools/test_repo_skeleton.py` (~150 lines)
- Modify: `src/ast_tools/tools/__init__.py` (register + schema)

**Interface:**
```python
_tool_repo_skeleton({
    "root_path": str,        # Required
    "max_depth": 5,          # Optional
    "include_tests": True,   # Optional
    "include_configs": True, # Optional
    "generate_deps": True    # Optional
}) -> {
    "project_type": str,
    "confidence": float,
    "detected_indicators": [str],
    "structure": {...},
    "dependencies": {...},
    "tree_ascii": str,
    "summary": str
}
```

**Key patterns (follow code_validate.py style):**
- `_tool_repo_skeleton(params: dict[str, Any]) -> dict[str, Any]`
- `register_tool("repo_skeleton", _tool_repo_skeleton, {inputSchema: ...})`
- No new dependencies (reuse Path, json, etc.)
- Graceful degradation for unknown project types

**Project type detection** (scoring-based):
| Type | Indicators | Weight |
|------|-----------|--------|
| python | pyproject.toml(3), setup.py(2), *.py(1), src/(2) | max ~8 |
| node | package.json(3), *.js(1), *.ts(1) | max ~5 |
| go | go.mod(3), *.go(1) | max ~4 |
| rust | Cargo.toml(3), *.rs(1) | max ~4 |

Confidence = min(1.0, score / 5.0)

**ASCII tree:** Recursive directory scan, max_depth, skip hidden, box-drawing chars.

---

## Tool 2: `file_related_suggest`

**Objective:** Smart related file suggestions via AST import analysis + test patterns + call graph.

**Files:**
- Create: `src/ast_tools/tools/file_related.py` (~180 lines)
- Create: `tests/tools/test_file_related.py` (~120 lines)
- Modify: `src/ast_tools/tools/__init__.py` (register + schema)

**Interface:**
```python
_tool_file_related_suggest({
    "file_path": str,              # Required
    "workspace": str,              # Optional (git root or cwd)
    "max_suggestions": 5,          # Optional
    "include_tests": True,         # Optional
    "include_imports": True        # Optional
}) -> {
    "file": str,
    "suggestions": [{
        "path": str,
        "reason": str,         # test_file | imported_by | imports_this | sibling | call_graph | name_match
        "confidence": float,
        "explanation": str
    }]
}
```

**Suggestion strategies (priority order):**
1. **Test files** — `test_<stem>.py`, `<stem>_test.py`, `tests/test_<stem>.py`
2. **Imported by** — what imports FROM this file (fan-in via grep import analysis)
3. **Imports this** — what this file imports (fan-out)
4. **Same-directory siblings** — similar-named .py files
5. **Name matching** — same stem across project dirs
6. **Call graph** — if structural_analysis tool available, use caller/callee info

---

## Registration (both tools)

In `src/ast_tools/tools/__init__.py`, add to imports section:
```python
from .repo_skeleton import _tool_repo_skeleton
from .file_related import _tool_file_related_suggest
```

And register with schemas matching the existing pattern.

---

## Execution Order

1. Dispatch **parallel subagents** for Tool 1 and Tool 2
2. Each follows TDD: write failing test → implement → verify → register
3. After both complete: full test suite, lint check, commit
