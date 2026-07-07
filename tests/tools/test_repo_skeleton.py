"""Tests for repo_skeleton MCP tool."""

import json
from pathlib import Path

import pytest

from src.ast_tools.tools.repo_skeleton import (
    _build_ascii_tree,
    _collect_structure,
    _detect_project_type,
    _parse_go_deps,
    _parse_node_deps,
    _parse_python_deps,
    _parse_rust_deps,
    _tool_repo_skeleton,
)

# =============================================================================
# Project Type Detection
# =============================================================================


pytestmark = pytest.mark.integration


class TestProjectTypeDetection:
    def test_python_pyproject(self, tmp_path: Path) -> None:
        """Python project with pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"')
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "__init__.py").write_text("")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "python"
        assert confidence >= 0.5

    def test_python_setup_py(self, tmp_path: Path) -> None:
        """Python project with setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup(name='test')")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "python"
        assert confidence >= 0.4

    def test_node_package_json(self, tmp_path: Path) -> None:
        """Node.js project with package.json."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "index.js").write_text("console.log('hi')")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "node"
        assert confidence >= 0.4

    def test_go_mod(self, tmp_path: Path) -> None:
        """Go project with go.mod."""
        (tmp_path / "go.mod").write_text("module example.com/test")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "go"
        assert confidence >= 0.4

    def test_rust_cargo(self, tmp_path: Path) -> None:
        """Rust project with Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "rust"
        assert confidence >= 0.4

    def test_unknown_project(self, tmp_path: Path) -> None:
        """Unknown project type with no recognized files."""
        (tmp_path / "random.txt").write_text("hello")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "unknown"
        assert confidence == 0.0

    def test_python_with_tsconfig_not_node(self, tmp_path: Path) -> None:
        """Python project with stray tsconfig.json shouldn't override. Both get points."""
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "tsconfig.json").write_text("{}")
        (tmp_path / "app.py").write_text("")
        proj_type, confidence, _indicators = _detect_project_type(tmp_path)
        assert proj_type == "python"  # pyproject.toml (3) > tsconfig (1) + *.py (1)
        assert confidence >= 0.5


# =============================================================================
# ASCII Tree Generation
# =============================================================================


class TestAsciiTree:
    def test_basic_tree(self, tmp_path: Path) -> None:
        """Basic directory tree."""
        srcdir = tmp_path / "src"
        srcdir.mkdir(parents=True)
        (srcdir / "main.py").write_text("")
        (tmp_path / "README.md").write_text("# test")
        tree = _build_ascii_tree(tmp_path)
        assert tree.startswith(tmp_path.name + "/")
        assert "README.md" in tree

    def test_max_depth(self, tmp_path: Path) -> None:
        """Tree respects max_depth."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f"
        deep.mkdir(parents=True)
        tree = _build_ascii_tree(tmp_path, max_depth=2)
        lines = tree.splitlines()
        depth_lines = [line for line in lines if "└──" in line or "├──" in line]
        max_nesting = max((len(line) for line in depth_lines), default=0)
        assert max_nesting < 30  # shallow nesting

    def test_hidden_dirs_excluded(self, tmp_path: Path) -> None:
        """Hidden directories (dot-prefixed) are excluded."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "config").write_text("")
        (tmp_path / "visible.txt").write_text("")
        tree = _build_ascii_tree(tmp_path)
        assert ".git" not in tree
        assert "visible.txt" in tree

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory produces root-only tree."""
        tree = _build_ascii_tree(tmp_path)
        lines = tree.splitlines()
        assert len(lines) == 1
        assert lines[0] == tmp_path.name + "/"

    def test_dirs_sorted_first(self, tmp_path: Path) -> None:
        """Directories come before files in tree."""
        (tmp_path / "zeta.txt").write_text("")
        sub = tmp_path / "aardvark"
        sub.mkdir(parents=True)
        (sub / "x.txt").write_text("")
        tree = _build_ascii_tree(tmp_path)
        aardvark_pos = tree.index("aardvark/")
        zeta_pos = tree.index("zeta.txt")
        assert aardvark_pos < zeta_pos, "dirs should appear before files"


# =============================================================================
# Dependency Parsing
# =============================================================================


class TestDependencyParsing:
    def test_python_deps(self, tmp_path: Path) -> None:
        """Parse Python pyproject.toml dependencies."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test"
version = "0.1.0"
dependencies = [
    "requests>=2.28",
    "click>=8.0",
]
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]
""")
        deps = _parse_python_deps(tmp_path)
        assert "requests>=2.28" in deps["direct"]
        assert "click>=8.0" in deps["direct"]
        assert "pytest>=8.0" in deps["dev"]
        assert "ruff>=0.4" in deps["dev"]

    def test_python_no_deps(self, tmp_path: Path) -> None:
        """Python project with no dependencies file yields empty deps."""
        deps = _parse_python_deps(tmp_path)
        assert deps == {"direct": [], "dev": []}

    def test_node_deps(self, tmp_path: Path) -> None:
        """Parse Node.js package.json dependencies."""
        pkg = tmp_path / "package.json"
        pkg.write_text(
            json.dumps(
                {
                    "dependencies": {"express": "^4.18", "lodash": "^4.17"},
                    "devDependencies": {"jest": "^29", "typescript": "^5.0"},
                }
            )
        )
        deps = _parse_node_deps(tmp_path)
        assert "express" in deps["direct"]
        assert "lodash" in deps["direct"]
        assert "jest" in deps["dev"]
        assert "typescript" in deps["dev"]

    def test_go_deps(self, tmp_path: Path) -> None:
        """Parse Go go.mod dependencies."""
        gomod = tmp_path / "go.mod"
        gomod.write_text("""
module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.4
)
""")
        deps = _parse_go_deps(tmp_path)
        assert "github.com/gin-gonic/gin" in deps["direct"]
        assert "github.com/stretchr/testify" in deps["direct"]

    def test_rust_deps(self, tmp_path: Path) -> None:
        """Parse Rust Cargo.toml dependencies."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text("""[package]
name = "test"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
""")
        deps = _parse_rust_deps(tmp_path)
        assert "serde" in deps["direct"]
        assert "tokio" in deps["direct"]
        assert "criterion" in deps["dev"]

    def test_no_deps_for_unknown(self, tmp_path: Path) -> None:
        """Unknown project type yields empty deps."""
        (tmp_path / "readme.txt").write_text("")
        result = _tool_repo_skeleton(
            {
                "root_path": str(tmp_path),
                "generate_deps": True,
            }
        )
        assert result["project_type"] == "unknown"
        assert result["dependencies"]["direct"] == []
        assert result["dependencies"]["dev"] == []


# =============================================================================
# Structure Collection
# =============================================================================


class TestStructureCollection:
    def test_detects_entry_points(self, tmp_path: Path) -> None:
        """Structure identifies entry point files."""
        srcdir = tmp_path / "src"
        srcdir.mkdir(parents=True)
        (srcdir / "main.py").write_text("print('hi')")
        structure = _collect_structure(tmp_path)
        assert any("main.py" in ep for ep in structure["entry_points"])

    def test_detects_test_files(self, tmp_path: Path) -> None:
        """Structure identifies test files."""
        testdir = tmp_path / "tests"
        testdir.mkdir(parents=True)
        (testdir / "test_foo.py").write_text("def test(): pass")
        structure = _collect_structure(tmp_path, include_tests=True)
        assert any("test_foo" in tf for tf in structure["test_files"])

    def test_build_config(self, tmp_path: Path) -> None:
        """Structure identifies build config files."""
        (tmp_path / "pyproject.toml").write_text("")
        structure = _collect_structure(tmp_path)
        key_files = [kf["path"] for kf in structure["key_files"]]
        assert "pyproject.toml" in key_files

    def test_skip_node_modules(self, tmp_path: Path) -> None:
        """node_modules directory is excluded from structure."""
        nm_dir = tmp_path / "node_modules" / "some_pkg"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.js").write_text("")
        structure = _collect_structure(tmp_path)
        dir_paths = [d["path"] for d in structure["directories"]]
        assert all("node_modules" not in p for p in dir_paths)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    def test_full_tool_pipeline(self, tmp_path: Path) -> None:
        """Full _tool_repo_skeleton pipeline for a Python project."""
        # Create Python project
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-project"
version = "0.1.0"
dependencies = ["requests>=2.28", "click>=8.0"]
[project.optional-dependencies]
dev = ["pytest>=8.0"]
""")
        srcdir = tmp_path / "src" / "mypkg"
        srcdir.mkdir(parents=True)
        (tmp_path / "src" / "__init__.py").write_text("")
        (srcdir / "__init__.py").write_text("")
        (srcdir / "main.py").write_text("def main(): pass")
        testdir = tmp_path / "tests"
        testdir.mkdir(parents=True)
        (testdir / "test_main.py").write_text("def test(): pass")
        (tmp_path / "README.md").write_text("# Test")

        result = _tool_repo_skeleton(
            {
                "root_path": str(tmp_path),
                "max_depth": 5,
                "include_tests": True,
                "include_configs": True,
                "generate_deps": True,
            }
        )

        assert result["project_type"] == "python"
        assert result["confidence"] > 0.8
        assert len(result["detected_indicators"]) >= 1
        assert result["structure"]["directories"]
        assert result["structure"]["key_files"]
        assert any("test_main" in tf for tf in result["structure"]["test_files"])
        assert "requests>=2.28" in result["dependencies"]["direct"]
        assert "pytest>=8.0" in result["dependencies"]["dev"]
        assert tmp_path.name in result["tree_ascii"]
        assert "project" in result["summary"]

    def test_node_project_full(self, tmp_path: Path) -> None:
        """Full pipeline for a Node.js project."""
        pkg = tmp_path / "package.json"
        pkg.write_text(
            json.dumps(
                {
                    "dependencies": {"express": "^4.18"},
                    "devDependencies": {"jest": "^29"},
                }
            )
        )
        (tmp_path / "index.js").write_text("console.log('hi')")
        (tmp_path / "README.md").write_text("# Node Project")

        result = _tool_repo_skeleton(
            {
                "root_path": str(tmp_path),
                "max_depth": 3,
                "generate_deps": True,
            }
        )

        assert result["project_type"] == "node"
        assert result["confidence"] > 0.4
        assert "express" in result["dependencies"]["direct"]
        assert "jest" in result["dependencies"]["dev"]

    def test_go_project_full(self, tmp_path: Path) -> None:
        """Full pipeline for a Go project."""
        (tmp_path / "go.mod").write_text("""
module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
)
""")
        (tmp_path / "main.go").write_text("package main\nfunc main() {}")

        result = _tool_repo_skeleton(
            {
                "root_path": str(tmp_path),
                "max_depth": 3,
                "generate_deps": True,
            }
        )

        assert result["project_type"] == "go"
        assert "github.com/gin-gonic/gin" in result["dependencies"]["direct"]

    def test_rust_project_full(self, tmp_path: Path) -> None:
        """Full pipeline for a Rust project."""
        (tmp_path / "Cargo.toml").write_text("""[package]
name = "test"
version = "0.1.0"

[dependencies]
serde = "1.0"

[dev-dependencies]
criterion = "0.5"
""")
        srcdir = tmp_path / "src"
        srcdir.mkdir(parents=True)
        (srcdir / "main.rs").write_text("fn main() {}")

        result = _tool_repo_skeleton(
            {
                "root_path": str(tmp_path),
                "max_depth": 3,
                "generate_deps": True,
            }
        )

        assert result["project_type"] == "rust"
        assert "serde" in result["dependencies"]["direct"]
        assert "criterion" in result["dependencies"]["dev"]

    def test_error_nonexistent_path(self) -> None:
        """Non-existent path returns error."""
        result = _tool_repo_skeleton({"root_path": "/nonexistent/path/xyz123"})
        assert "error" in result
        assert result["error_code"] == "NOT_FOUND"

    def test_error_file_not_dir(self, tmp_path: Path) -> None:
        """File path (not dir) returns error."""
        f = tmp_path / "file.txt"
        f.write_text("")
        result = _tool_repo_skeleton({"root_path": str(f)})
        assert "error" in result
        assert result["error_code"] == "NOT_A_DIR"

    def test_real_ast_tools(self) -> None:
        """Integration test: run on actual ast-tools repo."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        result = _tool_repo_skeleton(
            {
                "root_path": str(repo_root),
                "max_depth": 3,
                "generate_deps": True,
            }
        )
        assert result["project_type"] == "python"
        assert result["confidence"] >= 0.5
        assert result["structure"]["directories"]
        assert "pyproject.toml" in str(result["structure"]["key_files"])
        assert result["dependencies"]["direct"]
        assert "ast_tools" in result["summary"]
        assert len(result["tree_ascii"]) > 50
