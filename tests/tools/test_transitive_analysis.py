"""Tests for transitive_analysis tool — the "what breaks?" query."""

from pathlib import Path
from unittest.mock import patch

from ast_tools.tools.transitive_analysis import (
    _tool_transitive_dependents,
    _classify_risk,
    _resolve_target,
)


import pytest
pytestmark = pytest.mark.integration

class TestRiskClassification:
    def test_none(self) -> None:
        assert _classify_risk(0) == "none"

    def test_low(self) -> None:
        assert _classify_risk(1) == "low"
        assert _classify_risk(2) == "low"

    def test_medium(self) -> None:
        assert _classify_risk(3) == "medium"
        assert _classify_risk(9) == "medium"

    def test_high(self) -> None:
        assert _classify_risk(10) == "high"
        assert _classify_risk(100) == "high"


class TestTargetResolution:
    def test_module_path_passthrough(self) -> None:
        result = _resolve_target("ast_tools.tools.semantic_search", ".")
        assert result == "ast_tools.tools.semantic_search"

    def test_file_path_resolves(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        mod_file = pkg / "core.py"
        mod_file.write_text("def fn(): pass\n")

        result = _resolve_target(str(mod_file), str(tmp_path))
        assert result == "mypkg.core"


class TestTransitiveDependents:
    def test_nonexistent_target(self, tmp_path: Path) -> None:
        result = _tool_transitive_dependents({"target": "nonexistent", "cwd": str(tmp_path)})
        assert "error" in result or result["risk"] == "none"
        assert result["fan_out"] == 0

    def test_missing_target(self) -> None:
        result = _tool_transitive_dependents({})
        assert "error" in result

    def test_real_ast_tools_project(self) -> None:
        """Integration test: run on the real ast-tools project."""
        result = _tool_transitive_dependents({
            "target": "src/ast_tools/tools/module_imports.py",
            "cwd": ".",
        })
        assert result["target"] == "ast_tools.tools.module_imports"
        assert len(result["direct"]) >= 1  # At least impact_analysis imports it
        assert isinstance(result["transitive"], list)
        assert result["risk"] in ("none", "low", "medium", "high")

    def test_dependencies_direction(self) -> None:
        """Dependencies direction should return what the target imports."""
        result = _tool_transitive_dependents({
            "target": "ast_tools.tools.impact_analysis",
            "direction": "dependencies",
            "cwd": ".",
        })
        assert "ast_tools.tools.module_imports" in result["direct"]
        assert result["direction"] == "dependencies"
        assert result["fan_out"] > 0

    def test_dependents_depth_grouping(self) -> None:
        """Transitive layers should be grouped by BFS depth."""
        result = _tool_transitive_dependents({
            "target": "src/ast_tools/__init__.py",
            "cwd": ".",
        })
        for layer in result.get("transitive", []):
            assert "depth" in layer
            assert isinstance(layer["depth"], int)
            assert isinstance(layer["modules"], list)
