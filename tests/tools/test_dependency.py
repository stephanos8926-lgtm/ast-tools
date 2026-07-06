"""Tests for dependency graph analysis tools."""

import tempfile
from pathlib import Path

import pytest

from ast_tools.tools.dependency import (
    build_import_graph,
    find_circular_dependencies,
    find_dead_code,
    get_dependency_chain,
    get_external_dependencies,
)

pytestmark = pytest.mark.integration

class TestBuildImportGraph:
    """Test import graph building."""

    def test_build_graph_simple(self):
        """Test building graph for simple project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create module_a.py
            Path(tmpdir, "module_a.py").write_text("""
import module_b
from module_c import something
""")
            # Create module_b.py
            Path(tmpdir, "module_b.py").write_text("""
import module_c
""")
            # Create module_c.py
            Path(tmpdir, "module_c.py").write_text("""
# No imports
""")

            graph = build_import_graph(tmpdir)
            assert "module_a" in graph
            assert "module_b" in graph["module_a"]
            assert "module_c" in graph["module_a"]
            assert "module_c" in graph["module_b"]


class TestCircularDependencies:
    """Test circular dependency detection."""

    def test_no_cycles(self):
        """Test project without cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.py").write_text("import b")
            Path(tmpdir, "b.py").write_text("import c")
            Path(tmpdir, "c.py").write_text("pass")

            cycles = find_circular_dependencies(tmpdir)
            assert len(cycles) == 0

    def test_simple_cycle(self):
        """Test detection of A -> B -> A cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.py").write_text("import b")
            Path(tmpdir, "b.py").write_text("import a")

            cycles = find_circular_dependencies(tmpdir)
            assert len(cycles) > 0
            assert "severity" in cycles[0]

    def test_longer_cycle(self):
        """Test detection of A -> B -> C -> A cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.py").write_text("import b")
            Path(tmpdir, "b.py").write_text("import c")
            Path(tmpdir, "c.py").write_text("import a")

            cycles = find_circular_dependencies(tmpdir)
            assert len(cycles) > 0


class TestExternalDependencies:
    """Test external dependency detection."""

    def test_stdlib_only(self):
        """Test file with only stdlib imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, "test.py")
            test_file.write_text("""
import os
import sys
from pathlib import Path
""")

            result = get_external_dependencies(str(test_file), tmpdir)
            assert result["external_count"] == 0

    def test_third_party_imports(self):
        """Test detection of third-party imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, "test.py")
            test_file.write_text("""
import requests
from flask import Flask
import numpy as np
""")

            result = get_external_dependencies(str(test_file), tmpdir)
            assert result["external_count"] > 0
            modules = [e["module"] for e in result["externals"]]
            assert "requests" in modules
            assert "flask" in modules
            assert "numpy" in modules


class TestDeadCode:
    """Test dead code detection."""

    def test_no_dead_code(self):
        """Test project where all code is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("""
from utils import helper
helper()
""")
            Path(tmpdir, "utils.py").write_text("""
def helper():
    pass
""")

            result = find_dead_code(tmpdir)
            # helper is used, so should not be in dead code
            dead_funcs = result["dead_functions"]
            assert all(f["name"] != "helper" for f in dead_funcs)

    def test_dead_function(self):
        """Test detection of unused function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("""
def main():
    pass
""")
            Path(tmpdir, "utils.py").write_text("""
def unused_function():
    pass
""")

            result = find_dead_code(tmpdir)
            # unused_function should be detected
            dead_funcs = result["dead_functions"]
            assert any(f["name"] == "unused_function" for f in dead_funcs)


class TestDependencyChain:
    """Test dependency chain analysis."""

    def test_dependency_chain(self):
        """Test getting dependency chain for a symbol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("""
import os

def main():
    print(os.getcwd())

def helper():
    pass
""")

            # Temporarily move to the temp dir
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = get_dependency_chain(
                    symbol="main",
                    file_path="main.py",
                    project_root=tmpdir,
                    direction="upstream",
                    depth=2,
                )

                assert result["symbol"] == "main"
                assert result["file"] == "main.py"
            finally:
                os.chdir(old_cwd)


class TestIntegration:
    """Integration tests for dependency analysis."""

    def test_full_workflow(self):
        """Test complete dependency analysis workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small project structure
            (Path(tmpdir) / "app").mkdir()

            (Path(tmpdir) / "app" / "__init__.py").write_text("")
            (Path(tmpdir) / "app" / "main.py").write_text("""
from app.utils import process
from app.models import Data

def run():
    process(Data())
""")
            (Path(tmpdir) / "app" / "utils.py").write_text("""
from app.models import Data

def process(data: Data):
    return data.value
""")
            (Path(tmpdir) / "app" / "models.py").write_text("""
class Data:
    def __init__(self):
        self.value = 42
""")

            # Test import graph
            graph = build_import_graph(tmpdir)
            assert "app.main" in graph

            # Test for cycles (should be none)
            cycles = find_circular_dependencies(tmpdir)
            assert len(cycles) == 0

            # Test dead code (Data class is used)
            result = find_dead_code(tmpdir)
            assert not any(f["name"] == "Data" for f in result["dead_classes"])
