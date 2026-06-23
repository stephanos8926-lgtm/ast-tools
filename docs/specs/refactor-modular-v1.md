# AST-Tools Refactoring Spec — Modular Architecture

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Refactor monolithic `ast_tools_server.py` (1900+ lines, 11 tools) into a modular package structure with separated concerns.

**Architecture:** Professional Python package with src layout, one tool per module, shared utilities extracted.

**Tech Stack:** Python 3.13+, libcst, pytest, ruff, MCP SDK.

---

## Problem Statement

The current `ast_tools_server.py` is 1900+ lines with:
- Tool definitions mixed with handlers
- 11 tools in a single file
- No separation between MCP protocol and business logic
- Hard to test individual tools in isolation
- Interface extractor added as separate module (good pattern to continue)

## Goals

1. **One tool per module** — Each MCP tool lives in its own file under `src/ast_tools/tools/`
2. **Clean separation of concerns** — Server setup, tool registration, tool logic, utilities
3. **Professional package structure** — src layout, proper `__init__.py`, testable modules
4. **Backward compatibility** — All existing tests must pass unchanged
5. **Enable indexer addition** — Structure must accommodate semantic codebase database feature

## Compatibility Rules

- All existing tool signatures must remain unchanged
- All existing tests must pass without modification
- MCP tool names must not change (backward compatible with clients)
- Server entry point (`python -m ast_tools_server`) must work identically

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/__init__.py` | Create | Package root, exports server + tools |
| `src/ast_tools/server.py` | Create | MCP server setup, tool registration only |
| `src/ast_tools/tools/__init__.py` | Create | Tool package, re-exports all tools |
| `src/ast_tools/tools/ast_grep.py` | Create | Structural search tool |
| `src/ast_tools/tools/ast_edit.py` | Create | AST-based editing tool |
| `src/ast_tools/tools/ast_read.py` | Create | Structural context extraction |
| `src/ast_tools/tools/ast_generate_stub.py` | Create | Stub generation tool |
| `src/ast_tools/tools/ast_refactor_extract_interface.py` | Create | Interface extraction (move from interface_extractor.py) |
| `src/ast_tools/tools/structural_analysis.py` | Create | Call graphs, type hierarchies |
| `src/ast_tools/tools/project_info.py` | Create | Project manifest generation |
| `src/ast_tools/tools/codebase_summary.py` | Create | Architecture overview |
| `src/ast_tools/tools/find_references.py` | Create | Cross-file symbol search |
| `src/ast_tools/tools/impact_analysis.py` | Create | Change impact analysis |
| `src/ast_tools/tools/module_imports.py` | Create | Import graph analysis |
| `src/ast_tools/utils/__init__.py` | Create | Utilities package |
| `src/ast_tools/utils/annotations.py` | Create | AST annotation helpers, function signatures |
| `src/ast_tools/utils/cache.py` | Create | Content-hash caching (prep for semantic DB) |
| `src/ast_tools_server.py` | Keep | Entry point shim for backward compat |
| `tests/test_e2e.py` | Modify | Update imports to new structure |
| `tests/test_tools/` | Create | Per-tool test directory |

## Acceptance Criteria

- [ ] All 114 existing tests pass
- [ ] No test file modifications needed (backward compatible imports)
- [ ] Server starts identically: `python -m ast_tools_server`
- [ ] Each tool module independently testable
- [ ] Lint passes (ruff + pyright)
- [ ] Package installable: `pip install -e .`
- [ ] Entry point works: `python -c "from ast_tools import server"`

---

## Implementation Order

**Sequential phases** (shared files, dependencies):

1. **Phase 1**: Package structure + extract utils
2. **Phase 2**: Extract simple tools (codebase_summary, project_info)
3. **Phase 3**: Extract core tools (ast_read, ast_edit, ast_grep)
4. **Phase 4**: Extract remaining tools
5. **Phase 5**: Server refactor + tests

**Parallel dispatch pattern:** Within each phase, tools that don't share files can be extracted simultaneously.