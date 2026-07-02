"""Tests for blast_radius_v2 tool — unified impact analysis."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ast_tools.tools.blast_radius_v2 import (
    _tool_blast_radius_v2,
    _resolve_target_kind,
    _compute_confidence,
    _aggregate_risk,
    _combine_axes,
    _generate_recommendations,
    _find_class_in_workspace,
    _find_function_in_workspace,
)


# ===========================================================================
# Target resolution
# ===========================================================================


class TestTargetResolution:
    def test_identifies_file_target(self, tmp_path: Path) -> None:
        py_file = tmp_path / "foo.py"
        py_file.write_text("x = 1\n")
        result = _resolve_target_kind(str(py_file), str(tmp_path))
        assert result["kind"] == "file"
        assert "foo.py" in result["name"]

    def test_identifies_class_target(self, tmp_path: Path) -> None:
        py_file = tmp_path / "models.py"
        py_file.write_text("class MyModel:\n    pass\n")
        result = _resolve_target_kind("MyModel", str(tmp_path))
        # Should find it by scanning
        assert result["kind"] == "class"
        assert result["name"] == "MyModel"

    def test_identifies_function_target(self, tmp_path: Path) -> None:
        py_file = tmp_path / "utils.py"
        py_file.write_text("def helper():\n    pass\n")
        result = _resolve_target_kind("helper", str(tmp_path))
        assert result["kind"] == "function"
        assert result["name"] == "helper"

    def test_unknown_target_defaults_module(self, tmp_path: Path) -> None:
        result = _resolve_target_kind("some.random.module", str(tmp_path))
        assert result["kind"] == "module"
        assert result["name"] == "some.random.module"


# ===========================================================================
# Axes combination
# ===========================================================================


class TestAxesCombination:
    def test_deduplicates_across_axes(self) -> None:
        axes = {
            "import_graph": {
                "affected": 2,
                "risk": "medium",
                "confidence": 0.95,
                "details": ["src/core.py", "src/utils.py"],
            },
            "class_hierarchy": {
                "affected": 1,
                "risk": "low",
                "confidence": 0.90,
                "details": ["src/core.py"],  # Same file!
            },
        }
        result = _combine_axes(axes)
        assert result["total_affected"] == 2  # Not 3
        assert result["distinct_files"] == 2

    def test_no_axes_returns_empty(self) -> None:
        result = _combine_axes({})
        assert result["total_affected"] == 0
        assert result["by_file"] == []

    def test_none_result_skipped(self) -> None:
        axes = {"import_graph": None, "class_hierarchy": None}
        result = _combine_axes(axes)
        assert result["total_affected"] == 0


# ===========================================================================
# Confidence scoring
# ===========================================================================


class TestConfidenceScoring:
    def test_single_axis_confidence(self) -> None:
        axes = {
            "import_graph": {
                "affected": 5,
                "risk": "medium",
                "confidence": 0.95,
                "details": [],
            },
        }
        confidence = _compute_confidence(axes)
        assert confidence == 0.95

    def test_multi_axis_weighted_average(self) -> None:
        axes = {
            "import_graph": {"affected": 5, "risk": "medium", "confidence": 0.95, "details": []},
            "class_hierarchy": {"affected": 1, "risk": "none", "confidence": 0.90, "details": []},
        }
        confidence = _compute_confidence(axes)
        # weighted: (5+1)*0.95 + (1+1)*0.90 / (6+2) = 5.7+1.8 / 8 = 7.5/8 = 0.9375
        # Rounding: 0.94
        assert confidence == 0.94

    def test_empty_axes(self) -> None:
        confidence = _compute_confidence({})
        assert confidence == 1.0

    def test_none_skipped(self) -> None:
        axes = {"import_graph": None, "class_hierarchy": None}
        confidence = _compute_confidence(axes)
        assert confidence == 1.0


# ===========================================================================
# Risk aggregation
# ===========================================================================


class TestRiskAggregation:
    def test_highest_axis_wins(self) -> None:
        axes = {
            "import_graph": {"affected": 8, "risk": "medium"},
            "class_hierarchy": {"affected": 1, "risk": "low"},
        }
        assert _aggregate_risk(axes) == "medium"

    def test_two_low_axes_bump_to_medium(self) -> None:
        axes = {
            "import_graph": {"affected": 1, "risk": "low"},
            "class_hierarchy": {"affected": 1, "risk": "low"},
        }
        assert _aggregate_risk(axes) == "medium"

    def test_all_none_returns_none(self) -> None:
        axes = {
            "import_graph": {"affected": 0, "risk": "none"},
            "class_hierarchy": {"affected": 0, "risk": "none"},
        }
        assert _aggregate_risk(axes) == "none"

    def test_empty_axes_returns_none(self) -> None:
        assert _aggregate_risk({}) == "none"

    def test_none_skipped(self) -> None:
        axes = {"import_graph": None}
        assert _aggregate_risk(axes) == "none"

    def test_critical_overrides_medium(self) -> None:
        axes = {
            "import_graph": {"affected": 5, "risk": "medium"},
            "call_graph": {"affected": 25, "risk": "critical"},
        }
        assert _aggregate_risk(axes) == "critical"


# ===========================================================================
# Recommendations
# ===========================================================================


class TestRecommendations:
    def test_class_with_subclasses(self) -> None:
        result = {
            "axes": {
                "import_graph": {"affected": 0, "risk": "none"},
                "class_hierarchy": {"affected": 3, "risk": "low"},
                "call_graph": {"affected": 0, "risk": "none"},
            },
            "combined": {"distinct_files": 0},
        }
        recs = _generate_recommendations(result)
        assert any("subclass" in r for r in recs)

    def test_heavily_imported_module(self) -> None:
        result = {
            "axes": {
                "import_graph": {"affected": 15, "risk": "high"},
                "class_hierarchy": {"affected": 0, "risk": "none"},
                "call_graph": {"affected": 0, "risk": "none"},
            },
            "combined": {"distinct_files": 5},
        }
        recs = _generate_recommendations(result)
        assert any("deprecation" in r or "migration" in r for r in recs)

    def test_no_impact(self) -> None:
        result = {
            "axes": {
                "import_graph": {"affected": 0, "risk": "none"},
                "class_hierarchy": {"affected": 0, "risk": "none"},
                "call_graph": {"affected": 0, "risk": "none"},
            },
            "combined": {"distinct_files": 0},
        }
        recs = _generate_recommendations(result)
        assert any("No significant impact" in r for r in recs)

    def test_function_with_callers(self) -> None:
        result = {
            "axes": {
                "import_graph": {"affected": 0, "risk": "none"},
                "class_hierarchy": {"affected": 0, "risk": "none"},
                "call_graph": {"affected": 5, "risk": "low"},
            },
            "combined": {"distinct_files": 0},
        }
        recs = _generate_recommendations(result)
        assert any("caller" in r for r in recs)

    def test_many_distinct_files(self) -> None:
        result = {
            "axes": {
                "import_graph": {"affected": 3, "risk": "low"},
                "class_hierarchy": {"affected": 0, "risk": "none"},
                "call_graph": {"affected": 0, "risk": "none"},
            },
            "combined": {"distinct_files": 15},
        }
        recs = _generate_recommendations(result)
        assert any("feature flag" in r or "phased" in r for r in recs)


# ===========================================================================
# Helper tests
# ===========================================================================


class TestFindClass:
    def test_finds_class_in_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        py_file = tmp_path / "src" / "models.py"
        py_file.write_text("class MyService:\n    pass\n")
        result = _find_class_in_workspace("MyService", tmp_path)
        assert result is not None
        assert "models.py" in result

    def test_class_not_found(self, tmp_path: Path) -> None:
        result = _find_class_in_workspace("DoesNotExist", tmp_path)
        assert result is None


class TestFindFunction:
    def test_finds_function_in_workspace(self, tmp_path: Path) -> None:
        py_file = tmp_path / "utils.py"
        py_file.write_text("def my_func():\n    return 42\n")
        result = _find_function_in_workspace("my_func", tmp_path)
        assert result is not None
        assert "utils.py" in result

    def test_function_not_found(self, tmp_path: Path) -> None:
        result = _find_function_in_workspace("does_not_exist", tmp_path)
        assert result is None


# ===========================================================================
# Integration tests (run against real ast-tools code)
# ===========================================================================


class TestIntegration:
    def test_on_ast_tools_class(self) -> None:
        """Test on the GraphEngine class from ast-tools itself."""
        result = _tool_blast_radius_v2({
            "target": "GraphEngine",
            "cwd": ".",
            "include_imports": True,
            "include_hierarchy": True,
            "include_callers": True,
        })
        assert "error" not in result
        assert result["target_kind"] == "class"
        assert "summary" in result
        assert "axes" in result
        assert "recommendations" in result

    def test_on_ast_tools_module(self) -> None:
        """Test on a module path."""
        result = _tool_blast_radius_v2({
            "target": "ast_tools.tools.impact_analysis",
            "cwd": ".",
            "include_imports": True,
            "include_hierarchy": False,
            "include_callers": False,
        })
        assert "error" not in result
        assert result["target_kind"] in ("module", "file")
        assert "import_graph" in result["axes"]

    def test_on_ast_tools_file(self) -> None:
        """Test on a file path."""
        result = _tool_blast_radius_v2({
            "target": "src/ast_tools/tools/module_imports.py",
            "cwd": ".",
            "include_imports": True,
            "include_hierarchy": False,
            "include_callers": False,
        })
        assert "error" not in result
        # module_imports is heavily imported, should show up
        imp = result["axes"].get("import_graph", {})
        assert imp is not None

    def test_invalid_target_returns_error(self) -> None:
        result = _tool_blast_radius_v2({
            "target": "",
            "cwd": ".",
        })
        assert "error" in result

    def test_all_axes_disabled(self) -> None:
        """Test with all axes disabled — should return empty analysis."""
        result = _tool_blast_radius_v2({
            "target": "test_module",
            "cwd": ".",
            "include_imports": False,
            "include_hierarchy": False,
            "include_callers": False,
        })
        assert "error" not in result
        assert result["summary"]["total_affected"] == 0
        assert result["summary"]["risk"] == "none"

    def test_missing_target(self) -> None:
        result = _tool_blast_radius_v2({})
        assert "error" in result