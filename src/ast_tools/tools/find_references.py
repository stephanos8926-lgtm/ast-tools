"""find_references tool — find all references to a symbol across the codebase."""

from pathlib import Path
from typing import Any

from ast_tools.tools.structural_analysis import _ast_find_references


def _tool_find_references(args: dict[str, Any]) -> dict[str, Any]:
    """Find all references to a symbol across the codebase."""
    symbol = args["symbol"]
    cwd = args.get("cwd", ".")
    file_filter = args.get("file")
    limit = int(args.get("limit", 100))

    if not symbol:
        return {"error": "symbol is required", "error_code": "INVALID_INPUT", "tool": "find_references"}

    try:
        refs = _ast_find_references(symbol, cwd)
    except Exception as e:
        return {"error": str(e), "error_code": "INTERNAL", "tool": "find_references"}

    if file_filter:
        file_filter_path = str(Path(file_filter).resolve())
        filtered = []
        for ref in refs:
            ref_full = str(Path(cwd) / ref["file"])
            if ref_full == file_filter_path or ref["file"] == file_filter:
                filtered.append(ref)
        refs = filtered

    total = len(refs)
    truncated = total > limit
    if truncated:
        refs = refs[:limit]

    return {
        "symbol": symbol,
        "references": refs,
        "count": len(refs),
        "truncated": truncated,
        "total": total,
    }
