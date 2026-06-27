# ast-tools — Project State & Summary

**Last Updated:** 2026-07-23  
**Status:** ✅ **COMPLETE** — All 5 phases done, 114 tests passing

---

## Executive Summary

**ast-tools** is a fully modularized MCP server providing 11 structural code analysis and editing tools for Python, JavaScript, TypeScript, Rust, Go, Java, C, and C++.

**Key Achievement:** Successfully extracted all tool implementations from a monolithic 1,348-line server file into a clean, maintainable package structure. Server reduced to 445 lines (67% reduction) — now just tool definitions + dispatcher.

---

## Project Structure

```
ast-tools/
├── src/
│   ├── ast_tools_server.py          # MCP server (445 lines) — thin wrapper
│   ├── ast_tools/
│   │   ├── tools/                   # Tool implementations (11 tools)
│   │   │   ├── __init__.py          # Registry + helpers
│   │   │   ├── ast_grep.py          # Structural search (ast-grep CLI)
│   │   │   ├── ast_edit.py          # Surgical edits (libcst)
│   │   │   ├── ast_read.py          # API surface extraction
│   │   │   ├── structural_analysis.py  # Call graphs, refs, deps (jedi)
│   │   │   ├── find_references.py   # Cross-file symbol usage
│   │   │   ├── impact_analysis.py   # Change impact + risk assessment
│   │   │   ├── module_imports.py    # Fan-in/fan-out import analysis
│   │   │   ├── ast_generate_stub.py # .pyi stub generation
│   │   │   ├── ast_refactor_extract_interface.py  # ABC/Protocol extraction
│   │   │   ├── project_info.py      # Project manifest (project.json)
│   │   │   └── codebase_summary.py  # Architecture overview (<500 tokens)
│   │   └── utils/
│   │       ├── file_utils.py        # find_python_files, is_test_file, etc.
│   │       └── impact.py            # build_reverse_deps, classify_risk
│   └── project_tools.py             # Project intelligence CLI (1,038 lines)
├── tests/
│   ├── conftest.py                  # Test fixtures (create_test_project)
│   ├── test_e2e.py                  # E2E tests for core tools
│   ├── test_phase3_polish.py        # Error codes, CLI polish tests
│   └── test_project_tools.py        # Project info/impact analysis tests
├── docs/
│   ├── PHASE_SUMMARIES.md           # Phase 0-5 completion reports
│   └── REFACTORING_JOURNAL.md       # Less-learned, gotchas
├── pyproject.toml                   # Build config, deps, entry points
└── pytest.ini                       # Test config
```

---

## Tool Registry (11 Tools)

| Tool | Purpose | Implementation |
|------|---------|----------------|
| `ast_grep` | Structural code search via AST patterns | `src/ast_tools/tools/ast_grep.py` |
| `ast_edit` | Surgical AST-based edits (libcst) | `src/ast_tools/tools/ast_edit.py` |
| `ast_read` | Extract API surface from files | `src/ast_tools/tools/ast_read.py` |
| `ast_generate_stub` | Generate .pyi type stubs | `src/ast_tools/tools/ast_generate_stub.py` |
| `ast_refactor_extract_interface` | Extract ABC/Protocol from class | `src/ast_tools/tools/ast_refactor_extract_interface.py` |
| `structural_analysis` | Call graphs, type hierarchies, refs, deps | `src/ast_tools/tools/structural_analysis.py` |
| `project_info` | Project manifest (project.json) | `src/ast_tools/tools/project_info.py` |
| `codebase_summary` | High-level architecture overview | `src/ast_tools/tools/codebase_summary.py` |
| `find_references` | Find all symbol usages across codebase | `src/ast_tools/tools/find_references.py` |
| `impact_analysis` | Change impact + risk assessment | `src/ast_tools/tools/impact_analysis.py` |
| `module_imports` | Module-level fan-in/fan-out import analysis | `src/ast_tools/tools/module_imports.py` |

---

## Test Coverage

**114 tests** across 4 test files:
- `test_e2e.py`: 32 tests (E2E tool + CLI tests)
- `test_phase3_polish.py`: 17 tests (error codes, CLI polish, `__all__` filtering)
- `test_project_tools.py`: 65 tests (project info, impact analysis, framework detection)

**All tests passing ✅**

Run with: `python3 -m pytest`

---

## Git History (6 Commits)

```
a45d137 (HEAD → master) refactor: Phase 5 complete — server cleanup and integration
ee53c43 refactor: Phase 4 — extract module_imports tool
09ed96b refactor: Phase 3 — extract impact_analysis + find_references
884c16b refactor: Phase 2 — extract structural_analysis
445d64f refactor: Phase 1 — extract ast_grep, ast_edit, ast_read
826a0fa Initial: Monolithic server (1,348 lines)
```

**Diff stats:**
- **Lines added:** 30
- **Lines removed:** 939
- **Net change:** -909 lines (67% reduction in server file)

---

## Architecture

### Design Principles

1. **Registry Pattern** — Tools register themselves in `TOOL_REGISTRY` dict
2. **Thin Server** — Server only defines tool schemas + dispatches to handlers
3. **Extracted Tools** — All tool logic in `src/ast_tools/tools/`
4. **Shared Utils** — Common helpers in `src/ast_tools/utils/`
5. **Test Isolation** — Each test creates isolated temp projects

### Tool Registration

```python
# src/ast_tools/tools/__init__.py
TOOL_REGISTRY: dict[str, Callable] = {}

def register_tool(name: str):
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = func
        return func
    return decorator
```

Each tool file uses `@register_tool("tool_name")` decorator.

### Server Dispatcher

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name not in TOOL_REGISTRY:
        return error_response("NOT_FOUND", available_tools=list_tool_names())
    
    handler = get_tool_handler(name)
    result = await anyio.to_thread.run_sync(handler, arguments)
    return success_response(result)
```

---

## Development Workflow

### Adding a New Tool

1. Create `src/ast_tools/tools/new_tool.py`
2. Implement handler function with `@register_tool("new_tool")`
3. Add tool schema to `server.list_tools()` in `ast_tools_server.py`
4. Write tests in `tests/test_new_tool.py`
5. Run `python3 -m pytest` — all tests must pass

### Running Tests

```bash
# All tests
python3 -m pytest

# Specific test file
python3 -m pytest tests/test_e2e.py -v

# Specific test
python3 -m pytest tests/test_e2e.py::TestAstGrep::test_grep_function_definitions -v
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

---

## Key Lessons Learned

### What Went Well

1. **Incremental Extraction** — One tool at a time, test after each
2. **Registry Pattern** — Clean separation of concerns
3. **Test-Driven** — 114 tests caught issues immediately
4. **Shared Utils** — No code duplication across tools

### Gotchas / Pitfalls

1. **Circular Imports** — Map imports BEFORE extracting. Use local imports inside functions if needed.
2. **Missing Helper Functions** — When extracting, check what helpers the tool uses. Move or re-export them.
3. **Test Imports** — Tests importing from old locations need updating. Fix as you go.
4. **Unused Imports** — Server file accumulates unused imports. Clean up at the end.
5. **`patch` tool requires `path=` not `file=`** — Hermest tool quirk

### Refactoring Pattern (Established)

1. **Identify tool boundary** — What code belongs to this tool?
2. **Check dependencies** — What helpers/utils does it need?
3. **Create new file** — `src/ast_tools/tools/tool_name.py`
4. **Copy + register** — Implement with `@register_tool()`
5. **Update server** — Remove old code, import from new location
6. **Fix tests** — Update test imports
7. **Run tests** — Verify all pass
8. **Commit** — One extraction = one commit

---

## Next Steps / Future Work

### Potential Enhancements

1. **TypeScript/JavaScript Support** — Tree-sitter backend already exists (`ts_backend.py`), needs integration
2. **More Languages** — Kotlin, Swift, Ruby support via ast-grep
3. **Caching** — Cache AST parses for large projects
4. **Incremental Analysis** — Only re-analyze changed files
5. **Performance Profiling** — Identify slow tools, optimize

### Known Issues

- **Pyright errors** in tool files (pre-existing, not blocking)
- **jedi import** could not be resolved (environment issue, not code issue)
- **libcst import** — removed from server, but pyright still flags it

---

## Usage (MCP Client)

### Configure in Hermes

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  ast-tools:
    command: ["python3", "-m", "ast_tools_server"]
    cwd: "/home/sysop/Workspaces/ast-tools"
```

### Example Tool Calls

```python
# Structural search
mcp_ast_tools_ast_grep(pattern="def $FUNC($$$ARGS)", path="src/", lang="python")

# Extract API surface
mcp_ast_tools_ast_read(file="src/core/agent.py", include_private=True)

# Find all usages of a symbol
mcp_ast_tools_find_references(symbol="process_task", cwd="/path/to/project")

# Analyze change impact
mcp_ast_tools_impact_analysis(target="src/core/worker.py")
```

---

## Contact / Ownership

**Project:** ast-tools (formerly ast-mcp)  
**Owner:** Steven Albert Page, RapidWebs Enterprise, LLC  
**Location:** `~/Workspaces/ast-tools/`  
**Status:** Active development, production-ready

---

## Quick Reference

```bash
# Enter project
cd ~/Workspaces/ast-tools

# Run all tests
python3 -m pytest

# Run server manually (for debugging)
python3 src/ast_tools_server.py

# Check git status
git status

# View recent commits
git log --oneline -10
```

---

**End of Summary**