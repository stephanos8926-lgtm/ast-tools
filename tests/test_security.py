"""Tests for security utilities."""

import tempfile
from pathlib import Path

import pytest

from ast_tools.utils.security import (
    sanitize_fts5_query,
    sanitize_search_query,
    validate_limit,
    validate_project_path,
    validate_timeout,
)

pytestmark = pytest.mark.integration

class TestValidateProjectPath:
    """Tests for validate_project_path function."""

    def test_valid_relative_path(self):
        """Test that relative paths within CWD are accepted."""
        with tempfile.TemporaryDirectory():
            result = validate_project_path(".")
            assert result == Path.cwd().resolve()

    def test_valid_subdirectory(self):
        """Test that subdirectories within CWD are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            result = validate_project_path(str(subdir))
            assert result == subdir.resolve()

    def test_path_traversal_blocked(self):
        """Test that .. patterns are blocked."""
        with pytest.raises(ValueError, match="Path traversal"):
            validate_project_path("../../etc")

    def test_path_traversal_blocked_mixed(self):
        """Test that mixed traversal patterns are blocked."""
        with pytest.raises(ValueError, match="Path traversal"):
            validate_project_path("subdir/../../etc")

    def test_absolute_path_outside_allowed(self):
        """Test that absolute paths outside allowed roots are blocked."""
        with pytest.raises(ValueError, match="outside allowed directories"):
            validate_project_path("/etc/passwd")

    def test_symlink_blocked(self):
        """Test that symlinks escaping root are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path("/etc")
            link = Path(tmpdir) / "link"
            try:
                link.symlink_to(target)
                with pytest.raises(ValueError, match="outside allowed directories"):
                    validate_project_path(str(link))
            except (OSError, NotImplementedError):
                # Symlinks may not be supported in test environment
                pytest.skip("Symlinks not supported")

    def test_empty_path_rejected(self):
        """Test that empty paths are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_project_path("")

    def test_whitespace_path_rejected(self):
        """Test that whitespace-only paths are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_project_path("   ")

    def test_existing_file_rejected(self):
        """Test that existing files (not directories) are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test")
            with pytest.raises(ValueError, match="not a directory"):
                validate_project_path(str(file_path))


class TestSanitizeSearchQuery:
    """Tests for sanitize_search_query function."""

    def test_normal_query(self):
        """Test normal query passes through."""
        assert sanitize_search_query("hello world") == "hello world"

    def test_removes_boolean_operators(self):
        """Test that boolean operators are removed."""
        assert sanitize_search_query("auth OR password") == "auth password"
        assert sanitize_search_query("hello AND world") == "hello world"
        assert sanitize_search_query("test NOT null") == "test null"

    def test_removes_near_operator(self):
        """Test that NEAR operator is removed."""
        assert sanitize_search_query("test NEAR/0 foo") == "test /0 foo"

    def test_escapes_quotes(self):
        """Test that quotes are escaped."""
        assert sanitize_search_query('hello "world"') == 'hello ""world""'

    def test_escapes_special_chars(self):
        """Test that FTS5 special chars are escaped."""
        assert sanitize_search_query("func*") == "func"
        # Slashes are preserved (valid in file paths)
        assert sanitize_search_query("path/to/file") == "path/to/file"

    def test_limits_length(self):
        """Test that query length is limited."""
        long_query = "a" * 600
        result = sanitize_search_query(long_query)
        assert len(result) <= 500

    def test_empty_query(self):
        """Test empty query returns empty string."""
        assert sanitize_search_query("") == ""
        assert sanitize_search_query(None) == ""


class TestValidateLimit:
    """Tests for validate_limit function."""

    def test_valid_limit(self):
        assert validate_limit(100) == 100

    def test_none_returns_default(self):
        assert validate_limit(None) == 50

    def test_zero_clamped_to_one(self):
        assert validate_limit(0) == 1

    def test_negative_clamped_to_one(self):
        assert validate_limit(-10) == 1

    def test_over_max_clamped(self):
        assert validate_limit(2000) == 1000

    def test_string_limit(self):
        assert validate_limit("100") == 100

    def test_invalid_string_returns_default(self):
        assert validate_limit("abc") == 50


class TestValidateTimeout:
    """Tests for validate_timeout function."""

    def test_valid_timeout(self):
        assert validate_timeout(60) == 60

    def test_none_returns_default(self):
        assert validate_timeout(None) == 30

    def test_zero_clamped_to_one(self):
        assert validate_timeout(0) == 1

    def test_over_max_clamped(self):
        assert validate_timeout(500) == 300


class TestSanitizeFts5Query:
    """Tests for sanitize_fts5_query function (CLI alias)."""

    def test_alias_works(self):
        assert sanitize_fts5_query("test OR query") == "test query"

    def test_removes_near(self):
        assert sanitize_fts5_query("test NEAR/5 foo") == "test /5 foo"
