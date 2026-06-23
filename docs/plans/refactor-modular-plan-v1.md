# AST-Tools Modular Refactoring — Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task.

**Goal:** Refactor monolithic `ast_tools_server.py` (1914 lines) into modular package structure.

**Architecture:** Professional Python package with src layout, one tool per module, shared utilities.

**Tech Stack:** Python 3.13+, libcst, pytest, ruff, MCP SDK.

**Corrections from Forward Audit:**
- ✅ src/ directory already exists (no need to create)
- ⚠️ ast-grep CLI must be installed before Phase 3
- ⚠️ Import paths need `PYTHONPATH=src` or package restructuring
- 🔍 15+ helper functions identified for extraction (not just annotations)

---

## Phase 0: Prerequisites

### Task 0.1: Install ast-grep CLI

**Objective:** Install ast-grep CLI required for the ast_grep tool (Phase 3).

**Step 1: Install via cargo (recommended)**
```bash
cargo install ast-grep-cli
# OR via pip if available
pip install ast-grep
```

**Step 2: Verify installation**
```bash
which ast-grep
ast-grep --version
```

**Step 3: Commit**
```bash
git add -A && git commit -m "chore: install ast-grep CLI dependency"
```

---

## Phase 1: Package Structure + Extract Utils

**Objective:** Create the new package structure and extract shared utilities.

### Task 1.1: Create Package Directories

**Files:**
- Create: `src/ast_tools/__init__.py`
- Create: `src/ast_tools/server.py`
- Create: `src/ast_tools/tools/__init__.py`
- Create: `src/ast_tools/utils/__init__.py`

**Step 1: Create directories**
```bash
cd ~/Workspaces/ast-tools
mkdir -p src/ast_tools/tools src/ast_tools/utils
```

**Step 2: Create `src/ast_tools/__init__.py`**
```python
"""AST-Tools MCP Server — structural code analysis and editing."""

from .server import create_server, list_tools, call_tool

__all__ = ["create_server", "list_tools", "call_tool"]
```

**Step 3: Create `src/ast_tools/server.py`** (skeleton — tools imported later)
```python
"""MCP server setup and tool registration."""

from mcp.server import Server

def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("ast-tools")
    
    @server.list_tools()
    async def list_tools():
        from .tools import get_all_tools
        return await get_all_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        from .tools import get_tool_handler
        handler = get_tool_handler(name)
        return await handler(name, arguments)
    
    return server
```

**Step 4: Create `src/ast_tools/tools/__init__.py`** (skeleton — tools added in Phase 2+)
```python
"""AST-Tools: Individual tool implementations."""

from typing import Any

TOOL_REGISTRY: dict[str, callable] = {}

def register_tool(name: str, handler: callable):
    """Register a tool handler."""
    TOOL_REGISTRY[name] = handler

async def get_all_tools():
    """Return list of all registered tools."""
    from mcp.types import Tool
    # Tools will be populated as modules are imported
    return []

def get_tool_handler(name: str) -> callable:
    """Get handler for a tool by name."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]
```

**Step 5: Create `src/ast_tools/utils/__init__.py`**
```python
"""AST-Tools: Shared utilities."""
```

**Step 6: Verify package structure**
```bash
python3 -c "from ast_tools import server; print('OK')"
```

**Step 7: Commit**
```bash
git add -A && git commit -m "refactor: create modular package structure"
```

---

### Task 1.2: Extract Annotation Utilities

**Objective:** Move AST annotation helpers to `src/ast_tools/utils/annotations.py`.

**Files:**
- Create: `src/ast_tools/utils/annotations.py`

**Step 1: Find annotation-related code in ast_tools_server.py**
```bash
cd ~/Workspaces/ast-tools
grep -n "def.*signature\|def.*annotation\|libcst.*ann" src/ast_tools_server.py | head -20
```

**Step 2: Extract to `src/ast_tools/utils/annotations.py`**
(Full implementation — copy exact code from server.py lines containing annotation helpers)

**Step 3: Update server.py import**
```python
from .utils.annotations import function_signature, class_signature
```

**Step 4: Verify**
```bash
python3 -m pytest tests/test_e2e.py::TestMCPServer::test_list_tools -v
```

**Step 5: Commit**
```bash
git add -A && git commit -m "refactor: extract annotation utilities"
```

---

### Task 1.3: Extract Cache Utilities (Prep for Semantic DB)

**Objective:** Create content-hash caching utilities in `src/ast_tools/utils/cache.py`.

**Files:**
- Create: `src/ast_tools/utils/cache.py`

**Code:**
```python
"""Content-hash based caching for AST analysis."""

import hashlib
from pathlib import Path
from typing import Any, Optional

class FileCache:
    """Cache file contents with hash-based invalidation (Serena pattern)."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "ast-tools"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[str, Any]] = {}  # path -> (hash, data)
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_or_compute(self, file_path: str, compute_fn: callable) -> Any:
        """Get cached result or compute and cache it."""
        path = Path(file_path)
        if not path.exists():
            return None
        
        content = path.read_text()
        content_hash = self._compute_hash(content)
        
        if file_path in self._cache:
            cached_hash, cached_data = self._cache[file_path]
            if cached_hash == content_hash:
                return cached_data
        
        # Compute and cache
        data = compute_fn(content)
        self._cache[file_path] = (content_hash, data)
        return data
    
    def invalidate(self, file_path: str):
        """Invalidate cache for a file."""
        if file_path in self._cache:
            del self._cache[file_path]
    
    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
```

**Step 2: Wire into server.py**
```python
from .utils.cache import FileCache
_global_cache = FileCache()
```

**Step 3: Commit**
```bash
git add -A && git commit -m "feat: add content-hash cache utilities"
```

---

## Phase 2: Extract Simple Tools

**Objective:** Extract standalone tools that don't depend on complex shared state.

### Task 2.1: Extract `codebase_summary` Tool

**Files:**
- Create: `src/ast_tools/tools/codebase_summary.py`
- Modify: `src/ast_tools/tools/__init__.py`

**Step 1: Copy tool code from server.py**
(Find `_tool_codebase_summary` function and copy to new file)

**Step 2: Register in `tools/__init__.py`**
```python
from .codebase_summary import _tool_codebase_summary as codebase_summary_handler
register_tool("codebase_summary", codebase_summary_handler)
```

**Step 3: Verify**
```bash
python3 -m pytest tests/test_e2e.py::TestMCPServer::test_list_tools -v
```

**Step 4: Commit**
```bash
git commit -am "refactor: extract codebase_summary tool"
```

---

### Task 2.2: Extract `project_info` Tool

(Same pattern as Task 2.1)

---

### Task 2.3: Extract `ast_generate_stub` Tool

(Same pattern — uses annotation utilities from Phase 1)

---

## Phase 3: Extract Core Tools

**Objective:** Extract the heavily-used core tools: `ast_read`, `ast_edit`, `ast_grep`.

### Task 3.1: Extract `ast_read` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_read.py`

**Special handling:**
- Uses `_should_include()` helper (from annotation utils)
- Uses cache utilities
- Register in `tools/__init__.py`

---

### Task 3.2: Extract `ast_edit` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_edit.py`

**Special handling:**
- Uses libcst directly
- No special dependencies

---

### Task 3.3: Extract `ast_grep` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_grep.py`

**Special handling:**
- Calls external `ast-grep` CLI
- Uses terminal for subprocess

---

## Phase 4: Extract Remaining Tools

Extract in parallel where independent:

### Task 4.1: Extract `ast_refactor_extract_interface`
(Move from `interface_extractor.py` to proper module)

### Task 4.2: Extract `structural_analysis`

### Task 4.3: Extract `find_references`

### Task 4.4: Extract `impact_analysis`

### Task 4.5: Extract `module_imports`

---

## Phase 5: Server Refactor + Tests

### Task 5.1: Refactor `ast_tools_server.py` to Entry Point Shim

**Files:**
- Modify: `src/ast_tools_server.py`

**Code:**
```python
#!/usr/bin/env python3
"""AST-Tools MCP Server — entry point shim for backward compatibility."""

from ast_tools.server import create_server

server = create_server()

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    
    asyncio.run(main())
```

### Task 5.2: Update Test Imports

**Files:**
- Modify: `tests/test_e2e.py`

**Change:**
```python
# Before
from ast_tools_server import list_tools

# After
from ast_tools.server import list_tools
```

### Task 5.3: Run Full Test Suite

```bash
cd ~/Workspaces/ast-tools
python3 -m pytest tests/ -x -v --tb=short
```

### Task 5.4: Final Commit

```bash
git add -A && git commit -m "refactor: complete modular extraction (all 11 tools)"
```

---

## Verification Checklist

- [ ] All 114 tests pass
- [ ] No test modifications needed (backward compatible)
- [ ] Server starts: `python -m ast_tools_server`
- [ ] Lint passes: `ruff check src/ tests/`
- [ ] Type check: `pyright src/`
- [ ] Package installable: `pip install -e .`

---

## Rollback Plan

If any phase breaks:
```bash
git revert HEAD  # Undo last phase
# OR
git reset --hard HEAD~1  # Remove last commit entirely
```

Each phase is one commit = clean rollback.