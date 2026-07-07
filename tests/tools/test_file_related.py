"""Tests for file_related_suggest tool — all strategies."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ast_tools.tools.file_related import (
    _file_stem,
    _find_call_graph,
    _find_git_root,
    _find_imported_by,
    _find_imports_this,
    _find_name_matches,
    _find_siblings,
    _find_source_from_test,
    _find_test_files,
    _parse_imports,
    _tool_file_related_suggest,
)

pytestmark = pytest.mark.integration


class TestHelpers:
    """Test helper functions."""

    def test_file_stem_normal(self) -> None:
        assert _file_stem(Path("src/utils.py")) == "utils"

    def test_file_stem_test_prefix(self) -> None:
        assert _file_stem(Path("tests/test_utils.py")) == "utils"

    def test_file_stem_test_suffix(self) -> None:
        assert _file_stem(Path("utils_test.py")) == "utils"

    def test_find_git_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src/sub"
        subdir.mkdir(parents=True)
        root = _find_git_root(subdir / "file.py")
        assert root == tmp_path

    def test_find_git_root_no_git(self, tmp_path: Path) -> None:
        root = _find_git_root(tmp_path / "nope.py")
        assert root is None

    def test_parse_imports(self) -> None:
        content = """import os
import sys
from pathlib import Path
from . import utils
from ast_tools.tools import semantic_search
"""
        imports = _parse_imports(content)
        assert "os" in imports
        assert "pathlib" in imports
        assert "ast_tools.tools" in imports


class TestTestFileDetection:
    """Test test file detection strategies."""

    def test_finds_test_file_in_tests_dir(self, tmp_path: Path) -> None:
        (tmp_path / "src/utils.py").parent.mkdir(parents=True)
        (tmp_path / "src/utils.py").write_text("def util(): pass")
        (tmp_path / "tests/test_utils.py").parent.mkdir(parents=True)
        (tmp_path / "tests/test_utils.py").touch()

        result = _find_test_files(tmp_path / "src/utils.py", tmp_path, "utils", 5)
        assert len(result) > 0
        assert str(tmp_path / "tests/test_utils.py") in [r["path"] for r in result]

    def test_reverse_test_to_source(self, tmp_path: Path) -> None:
        (tmp_path / "src/core.py").parent.mkdir(parents=True)
        (tmp_path / "src/core.py").touch()
        (tmp_path / "tests/test_core.py").parent.mkdir(parents=True)
        (tmp_path / "tests/test_core.py").touch()

        result = _find_source_from_test(tmp_path / "tests/test_core.py", tmp_path, "core", 5)
        assert len(result) > 0
        assert str(tmp_path / "src/core.py") in [r["path"] for r in result]


class TestImportRelationships:
    """Test import-based relationship detection."""

    def test_finds_imported_by(self, tmp_path: Path) -> None:
        target = tmp_path / "src" / "mymodule" / "utils.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def helper(): pass")

        importer = tmp_path / "src" / "main.py"
        importer.parent.mkdir(parents=True, exist_ok=True)
        importer.write_text("from mymodule.utils import helper\n")

        result = _find_imported_by(target, tmp_path, "utils", 5, set())
        assert isinstance(result, list)

    def test_finds_imports_this(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)

        utils_file = src_dir / "utils.py"
        utils_file.write_text("def fmt(): pass")

        main_file = src_dir / "main.py"
        main_file.write_text("import os\nfrom pathlib import Path\nimport json\n")

        result = _find_imports_this(main_file, tmp_path, 5, set())
        assert isinstance(result, list)


class TestSiblingDetection:
    """Test sibling file detection."""

    def test_finds_same_dir_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()

        result = _find_siblings(tmp_path / "a.py", 5, set())
        assert len(result) > 0
        assert str(tmp_path / "b.py") in [r["path"] for r in result]

    def test_excludes_self(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()

        result = _find_siblings(tmp_path / "a.py", 5, set())
        paths = [r["path"] for r in result]
        assert str(tmp_path / "a.py") not in paths

    def test_excludes_existing(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()

        result = _find_siblings(tmp_path / "a.py", 5, {str(tmp_path / "b.py")})
        assert len(result) == 0


class TestNameMatching:
    """Test same-stem name matching across project."""

    def test_finds_same_stem_across_project(self, tmp_path: Path) -> None:
        (tmp_path / "api/user.py").parent.mkdir(parents=True)
        (tmp_path / "api/user.py").touch()
        (tmp_path / "models/user.py").parent.mkdir(parents=True)
        (tmp_path / "models/user.py").touch()

        result = _find_name_matches("user", tmp_path, tmp_path / "api/user.py", 5, set())
        assert str(tmp_path / "models/user.py") in [r["path"] for r in result]


class TestCallGraph:
    """Test call graph integration strategy."""

    @patch("ast_tools.tools.file_related._ast_find_callers")
    def test_direct_call_graph(self, mock_fc) -> None:
        """Direct unit test of _find_call_graph."""
        mock_fc.side_effect = lambda sym, root, max_files=100, max_depth=50: (
            [{"file": "caller.py", "line": 5, "caller": "main", "context": "greet()"}]
            if sym == "greet"
            else []
        )

        tmp = Path(__file__).parent / "_cg_test_ws"
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "target.py").write_text("def greet():\n    pass\n")

        result = _find_call_graph(tmp / "target.py", tmp, 10, set())

        assert len(result) == 1
        assert result[0]["reason"] == "call_graph"
        assert result[0]["confidence"] == 0.55
        assert "caller.py" in result[0]["path"]

    @patch("ast_tools.tools.file_related._ast_find_callers")
    def test_call_graph_via_tool_suggest(self, mock_fc) -> None:
        """Integration through _tool_file_related_suggest."""
        mock_fc.side_effect = lambda sym, root, max_files=100, max_depth=50: (
            [{"file": "src/caller.py", "line": 5, "caller": "main", "context": "greet()"}]
            if sym == "greet"
            else []
        )

        tmp = Path(__file__).parent / "_cg_integ_ws"
        (tmp / "lib").mkdir(parents=True, exist_ok=True)
        (tmp / "src").mkdir(parents=True, exist_ok=True)
        (tmp / "lib" / "target.py").write_text("def greet():\n    pass\n")
        (tmp / "src" / "caller.py").write_text("from lib.target import greet\ngreet()\n")

        result = _tool_file_related_suggest(
            {
                "file_path": str(tmp / "lib" / "target.py"),
                "workspace": str(tmp),
                "max_suggestions": 10,
                "include_imports": False,
                "include_tests": False,
            }
        )

        cg = [s for s in result["suggestions"] if s["reason"] == "call_graph"]
        assert len(cg) > 0, f"Expected call_graph suggestions, got all: {result['suggestions']}"
        assert str(tmp / "src" / "caller.py") in [s["path"] for s in cg]
        assert cg[0]["confidence"] == 0.55
        assert "'greet'" in cg[0]["explanation"]


class TestIntegration:
    """Integration tests for the full tool."""

    def test_missing_file_path(self) -> None:
        result = _tool_file_related_suggest({})
        assert "error" in result

    def test_nonexistent_file(self) -> None:
        result = _tool_file_related_suggest({"file_path": "/nonexistent/file.py"})
        assert "error" in result

    def test_valid_file(self, tmp_path: Path) -> None:
        (tmp_path / "src/__init__.py").parent.mkdir(parents=True)
        (tmp_path / "src/__init__.py").touch()
        (tmp_path / "src/utils.py").write_text("import json\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests/test_utils.py").touch()

        result = _tool_file_related_suggest(
            {
                "file_path": str(tmp_path / "src/utils.py"),
                "workspace": str(tmp_path),
                "include_imports": False,
            }
        )
        assert "suggestions" in result
        reasons = [s["reason"] for s in result["suggestions"]]
        assert "test_file" in reasons

    def test_suggestions_sorted_by_confidence(self, tmp_path: Path) -> None:
        (tmp_path / "src/core.py").parent.mkdir(parents=True)
        (tmp_path / "src/core.py").touch()
        (tmp_path / "tests/test_core.py").parent.mkdir(parents=True)
        (tmp_path / "tests/test_core.py").touch()
        (tmp_path / "src/helper.py").touch()

        result = _tool_file_related_suggest(
            {
                "file_path": str(tmp_path / "src/core.py"),
                "workspace": str(tmp_path),
                "include_imports": False,
            }
        )
        confidences = [s["confidence"] for s in result["suggestions"]]
        assert confidences == sorted(confidences, reverse=True)

    def test_deduplicates(self, tmp_path: Path) -> None:
        (tmp_path / "src/core.py").parent.mkdir(parents=True)
        (tmp_path / "src/core.py").touch()
        (tmp_path / "tests/test_core.py").parent.mkdir(parents=True)
        (tmp_path / "tests/test_core.py").touch()

        result = _tool_file_related_suggest(
            {
                "file_path": str(tmp_path / "src/core.py"),
                "workspace": str(tmp_path),
                "include_imports": False,
                "max_suggestions": 5,
            }
        )
        paths = [s["path"] for s in result["suggestions"]]
        assert len(paths) == len(set(paths))
