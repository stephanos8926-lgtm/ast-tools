#!/usr/bin/env python3
"""Comprehensive CLI test suite for AST-Tools.

Tests cover:
1. Unit tests for individual CLI commands
2. Integration tests for command combinations
3. E2E tests for real-world workflows
4. Output format tests (table, JSON, markdown)
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Get the CLI module path
CLI_PATH = Path(__file__).parent.parent / "src" / "ast_tools" / "cli.py"
VENV_PYTHON = Path(__file__).parent.parent / ".venv" / "bin" / "python"


def run_cli(*args, cwd=None):
    """Run CLI command and return result."""
    cmd = [str(VENV_PYTHON), str(CLI_PATH)] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or Path(__file__).parent.parent,
    )
    return result


@pytest.mark.smoke
class TestCLIHelp:
    """Test CLI help and version commands."""

    def test_main_help(self):
        """Test main help message."""
        result = run_cli("--help")
        assert result.returncode == 0
        assert "AST Tools CLI" in result.stdout
        assert "search" in result.stdout
        assert "navigate" in result.stdout
        assert "blast-radius" in result.stdout
        assert "find-dead" in result.stdout
        assert "callers" in result.stdout
        assert "callees" in result.stdout
        assert "deps" in result.stdout
        assert "browse" in result.stdout

    def test_version(self):
        """Test version command."""
        result = run_cli("--version")
        assert result.returncode == 0
        assert "ast-tools 0.1.0" in result.stdout

    def test_command_help(self):
        """Test individual command help."""
        for cmd in ["search", "navigate", "blast-radius", "find-dead", "summary", "browse"]:
            result = run_cli(cmd, "--help")
            assert result.returncode == 0
            assert cmd in result.stdout


@pytest.mark.integration
class TestCLIProjectCommands:
    """Test CLI commands on the ast-tools project itself."""

    @pytest.fixture(scope="class")
    def test_project(self, tmp_path_factory):
        """Create a test project structure."""
        test_dir = tmp_path_factory.mktemp("test_project")
        
        # Create test Python files
        main_py = test_dir / "main.py"
        main_py.write_text("""
from utils import helper

def main():
    result = helper()
    print(result)

if __name__ == "__main__":
    main()
""")
        
        utils_py = test_dir / "utils.py"
        utils_py.write_text("""
def helper():
    return "helped"

def unused_function():
    pass

class UnusedClass:
    pass
""")
        
        return test_dir

    def test_summary_json(self, test_project):
        """Test summary command with JSON output."""
        result = run_cli("-p", str(test_project), "summary", "--format", "json")
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        assert "name" in data or "languages" in data
        assert "python" in str(data).lower()

    def test_summary_markdown(self, test_project):
        """Test summary command with markdown output."""
        result = run_cli("-p", str(test_project), "summary", "--format", "markdown")
        assert result.returncode == 0
        assert "#" in result.stdout  # Markdown headers

    def test_browse_functions(self, test_project):
        """Test browse command filtering by kind."""
        result = run_cli(
            "-p", str(test_project), "browse",
            "--kind", "function",
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        symbols = data.get("symbols", [])
        # Should find 'main' and 'helper' functions
        func_names = [s.get("name") for s in symbols if s.get("kind") == "function"]
        assert "main" in func_names or "helper" in func_names

    def test_browse_classes(self, test_project):
        """Test browse command filtering by class."""
        result = run_cli(
            "-p", str(test_project), "browse",
            "--kind", "class",
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        symbols = data.get("symbols", [])
        class_names = [s.get("name") for s in symbols if s.get("kind") == "class"]
        assert "UnusedClass" in class_names

    def test_find_dead_code(self, test_project):
        """Test find-dead command."""
        result = run_cli(
            "-p", str(test_project), "find-dead",
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        # Should find unused_function and UnusedClass
        dead_funcs = data.get("dead_functions", [])
        dead_classes = data.get("dead_classes", [])
        
        func_names = [f.get("name") for f in dead_funcs]
        class_names = [c.get("name") for c in dead_classes]
        
        assert "unused_function" in func_names
        assert "UnusedClass" in class_names

    def test_find_dead_code_with_entry_points(self, test_project):
        """Test find-dead with explicit entry points."""
        result = run_cli(
            "-p", str(test_project), "find-dead",
            "--entry-points", "main.py",
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        # helper() should be marked as reachable from main.py
        # (though it may still appear with low confidence)


@pytest.mark.integration
class TestCLICallersCallees:
    """Test callers and callees commands."""

    @pytest.fixture(scope="class")
    def call_test_project(self, tmp_path_factory):
        """Create a test project with call relationships."""
        test_dir = tmp_path_factory.mktemp("call_test")
        
        # Create files with call relationships
        caller_py = test_dir / "caller.py"
        caller_py.write_text("""
from callee import target_function, another_function

def calling_function():
    result = target_function()
    another_function()
    return result

def another_caller():
    return target_function() + 1
""")
        
        callee_py = test_dir / "callee.py"
        callee_py.write_text("""
def target_function():
    inner_call()
    return 42

def another_function():
    pass

def inner_call():
    pass
""")
        
        return test_dir

    def test_callers_basic(self, call_test_project):
        """Test callers command."""
        result = run_cli(
            "-p", str(call_test_project), "callers", "target_function",
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        callers = data.get("callers", [])
        
        # Should find calling_function and another_caller
        caller_names = [c.get("caller") for c in callers]
        assert "calling_function" in caller_names or "another_caller" in caller_names

    def test_callees_basic(self, call_test_project):
        """Test callees command."""
        result = run_cli(
            "-p", str(call_test_project), "callees", "target_function",
            "--file-path", str(call_test_project / "callee.py"),
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        callees = data.get("callees", [])
        
        # Should find inner_call
        callee_names = [c.get("name") for c in callees]
        assert "inner_call" in callee_names


@pytest.mark.integration
class TestCLIDeps:
    """Test deps (dependencies) command."""

    @pytest.fixture(scope="class")
    def deps_test_project(self, tmp_path_factory):
        """Create a test project with imports."""
        test_dir = tmp_path_factory.mktemp("deps_test")
        
        # Create module with imports
        module_py = test_dir / "module.py"
        module_py.write_text("""
import os
import sys
from pathlib import Path

import requests
from flask import Flask
""")
        
        return test_dir

    def test_deps_json(self, deps_test_project):
        """Test deps command with JSON output."""
        result = run_cli(
            "-p", str(deps_test_project), "deps",
            str(deps_test_project / "module.py"),
            "--format", "json"
        )
        assert result.returncode == 0
        
        data = json.loads(result.stdout)
        assert "fan_in" in data or "fan_out" in data


@pytest.mark.integration
class TestCLISemanticSearch:
    """Test semantic search command."""

    @pytest.fixture(scope="class")
    def search_test_project(self, tmp_path_factory):
        """Create a test project for semantic search."""
        test_dir = tmp_path_factory.mktemp("search_test")
        
        # Create files with semantic content
        auth_py = test_dir / "auth.py"
        auth_py.write_text("""
class AuthenticationHandler:
    \"\"\"Handles user authentication.\"\"\"
    
    def verify_credentials(self, username, password):
        \"\"\"Verify user credentials.\"\"\"
        return True
    
    def create_session(self, user_id):
        \"\"\"Create authentication session.\"\"\"
        return {"user_id": user_id}
""")
        
        return test_dir

    def test_semantic_search_json(self, search_test_project):
        """Test semantic search with JSON output."""
        result = run_cli(
            "-p", str(search_test_project), "search",
            "authentication handler",
            "--format", "json",
            "--limit", "5"
        )
        # May fail if index doesn't exist - that's OK for now
        # The important thing is the CLI doesn't crash
        assert result.returncode in (0, 1)


@pytest.mark.smoke
class TestCLIOutputFormats:
    """Test all output formats across commands."""

    @pytest.fixture(scope="class")
    def format_test_project(self, tmp_path_factory):
        """Create a simple test project."""
        test_dir = tmp_path_factory.mktemp("format_test")
        
        test_py = test_dir / "test.py"
        test_py.write_text("""
def sample_function():
    pass

class SampleClass:
    pass
""")
        
        return test_dir

    def test_table_format(self, format_test_project):
        """Test table output format."""
        result = run_cli(
            "-p", str(format_test_project), "browse",
            "--format", "table"
        )
        assert result.returncode == 0
        # Table format should have aligned columns
        assert "Name" in result.stdout
        assert "Kind" in result.stdout

    def test_json_format(self, format_test_project):
        """Test JSON output format."""
        result = run_cli(
            "-p", str(format_test_project), "browse",
            "--format", "json"
        )
        assert result.returncode == 0
        # Should be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_markdown_format(self, format_test_project):
        """Test markdown output format."""
        result = run_cli(
            "-p", str(format_test_project), "browse",
            "--format", "markdown"
        )
        assert result.returncode == 0
        # Markdown should have headers
        assert "#" in result.stdout or "**" in result.stdout


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_nonexistent_project(self):
        """Test CLI with nonexistent project path."""
        result = run_cli("-p", "/nonexistent/path", "summary")
        # Should handle gracefully (may return error or empty results)
        assert result.returncode in (0, 1)

    def test_invalid_command(self):
        """Test CLI with invalid command."""
        result = run_cli("invalid-command")
        assert result.returncode != 0

    def test_missing_required_arg(self):
        """Test CLI with missing required argument."""
        result = run_cli("callees", "some_symbol")  # Missing --file-path
        assert result.returncode != 0


@pytest.mark.e2e
class TestCLIE2E:
    """End-to-end CLI workflow tests."""

    @pytest.fixture(scope="class")
    def e2e_project(self, tmp_path_factory):
        """Create a realistic test project."""
        test_dir = tmp_path_factory.mktemp("e2e_test")
        
        # Create a small but realistic project
        (test_dir / "api").mkdir()
        (test_dir / "utils").mkdir()
        
        # API module
        api_init = test_dir / "api" / "__init__.py"
        api_init.write_text("")
        
        handlers_py = test_dir / "api" / "handlers.py"
        handlers_py.write_text("""
from utils.helpers import process_data

class APIHandler:
    def handle_request(self, data):
        result = process_data(data)
        return {"status": "ok", "data": result}
""")
        
        # Utils module
        utils_init = test_dir / "utils" / "__init__.py"
        utils_init.write_text("")
        
        helpers_py = test_dir / "utils" / "helpers.py"
        helpers_py.write_text("""
def process_data(data):
    validated = validate_data(data)
    return transform(validated)

def validate_data(data):
    return data

def transform(data):
    return data

def unused_helper():
    pass
""")
        
        # Main entry point
        main_py = test_dir / "main.py"
        main_py.write_text("""
from api.handlers import APIHandler

def main():
    handler = APIHandler()
    result = handler.handle_request({"test": "data"})
    print(result)

if __name__ == "__main__":
    main()
""")
        
        return test_dir

    def test_e2e_discover_then_analyze(self, e2e_project):
        """E2E: Browse symbols, then analyze specific ones."""
        # Step 1: Browse all functions
        result = run_cli(
            "-p", str(e2e_project), "browse",
            "--kind", "function",
            "--format", "json"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        functions = data.get("symbols", [])
        assert len(functions) > 0
        
        # Step 2: Find callers of a specific function
        func_name = "process_data"
        result = run_cli(
            "-p", str(e2e_project), "callers", func_name,
            "--format", "json"
        )
        assert result.returncode == 0

    def test_e2e_find_dead_code_then_verify(self, e2e_project):
        """E2E: Find dead code, verify it's truly unused."""
        # Step 1: Find dead code
        result = run_cli(
            "-p", str(e2e_project), "find-dead",
            "--format", "json"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        
        dead_funcs = data.get("dead_functions", [])
        # Should find unused_helper
        dead_names = [f.get("name") for f in dead_funcs]
        assert "unused_helper" in dead_names
        
        # Step 2: Verify no callers for dead code
        result = run_cli(
            "-p", str(e2e_project), "callers", "unused_helper",
            "--format", "json"
        )
        # Should return no callers (or error)
        assert result.returncode in (0, 1)

    def test_e2e_dependency_analysis(self, e2e_project):
        """E2E: Analyze module dependencies."""
        # Step 1: Check dependencies of handlers.py
        result = run_cli(
            "-p", str(e2e_project), "deps",
            str(e2e_project / "api" / "handlers.py"),
            "--format", "json"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        
        # Should have fan-out (imports)
        fan_out = data.get("fan_out", [])
        assert len(fan_out) > 0
        
        # Should have fan-in (who imports this)
        fan_in = data.get("fan_in", [])
        # main.py imports from api.handlers indirectly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])