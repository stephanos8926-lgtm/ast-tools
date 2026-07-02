# Phase 10.3 — Blast Radius v2

**Goal:** Combine transitive import analysis + class hierarchy + call graph into a unified blast radius MCP tool with confidence scoring and per-axis breakdown.

**Architecture:** New tool file `blast_radius_v2.py` that calls existing functions from `transitive_analysis.py`, `class_hierarchy.py`, and `structural_analysis.py`. Does not duplicate — delegates.

---

## Interface Contract

### Input
```python
{
    "target": str,          # Required — file path, symbol name, or class name
    "cwd": str,             # Optional — project root (default: ".")
    "max_depth": int,       # Optional — traversal depth (default: 5)
    "include_imports": bool,# Optional — include import graph axis (default: True)
    "include_hierarchy": bool, # Optional — include class hierarchy axis (default: True)
    "include_callers": bool,   # Optional — include call graph axis (default: True)
}
```

### Output
```python
{
    "target": "ast_tools.tools.GraphEngine",
    "target_kind": "class",          # "file", "class", "function", "module"
    "target_file": "/abs/path.py",

    "summary": {
        "total_affected": 18,
        "distinct_files": 7,
        "risk": "medium",              # none/low/medium/high/critical
        "confidence": 0.85,            # 0.0-1.0
    },

    "axes": {
        "import_graph": {
            "affected": 8,
            "risk": "medium",
            "confidence": 0.95,
            "details": ["module_a", "module_b", ...],
        },
        "class_hierarchy": {
            "affected": 3,
            "risk": "low",
            "confidence": 0.90,
            "details": ["SubClass1", "SubClass2"],
        },
        "call_graph": {
            "affected": 7,
            "risk": "medium",
            "confidence": 0.75,
            "details": ["function_x in file_y", ...],
        },
    },

    "by_file": [
        {"file": "src/ast_tools/kg/graph_engine.py", "reasons": ["import_graph", "class_hierarchy"]},
    ],

    "recommendations": [
        "Class has 3 subclasses — test each before making changes",
        "Module is imported by 8 files — consider deprecation path",
    ],
}
```

---

## Implementation

### File: `src/ast_tools/tools/blast_radius_v2.py`

#### Functions

1. **`_resolve_target(target, cwd)`** — Determine if target is file, class, function, or module. Returns kind + resolved paths.
2. **`_axis_import_graph(target, cwd, max_depth)`** — Call `_tool_transitive_dependents()` or the underlying `_build_import_graph` BFS. Returns affected list + risk.
3. **`_axis_class_hierarchy(target, file_path, cwd)`** — If target is a class, call class_hierarchy internals. Returns affected subclasses + interface chain.
4. **`_axis_call_graph(target, file_path, cwd)`** — If target is a function/symbol, call `_ast_find_callers` from structural_analysis. Returns affected callers.
5. **`_combine_axes(results)`** — Union of all affected files, aggregate risk scoring, confidence computation.
6. **`_compute_confidence(axis_results)`** — Each axis has inherent confidence: import_graph=0.95 (AST-parsed, reliable), class_hierarchy=0.90 (AST-parsed, cross-file edge cases), call_graph=0.75 (jedi-based, may be incomplete).
7. **`_generate_recommendations(result)`** — Heuristic recommendations based on patterns (e.g., "Class has N subclasses", "Module is imported by N files").
8. **`_tool_blast_radius_v2(params)`** — Main handler, wires everything together.

#### Key implementation rules
- **Delegate, don't duplicate** — import and call existing functions from transitive_analysis, class_hierarchy, structural_analysis
- **Graceful degradation** — if an axis fails (e.g., class_hierarchy for a non-class target), skip it with a note rather than error
- **Deduplicate** — same file appearing via multiple axes should be counted once in `by_file` but the reasons should accumulate
- **Risk scoring**: none(0) < low(1-3) < medium(4-9) < high(10-19) < critical(20+)
- **Aggregate risk** = highest non-zero axis risk, unless all low → medium if 2+ axes active
- **Confidence** = weighted average of axis confidences (weighted by affected count per axis)

### File: `tests/tools/test_blast_radius_v2.py`

Test classes:
- `TestTargetResolution` — file path, class name, function name, symbol
- `TestImportGraphAxis` — mock/reuse transitive analysis
- `TestClassHierarchyAxis` — mock/reuse class hierarchy functions
- `TestCallGraphAxis` — mock/reuse caller analysis
- `TestAxesCombination` — deduplication, union, risk aggregation
- `TestConfidenceScoring` — weighted average, axis skipping
- `TestRecommendations` — heuristic generation
- `TestIntegration` — full end-to-end on real ast-tools files

### Do NOT modify `__init__.py` — I will handle registration.

---

## Verification

```bash
pytest tests/tools/test_blast_radius_v2.py -v --tb=short
python3 -c "from ast_tools.tools.blast_radius_v2 import _tool_blast_radius_v2; print('OK')"
pytest tests/tools/test_class_hierarchy.py tests/tools/test_transitive_analysis.py tests/test_project_tools.py -q --tb=short
```