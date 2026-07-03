"""Governance differ — compare architecture between branches."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .schema import GovernanceConfig, load_governance
from .scanner import Violation, scan_project
from .reporter import format_violations


def diff_branches(
    base_branch: str = "main",
    cwd: str | Path | None = None,
    config: GovernanceConfig | None = None,
    fail_on: str = "error",
) -> dict[str, Any]:
    """Compare governance state between current and base branch.

    Scans both branches independently and diffs the violations.

    Args:
        base_branch: Branch to compare against.
        cwd: Project root.
        config: Governance config (loaded once, shared across scans).
        fail_on: Minimum severity for reporting.

    Returns:
        Dict with current violations, base violations, and delta.
    """
    root = Path(cwd or os.getcwd()).resolve()
    cfg = config or load_governance()
    if cfg is None:
        return {"error": "No governance.yaml found"}

    # Scan current branch
    current_violations = scan_project(root, cfg)

    # Scan base branch via git worktree
    base_violations: list[Violation] = []
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=root,
        )
        if result.returncode != 0:
            return {
                "current": [v.to_dict() for v in current_violations],
                "base": [],
                "delta": [],
                "warning": "Not a git repository",
            }

        # Checkout base branch in temp dir for scan
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["git", "worktree", "add", "--detach", tmpdir, base_branch],
                capture_output=True, cwd=root,
            )
            try:
                base_violations = scan_project(Path(tmpdir), cfg)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", tmpdir],
                    capture_output=True, cwd=root,
                )

    except Exception as e:
        return {
            "current": [v.to_dict() for v in current_violations],
            "base": [],
            "delta": [],
            "error": f"Branch diff failed: {e}",
        }

    # Compute delta
    current_keys = {v.to_dict()["message"] for v in current_violations}
    base_keys = {v.to_dict()["message"] for v in base_violations}

    new_violations = [v for v in current_violations if v.to_dict()["message"] not in base_keys]
    fixed_violations = [v for v in base_violations if v.to_dict()["message"] not in current_keys]

    return {
        "current": [v.to_dict() for v in current_violations],
        "base": [v.to_dict() for v in base_violations],
        "delta": {
            "new": [v.to_dict() for v in new_violations],
            "fixed": [v.to_dict() for v in fixed_violations],
            "total_new": len(new_violations),
            "total_fixed": len(fixed_violations),
        },
    }