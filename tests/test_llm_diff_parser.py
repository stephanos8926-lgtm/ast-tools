"""Tests for LLM diff parser."""

from ast_tools.llm.diff_parser import parse_and_validate_diff


class TestParseSimpleDiff:
    """Simple single-hunk diffs."""

    def test_single_line_replacement(self):
        original = "x = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert result.success is True
        assert result.applied_text == "x = 2\n"
        assert result.parsed_hunks == 1
        assert result.matched_hunks == 1

    def test_with_context_lines(self):
        original = "import os\nx = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1,2 +1,2 @@\n import os\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert result.success is True
        assert result.applied_text == "import os\nx = 2\n"
        assert result.confidence >= 0.5


class TestParseInvalidDiff:
    """Diffs that should fail validation."""

    def test_empty_diff(self):
        result = parse_and_validate_diff("", "content")
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_malformed_diff(self):
        result = parse_and_validate_diff("this is not a diff", "content")
        assert result.success is False
        assert "no hunks" in result.error.lower() or "not a diff" in result.error.lower()

    def test_context_mismatch(self):
        original = "y = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert result.success is False
        assert "no hunks matched" in result.error.lower()

    def test_removed_lines_mismatch(self):
        original = "x = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-y = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert result.success is False


class TestParseMultiHunk:
    """Diffs with multiple hunks."""

    def test_two_hunks(self):
        original = "import os\nimport sys\n\nx = 1\n"
        diff = (
            "--- a/test.py\n+++ b/test.py\n"
            "@@ -1,2 +1,1 @@\n-import os\n-import sys\n+import os, sys\n"
            "@@ -3,2 +2,2 @@\n-x = 1\n+y = 1\n"
        )
        result = parse_and_validate_diff(diff, original)
        assert result.success is True
        assert result.parsed_hunks == 2
        assert result.matched_hunks == 2

    def test_partial_hunk_failure(self):
        """One hunk fails validation, other succeeds."""
        original = "a = 1\nb = 2\n"
        diff = (
            "--- a/test.py\n+++ b/test.py\n"
            "@@ -1 +1 @@\n-x = 1\n+x = 2\n"  # Hunk 1: fails (context mismatch)
            "@@ -2 +2 @@\n-b = 2\n+b = 3\n"  # Hunk 2: succeeds
        )
        result = parse_and_validate_diff(diff, original)
        # Should succeed with partial match
        assert result.matched_hunks == 1
        assert result.parsed_hunks == 2


class TestConfidenceScoring:
    """Confidence reflects context match quality."""

    def test_high_confidence_with_context(self):
        original = "a = 1\nb = 2\nc = 3\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1,3 +1,3 @@\n a = 1\n-b = 2\n+z = 2\n c = 3\n"
        result = parse_and_validate_diff(diff, original)
        assert result.confidence >= 0.5

    def test_lower_confidence_without_context(self):
        original = "x = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert result.confidence < 0.7  # No context lines to match


class TestParseResultFields:
    """ParseResult dataclass fields."""

    def test_edits_contain_expected_fields(self):
        original = "x = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert len(result.edits) == 1
        edit = result.edits[0]
        assert "start_line" in edit
        assert "end_line" in edit
        assert "old_text" in edit
        assert "new_text" in edit
        assert edit["old_text"] == "x = 1"
        assert edit["new_text"] == "x = 2"

    def test_confidence_range(self):
        original = "x = 1\n"
        diff = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = parse_and_validate_diff(diff, original)
        assert 0.0 <= result.confidence <= 1.0
