"""Tests for Phase 3 polish: __all__ filtering, structured error codes, CLI polish."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ast_tools.tools.ast_grep import _tool_ast_grep
from ast_tools.tools.ast_read import _tool_ast_read
from ast_tools.tools.ast_edit import _tool_ast_edit
from ast_tools_server import (
    _tool_structural_analysis,
    _tool_find_references,
    _tool_impact_analysis,
    call_tool,
)

# Import extracted tools from package
from ast_tools.tools import (
    _tool_project_info,
    _tool_codebase_summary,
)


# ─── Helpers ───────────────────────────────────────────────────────────────

def _make_file(directory: str, name: str, content: str) -> str:
    """Create a file and return its full path."""
    path = os.path.join(directory, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


@contextmanager
def _chdir(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


@pytest.fixture
def tmp_proj(tmp_path):
    """Create a temporary project with an __all__ module."""
    root = tmp_path
    core = str(root / "core.py")
    with open(core, "w") as f:
        f.write('''\
"""Core module."""

__all__ = ["DataProcessor", "create_processor"]


class DataProcessor:
    """Process data."""

    def __init__(self, name: str):
        self.name = name

    def process(self, data: list) -> list:
        """Process items."""
        return data


class _InternalHelper:
    """Not exported via __all__."""

    def help(self):
        pass


class AlsoExported:
    """Also not in __all__."""

    pass


def create_processor(name: str) -> DataProcessor:
    """Factory function."""
    return DataProcessor(name)


def _private_func() -> int:
    """Private -- not in __all__."""
    return 42


SECRET_VALUE = 42
PUBLIC_VALUE = 99
''')
    return root


# ─── __all__ filtering tests ──────────────────────────────────────────────

class TestAllFiltering:
    def test_no_all_returns_all(self, tmp_path):
        """Without __all__, all public symbols are returned."""
        core = _make_file(str(tmp_path), "no_all.py", '''\
"""Module without __all__."""

class DataProcessor:
    """Process data."""

    def __init__(self, name: str):
        self.name = name

    def process(self, data: list) -> list:
        """Process items."""
        return data


class _InternalHelper:
    """Private."""

    def help(self):
        pass


class AlsoPublic:
    """Public, no __all__ filter."""

    pass


def create_processor(name: str) -> DataProcessor:
    """Factory function."""
    return DataProcessor(name)


def _private_func() -> int:
    """Private function."""
    return 42

PUBLIC_VALUE = 42
''')
        result = _tool_ast_read({"file": core})
        assert result["filtered_by__all__"] is False
        class_names = [c["name"] for c in result["classes"]]
        assert "DataProcessor" in class_names
        assert "_InternalHelper" not in class_names  # private excluded
        assert "AlsoPublic" in class_names
        func_names = [f["name"] for f in result["functions"]]
        assert "create_processor" in func_names
        assert "_private_func" not in func_names  # private excluded

    def test_all_filters_classes(self, tmp_proj):
        """With __all__, only listed classes appear."""
        core = os.path.join(tmp_proj, "core.py")
        result = _tool_ast_read({"file": core})
        assert result["filtered_by__all__"] is True
        class_names = [c["name"] for c in result["classes"]]
        assert "DataProcessor" in class_names  # in __all__
        assert "AlsoExported" not in class_names  # NOT in __all__
        assert "_InternalHelper" not in class_names  # private AND not in __all__

    def test_all_filters_functions(self, tmp_proj):
        """With __all__, only listed functions appear."""
        core = os.path.join(tmp_proj, "core.py")
        result = _tool_ast_read({"file": core})
        func_names = [f["name"] for f in result["functions"]]
        assert "create_processor" in func_names  # in __all__
        assert "_private_func" not in func_names  # private AND not in __all__

    def test_all_filters_variables(self, tmp_proj):
        """With __all__, only listed variables appear."""
        core = os.path.join(tmp_proj, "core.py")
        result = _tool_ast_read({"file": core})
        var_names = [v["name"] for v in result["variables"]]
        assert "SECRET_VALUE" not in var_names  # not in __all__
        assert "PUBLIC_VALUE" not in var_names  # not in __all__
        assert "__all__" not in var_names  # __all__ itself is skipped

    def test_all_with_include_private(self, tmp_proj):
        """__all__ filtering works alongside include_private."""
        core = os.path.join(tmp_proj, "core.py")
        result = _tool_ast_read({"file": core, "include_private": True})
        assert result["filtered_by__all__"] is True
        class_names = [c["name"] for c in result["classes"]]
        assert "DataProcessor" in class_names  # in __all__ + public
        assert "_InternalHelper" not in class_names  # private, NOT in __all__
        assert "AlsoExported" not in class_names  # public, NOT in __all__

    def test_empty_all(self, tmp_path):
        """Empty __all__ = [] hides everything."""
        core = _make_file(str(tmp_path), "empty_all.py", '''\
__all__ = []

class MyClass:
    pass

def my_func():
    pass

MY_VAR = 1
''')
        result = _tool_ast_read({"file": core})
        assert result["filtered_by__all__"] is True
        assert len(result["classes"]) == 0
        assert len(result["functions"]) == 0
        assert len(result["variables"]) == 0

    def test_all_without_imports(self, tmp_proj):
        """__all__ filtering works even without imports."""
        core = os.path.join(tmp_proj, "core.py")
        result = _tool_ast_read({"file": core, "include_imports": False})
        assert result["filtered_by__all__"] is True
        assert "imports" not in result
        assert len(result["classes"]) == 1  # only DataProcessor


# ─── Structured error codes tests ─────────────────────────────────────────

class TestErrorCodes:
    def test_ast_read_file_not_found(self):
        result = _tool_ast_read({"file": "/nonexistent/path/to/file.py"})
        assert "error" in result
        assert result["error_code"] == "NOT_FOUND"
        assert result["tool"] == "ast_read"

    def test_ast_read_syntax_error(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def broken(:\n  pass\n")
            f.flush()
            result = _tool_ast_read({"file": f.name})
            os.unlink(f.name)
        assert "error" in result
        assert result["error_code"] == "PARSE_ERROR"
        assert result["tool"] == "ast_read"

    def test_ast_edit_file_not_found(self):
        result = _tool_ast_edit({
            "file": "/nonexistent/path/to/file.py",
            "operation": "rename_function",
            "params": {"old_name": "foo", "new_name": "bar"},
        })
        assert "error" in result
        assert result["error_code"] == "NOT_FOUND"
        assert result["tool"] == "ast_edit"

    def test_ast_edit_syntax_error(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def broken(:\n  pass\n")
            f.flush()
            result = _tool_ast_edit({
                "file": f.name,
                "operation": "rename_function",
                "params": {"old_name": "foo", "new_name": "bar"},
            })
            os.unlink(f.name)
        assert "error" in result
        assert result["error_code"] == "PARSE_ERROR"
        assert result["tool"] == "ast_edit"

    def test_ast_edit_unknown_operation(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def foo(): pass\n")
            f.flush()
            result = _tool_ast_edit({
                "file": f.name,
                "operation": "nonexistent_op",
                "params": {},
            })
            os.unlink(f.name)
        assert "error" in result
        assert result["error_code"] == "INVALID_INPUT"
        assert result["tool"] == "ast_edit"

    def test_ast_grep_cli_not_found(self):
        """ast-grep CLI not installed returns NOT_FOUND error code."""
        result = _tool_ast_grep({
            "pattern": "def $FUNC($$$ARGS): $BODY",
            "path": "/nonexistent/zzz",
            "lang": "python",
        })
        # ast-grep not installed returns NOT_FOUND
        assert result.get("error_code") == "NOT_FOUND" or "matches" in result

    def test_structural_analysis_missing_file(self):
        result = _tool_structural_analysis({
            "analysis_type": "references",
            "symbol": "Foo",
        })
        assert "error" in result
        assert result["error_code"] == "INVALID_INPUT"
        assert result["tool"] == "structural_analysis"

    def test_structural_analysis_missing_symbol(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            result = _tool_structural_analysis({
                "analysis_type": "callers",
                "file": f.name,
            })
            os.unlink(f.name)
        assert "error" in result
        assert result["error_code"] == "INVALID_INPUT"
        assert result["tool"] == "structural_analysis"

    def test_find_references_empty_symbol(self):
        result = _tool_find_references({"symbol": ""})
        assert "error" in result
        assert result["error_code"] == "INVALID_INPUT"
        assert result["tool"] == "find_references"

    def test_call_tool_unknown(self):
        """call_tool returns structured error for unknown tool."""
        result = asyncio.run(call_tool("nonexistent_tool_xyz", {}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data
        assert data["error_code"] == "NOT_FOUND"

    def test_call_tool_internal_error(self):
        """call_tool top-level handler returns error_code on unexpected errors."""
        result = asyncio.run(call_tool("ast_read", {}))  # missing 'file' param
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data
        assert "error_code" in data


@pytest.fixture
def src_dir():
    """Return the src directory path."""
    return str(Path(__file__).parent.parent / "src")


# ─── CLI polish tests ─────────────────────────────────────────────────────

class TestCLIPolish:
    def _run_cli(self, args, cwd):
        env = os.environ.copy()
        env["PYTHONPATH"] = self._src_dir
        proc = subprocess.run(
            [sys.executable, "-m", "project_tools"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        return proc

    @property
    def _src_dir(self):
        return str(Path(__file__).parent.parent / "src")

    def test_version_flag(self, tmp_path):
        proc = self._run_cli(["--version"], tmp_path)
        assert proc.returncode == 0
        assert "ast-tools 0.1.0" in proc.stdout

    def test_help_flag(self, tmp_path):
        proc = self._run_cli(["--help"], tmp_path)
        assert proc.returncode == 0
        assert "project-init" in proc.stdout
        assert "project-summary" in proc.stdout

    def test_project_summary_subcommand(self, tmp_path):
        root = str(tmp_path)
        _make_file(root, "app.py", '''\
"""My app."""

__all__ = ["main"]

def main():
    """Main entry point."""
    print("hello")
''')
        proc = self._run_cli(["project-summary"], tmp_path)
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "name" in data
        assert "version" in data
        assert "languages" in data
        assert "module_count" in data
        assert "symbol_count" in data

    def test_no_command_prints_help(self, tmp_path):
        proc = self._run_cli([], tmp_path)
        assert proc.returncode == 1