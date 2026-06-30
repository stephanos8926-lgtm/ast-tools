# ast-tools — Refactoring Journal

**Lessons Learned, Gotchas, and Patterns Discovered**

---

## The Extract-to-Subpackage Pattern

**Established through 5 phases, 11 tools, 6 commits**

### Steps (in order — do not skip)

1. **Pre-flight dependency analysis**
   ```bash
   grep -rn "from ast_tools.* import" src/ | grep -v __pycache__
   ```
   Map ALL imports TO and FROM the target. Prevents circular import surprises.

2. **Identify split boundaries**
   Group code by responsibility. Each group becomes a submodule. Shared utilities → `utils/`.

3. **Create subpackage directory**
   ```bash
   mkdir -p src/ast_tools/tools/
   mkdir -p src/ast_tools/utils/
   ```
   Add `__init__.py` with registry.

4. **Extract each submodule**
   Write completely and correctly the FIRST time. Preserve all comments, docstrings, type hints. Remove dead code.

5. **Create registry**
   ```python
   # src/ast_tools/tools/__init__.py
   TOOL_REGISTRY: dict[str, Callable] = {}

   def register_tool(name: str):
       def decorator(func: Callable) -> Callable:
           TOOL_REGISTRY[name] = func
           return func
       return decorator
   ```

6. **Update server**
   Remove old code. Import from new location:
   ```python
   from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names
   ```

7. **Fix test imports**
   ```python
   # Before
   from ast_tools_server import _tool_structural_analysis

   # After
   from ast_tools.tools.structural_analysis import _tool_structural_analysis
   ```

8. **Run tests after EVERY extraction**
   Not at the end. One extraction = one test run = one commit.

9. **Commit independently**
   ```bash
   git commit -m "refactor: extract X from server into tools/X.py"
   ```

---

## Critical Lessons Learned

### Lesson 1: Circular Imports are the #1 Enemy

**Problem:** Module A imports from B, B imports from A → `ImportError`.

**Solution:**
- Map the dependency graph BEFORE extracting
- Create shared base module → both import from base
- Use local imports inside function bodies (not module-level)
- Remove imports from `__init__.py` if they cause cycles

**Example from Phase 2:**
```python
# BAD: Circular
# utils/file_utils.py imports tools.ast_grep
# tools.ast_grep imports utils.file_utils

# GOOD: Shared base
# utils/file_utils.py — no imports from tools/
# tools/ast_grep.py — imports utils.file_utils
```

### Lesson 2: Check What Helpers the Tool Uses

**Problem:** Extracted tool calls `_find_python_files()` → `NameError`.

**Solution:** Before extracting, grep for helper function calls:
```bash
grep "^def _" src/ast_tools_server.py
grep "_find_python_files" src/ast_tools_server.py
```

Move helpers to `utils/` or create wrapper functions.

**Example from Phase 2:**
```python
# In structural_analysis.py
from ast_tools.utils.file_utils import find_python_files

def _find_python_files(project_root: str, max_files: int | None = None) -> list[Path]:
    """Wrapper to avoid NameError."""
    return find_python_files(project_root, max_files)
```

### Lesson 3: Test Imports Break Silently

**Problem:** Test imports from old location (`ast_tools_server`) → `ImportError`.

**Solution:** Fix test imports IMMEDIATELY after extraction. Don't batch.

**Example from Phase 5:**
```python
# Before (10 occurrences in test_project_tools.py)
from ast_tools_server import _tool_impact_analysis

# After
from ast_tools.tools.impact_analysis import _tool_impact_analysis
```

**Fix all at once:**
```python
content = content.replace(
    "from ast_tools_server import _tool_impact_analysis",
    "from ast_tools.tools.impact_analysis import _tool_impact_analysis"
)
```

### Lesson 4: Remove Unused Imports at the End

**Problem:** Server file had `import ast`, `import libcst`, etc. — no longer used after extraction.

**Solution:** After all extractions, audit server imports:
```python
# KEPT (actually used)
import json
import logging
import sys
from typing import Any
import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names

# REMOVED (no longer used)
import ast          # → in tools now
import os           # → in tools now
import subprocess   # → in tools now
from pathlib import Path  # → in tools now
import libcst as cst  # → in tools now
```

### Lesson 5: `patch` Tool Requires `path=` not `file=`

**Problem:** Hermes `patch` tool failed silently with "path required" error.

**Solution:** Always use:
```python
patch(path="file.py", old_string="...", new_string="...")
```

NOT:
```python
patch(file="file.py", old_string="...", new_string="...")  # FAILS
```

**This cost 7 consecutive failures in session 2026-07-20.**

---

## Anti-Patterns (Never Do These)

1. **Extract without checking imports first** → Circular imports waste 3+ tool calls
2. **Create tools without registry** → Can't dispatch dynamically
3. **Run 5 extractions before testing** → Debug 5 failures simultaneously
4. **Leave compat shims that don't re-export everything** → Tests break silently
5. **Assume other agent's stashed changes are safe** → Check `git status` first
6. **Manually rearrange imports for I001** → Use `ruff --select I001 --fix`
7. **Batch test import fixes** → Fix as you extract, not at the end

---

## Tool Selection Table

| Task | ✅ Use | ❌ Not This |
|------|--------|-------------|
| Find all functions matching pattern | `ast_grep` | `search_files` (regex) |
| Get file's API surface | `ast_read` | `read_file` (line-by-line) |
| Rename Python function/class | `ast_edit` | `patch` / `sed` / `awk` |
| Find callers/callees of symbol | `structural_analysis` | `grep` |
| What breaks if I change X | `impact_analysis` | Manual tracing |
| Cross-file symbol references | `find_references` | `grep` |
| Module imports (fan-in/fan-out) | `module_imports` | `grep` + manual |
| Project overview (<500 tokens) | `codebase_summary` | Reading every entry point |
| Edit non-Python (JSON, YAML) | `patch` or `write_file` | `ast_edit` |
| Edit Python (syntax-safe) | `ast_edit` | `patch` / `sed` / `awk` |
| General text search in files | `search_files` | `ast_grep` (overkill) |

---

## Performance Notes

- **ast_grep:** Fast (CLI, compiled), uses ast-grep binary
- **ast_edit:** Moderate (libcst parsing), thread-pooled with `anyio.to_thread.run_sync`
- **structural_analysis:** Slow (jedi semantic analysis), thread-pooled
- **impact_analysis:** Moderate (AST parsing + graph traversal), thread-pooled
- **project_info:** Slow (scans entire project), cached via project.json

**All tools run in threads** to avoid blocking async event loop.

---

## Testing Strategy

### Test Categories

1. **E2E Tests** (`test_e2e.py`)
   - Tool functionality with temp projects
   - CLI commands
   - MCP server protocol

2. **Polish Tests** (`test_phase3_polish.py`)
   - Error codes (NOT_FOUND, SYNTAX_ERROR, etc.)
   - CLI help/version flags
   - `__all__` filtering

3. **Project Tests** (`test_project_tools.py`)
   - Framework detection (pytest, unittest)
   - Entry point detection
   - Language detection
   - Dependency graph
   - Impact analysis
   - Find references

### Test Fixture

```python
@pytest.fixture
def test_project(tmp_path):
    """Create a test project and return its path."""
    return create_test_project(str(tmp_path))
```

`create_test_project()` from `conftest.py` creates:
- `src/core/agent.py`
- `src/core/worker.py`
- `src/api/handlers.py`
- `tests/test_agent.py`

### Running Tests

```bash
# All tests (fast, ~5-10s)
python3 -m pytest

# Verbose
python3 -m pytest -v

# Specific file
python3 -m pytest tests/test_e2e.py -v

# Specific test
python3 -m pytest tests/test_e2e.py::TestAstGrep::test_grep_function_definitions -v

# Coverage
python3 -m pytest --cov=ast_tools --cov-report=html
```

---

## Git Hygiene

### Commit Messages

```
refactor: Phase 1 — extract ast_grep, ast_edit, ast_read
refactor: Phase 2 — extract structural_analysis
refactor: Phase 3 — extract impact_analysis + find_references
refactor: Phase 4 — extract module_imports
refactor: Phase 5 — server cleanup and integration
```

### Branch Strategy

- Work on `master` (fast iterations, tests always passing)
- One commit per phase
- No feature branches (refactoring is linear)

### Pre-Commit Checklist

```bash
# Check for uncommitted changes
git status

# Run tests
python3 -m pytest

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Stage + commit
git add -A
git commit -m "refactor: ..."
```

---

## Future Enhancements

### Short-Term

1. **TypeScript backend** — Integrate `ts_backend.py` (Tree-sitter, already exists)
2. **Documentation** — Auto-generate from tool docstrings
3. **Caching** — Cache AST parses for large projects
4. **Incremental analysis** — Only re-analyze changed files

### Long-Term

1. **More languages** — Kotlin, Swift, Ruby via ast-grep
2. **Performance** — Profile slow tools, optimize
3. **Remote server** — Deploy as HTTP endpoint
4. **Plugin system** — Allow custom tools

---

## Contact / Ownership

**Project:** ast-tools  
**Owner:** Steven Albert Page, RapidWebs Enterprise, LLC  
**Location:** `~/Workspaces/ast-tools/`  
**Status:** Production-ready (2026-07-23)

---

**End of Journal**