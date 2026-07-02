# Phase 10.1: Transitive Import Resolution — Implementation Plan

**Goal:** Answer "What breaks if I change X?" with transitive dependency chains computed from live AST data, not stale JSON files.

**Architecture:** Refactor `module_imports.py` to expose a reusable `_build_import_graph()` that produces a clean `{module: [dep1, dep2]}` dict. Use this live graph in a new `transitive_dependents` MCP tool and wire it into `impact_analysis` to replace the brittle JSON file path.

**Files:**
- Modify: `src/ast_tools/tools/module_imports.py` — extract `_build_import_graph()`
- Modify: `src/ast_tools/tools/impact_analysis.py` — use live graph instead of JSON file
- Create: `src/ast_tools/tools/transitive_analysis.py` — new MCP tool for transitive chain
- Modify: `src/ast_tools/tools/__init__.py` — register new tool + schema
- Create: `tests/tools/test_transitive_analysis.py` — tests

---

### Task 1: Extract `_build_import_graph()` from module_imports

**Objective:** Pull the import-graph building logic out of `_tool_module_imports` into a standalone function.

**Files:**
- Modify: `src/ast_tools/tools/module_imports.py:20-196`

**Step 1:** Write failing test verifying `_build_import_graph()` works standalone.

**Step 2:** Extract the graph-building loop from `_tool_module_imports` (lines 112-179 that build fan-in) into a new module-level function `_build_import_graph(root: Path, max_files: int = 500) -> dict[str, set[str]]`.

**Step 3:** Make `_tool_module_imports` call `_build_import_graph()` internally (backward compat).

**Verify:** `pytest tests/tools/test_transitive_analysis.py -v` — test passes.

---

### Task 2: Create `transitive_dependents` MCP tool

**Objective:** New tool that returns full transitive chain with depth levels.

**Files:**
- Create: `src/ast_tools/tools/transitive_analysis.py`
- Modify: `src/ast_tools/tools/__init__.py` — register

**Interface:**
```python
_tool_transitive_dependents(params: dict[str, Any]) -> dict[str, Any]
```

**Input:**
```json
{
  "target": "src/ast_tools/tools/semantic_search.py",
  "direction": "dependents",   // "dependents" or "dependencies"
  "max_depth": 10,
  "cwd": "."
}
```

**Output:**
```json
{
  "target": "src/ast_tools/tools/semantic_search.py",
  "direction": "dependents",
  "direct": ["src/ast_tools/context/injector.py"],
  "transitive": [
    {"depth": 1, "modules": ["src/ast_tools/context/injector.py", ...]},
    {"depth": 2, "modules": ["src/ast_tools/tools/context_tools.py", ...]}
  ],
  "all_affected": ["src/ast_tools/context/injector.py", ...],
  "risk": "medium",
  "fan_out": 2
}
```

**Logic:**
- Build live graph via `_build_import_graph()`
- BFS from target, tracking depth
- Risk: 0 direct → "none", 1-2 → "low", 3-9 → "medium", 10+ → "high"

---

### Task 3: Wire live graph into `impact_analysis`

**Objective:** Replace `dependency_graph.json` reading with live `_build_import_graph()` call.

**Files:**
- Modify: `src/ast_tools/tools/impact_analysis.py:51-96`

**Step 1:** Replace lines 53-69 (JSON file parsing) with live graph built on the fly:
```python
dep_graph = _build_import_graph(root)
reverse_deps = build_reverse_deps(dep_graph)
```

---

### Task 4: Write comprehensive tests

**Test file:** `tests/tools/test_transitive_analysis.py`

**Test classes:**
- `TestImportGraphBuilding` — `_build_import_graph` on real ast-tools code
- `TestTransitiveDependents` — `_tool_transitive_dependents` with live project
- `TestRiskClassification` — verify risk thresholds
- `TestIntegration` — end to end through impacted chain