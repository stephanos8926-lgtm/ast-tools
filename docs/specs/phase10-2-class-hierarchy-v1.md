# Phase 10.2 — Class Hierarchy Analysis

**Goal:** Add an MCP tool that analyzes class hierarchies — parent/child chains, MRO computation, interface detection (ABC/Protocol), and method override tracking.

**Architecture:** Single new tool file `class_hierarchy.py` + test file, following the same pattern as `transitive_analysis.py`.

**Tech Stack:** Python stdlib only (`ast`, `pathlib`, `typing`, `collections`).

---

## Interface Contract

### Input
```python
{
    "target": str,          # Class name or "file:ClassName"
    "file": str,            # Optional — file containing the class
    "workspace": str,       # Optional — project root
    "max_depth": int,       # Default 10
}
```

### Output
```python
{
    "class": str,
    "file": str,
    "bases": ["Base1", "Base2"],       # Direct parents
    "mro": ["Child", "Parent", "object"],  # Full MRO
    "subclasses": ["Sub1", "Sub2"],     # Classes that inherit from this
    "interfaces": ["ABC", "Protocol"],  # ABC/Protocol inheritance
    "methods": {
        "own": ["method_a"],
        "inherited": [{"name": "method_b", "from": "Base1"}],
        "overrides": [{"name": "method_c", "from": "Base1"}]
    },
    "metrics": {
        "depth": 3,
        "num_methods": 5,
        "num_overrides": 1,
        "is_abstract": False,
        "is_final": False,
        "has_concrete_methods": True
    }
}
```

### Tool Name
`class_hierarchy` — registered as `_tool_class_hierarchy`

---

## Implementation

### File: `src/ast_tools/tools/class_hierarchy.py`

Core functions:
1. `_resolve_target(target, file_path, workspace)` — Find the class definition
2. `_extract_classes(file_path)` — Parse file and return all class AST nodes
3. `_compute_mro(class_node, all_classes)` — C3 linearization
4. `_find_methods(node)` — Extract methods from a class node
5. `_detect_interface(bases)` — Check for ABC/Protocol
6. `_find_subclasses(class_name, workspace)` — Scan workspace for classes that inherit from this
7. `_tool_class_hierarchy(params)` — Main handler

Key implementation details:
- Parse files with `ast.parse()`
- Build a name→class_node map for the file first
- For cross-file references, search workspace by scanning Python files
- MRO uses C3 algorithm (same as Python's)
- Track method categories: own (defined in this class), inherited (defined in parent, visible here), overrides (defined in parent, redefined here)

### File: `tests/tools/test_class_hierarchy.py`

Test classes:
- `TestTargetResolution` — Finding class definitions by name/file
- `TestMROResolution` — Computing C3 linearization
- `TestMethodAnalysis` — Own vs inherited vs overridden
- `TestInterfaceDetection` — ABC/Protocol detection
- `TestSubclassDetection` — Finding classes that inherit
- `TestClassHierarchyIntegration` — Full end-to-end on real ast-tools classes (GraphEngine, etc.)

---

## Verification

```bash
pytest tests/tools/test_class_hierarchy.py -v --tb=short
# Expected: ALL PASSING

python3 -c "from ast_tools.tools.class_hierarchy import _tool_class_hierarchy; print('import OK')"
```