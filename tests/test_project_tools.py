#!/usr/bin/env python3
"""TDD tests for project_tools.py fixes (Phase 0 Batch B)."""

import json
import sys
import tempfile
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ast_tools._project_tools import (
    _detect_entry_points,
    _detect_test_framework,
    _extract_languages,
    generate_project_json,
    project_info_summary,
    project_init,
    project_verify,
)

# ─── Helpers ─────────────────────────────────────────────────────────────


def _make_project(base: str, layout="flat", files=None):
    """Create a temp project. layout='flat' or 'src'."""
    root = Path(base)
    pkg_root = root / "src" / "mypkg" if layout == "src" else root / "mypkg"
    pkg_root.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    (pkg_root / "__init__.py").write_text('"""Package."""\n')

    if files:
        for rel_path, content in files.items():
            fp = root / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

    # Create a .git dir so find_project_root works
    (root / ".git").mkdir(exist_ok=True)
    return root


# ─── Bug 5: Dependency graph for src/ layout ─────────────────────────────


class TestDependencyGraphSrcLayout:
    """Bug 5: dependency graph should resolve imports in src/ layout."""

    def test_flat_layout_deps(self):
        """Flat layout: direct imports should be resolved."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "from mypkg.core import Foo\n",
                },
            )
            _ = project_init(root)
            # Read dependency graph
            dep_file = root / "references" / "dependency_graph.json"
            assert dep_file.exists()
            dep_graph = json.loads(dep_file.read_text())
            # main.py should depend on core.py
            main_deps = dep_graph.get("mypkg/main.py", [])
            assert "mypkg/core.py" in main_deps, f"Expected mypkg/core.py in deps, got {main_deps}"

    def test_src_layout_deps(self):
        """Src layout: imports using package name should resolve to src/ paths."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="src",
                files={
                    "src/mypkg/core.py": "class Foo:\n    pass\n",
                    "src/mypkg/main.py": "from mypkg.core import Foo\n",
                },
            )
            _ = project_init(root)
            dep_file = root / "references" / "dependency_graph.json"
            assert dep_file.exists()
            dep_graph = json.loads(dep_file.read_text())
            main_deps = dep_graph.get("src/mypkg/main.py", [])
            assert "src/mypkg/core.py" in main_deps, (
                f"Expected src/mypkg/core.py in deps, got {main_deps}"
            )

    def test_relative_imports(self):
        """Relative imports should be resolved."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="src",
                files={
                    "src/mypkg/core.py": "class Foo:\n    pass\n",
                    "src/mypkg/main.py": "from .core import Foo\n",
                },
            )
            _ = project_init(root)
            dep_file = root / "references" / "dependency_graph.json"
            dep_graph = json.loads(dep_file.read_text())
            main_deps = dep_graph.get("src/mypkg/main.py", [])
            assert "src/mypkg/core.py" in main_deps, (
                f"Expected src/mypkg/core.py in deps, got {main_deps}"
            )

    def test_parent_relative_imports(self):
        """Parent relative imports (from .. import x) should resolve."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="src",
                files={
                    "src/mypkg/core/base.py": "class Foo:\n    pass\n",
                    "src/mypkg/extra/main.py": "from ..core.base import Foo\n",
                },
            )
            _ = project_init(root)
            dep_file = root / "references" / "dependency_graph.json"
            dep_graph = json.loads(dep_file.read_text())
            main_deps = dep_graph.get("src/mypkg/extra/main.py", [])
            assert "src/mypkg/core/base.py" in main_deps, (
                f"Expected src/mypkg/core/base.py in deps, got {main_deps}"
            )


# ─── Bug 6: project_verify output bloat ──────────────────────────────────


class TestProjectVerifyOutput:
    """Bug 6: project_verify should return diffs only by default."""

    def test_ok_status_small_output(self):
        """When status is 'ok', output should be <500 bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            # Add .gitignore to exclude generated files from scanning
            (root / ".gitignore").write_text("references/\nproject.json\n*.json\n")
            # First init to create project.json
            project_init(root)
            # Now verify — should be 'ok'
            result = project_verify(root)
            assert result["status"] == "ok", (
                f"Expected ok, got {result['status']}: {result['diffs']}"
            )
            output = json.dumps(result)
            assert len(output) < 500, f"Output too large: {len(output)} bytes"

    def test_stale_has_diffs_not_full_copies(self):
        """When stale, output should have diffs, not full committed+generated copies by default."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            (root / ".gitignore").write_text("references/\nproject.json\n")
            project_init(root)
            # Modify a file to make it stale
            (root / "mypkg" / "core.py").write_text("class Foo:\n    pass\nclass Bar:\n    pass\n")
            result = project_verify(root)
            assert result["status"] == "stale"
            assert "diffs" in result
            assert len(result["diffs"]) > 0
            # Default: no full committed/generated copies
            assert "committed" not in result or result.get("committed") is None
            assert "generated" not in result or result.get("generated") is None

    def test_full_true_includes_copies(self):
        """When full=True, output should include committed and generated."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)
            (root / "mypkg" / "core.py").write_text("class Foo:\n    pass\nclass Bar:\n    pass\n")
            result = project_verify(root, full=True)
            assert result["status"] == "stale"
            assert "committed" in result
            assert "generated" in result

    def test_missing_status(self):
        """When project.json doesn't exist, status should be 'missing'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = project_verify(root)
            assert result["status"] == "missing"


# ─── Bug 7: Test framework detection ────────────────────────────────────


class TestFrameworkDetection:
    """Bug 7: _detect_test_framework should detect pytest via conftest.py and imports."""

    def test_conftest_presence(self):
        """If conftest.py exists, detect pytest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "tests/conftest.py": "# pytest config\n",
                    "tests/test_core.py": "def test_foo():\n    pass\n",
                },
            )
            framework, count, _cmd = _detect_test_framework(root)
            assert framework == "pytest", f"Expected pytest, got {framework}"
            assert count >= 1

    def test_pytest_in_pyproject(self):
        """If pyproject.toml has pytest, detect it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "pyproject.toml": "[tool.pytest.ini_options]\naddopts = '-q'\n",
                    "tests/test_core.py": "def test_foo():\n    pass\n",
                },
            )
            framework, _count, _cmd = _detect_test_framework(root)
            assert framework == "pytest"

    def test_pytest_import_in_test_file(self):
        """If test files import pytest, detect it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "tests/test_core.py": "import pytest\n\ndef test_foo():\n    pass\n",
                },
            )
            framework, _count, _cmd = _detect_test_framework(root)
            assert framework == "pytest"

    def test_unknown_when_no_tests(self):
        """If no test files, return unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            framework, count, _cmd = _detect_test_framework(root)
            assert framework == "unknown"
            assert count == 0


# ─── Bug 8: Entry point detection ───────────────────────────────────────


class TestEntryPointDetection:
    """Bug 8: _detect_entry_points should detect main, argparse, __name__==__main__."""

    def test_def_main(self):
        """Should detect def main() as entry point."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "def main():\n    pass\n",
                },
            )
            entries = _detect_entry_points(root)
            assert any("main" in e for e in entries), f"Expected main entry, got {entries}"

    def test_if_name_main(self):
        """Should detect if __name__ == '__main__' blocks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/run.py": "import sys\n\nif __name__ == '__main__':\n    print('hello')\n",
                },
            )
            entries = _detect_entry_points(root)
            assert any("run" in e for e in entries), f"Expected run entry, got {entries}"

    def test_argparse_import(self):
        """Should detect argparse imports as CLI tools."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/cli.py": "import argparse\n\ndef main():\n    pass\n",
                },
            )
            entries = _detect_entry_points(root)
            assert any("cli" in e for e in entries), f"Expected cli entry, got {entries}"

    def test_project_scripts(self):
        """Should still detect [project.scripts] from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "pyproject.toml": "[project.scripts]\nmytool = 'mypkg.core:main'\n",
                },
            )
            entries = _detect_entry_points(root)
            assert any("mytool" in e or "mypkg.core:main" in e for e in entries), (
                f"Expected mytool entry, got {entries}"
            )


# ─── Bug 9: Language detection beyond code ───────────────────────────────


class TestLanguageDetection:
    """Bug 9: _extract_languages should count config/doc files."""

    def test_markdown_detected(self):
        """Should detect .md files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "README.md": "# Hello\n",
                },
            )
            langs = _extract_languages(root)
            # New format: {all: {...}, code: {...}, config: {...}}
            all_langs = langs.get("all", {})
            assert "markdown" in all_langs, f"Expected markdown, got {list(all_langs.keys())}"

    def test_yaml_toml_json_detected(self):
        """Should detect .yaml, .toml, .json files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "config.yaml": "key: value\n",
                    "pyproject.toml": "[project]\nname='x'\n",
                    "data.json": "{}\n",
                },
            )
            langs = _extract_languages(root)
            all_langs = langs.get("all", {})
            assert "yaml" in all_langs, f"Expected yaml, got {list(all_langs.keys())}"
            assert "toml" in all_langs, f"Expected toml, got {list(all_langs.keys())}"
            assert "json" in all_langs, f"Expected json, got {list(all_langs.keys())}"

    def test_code_languages_still_work(self):
        """Existing code language detection should still work."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "script.js": "var x = 1;\n",
                },
            )
            langs = _extract_languages(root)
            all_langs = langs.get("all", {})
            assert "python" in all_langs
            assert "javascript" in all_langs

    def test_code_and_config_separate(self):
        """generate_project_json should report code_languages and config_languages separately."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "README.md": "# Hello\n",
                },
            )
            data = generate_project_json(root)
            assert "code_languages" in data or "languages" in data
            # At minimum, python should be in languages
            langs = data.get("languages", {})
            # languages is now {all:..., code:..., config:...} or flat
            if "all" in langs:
                assert "python" in langs["all"]
            else:
                assert "python" in langs


# ─── Bug 10: tree-sitter backend ─────────────────────────────────────────


class TestTreeSitterBackend:
    """Bug 10: tree-sitter backend for ast_grep and ast_read."""

    def test_ts_backend_module_exists(self):
        """ts_backend.py should exist and be importable."""
        from ts_backend import ts_grep, ts_parse, ts_read

        assert callable(ts_parse)
        assert callable(ts_grep)
        assert callable(ts_read)

    def test_ts_parse_python(self):
        """ts_parse should parse Python source."""
        from ts_backend import ts_parse

        source = "def hello():\n    pass\n"
        tree = ts_parse(source, lang="python")
        assert tree is not None
        assert tree.root_node is not None

    def test_ts_grep_function_definition(self):
        """ts_grep should find function definitions."""
        from ts_backend import ts_grep, ts_parse

        source = "def hello():\n    pass\ndef world():\n    pass\n"
        tree = ts_parse(source, lang="python")
        matches = ts_grep(tree, "function_definition")
        assert len(matches) >= 2

    def test_ts_grep_class_definition(self):
        """ts_grep should find class definitions."""
        from ts_backend import ts_grep, ts_parse

        source = "class Foo:\n    pass\n"
        tree = ts_parse(source, lang="python")
        matches = ts_grep(tree, "class_definition")
        assert len(matches) >= 1

    def test_ts_read_extracts_functions(self):
        """ts_read should extract function names from parse tree."""
        from ts_backend import ts_parse, ts_read

        source = "def hello():\n    pass\nclass Foo:\n    def bar(self):\n        pass\n"
        tree = ts_parse(source, lang="python")
        result = ts_read(tree)
        assert "functions" in result
        names = [f["name"] for f in result["functions"]]
        assert "hello" in names

    def test_ts_read_extracts_classes(self):
        """ts_read should extract class names from parse tree."""
        from ts_backend import ts_parse, ts_read

        source = "class Foo:\n    pass\nclass Bar:\n    pass\n"
        tree = ts_parse(source, lang="python")
        result = ts_read(tree)
        assert "classes" in result
        names = [c["name"] for c in result["classes"]]
        assert "Foo" in names
        assert "Bar" in names


# ─── Phase 1: project_info upgrades ──────────────────────────────────────


class TestProjectInfoSummary:
    """Phase 1: project_info_summary returns compact dict (<500 tokens)."""

    def test_summary_returns_dict(self):
        """project_info_summary should return a dict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert isinstance(result, dict)

    def test_summary_has_required_keys(self):
        """Summary should have name, version, languages, module_count, symbol_count."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert "name" in result
            assert "version" in result
            assert "languages" in result
            assert "module_count" in result
            assert "symbol_count" in result
            assert "entry_points" in result
            assert "test_framework" in result
            assert "modules" in result

    def test_summary_is_compact(self):
        """Summary JSON should be under 2000 bytes (<500 tokens)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "def main():\n    pass\n",
                },
            )
            result = project_info_summary(root)
            json_str = json.dumps(result)
            assert len(json_str) < 2000, f"Summary too large: {len(json_str)} bytes"

    def test_summary_module_count(self):
        """module_count should reflect number of modules with symbols."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "def main():\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert result["module_count"] >= 2

    def test_summary_symbol_count(self):
        """symbol_count should reflect total symbols."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "def main():\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert result["symbol_count"] >= 2  # Foo + main

    def test_summary_modules_is_list_of_names(self):
        """modules should be a list of module path strings."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert isinstance(result["modules"], list)
            for m in result["modules"]:
                assert isinstance(m, str)

    def test_summary_test_framework(self):
        """Summary should include test_framework."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "tests/conftest.py": "# pytest\n",
                    "tests/test_core.py": "def test_foo():\n    pass\n",
                },
            )
            result = project_info_summary(root)
            assert result["test_framework"] == "pytest"


class TestIncrementalScanning:
    """Phase 1: hash-based incremental scanning."""

    def test_file_hashes_stored(self):
        """project_init should create .file_hashes.json in references/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)
            hashes_file = root / "references" / ".file_hashes.json"
            assert hashes_file.exists(), "Should create .file_hashes.json"
            hashes = json.loads(hashes_file.read_text())
            assert isinstance(hashes, dict)
            assert len(hashes) > 0

    def test_hashes_content_is_md5(self):
        """Stored hashes should be hex MD5 strings (32 chars)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)
            hashes_file = root / "references" / ".file_hashes.json"
            hashes = json.loads(hashes_file.read_text())
            for _path, hash_val in hashes.items():
                assert isinstance(hash_val, str)
                assert len(hash_val) == 32, f"Expected MD5 hex, got: {hash_val}"

    def test_reinit_uses_cache(self):
        """Second project_init should use cached hashes for unchanged files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)
            hashes_file = root / "references" / ".file_hashes.json"
            hashes1 = json.loads(hashes_file.read_text())

            # Re-init without changes
            project_init(root)
            hashes2 = json.loads(hashes_file.read_text())
            assert hashes1 == hashes2, "Hashes should be stable across re-inits"

    def test_changed_file_updates_hash(self):
        """Modifying a file should update its hash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)
            hashes_file = root / "references" / ".file_hashes.json"
            hashes1 = json.loads(hashes_file.read_text())

            # Modify a file
            (root / "mypkg" / "core.py").write_text("class Foo:\n    pass\nclass Bar:\n    pass\n")
            project_init(root)
            hashes2 = json.loads(hashes_file.read_text())

            # Hash for core.py should change
            core_key = next(k for k in hashes2 if "core.py" in k)
            assert hashes1[core_key] != hashes2[core_key], "Hash should change when file changes"


class TestChangeDetection:
    """Phase 1: diff mode for project_info."""

    def test_diff_returns_changes(self):
        """diff=True should return added/removed/modified symbols."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)

            # Modify: add Bar, remove Foo
            (root / "mypkg" / "core.py").write_text("class Bar:\n    pass\n")
            result = generate_project_json(root, diff=True)

            assert "diff" in result

    def test_diff_no_changes(self):
        """diff=True on unchanged project should show no changes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)

            result = generate_project_json(root, diff=True)
            # Should have empty added/removed/modified
            diff = result.get("diff", {})
            assert len(diff.get("added", [])) == 0
            assert len(diff.get("removed", [])) == 0
            assert len(diff.get("modified", [])) == 0

    def test_diff_detects_added_symbols(self):
        """diff=True should detect newly added symbols."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            project_init(root)

            # Add new symbol
            (root / "mypkg" / "core.py").write_text(
                "class Foo:\n    pass\nclass NewClass:\n    pass\n"
            )
            result = generate_project_json(root, diff=True)
            assert "diff" in result
            diff = result["diff"]
            added_names = [s["name"] for s in diff["added"]]
            assert "NewClass" in added_names, f"Expected NewClass in added, got {added_names}"

    def test_diff_detects_removed_symbols(self):
        """diff=True should detect removed symbols."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\nclass Keep:\n    pass\n",
                },
            )
            project_init(root)

            # Remove Foo
            (root / "mypkg" / "core.py").write_text("class Keep:\n    pass\n")
            result = generate_project_json(root, diff=True)
            assert "diff" in result
            diff = result["diff"]
            removed_names = [s["name"] for s in diff["removed"]]
            assert "Foo" in removed_names, f"Expected Foo in removed, got {removed_names}"


# ─── codebase_summary tool tests ──────────────────────────────────────────


class TestCodebaseSummary:
    """Tests for the codebase_summary tool."""

    def test_returns_dict(self):
        """codebase_summary should return a dict."""
        from ast_tools.tools import _tool_codebase_summary

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = _tool_codebase_summary({"cwd": str(root)})
            assert isinstance(result, dict)

    def test_has_required_keys(self):
        """codebase_summary should have name, languages, module_count, symbol_count."""
        from ast_tools.tools import _tool_codebase_summary

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = _tool_codebase_summary({"cwd": str(root)})
            assert "name" in result
            assert "languages" in result
            assert "module_count" in result
            assert "symbol_count" in result
            assert "entry_points" in result
            assert "test_framework" in result

    def test_under_2000_bytes(self):
        """codebase_summary JSON should be under 2000 bytes."""
        from ast_tools.tools import _tool_codebase_summary

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "def main():\n    pass\n",
                },
            )
            result = _tool_codebase_summary({"cwd": str(root)})
            json_str = json.dumps(result)
            assert len(json_str) < 2000, f"Summary too large: {len(json_str)} bytes"

    def test_includes_tree(self):
        """codebase_summary should include a directory tree."""
        from ast_tools.tools import _tool_codebase_summary

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            result = _tool_codebase_summary({"cwd": str(root)})
            assert "tree" in result
            assert isinstance(result["tree"], dict)
            assert len(result["tree"]) > 0

    def test_includes_test_mapping(self):
        """codebase_summary should include test-to-source mapping."""
        from ast_tools.tools import _tool_codebase_summary

        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "tests/test_core.py": "from mypkg.core import Foo\n\ndef test_foo():\n    pass\n",
                },
            )
            result = _tool_codebase_summary({"cwd": str(root)})
            assert "test_mapping" in result
            assert isinstance(result["test_mapping"], dict)


# ─── find_references tool tests ───────────────────────────────────────────


class TestFindReferences:
    """Tests for the find_references tool."""

    def test_finds_known_references(self):
        """find_references should find references to a known symbol."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "from mypkg.core import Foo\n\ndef main():\n    f = Foo()\n",
                },
            )
            from ast_tools.tools.find_references import _tool_find_references

            result = _tool_find_references({"symbol": "Foo", "cwd": str(root)})
            assert "error" not in result
            assert result["count"] > 0
            # Should find Foo in main.py (import + usage)
            files_found = [r["file"] for r in result["references"]]
            assert any("main.py" in f for f in files_found), (
                f"Expected main.py in results, got {files_found}"
            )

    def test_respects_file_filter(self):
        """find_references should filter to a specific file when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "from mypkg.core import Foo\n\ndef main():\n    f = Foo()\n",
                    "mypkg/other.py": "from mypkg.core import Foo\n",
                },
            )
            from ast_tools.tools.find_references import _tool_find_references

            result = _tool_find_references(
                {
                    "symbol": "Foo",
                    "cwd": str(root),
                    "file": str(root / "mypkg" / "main.py"),
                }
            )
            assert "error" not in result
            for ref in result["references"]:
                assert "main.py" in ref["file"], f"Expected only main.py, got {ref['file']}"

    def test_respects_limit(self):
        """find_references should cap results to limit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/main.py": "from mypkg.core import Foo\nf1 = Foo()\nf2 = Foo()\nf3 = Foo()\n",
                },
            )
            from ast_tools.tools.find_references import _tool_find_references

            result = _tool_find_references(
                {
                    "symbol": "Foo",
                    "cwd": str(root),
                    "limit": 2,
                }
            )
            assert "error" not in result
            assert result["count"] <= 2
            assert len(result["references"]) <= 2

    def test_empty_for_unknown_symbol(self):
        """find_references should return empty for unknown symbol."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                },
            )
            from ast_tools.tools.find_references import _tool_find_references

            result = _tool_find_references(
                {
                    "symbol": "NonExistentSymbol",
                    "cwd": str(root),
                }
            )
            assert "error" not in result
            assert result["count"] == 0
            assert len(result["references"]) == 0


# ─── impact_analysis tool tests ────────────────────────────────────────────


class TestImpactAnalysis:
    """Tests for the impact_analysis tool."""

    def _make_dep_project(self, tmp):
        """Create a project with a known dependency chain."""
        root = _make_project(
            tmp,
            layout="flat",
            files={
                "mypkg/core.py": "class Foo:\n    pass\n",
                "mypkg/middle.py": "from mypkg.core import Foo\n\nclass Bar:\n    pass\n",
                "mypkg/main.py": "from mypkg.middle import Bar\n\ndef main():\n    pass\n",
                "tests/test_core.py": "from mypkg.core import Foo\n\ndef test_foo():\n    pass\n",
            },
        )
        return root

    def test_returns_dict(self):
        """impact_analysis should return a dict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert isinstance(result, dict)

    def test_direct_dependents(self):
        """Should find direct dependents of a module."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "direct_dependents" in result
            direct = result["direct_dependents"]
            assert "mypkg/middle.py" in direct, f"Expected mypkg/middle.py, got {direct}"

    def test_transitive_dependents(self):
        """Should find transitive dependents (dependents of dependents)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "transitive_dependents" in result
            transitive = result["transitive_dependents"]
            # main.py depends on middle.py which depends on core.py
            assert "mypkg/main.py" in transitive, (
                f"Expected mypkg/main.py in transitive, got {transitive}"
            )

    def test_risk_low(self):
        """Risk should be 'low' for 0-2 direct dependents."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "risk" in result
            # core.py has 1 direct dependent (middle.py) + 1 test = low
            assert result["risk"] == "low", f"Expected low risk, got {result['risk']}"

    def test_risk_medium(self):
        """Risk should be 'medium' for 3-10 direct dependents."""
        with tempfile.TemporaryDirectory() as tmp:
            files = {
                "mypkg/core.py": "class Foo:\n    pass\n",
            }
            # Create 5 files that all import core.py
            for i in range(5):
                files[f"mypkg/user_{i}.py"] = (
                    f"from mypkg.core import Foo\n\ndef func_{i}():\n    pass\n"
                )
            files["tests/test_core.py"] = (
                "from mypkg.core import Foo\n\ndef test_foo():\n    pass\n"
            )
            root = _make_project(tmp, layout="flat", files=files)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "risk" in result
            assert result["risk"] == "medium", f"Expected medium risk, got {result['risk']}"

    def test_risk_high(self):
        """Risk should be 'high' for 10+ direct dependents."""
        with tempfile.TemporaryDirectory() as tmp:
            files = {
                "mypkg/core.py": "class Foo:\n    pass\n",
            }
            # Create 12 files that all import core.py
            for i in range(12):
                files[f"mypkg/user_{i}.py"] = (
                    f"from mypkg.core import Foo\n\ndef func_{i}():\n    pass\n"
                )
            root = _make_project(tmp, layout="flat", files=files)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "risk" in result
            assert result["risk"] == "high", f"Expected high risk, got {result['risk']}"

    def test_test_files_detected(self):
        """Should identify test files that reference the target."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "test_files" in result
            test_files = result["test_files"]
            assert any("test_core.py" in tf for tf in test_files), (
                f"Expected test_core.py, got {test_files}"
            )

    def test_symbol_based_impact(self):
        """Should find callers when target is a symbol name."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "def helper():\n    pass\n",
                    "mypkg/main.py": "from mypkg.core import helper\n\ndef main():\n    helper()\n",
                },
            )
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "helper",
                    "cwd": str(root),
                }
            )
            assert isinstance(result, dict)
            # Should find main.py as a caller
            callers = result.get("callers", [])
            caller_files = [c.get("file", "") for c in callers]
            assert any("main.py" in f for f in caller_files), (
                f"Expected main.py in callers, got {caller_files}"
            )

    def test_no_dependents(self):
        """Module with no dependents should return empty lists."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(
                tmp,
                layout="flat",
                files={
                    "mypkg/core.py": "class Foo:\n    pass\n",
                    "mypkg/other.py": "class Bar:\n    pass\n",
                },
            )
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert isinstance(result, dict)
            assert result["direct_dependents"] == []
            assert result["transitive_dependents"] == []
            assert result["risk"] == "low"

    def test_fan_out_count(self):
        """Should include fan_out count."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_dep_project(tmp)
            from ast_tools.tools.impact_analysis import _tool_impact_analysis

            result = _tool_impact_analysis(
                {
                    "target": "mypkg/core.py",
                    "cwd": str(root),
                }
            )
            assert "fan_out" in result
            assert isinstance(result["fan_out"], int)
            assert result["fan_out"] >= 0
