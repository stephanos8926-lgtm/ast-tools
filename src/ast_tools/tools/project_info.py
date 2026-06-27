"""project_info tool — project intelligence manifest."""

from typing import Any


def _tool_project_info(args: dict[str, Any]) -> dict[str, Any]:
    """Return project intelligence for the given directory."""
    cwd = args.get("cwd", ".")
    full = args.get("full", False)
    diff = args.get("diff", False)

    try:
        from project_tools import generate_project_json, project_info, project_info_summary

        if diff:
            return generate_project_json(cwd, diff=True)
        if full:
            return project_info(cwd)
        return project_info_summary(cwd)
    except Exception as e:
        return {"error": str(e), "error_code": "INTERNAL", "tool": "project_info"}
