"""Tests for the fixer plugin system."""

import importlib
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from ast_tools.fix.engine import FixEngine, FixContext
from ast_tools.fix.config import FixConfig
from ast_tools.fix.fixers import (
    FixerBase,
    FixAction,
    FixerConfig as FixerPluginConfig,
    PluginManager,
    plugin_manager,
    get_fixer_for_language,
    get_all_fixers,
    register_plugin_fixers,
)
from tests.fixtures.custom_fixer_example import TrailingNewlineFixer


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_plugin_manager():
    """Reset the singleton between tests to prevent leakage."""
    plugin_manager._plugins.clear()
    yield
    plugin_manager._plugins.clear()


@pytest.fixture
def project_root():
    """Use the current working directory as a safe project root for engine tests."""
    return Path(".").resolve()


@pytest.fixture
def temp_py_file():
    """Create a temp Python file with content to fix."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write("x = 1\n\n\n")  # Extra trailing newlines
        tmp_path = f.name
    yield Path(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_dir_with_files():
    """Create a temp directory with mix of fixable and clean files."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # File 1: needs trailing newline fix
        (base / "needs_fix.py").write_text("y = 2\n\n\n")

        # File 2: already clean
        (base / "clean.py").write_text("z = 3\n")

        # File 3: subdirectory file
        sub = base / "sub"
        sub.mkdir()
        (sub / "sub_file.py").write_text("w = 4\n\n\n\n")

        yield base


# =============================================================================
# PluginManager Tests
# =============================================================================


class TestPluginManager:
    """Test the PluginManager singleton."""

    def test_singleton(self):
        """PluginManager should be a singleton."""
        pm1 = PluginManager()
        pm2 = PluginManager()
        assert pm1 is pm2

    def test_register_plugin(self):
        """Register a valid plugin and retrieve it."""
        pm = PluginManager()
        pm.register("trailing_newline", "tests.fixtures.custom_fixer_example:TrailingNewlineFixer")

        cls = pm.get_class("trailing_newline")
        assert cls is not None
        assert cls == TrailingNewlineFixer

    def test_register_and_instantiate(self):
        """Registered plugin class can be instantiated and used."""
        pm = PluginManager()
        pm.register("trailing_newline", "tests.fixtures.custom_fixer_example:TrailingNewlineFixer")

        cls = pm.get_class("trailing_newline")
        fixer = cls()
        assert fixer.is_available()
        assert fixer.name == "trailing_newline"

    def test_get_nonexistent_plugin(self):
        """Getting a non-existent plugin returns None."""
        pm = PluginManager()
        assert pm.get_class("nonexistent") is None

    def test_register_invalid_module(self):
        """Registering an invalid module entry point raises ImportError."""
        pm = PluginManager()
        with pytest.raises((ImportError, ModuleNotFoundError)):
            pm.register("bad", "nonexistent_module:SomeClass")

    def test_register_invalid_class(self):
        """Registering a valid module but invalid class name."""
        pm = PluginManager()
        with pytest.raises(AttributeError):
            pm.register("bad", "tests.fixtures.custom_fixer_example:NonExistentClass")

    def test_get_all_plugins(self):
        """get_all() returns all registered plugin classes."""
        pm = PluginManager()
        pm.register("tn", "tests.fixtures.custom_fixer_example:TrailingNewlineFixer")

        all_p = pm.get_all()
        assert "tn" in all_p
        assert all_p["tn"] == TrailingNewlineFixer

    def test_load_from_config(self):
        """load_from_config() processes a dict of name -> entry_point."""
        pm = PluginManager()
        config = {
            "tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer",
        }
        pm.load_from_config(config)

        assert pm.get_class("tn") is not None

    def test_load_from_config_empty(self):
        """load_from_config() with None or empty dict is a no-op."""
        pm = PluginManager()
        pm.load_from_config(None)
        assert pm.get_all() == {}

        pm.load_from_config({})
        assert pm.get_all() == {}

    def test_load_from_config_bad_plugin(self):
        """load_from_config() with a bad entry point doesn't crash."""
        pm = PluginManager()
        config = {
            "good": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer",
            "bad": "nonexistent:Boom",
        }
        # Should not raise — errors are logged, not propagated
        pm.load_from_config(config)

        # Good one should be registered
        assert pm.get_class("good") is not None
        # Bad one should not
        assert pm.get_class("bad") is None


# =============================================================================
# register_plugin_fixers() Tests
# =============================================================================


class TestRegisterPluginFixers:
    """Test the register_plugin_fixers convenience function."""

    def test_register_plugin_fixers(self):
        """register_plugin_fixers() loads plugins into the global manager."""
        register_plugin_fixers({
            "tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer",
        })

        cls = get_fixer_for_language("tn")
        assert cls is not None
        assert cls == TrailingNewlineFixer

    def test_get_fixer_for_language_custom(self):
        """get_fixer_for_language returns custom fixers."""
        register_plugin_fixers({"tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"})
        cls = get_fixer_for_language("tn")
        assert cls is TrailingNewlineFixer

    def test_get_fixer_builtin_still_works(self):
        """Built-in fixers should still be accessible after registering plugins."""
        register_plugin_fixers({"tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"})

        python_fixer = get_fixer_for_language("python")
        assert python_fixer is not None
        assert python_fixer.__name__ == "RuffFixer"

    def test_get_all_fixers_includes_plugins(self):
        """get_all_fixers should include both built-in and plugin fixers."""
        n_builtin = len(get_all_fixers())

        register_plugin_fixers({"tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"})
        all_fixers = get_all_fixers()

        assert "tn" in all_fixers
        assert all_fixers["tn"] == TrailingNewlineFixer
        assert len(all_fixers) == n_builtin + 1

    def test_register_plugin_fixers_multiple(self):
        """Multiple plugins can be registered and used."""
        register_plugin_fixers({
            "tn": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer",
        })

        assert get_fixer_for_language("tn") is TrailingNewlineFixer


# =============================================================================
# Plugin + FixEngine Integration Tests
# =============================================================================


class TestFixEngineWithPlugin:
    """Test that FixEngine correctly picks up and uses custom plugins."""

    def test_fixengine_accepts_plugins(self, project_root):
        """FixEngine can accept custom plugins and use them."""
        # Create a test file within the project root (satisfies _check_file_safety)
        test_file = project_root / "test_plugin_tmp_fix.py"
        test_file.write_text("x = 1\n\n\n")  # Extra trailing newlines

        try:
            cfg = FixConfig()
            ctx = FixContext(
                project_root=project_root,
                target_paths=[test_file],
                languages={"python"},
                config=cfg,
            )
            engine = FixEngine(
                ctx,
                plugin_fixers={"python": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"},
            )
            result = engine.run()
            assert result.success
            # After fix, file should end with exactly one newline
            final = test_file.read_text()
            assert final == "x = 1\n", f"Expected normalized, got {repr(final)}"
        finally:
            test_file.unlink(missing_ok=True)

    def test_plugin_fixer_detects_and_fixes(self, project_root):
        """Plugin fixer detects all relevant files and fixes them."""
        # Create files within project root
        test_dir = project_root / "test_plugin_tmp_dir"
        test_dir.mkdir(exist_ok=True)

        try:
            (test_dir / "needs_fix.py").write_text("y = 2\n\n\n")
            (test_dir / "clean.py").write_text("z = 3\n")
            sub = test_dir / "sub"
            sub.mkdir()
            (sub / "sub_file.py").write_text("w = 4\n\n\n\n")

            cfg = FixConfig()
            ctx = FixContext(
                project_root=project_root,
                target_paths=[test_dir],
                languages={"python"},
                config=cfg,
            )
            engine = FixEngine(
                ctx,
                plugin_fixers={"python": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"},
            )
            result = engine.run()

            assert result.success
            assert result.files_changed == 2  # needs_fix.py and sub/sub_file.py
            assert result.total_fixes == 2  # Two files had extra newlines

            # Verify files are fixed
            assert (test_dir / "needs_fix.py").read_text() == "y = 2\n"
            assert (test_dir / "sub" / "sub_file.py").read_text() == "w = 4\n"
            # Clean file should be unchanged
            assert (test_dir / "clean.py").read_text() == "z = 3\n"
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_plugin_with_builtin_together(self, project_root):
        """Plugin and built-in fixers should work harmoniously."""
        test_file = project_root / "test_plugin_tmp_both.py"
        test_file.write_text("x=1\n\n\n")

        try:
            cfg = FixConfig()
            ctx = FixContext(
                project_root=project_root,
                target_paths=[test_file],
                languages={"python"},
                config=cfg,
            )
            engine = FixEngine(
                ctx,
                plugin_fixers={"python": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"},
            )
            result = engine.run()
            assert result.success

            final = test_file.read_text()
            # Plugin should normalize trailing newlines; ruff also formats (removes spaces around =)
            assert final == "x=1\n"
        finally:
            test_file.unlink(missing_ok=True)

    def test_plugin_fixer_convergence(self, project_root):
        """Plugin fixer should converge in one iteration."""
        test_file = project_root / "test_plugin_tmp_conv.py"
        test_file.write_text("x = 1\n\n\n")

        try:
            cfg = FixConfig(max_iterations=5)
            ctx = FixContext(
                project_root=project_root,
                target_paths=[test_file],
                languages={"python"},
                config=cfg,
            )
            engine = FixEngine(
                ctx,
                plugin_fixers={"python": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"},
            )
            result = engine.run()
            assert result.converged
            assert result.iterations == 1, (
                f"Expected 1 iteration, got {result.iterations}"
            )
        finally:
            test_file.unlink(missing_ok=True)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPluginErrorHandling:
    """Test that plugin errors are handled gracefully."""

    def test_bad_module_doesnt_crash(self):
        """A bad plugin entry point doesn't crash the system."""
        register_plugin_fixers({"bad": "nonexistent_module:Class"})
        # Should be silently skipped
        assert get_fixer_for_language("bad") is None

    def test_fixengine_with_none_plugin(self, project_root):
        """FixEngine with no plugins works normally."""
        test_file = project_root / "test_plugin_tmp_no_plugin.py"
        test_file.write_text("x=1\n")

        try:
            cfg = FixConfig()
            ctx = FixContext(
                project_root=project_root,
                target_paths=[test_file],
                languages={"python"},
                config=cfg,
            )
            engine = FixEngine(ctx)  # No plugin_fixers
            result = engine.run()
            assert result.success
        finally:
            test_file.unlink(missing_ok=True)

    def test_plugin_manager_persists_across_calls(self):
        """PluginManager state persists across calls (singleton)."""
        pm1 = PluginManager()
        pm1.register("tn", "tests.fixtures.custom_fixer_example:TrailingNewlineFixer")

        pm2 = PluginManager()
        assert pm2.get_class("tn") is not None

        # The instance is the same
        assert pm1 is pm2


# =============================================================================
# Manual Fixer Integration Tests
# =============================================================================


class TestCustomFixerDirectly:
    """Test the custom fixer directly (not through plugin system)."""

    def test_fixer_name_and_description(self):
        """Fixer has correct metadata."""
        fixer = TrailingNewlineFixer()
        assert fixer.name == "trailing_newline"
        assert "newline" in fixer.description
        assert fixer.is_available()

    def test_analyze_missing_newline(self, temp_py_file):
        """Fixer detects missing/extra trailing newline."""
        temp_py_file.write_text("x = 1")  # No trailing newline
        fixer = TrailingNewlineFixer()
        actions = fixer.analyze([temp_py_file])
        assert len(actions) == 1
        assert "missing" in actions[0].description.lower()

    def test_analyze_extra_newlines(self, temp_py_file):
        """Fixer detects extra trailing newlines."""
        fixer = TrailingNewlineFixer()
        actions = fixer.analyze([temp_py_file])
        assert len(actions) == 1
        assert "extra" in actions[0].description.lower()

    def test_analyze_clean_file(self, temp_py_file):
        """Fixer detects no changes for clean file."""
        temp_py_file.write_text("x = 1\n")  # Already clean
        fixer = TrailingNewlineFixer()
        actions = fixer.analyze([temp_py_file])
        assert len(actions) == 0

    def test_verify_before_fix(self, temp_py_file):
        """Verify should report issues before fixing."""
        fixer = TrailingNewlineFixer()
        issues = fixer.verify([temp_py_file])
        assert len(issues) == 1

    def test_verify_after_fix(self, temp_py_file):
        """Verify should report no issues after fixing."""
        fixer = TrailingNewlineFixer()
        actions = fixer.analyze([temp_py_file])
        fixer.apply_fix(actions[0])
        issues = fixer.verify([temp_py_file])
        assert len(issues) == 0

    def test_apply_and_check_content(self, temp_py_file):
        """Applying fix should normalize the file content."""
        fixer = TrailingNewlineFixer()
        actions = fixer.analyze([temp_py_file])
        assert len(actions) == 1

        result = fixer.apply_fix(actions[0])
        assert result

        content = temp_py_file.read_text()
        assert content == "x = 1\n"

    def test_detect_scans_directory(self, temp_dir_with_files):
        """detect() finds Python files in directories recursively."""
        fixer = TrailingNewlineFixer()
        files = fixer.detect([temp_dir_with_files])
        paths = {str(p.relative_to(temp_dir_with_files)) for p in files}
        assert "needs_fix.py" in paths
        assert "clean.py" in paths
        assert "sub/sub_file.py" in paths

    def test_detect_non_python_ignored(self):
        """detect() ignores non-.py files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "test.js").write_text("")
            (base / "test.go").write_text("")
            (base / "test.py").write_text("x = 1")

            fixer = TrailingNewlineFixer()
            files = fixer.detect([base])
            assert len(files) == 1
            assert files[0].suffix == ".py"