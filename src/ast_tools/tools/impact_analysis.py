from ast_tools.tools.module_imports import _build_import_graph

"""impact_analysis tool — analyze the impact of changing a file or symbol."""

import json
from pathlib import Path
from typing import Any

from ast_tools.tools.structural_analysis import _ast_find_callers
from ast_tools.utils.file_utils import file_to_module, is_test_file
from ast_tools.utils.impact import build_reverse_deps, classify_risk, get_transitive_deps


def _tool_impact_analysis(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze the impact of changing a file or symbol."""
    target = args.get("target")
    if not target:
        return {
            "error": "target is required",
            "error_code": "INVALID_INPUT",
            "tool": "impact_analysis",
        }

    cwd = args.get("cwd", ".")

    from ast_tools._project_tools import find_project_root

    root = find_project_root(cwd)

    result: dict[str, Any] = {
        "target": target,
        "direct_dependents": [],
        "transitive_dependents": [],
        "test_files": [],
        "risk": "low",
        "fan_out": 0,
    }

    target_path = Path(target)
    is_file = False
    if target_path.exists() and str(target).endswith(".py"):
        is_file = True
        target_rel = file_to_module(str(target_path.resolve()), root)
    elif (root / target).exists() and (root / target).is_file():
        is_file = True
        target_rel = str(Path(target))
    else:
        cwd_path = Path(cwd) / target
        if cwd_path.exists() and str(target).endswith(".py"):
            is_file = True
            target_rel = file_to_module(str(cwd_path.resolve()), root)

    if is_file:
        # File/module target: use dependency graph
        dep_graph = _build_import_graph(root)
        reverse_deps = build_reverse_deps({k: list(v) for k, v in dep_graph.items()})

        # Build lookup keys: try dotted module path form too
        # (_build_import_graph uses dotted paths like mypkg.core)
        lookup_keys = [target_rel, target_rel.replace("\\", "/")]
        target_module = target_rel
        if "/" in target_rel or "\\" in target_rel:
            target_module = target_rel.replace("\\", "/")
            if target_module.endswith(".py"):
                target_module = target_module[:-3]
            target_module = target_module.replace("/", ".")
        lookup_keys.append(target_module)

        direct_dotted: list[str] = []
        for key in lookup_keys:
            direct_dotted.extend(reverse_deps.get(key, []))
        direct_dotted = sorted(set(direct_dotted))

        all_transitive: list[str] = []
        for d in direct_dotted:
            transitive = get_transitive_deps(d, reverse_deps)
            all_transitive.extend(transitive)
        all_transitive.extend(get_transitive_deps(target_module, reverse_deps))
        transitive_only_dotted = sorted(set(all_transitive) - set(direct_dotted))

        # Convert dotted module paths to file paths for output consistency
        def _dotted_to_filepath(d: str) -> str:
            return d.replace(".", "/") + ".py"

        direct = sorted(set(_dotted_to_filepath(d) for d in direct_dotted))
        transitive_only = sorted(set(_dotted_to_filepath(d) for d in transitive_only_dotted))

        result["direct_dependents"] = direct
        result["transitive_dependents"] = transitive_only

        fan_out = len(direct)
        result["fan_out"] = fan_out
        result["risk"] = classify_risk(fan_out)

        all_affected = set(direct) | set(transitive_only)
        test_files = sorted(f for f in all_affected if is_test_file(f))
        result["test_files"] = test_files

    else:
        # Symbol target: use AST-based caller search
        callers = _ast_find_callers(str(target), str(root))
        caller_files = sorted({c["file"] for c in callers})
        result["direct_dependents"] = caller_files
        result["callers"] = callers
        result["fan_out"] = len(caller_files)
        result["risk"] = classify_risk(len(caller_files))
        test_files = sorted(f for f in caller_files if is_test_file(f))
        result["test_files"] = test_files
        result["transitive_dependents"] = []

    return result
