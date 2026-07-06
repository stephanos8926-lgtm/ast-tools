"""MCP tool: Transitive dependency analysis — the "what breaks?" question."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ast_tools.tools.module_imports import _build_import_graph
from ast_tools.utils.file_utils import file_to_module
from ast_tools.utils.impact import build_reverse_deps


def _classify_risk(count: int) -> str:
    if count >= 10:
        return "high"
    if count >= 3:
        return "medium"
    if count >= 1:
        return "low"
    return "none"


def _resolve_target(target: str, cwd: str | Path) -> str:
    """Resolve a file path or module name to a dotted module path."""
    target_path = Path(target)

    # If it's a file path, convert to module path
    if target.endswith(".py") or "/" in str(target) or "\\" in str(target):
        if not target_path.is_absolute():
            target_path = (Path(cwd) / target).resolve()
        try:
            root = target_path
            for parent in target_path.parents:
                if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                    root = parent
                    break
            resolved = file_to_module(str(target_path), root)
            if resolved.startswith("src."):
                resolved = resolved[4:]
        except Exception:
            resolved = str(target_path).replace("/", ".").replace("\\", ".").rstrip(".py")
        return resolved

    # Already a dotted module path — use as-is
    return target


def _tool_transitive_dependents(params: dict[str, Any]) -> dict[str, Any]:
    """Find all files affected (transitively) by changes to a target file or module.

    Builds a live import graph and BFS-traverses it to find the full
    chain of affected modules — direct dependents plus transitive ones
    grouped by depth.

    Args:
        target: File path or dotted module path to analyze.
        direction: ``"dependents"`` (who imports from this, default) or
            ``"dependencies"`` (what this imports).
        max_depth: How many levels deep to traverse (default 10).
        cwd: Working directory for relative path resolution (default ``"."``).

    Returns:
        Dict with ``direct``, ``transitive`` (depth-grouped),
        ``all_affected``, ``fan_out``, and ``risk``.
    """
    target = params.get("target", "")
    if not target:
        return {"error": "target is required", "error_code": "MISSING_PARAM"}

    direction = params.get("direction", "dependents")
    max_depth = int(params.get("max_depth", 10))
    cwd = params.get("cwd", ".")

    root = Path(cwd).resolve()
    module_target = _resolve_target(target, str(root))

    try:
        graph = _build_import_graph(root)
    except Exception as exc:
        return {"error": f"Failed to build import graph: {exc}", "error_code": "GRAPH_FAILED"}

    if direction == "dependents":
        # Who imports FROM this module? → BFS over reverse graph
        graph = build_reverse_deps({k: list(v) for k, v in graph.items()})

    # --- BFS with depth tracking ---
    if module_target not in graph:
        return {
            "target": module_target,
            "direction": direction,
            "direct": [],
            "transitive": [],
            "all_affected": [],
            "fan_out": 0,
            "risk": "none",
            "note": f"Target '{module_target}' not found in import graph",
        }

    direct = sorted(graph.get(module_target, []))
    transitive_by_depth: list[dict[str, Any]] = []
    all_affected: set[str] = set(direct)
    visited: set[str] = {module_target}

    # BFS level by level
    current_level: list[str] = list(direct)
    depth = 1
    while current_level and depth <= max_depth:
        next_level: list[str] = []
        for mod in current_level:
            if mod in visited:
                continue
            visited.add(mod)
            for dep in graph.get(mod, []):
                if dep not in visited and dep not in all_affected:
                    next_level.append(dep)
                    all_affected.add(dep)

        if current_level:
            # Only include modules that haven't appeared in a prior depth
            [m for m in current_level if m not in visited or m == current_level[0]]
            # Simpler: just include all non-target, non-duplicate at this depth
            seen_before = {m for layer in transitive_by_depth for m in layer["modules"]} | set(direct)
            fresh = sorted(m for m in current_level if m not in seen_before and m != module_target)
            if fresh:
                transitive_by_depth.append({"depth": depth, "modules": fresh})

        current_level = next_level
        depth += 1

    fan_out = len(direct)
    return {
        "target": module_target,
        "direction": direction,
        "direct": direct,
        "transitive": transitive_by_depth,
        "all_affected": sorted(set(direct) | {m for layer in transitive_by_depth for m in layer["modules"]}),
        "fan_out": fan_out,
        "risk": _classify_risk(fan_out),
    }
