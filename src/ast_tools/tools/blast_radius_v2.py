"""MCP tool: Blast Radius v2 — unified impact analysis combining
import graph + class hierarchy + call graph into a single score.

Delegates to existing tools rather than duplicating logic.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ast_tools.tools.class_hierarchy import (
    _extract_class_definitions,
    _find_subclasses,
)
from ast_tools.tools.module_imports import _build_import_graph
from ast_tools.tools.transitive_analysis import _classify_risk, _resolve_target
from ast_tools.utils.file_utils import find_python_files
from ast_tools.utils.impact import build_reverse_deps

# ---------------------------------------------------------------------------
# Axis configurations — base confidence per analysis method
# ---------------------------------------------------------------------------

AXIS_CONFIDENCE = {
    "import_graph": 0.95,      # AST-parsed, deterministic
    "class_hierarchy": 0.90,   # AST-parsed, cross-file edge cases
    "call_graph": 0.75,        # String-grep based, may be incomplete
}


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def _resolve_target_kind(target: str, cwd: str) -> dict[str, str]:
    """Determine whether *target* is a file, class, function, or module.

    Returns a dict with *kind*, *name*, and optionally *file_path*.
    """
    root = Path(cwd).resolve()

    # 1 — Check if it's a file path
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = (root / target).resolve()
    else:
        target_path = target_path.resolve()

    if target_path.exists() and target_path.is_file():
        return {
            "kind": "file",
            "name": str(target_path),
            "file_path": str(target_path),
        }

    # 2 — Check if it's a class in the workspace
    # Quick heuristic: scan a sample of files for class definitions
    if not target.startswith(".") and not target.endswith(".py"):
        class_file = _find_class_in_workspace(target, root)
        if class_file:
            return {
                "kind": "class",
                "name": target,
                "file_path": class_file,
            }

    # 3 — Check if it's a function (heuristic: scan for def target())
    if not target.startswith(".") and not target.endswith(".py"):
        func_file = _find_function_in_workspace(target, root)
        if func_file:
            return {
                "kind": "function",
                "name": target,
                "file_path": func_file,
            }

    # 4 — Default to module path
    return {"kind": "module", "name": target, "file_path": ""}


def _find_class_in_workspace(class_name: str, root: Path) -> str | None:
    """Scan workspace for a class definition with the given name."""
    for py_file in find_python_files(str(root), max_files=200):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    return str(py_file)
        except (SyntaxError, OSError):
            continue
    return None


def _find_function_in_workspace(func_name: str, root: Path) -> str | None:
    """Scan workspace for a function definition with the given name."""
    for py_file in find_python_files(str(root), max_files=200):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    return str(py_file)
        except (SyntaxError, OSError):
            continue
    return None


# ---------------------------------------------------------------------------
# Axis: import graph analysis
# ---------------------------------------------------------------------------

def _axis_import_graph(
    target: str,
    cwd: str,
    max_depth: int = 5,
) -> dict[str, Any] | None:
    """Analyze impact via the import graph.

    Returns dict with *affected*, *risk*, *confidence*, *details* or
    *None* if the axis cannot run.
    """
    root = Path(cwd).resolve()

    try:
        graph = _build_import_graph(root)
    except Exception:
        return None

    module_target = _resolve_target(target, str(root))

    reverse = build_reverse_deps({k: list(v) for k, v in graph.items()})

    if module_target not in reverse:
        return {
            "affected": 0,
            "risk": "none",
            "confidence": AXIS_CONFIDENCE["import_graph"],
            "details": [],
        }

    # BFS for dependents up to max_depth
    affected: set[str] = set()
    visited: set[str] = {module_target}
    current: list[str] = list(reverse.get(module_target, []))

    depth = 0
    while current and depth < max_depth:
        next_level: list[str] = []
        for mod in current:
            if mod in visited:
                continue
            visited.add(mod)
            affected.add(mod)
            for dep in reverse.get(mod, []):
                if dep not in visited:
                    next_level.append(dep)
        current = next_level
        depth += 1

    count = len(affected)
    return {
        "affected": count,
        "risk": _classify_risk(count),
        "confidence": AXIS_CONFIDENCE["import_graph"],
        "details": sorted(affected)[:50],  # cap output
    }


# ---------------------------------------------------------------------------
# Axis: class hierarchy analysis
# ---------------------------------------------------------------------------

def _axis_class_hierarchy(
    target: str,
    file_path: str,
    cwd: str,
) -> dict[str, Any] | None:
    """Analyze impact via class hierarchy (subclasses).

    Returns *None* if the target isn't a class or can't be analysed.
    """
    if not file_path:
        return None

    try:
        classes = _extract_class_definitions(file_path)
    except Exception:
        return None

    if target not in classes:
        return None

    root = Path(cwd).resolve()
    try:
        subclasses = _find_subclasses(target, str(root), classes)
    except Exception:
        subclasses = []

    if not subclasses:
        return {
            "affected": 0,
            "risk": "none",
            "confidence": AXIS_CONFIDENCE["class_hierarchy"],
            "details": [],
        }

    count = len(subclasses)
    return {
        "affected": count,
        "risk": _classify_risk(count),
        "confidence": AXIS_CONFIDENCE["class_hierarchy"],
        "details": subclasses,
    }


# ---------------------------------------------------------------------------
# Axis: call graph analysis
# ---------------------------------------------------------------------------

def _axis_call_graph(
    target: str,
    file_path: str,
    cwd: str,
) -> dict[str, Any] | None:
    """Analyze impact via call graph (callers).

    Uses *structural_analysis._ast_find_callers* when available, otherwise
    falls back to a simple text search for the function name.
    """
    if not file_path:
        return None

    root = Path(cwd).resolve()

    try:
        from ast_tools.tools.structural_analysis import _ast_find_callers

        callers = _ast_find_callers(target, str(root))
    except Exception:
        # Fallback: grep for the function name
        callers = _fallback_find_callers(target, str(root))

    if not callers:
        return {
            "affected": 0,
            "risk": "none",
            "confidence": AXIS_CONFIDENCE["call_graph"],
            "details": [],
        }

    count = len(callers)
    details = [
        f"{c.get('caller', c.get('name', '?'))} in {c['file']}" if isinstance(c, dict) else str(c)
        for c in callers[:50]
    ]
    return {
        "affected": count,
        "risk": _classify_risk(count),
        "confidence": AXIS_CONFIDENCE["call_graph"],
        "details": details,
    }


def _fallback_find_callers(target: str, project_root: str) -> list[dict[str, Any]]:
    """Simple text-based fallback for finding callers."""
    import subprocess

    root = Path(project_root)

    # Use ripgrep for speed, fall back to grep
    try:
        result = subprocess.run(
            ["rg", "-l", target, "--type", "py", str(root)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = result.stdout.strip().splitlines()
    except (subprocess.SubprocessError, FileNotFoundError):
        # Manual search
        files = []
        for py_file in find_python_files(project_root, max_files=100):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                if target in content:
                    files.append(str(py_file.relative_to(root)))
            except OSError:
                continue

    return [{"name": target, "file": f} for f in files]


# ---------------------------------------------------------------------------
# Combination logic
# ---------------------------------------------------------------------------

def _combine_axes(
    axis_results: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    """Union all affected files across axes, deduplicate."""
    by_file: dict[str, set[str]] = {}

    for axis_name, result in axis_results.items():
        if result is None:
            continue
        for detail in result.get("details", []):
            # Normalize to file path if it looks like one
            if isinstance(detail, str) and "/" in detail:
                by_file.setdefault(detail, set()).add(axis_name)
            elif isinstance(detail, str):
                # It's a module or class name — note the axis
                by_file.setdefault(detail, set()).add(axis_name)
            elif isinstance(detail, dict):
                fp = detail.get("file", detail.get("name", str(detail)))
                by_file.setdefault(fp, set()).add(axis_name)

    total_affected = len(by_file)
    by_file_list = sorted(
        [{"file": f, "reasons": sorted(r)} for f, r in by_file.items()],
        key=lambda x: -len(x["reasons"]),
    )

    return {
        "total_affected": total_affected,
        "distinct_files": total_affected,
        "by_file": by_file_list,
    }


def _compute_confidence(
    axis_results: dict[str, dict[str, Any] | None],
) -> float:
    """Weighted average of axis confidences (weighted by affected count)."""
    total_weight = 0.0
    weighted_sum = 0.0

    for axis_name, result in axis_results.items():
        if result is None:
            continue
        weight = result.get("affected", 0) + 1  # +1 to avoid zero weight
        confidence = result.get("confidence", AXIS_CONFIDENCE.get(axis_name, 0.5))
        weighted_sum += weight * confidence
        total_weight += weight

    if total_weight == 0:
        return 1.0
    return round(weighted_sum / total_weight, 2)


def _aggregate_risk(
    axis_results: dict[str, dict[str, Any] | None],
) -> str:
    """Aggregate risk across all axes.

    Rules:
    - Highest non-none axis risk wins
    - If 2+ axes have "low", bump to "medium"
    """
    risk_order = ["none", "low", "medium", "high", "critical"]
    active_risks: list[str] = []
    low_count = 0

    for result in axis_results.values():
        if result is None:
            continue
        risk = result.get("risk", "none")
        if risk != "none":
            active_risks.append(risk)
            if risk == "low":
                low_count += 1

    if not active_risks:
        return "none"

    highest = max(active_risks, key=lambda r: risk_order.index(r))

    if highest == "low" and low_count >= 2:
        return "medium"

    if highest == "none":
        return "none"

    return highest


def _generate_recommendations(result: dict[str, Any]) -> list[str]:
    """Generate heuristic recommendations based on analysis results."""
    recs: list[str] = []

    axes = result.get("axes", {})

    # Import graph recommendations
    imp = axes.get("import_graph")
    if imp and imp["affected"] > 0:
        if imp["affected"] <= 3:
            recs.append(
                f"Module is imported by {imp['affected']} file(s) — "
                "review each dependent before making changes"
            )
        elif imp["affected"] <= 10:
            recs.append(
                f"Module is imported by {imp['affected']} file(s) — "
                "consider a deprecation path or feature flag"
            )
        else:
            recs.append(
                f"Module is imported by {imp['affected']} file(s) — "
                "significant blast radius; use gradual migration strategy"
            )

    # Class hierarchy recommendations
    hier = axes.get("class_hierarchy")
    if hier and hier["affected"] > 0:
        recs.append(
            f"Class has {hier['affected']} subclass(es) — "
            "test each before making changes"
        )

    # Call graph recommendations
    cg = axes.get("call_graph")
    if cg and cg["affected"] > 0:
        if cg["affected"] <= 5:
            recs.append(
                f"Function has {cg['affected']} caller(s) — "
                "verify each caller before refactoring"
            )
        else:
            recs.append(
                f"Function has {cg['affected']} caller(s) — "
                "high call frequency; consider deprecation wrapper"
            )

    # Cross-cutting
    files = result.get("combined", {}).get("distinct_files", 0)
    if files > 10:
        recs.append(
            f"Affects {files} distinct files — "
            "consider feature flag or phased rollout"
        )

    if not recs:
        recs.append("No significant impact detected — changes appear safe")

    return recs


# ---------------------------------------------------------------------------
# Main tool handler
# ---------------------------------------------------------------------------

def _tool_blast_radius_v2(params: dict[str, Any]) -> dict[str, Any]:
    """Analyze blast radius across three axes: import graph, class hierarchy, call graph.

    Args:
        target: File path, class name, function, or dotted module path.
        cwd: Project root (default: ``\".\"``).
        max_depth: BFS depth for import graph traversal (default 5).
        include_imports: Include import graph axis (default True).
        include_hierarchy: Include class hierarchy axis (default True).
        include_callers: Include call graph axis (default True).

    Returns:
        Dict with **summary**, **axes**, **combined**, and **recommendations**.
    """
    target = params.get("target", "")
    if not target:
        return {"error": "target is required", "error_code": "MISSING_PARAM"}

    cwd = params.get("cwd", ".")
    max_depth = int(params.get("max_depth", 5))
    include_imports = params.get("include_imports", True)
    include_hierarchy = params.get("include_hierarchy", True)
    include_callers = params.get("include_callers", True)

    # Resolve target kind
    resolved = _resolve_target_kind(target, cwd)
    kind = resolved["kind"]
    target_name = resolved["name"]
    file_path = resolved.get("file_path", "")

    # Run each axis
    axes: dict[str, Any] = {}

    if include_imports:
        axes["import_graph"] = _axis_import_graph(target_name, cwd, max_depth)

    if include_hierarchy and kind == "class":
        axes["class_hierarchy"] = _axis_class_hierarchy(
            target_name, file_path, cwd,
        )
    elif include_hierarchy:
        axes["class_hierarchy"] = {
            "affected": 0,
            "risk": "none",
            "confidence": AXIS_CONFIDENCE["class_hierarchy"],
            "details": [],
            "note": "Target is not a class — hierarchy analysis skipped",
        }

    if include_callers and kind in ("class", "function"):
        axes["call_graph"] = _axis_call_graph(target_name, file_path, cwd)
    elif include_callers:
        axes["call_graph"] = {
            "affected": 0,
            "risk": "none",
            "confidence": AXIS_CONFIDENCE["call_graph"],
            "details": [],
            "note": "Target is not a symbol — call graph analysis skipped",
        }

    # Combine results
    combined = _combine_axes(axes)
    confidence = _compute_confidence(axes)
    risk = _aggregate_risk(axes)
    recommendations = _generate_recommendations({"axes": axes, "combined": combined})

    return {
        "target": target_name,
        "target_kind": kind,
        "target_file": file_path or None,
        "summary": {
            "total_affected": combined["total_affected"],
            "distinct_files": combined["distinct_files"],
            "risk": risk,
            "confidence": confidence,
        },
        "axes": axes,
        "combined": combined,
        "recommendations": recommendations,
    }
