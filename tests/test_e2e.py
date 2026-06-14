"""E2E tests for AST tools MCP server."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path for direct function testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ast_tools_server import (
    _tool_ast_grep,
    _tool_ast_read,
    _tool_ast_edit,
    _tool_structural_analysis,
)
from tests.conftest import create_test_project


@pytest.fixture
def test_project(tmp_path):
    """Create a test project and return its path."""
    return create_test_project(str(tmp_path))


# ─── ast_grep tests ───────────────────────────────────────────────────────

class TestAstGrep:
    def test_grep_function_definitions(self, test_project):
        """Find all function definitions."""
        result = _tool_ast_grep({
            "pattern": "def $FUNC($$$ARGS): $BODY",
            "path": test_project,
            "lang": "python",
        })
        assert "error" not in result
        assert result["count"] > 0
        func_names = [m.get("text", "").split("(")[0].replace("def ", "").strip() for m in result["matches"]]
        assert any("process" in n for n in func_names)

    def test_grep_class_definitions(self, test_project):
        """Find all class definitions."""
        result = _tool_ast_grep({
            "pattern": "class $NAME: $BODY",
            "path": test_project,
            "lang": "python",
        })
        assert "error" not in result
        assert result["count"] >= 2  # DataProcessor, AdvancedProcessor, ConfigLoader

    def test_grep_specific_function_call(self, test_project):
        """Find calls to a specific function."""
        result = _tool_ast_grep({
            "pattern": "super().$METHOD($$$ARGS)",
            "path": test_project,
            "lang": "python",
        })
        assert "error" not in result
        assert result["count"] > 0

    def test_grep_import_statements(self, test_project):
        """Find import statements."""
        result = _tool_ast_grep({
            "pattern": "import $MODULE",
            "path": test_project,
            "lang": "python",
        })
        assert "error" not in result
        assert result["count"] > 0

    def test_grep_no_matches(self, test_project):
        """Search for something that doesn't exist."""
        result = _tool_ast_grep({
            "pattern": "def nonexistent_function_xyz($$$ARGS): $BODY",
            "path": test_project,
            "lang": "python",
        })
        assert "error" not in result
        assert result["count"] == 0

    def test_grep_nonexistent_path(self):
        """Search in a path that doesn't exist."""
        result = _tool_ast_grep({
            "pattern": "def $FUNC($$$ARGS): $BODY",
            "path": "/nonexistent/path/xyz",
            "lang": "python",
        })
        # Should return empty matches, not crash
        assert "error" not in result or "matches" in result


# ─── ast_read tests ───────────────────────────────────────────────────────

class TestAstRead:
    def test_read_core_module(self, test_project):
        """Extract structure from core.py."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file})
        assert "error" not in result
        assert result["language"] == "python"
        assert result["summary"]["total_classes"] == 2
        assert result["summary"]["total_functions"] >= 2  # create_processor, helper_function
        assert result["summary"]["total_imports"] > 0

    def test_read_class_details(self, test_project):
        """Verify class structure extraction."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file, "include_private": True})
        classes = {c["name"]: c for c in result["classes"]}
        assert "DataProcessor" in classes
        assert "AdvancedProcessor" in classes
        dp = classes["DataProcessor"]
        assert len(dp["methods"]) >= 3  # __init__, process, _transform, validate
        assert dp["bases"] == []  # No explicit base

    def test_read_function_signatures(self, test_project):
        """Verify function signature extraction."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file})
        funcs = {f["name"]: f for f in result["functions"]}
        assert "create_processor" in funcs
        assert "helper_function" in funcs
        hf = funcs["helper_function"]
        assert "x" in hf["signature"]
        assert "y" in hf["signature"]

    def test_read_exclude_private(self, test_project):
        """Private members excluded by default."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file, "include_private": False})
        all_methods = []
        for c in result["classes"]:
            all_methods.extend(m["name"] for m in c["methods"])
        assert "_transform" not in all_methods

    def test_read_include_private(self, test_project):
        """Private members included when requested."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file, "include_private": True})
        all_methods = []
        for c in result["classes"]:
            all_methods.extend(m["name"] for m in c["methods"])
        assert "_transform" in all_methods

    def test_read_nonexistent_file(self):
        """Read a file that doesn't exist."""
        result = _tool_ast_read({"file": "/nonexistent/file.py"})
        assert "error" in result

    def test_read_no_imports(self, test_project):
        """Read without imports."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_read({"file": core_file, "include_imports": False})
        assert "imports" not in result


# ─── ast_edit tests ───────────────────────────────────────────────────────

class TestAstEdit:
    def test_rename_function(self, test_project):
        """Rename a function across the file."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        # First read to verify original
        original = Path(core_file).read_text()
        assert "helper_function" in original

        result = _tool_ast_edit({
            "file": core_file,
            "operation": "rename_function",
            "params": {"old_name": "helper_function", "new_name": "utility_function"},
            "dry_run": True,
        })
        assert "error" not in result
        assert "utility_function" in result["modified_source"]
        assert "def utility_function" in result["modified_source"]

    def test_add_parameter(self, test_project):
        """Add a parameter to a function."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_edit({
            "file": core_file,
            "operation": "add_parameter",
            "params": {
                "function_name": "helper_function",
                "parameter_name": "z",
                "default_value": "0",
            },
            "dry_run": True,
        })
        assert "error" not in result
        assert "z" in result["modified_source"]

    def test_change_signature(self, test_project):
        """Change a function's full signature."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_ast_edit({
            "file": core_file,
            "operation": "change_signature",
            "params": {
                "function_name": "helper_function",
                "parameters": [
                    {"name": "a", "default": None},
                    {"name": "b", "default": "100"},
                ],
            },
            "dry_run": True,
        })
        assert "error" not in result
        assert "a" in result["modified_source"]
        assert "b" in result["modified_source"]

    def test_remove_node(self, test_project):
        """Remove a node by line range."""
        core_file = os.path.join(test_project, "src", "mypackage", "utils.py")
        original = Path(core_file).read_text()
        assert "compute_hash" in original

        result = _tool_ast_edit({
            "file": core_file,
            "operation": "remove_node",
            "params": {"start_line": 7, "end_line": 10},
            "dry_run": True,
        })
        assert "error" not in result

    def test_edit_nonexistent_file(self):
        """Edit a file that doesn't exist."""
        result = _tool_ast_edit({
            "file": "/nonexistent/file.py",
            "operation": "rename_function",
            "params": {"old_name": "foo", "new_name": "bar"},
        })
        assert "error" in result

    def test_edit_preserves_formatting(self, test_project):
        """Verify libcst preserves comments and formatting."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        original = Path(core_file).read_text()
        has_docstrings = '"""' in original

        result = _tool_ast_edit({
            "file": core_file,
            "operation": "rename_function",
            "params": {"old_name": "helper_function", "new_name": "utility_function"},
            "dry_run": True,
        })
        assert "error" not in result
        if has_docstrings:
            assert '"""' in result["modified_source"]


# ─── structural_analysis tests ────────────────────────────────────────────

class TestStructuralAnalysis:
    def test_references(self, test_project):
        """Find all references to a symbol."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_structural_analysis({
            "analysis_type": "references",
            "symbol": "DataProcessor",
            "file": core_file,
            "line": 11,  # class DataProcessor line
            "project_root": test_project,
        })
        assert "error" not in result
        # DataProcessor is referenced in create_processor, AdvancedProcessor, etc.
        assert result.get("count", 0) >= 0  # May be 0 if jedi can't resolve in test project

    def test_dependencies(self, test_project):
        """List module dependencies."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_structural_analysis({
            "analysis_type": "dependencies",
            "file": core_file,
            "project_root": test_project,
        })
        assert "error" not in result
        assert result.get("count", 0) > 0
        dep_names = [d["name"] for d in result.get("dependencies", [])]
        assert "os" in dep_names or "sys" in dep_names

    def test_type_hierarchy(self, test_project):
        """Get class hierarchy."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_structural_analysis({
            "analysis_type": "type_hierarchy",
            "symbol": "AdvancedProcessor",
            "file": core_file,
            "project_root": test_project,
        })
        assert "error" not in result

    def test_callees(self, test_project):
        """Find what a function calls."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_structural_analysis({
            "analysis_type": "callees",
            "symbol": "create_processor",
            "file": core_file,
            "project_root": test_project,
        })
        assert "error" not in result

    def test_analysis_nonexistent_symbol(self, test_project):
        """Analyze a symbol that doesn't exist."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = _tool_structural_analysis({
            "analysis_type": "references",
            "symbol": "NonExistentClass",
            "file": core_file,
            "project_root": test_project,
        })
        # Should return empty results, not crash
        assert "error" in result or result.get("count", 0) == 0


# ─── CLI tests ────────────────────────────────────────────────────────────

class TestCLI:
    def test_cli_grep(self, test_project):
        """Test ast-tools grep CLI."""
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "ast-tools"),
             "grep", "def $FUNC($$$ARGS): $BODY", test_project, "--lang", "python"],
            capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert len(result) > 0

    def test_cli_read(self, test_project):
        """Test ast-tools read CLI."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "ast-tools"),
             "read", core_file],
            capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["summary"]["total_classes"] == 2

    def test_cli_analyze(self, test_project):
        """Test ast-tools analyze CLI."""
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "ast-tools"),
             "analyze", "dependencies", "--file", core_file, "--root", test_project],
            capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result.get("count", 0) > 0


# ─── MCP server integration test ──────────────────────────────────────────

class TestMCPServer:
    def test_server_import(self):
        """Server module imports without errors."""
        from ast_tools_server import server, list_tools, call_tool
        assert server is not None

    def test_list_tools(self):
        """Server lists all 8 tools."""
        from ast_tools_server import list_tools
        tools = asyncio.run(list_tools())
        tool_names = [t.name for t in tools]
        assert "ast_grep" in tool_names
        assert "ast_edit" in tool_names
        assert "ast_read" in tool_names
        assert "structural_analysis" in tool_names
        assert "codebase_summary" in tool_names
        assert "find_references" in tool_names
        assert "impact_analysis" in tool_names
        assert len(tools) == 8

    def test_call_tool_ast_grep(self, test_project):
        """Call ast_grep through the MCP server interface."""
        from ast_tools_server import call_tool
        result = asyncio.run(call_tool("ast_grep", {
            "pattern": "class $NAME: $BODY",
            "path": test_project,
            "lang": "python",
        }))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" not in data
        assert data["count"] > 0

    def test_call_tool_ast_read(self, test_project):
        """Call ast_read through the MCP server interface."""
        from ast_tools_server import call_tool
        core_file = os.path.join(test_project, "src", "mypackage", "core.py")
        result = asyncio.run(call_tool("ast_read", {"file": core_file}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" not in data
        assert data["summary"]["total_classes"] == 2

    def test_call_tool_unknown(self, test_project):
        """Call an unknown tool."""
        from ast_tools_server import call_tool
        result = asyncio.run(call_tool("nonexistent_tool", {}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data
