"""
Custom fixer example for testing the plugin system.

This module provides a TrailingNewlineFixer that ensures Python files end
with exactly one newline. It's a simple, deterministic fixer that
demonstrates how to write and register a custom fixer plugin.
"""

from pathlib import Path

from ast_tools.fix.fixers import FixerBase, FixAction, FixerConfig


class TrailingNewlineFixer(FixerBase):
    """Ensure files end with exactly one newline (enforce PEP 8 W292)."""

    name = "trailing_newline"
    description = "Ensure files end with exactly one newline"
    supported_languages = ["python"]
    file_extensions = [".py"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect Python files in target paths."""
        python_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                python_files.append(path)
            elif path.is_dir():
                python_files.extend(path.rglob("*.py"))
        return python_files

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Check files for missing/extra trailing newlines."""
        actions = []
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            fixed = self._normalize_trailing_newline(original)
            if fixed != original:
                changes = []
                if not original.endswith("\n"):
                    changes.append("missing trailing newline")
                elif original.endswith("\n\n"):
                    changes.append("extra trailing newlines")
                else:
                    changes.append("inconsistent line ending")

                actions.append(FixAction(
                    tool=self.name,
                    file_path=file_path,
                    description=f"Normalize trailing newline: {', '.join(changes)}",
                    original_content=original,
                    fixed_content=fixed,
                    safety="safe",
                    metadata={"type": "format", "changes": changes},
                ))
        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Check if files have correct trailing newlines."""
        issues = []
        for file_path in files:
            content = file_path.read_text(encoding="utf-8")
            if not content.endswith("\n"):
                issues.append(f"{file_path}: missing trailing newline")
            elif content.endswith("\n\n"):
                issues.append(f"{file_path}: extra trailing newlines")
        return issues

    def is_available(self) -> bool:
        """Always available - no external tool needed."""
        return True

    @staticmethod
    def _normalize_trailing_newline(content: str) -> str:
        """Ensure content ends with exactly one newline."""
        # Strip all trailing newlines, then add exactly one
        stripped = content.rstrip("\n")
        return stripped + "\n"


# The entry point referenced by the plugin config:
# "trailing_newline": "tests.fixtures.custom_fixer_example:TrailingNewlineFixer"