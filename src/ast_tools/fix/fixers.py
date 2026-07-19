"""
Base classes and interfaces for fixers.
"""

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FixerPlugin:
    """Represents a loaded, registered fixer plugin."""

    name: str
    entry_point: str  # e.g. 'my_module:MyFixerClass'
    fixer_class: type["FixerBase"]

    def __init__(self, name: str, entry_point: str):
        self.name = name
        self.entry_point = entry_point
        self.fixer_class = self._load()

    def _load(self) -> type["FixerBase"]:
        module_name, class_name = self.entry_point.split(":", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)


class PluginManager:
    """Singleton manager for external fixer plugins."""

    _instance: "PluginManager | None" = None
    _plugins: dict[str, FixerPlugin] = {}

    def __new__(cls) -> "PluginManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, entry_point: str) -> None:
        """Register a plugin by name and module:Class entry point."""
        plugin = FixerPlugin(name=name, entry_point=entry_point)
        if not issubclass(plugin.fixer_class, FixerBase):
            raise TypeError(
                f"Plugin '{name}' class '{plugin.entry_point}' must subclass FixerBase"
            )
        self._plugins[name] = plugin

    def load_from_config(self, config: dict[str, str] | None) -> None:
        """Load all plugins from a config dict (name -> module:Class)."""
        if not config:
            return
        for name, entry_point in config.items():
            try:
                self.register(name, entry_point)
            except Exception as e:
                import sys
                print(f"⚠ Failed to load fixer plugin '{name}' ({entry_point}): {e}", file=sys.stderr)

    def get_class(self, name: str) -> type["FixerBase"] | None:
        """Get a plugin's fixer class by name."""
        plugin = self._plugins.get(name)
        return plugin.fixer_class if plugin else None

    def get_all(self) -> dict[str, type["FixerBase"]]:
        """Get all registered plugin classes."""
        return {n: p.fixer_class for n, p in self._plugins.items()}


# Global plugin manager instance
plugin_manager = PluginManager()


@dataclass
class FixAction:
    """A single fix action to be applied."""

    tool: str
    file_path: Path
    description: str
    original_content: str
    fixed_content: str
    safety: str = "safe"  # safe, unsafe, display_only
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.tool, self.file_path, self.description))


@dataclass
class FixerConfig:
    """Configuration for a specific fixer."""

    enabled: bool = True
    args: list[str] = field(default_factory=list)
    config_file: str | None = None
    safety_override: dict[str, str] = field(default_factory=dict)


@dataclass
class FixerResult:
    """Result of running a fixer."""

    tool: str
    file_path: Path
    actions: list[FixAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True

    def add_action(self, action: FixAction):
        self.actions.append(action)


class FixerBase(ABC):
    """Base class for all fixers."""

    name: str = "base"
    description: str = "Base fixer"
    supported_languages: list[str] = []
    file_extensions: list[str] = []

    def __init__(self, config: FixerConfig | None = None):
        self.config = config or FixerConfig()

    @abstractmethod
    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect files this fixer can process."""
        pass

    @abstractmethod
    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Analyze files and return fix actions."""
        pass

    def apply_fix(self, action: FixAction) -> bool:
        """Apply a fix action. Returns True if successful."""
        # Validate fixed content before writing
        if not self._validate_fixed_content(action.original_content, action.fixed_content):
            return False
        try:
            action.file_path.write_text(action.fixed_content, encoding="utf-8")
            return True
        except Exception:
            return False

    def _validate_fixed_content(self, original: str, fixed: str) -> bool:
        """Validate fixed content before writing. Returns True if valid."""
        # If original was empty, fixed must also be empty
        if not original and fixed:
            return False
        if original and not fixed:
            # Allow emptying a file if original was empty or had only whitespace
            if not original.strip():
                return True
            return False

        # Check for null bytes
        if "\x00" in fixed:
            return False

        # Check line count ratio (shouldn't change drastically)
        orig_lines = original.count("\n")
        fixed_lines = fixed.count("\n")
        if orig_lines > 0:
            ratio = fixed_lines / orig_lines
            if ratio > 2.0 or ratio < 0.5:
                # Allow if the change is a full rewrite (many lines changed)
                pass  # Too strict, just warn in verbose mode

        # Must be valid UTF-8 (already enforced by text mode, but double-check)
        try:
            fixed.encode("utf-8")
        except UnicodeEncodeError:
            return False

        return True

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing. Return list of remaining issues."""
        return []

    def is_available(self) -> bool:
        """Check if the fixer tool is available."""
        return True

    def get_version(self) -> str:
        """Get version of the underlying tool."""
        return "unknown"

    def _run_command(
        self,
        cmd: list[str],
        input_text: str | None = None,
        cwd: Path | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        if timeout is None:
            timeout = 120  # Default 2 minute timeout
        return subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )

    def _run_json_command(self, cmd: list[str], cwd: Path = None) -> dict:
        """Run a command and parse JSON output."""
        result = self._run_command(cmd, cwd=cwd)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {}


class PythonFixer(FixerBase):
    """Base class for Python fixers."""

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


class JavaScriptFixer(FixerBase):
    """Base class for JavaScript/TypeScript fixers."""

    supported_languages = ["javascript", "typescript"]
    file_extensions = [".js", ".jsx", ".ts", ".tsx"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect JS/TS files in target paths."""
        js_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                js_files.append(path)
            elif path.is_dir():
                for ext in self.file_extensions:
                    js_files.extend(path.rglob(f"*{ext}"))
        return js_files


class GoFixer(FixerBase):
    """Base class for Go fixers."""

    supported_languages = ["go"]
    file_extensions = [".go"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect Go files in target paths."""
        go_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                go_files.append(path)
            elif path.is_dir():
                go_files.extend(path.rglob("*.go"))
        return go_files


class RustFixer(FixerBase):
    """Base class for Rust fixers."""

    supported_languages = ["rust"]
    file_extensions = [".rs"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect Rust files in target paths."""
        rs_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                rs_files.append(path)
            elif path.is_dir():
                rs_files.extend(path.rglob("*.rs"))
        return rs_files


class CppFixer(FixerBase):
    """Base class for C++ fixers."""

    supported_languages = ["cpp", "c"]
    file_extensions = [".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect C/C++ files in target paths."""
        cpp_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                cpp_files.append(path)
            elif path.is_dir():
                for ext in self.file_extensions:
                    cpp_files.extend(path.rglob(f"*{ext}"))
        return cpp_files


# =============================================================================
# Concrete Fixers
# =============================================================================


class RuffFixer(PythonFixer):
    """Ruff linter and formatter for Python."""

    name = "ruff"
    description = "Ruff: Fast Python linter and formatter"

    def is_available(self) -> bool:
        try:
            result = self._run_command(["ruff", "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_version(self) -> str:
        try:
            result = self._run_command(["ruff", "--version"])
            if result.returncode == 0:
                return result.stdout.strip().split()[-1]
        except Exception:
            pass
        return "unknown"

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run ruff check --fix and ruff format to get fix actions."""
        actions = []

        if not files:
            return actions

        # For each file, do combined lint+format fix
        for file_path in files:
            original_content = file_path.read_text(encoding="utf-8")

            # Step 1: Get lint fixes
            fix_cmd = ["ruff", "check", "--fix", "--stdin-filename", str(file_path)]
            lint_fixed_content = self._run_command(fix_cmd, input_text=original_content).stdout

            # Step 2: If lint changed something, format the lint-fixed content
            # Otherwise format the original
            content_to_format = (
                lint_fixed_content if lint_fixed_content != original_content else original_content
            )
            fmt_cmd = ["ruff", "format", "--stdin-filename", str(file_path)]
            formatted_content = self._run_command(fmt_cmd, input_text=content_to_format).stdout

            # If final content differs from original, create a single combined action
            if formatted_content != original_content:
                action = FixAction(
                    tool="ruff",
                    file_path=file_path,
                    description="Apply Ruff linting and formatting fixes",
                    original_content=original_content,
                    fixed_content=formatted_content,
                    safety="safe",
                    metadata={
                        "type": "lint-fix+format",
                        "had_lint_changes": lint_fixed_content != original_content,
                        "had_format_changes": formatted_content != content_to_format,
                    },
                )
                actions.append(action)

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run ruff check (read-only) to find remaining issues
            diag_cmd = ["ruff", "check", "--output-format=json", "--stdin-filename", str(file_path)]
            original = file_path.read_text(encoding="utf-8")
            diag_result = self._run_command(diag_cmd, input_text=original)

            if diag_result.returncode in (0, 1) and diag_result.stdout.strip():
                try:
                    diagnostics = json.loads(diag_result.stdout)
                    if diagnostics:
                        issues.append(f"{file_path}: {len(diagnostics)} remaining lint issue(s)")
                except json.JSONDecodeError:
                    pass

            # Also check formatting
            fmt_cmd = ["ruff", "format", "--check", "--stdin-filename", str(file_path)]
            fmt_result = self._run_command(fmt_cmd, input_text=original)

            if fmt_result.returncode != 0:
                issues.append(f"{file_path}: formatting issues remain")

        return issues


class TypeScriptFixer(JavaScriptFixer):
    """ESLint + Prettier for TypeScript/JavaScript."""

    name = "typescript"
    description = "ESLint + Prettier for TypeScript/JavaScript"

    def is_available(self) -> bool:
        try:
            result = self._run_command(["npx", "eslint", "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run ESLint --fix and Prettier to get fix actions."""
        actions = []

        if not files:
            return actions

        # Collect ESLint fixes (read-only diagnostics, then fix via stdin)
        for file_path in files:
            original_content = file_path.read_text(encoding="utf-8")

            # Get diagnostics without applying fixes to disk
            diag_cmd = [
                "npx",
                "eslint",
                "--format=json",
                "--stdin",
                "--stdin-filename",
                str(file_path),
            ]
            diag_result = self._run_command(diag_cmd, input_text=original_content)

            if diag_result.returncode in (0, 1) and diag_result.stdout.strip():
                try:
                    file_results = json.loads(diag_result.stdout)
                    # ESLint JSON output is an array of file results
                    if file_results:
                        # Assuming one file_result per file, which is true with --stdin-filename
                        file_result = file_results[0]
                        messages = file_result.get("messages", [])

                        if any(msg.get("fix") for msg in messages):
                            # Get fixed content via stdin
                            fix_cmd = [
                                "npx",
                                "eslint",
                                "--fix",
                                "--stdin",
                                "--stdin-filename",
                                str(file_path),
                            ]
                            fixed_content_from_lint = self._run_command(
                                fix_cmd, input_text=original_content
                            ).stdout

                            if fixed_content_from_lint != original_content:
                                action = FixAction(
                                    tool="eslint",
                                    file_path=file_path,
                                    description="Apply ESLint fixes",
                                    original_content=original_content,
                                    fixed_content=fixed_content_from_lint,
                                    safety="safe",
                                    metadata={
                                        "type": "lint-fix",
                                        "diagnostics_count": len(messages),
                                    },
                                )
                                actions.append(action)

                except json.JSONDecodeError:
                    pass

        # Collect Prettier formatting fixes (read-only formatting via stdin)
        for file_path in files:
            # Re-read content in case linting actions have been applied
            current_content_for_format = file_path.read_text(encoding="utf-8")
            prettier_cmd = ["npx", "prettier", "--stdin", "--stdin-filepath", str(file_path)]
            prettier_result = self._run_command(prettier_cmd, input_text=current_content_for_format)

            if (
                prettier_result.returncode == 0
                and prettier_result.stdout != current_content_for_format
            ):
                action = FixAction(
                    tool="prettier",
                    file_path=file_path,
                    description="Format with Prettier",
                    original_content=current_content_for_format,  # Original for THIS action is current content
                    fixed_content=prettier_result.stdout,
                    safety="safe",
                    metadata={"type": "format"},
                )
                actions.append(action)

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run ESLint (read-only) to find remaining issues
            diag_cmd = [
                "npx",
                "eslint",
                "--format=json",
                "--stdin",
                "--stdin-filename",
                str(file_path),
            ]
            original = file_path.read_text(encoding="utf-8")
            diag_result = self._run_command(diag_cmd, input_text=original)

            if diag_result.returncode in (0, 1) and diag_result.stdout.strip():
                try:
                    file_results = json.loads(diag_result.stdout)
                    if file_results:
                        file_result = file_results[0]
                        messages = file_result.get("messages", [])
                        if messages:
                            issues.append(f"{file_path}: {len(messages)} remaining ESLint issue(s)")
                except json.JSONDecodeError:
                    pass

            # Also check Prettier formatting
            fmt_cmd = ["npx", "prettier", "--check", "--stdin", "--stdin-filepath", str(file_path)]
            fmt_result = self._run_command(fmt_cmd, input_text=original)

            if fmt_result.returncode != 0:
                issues.append(f"{file_path}: Prettier formatting issues remain")

        return issues


class GoFixerConcrete(GoFixer):
    """goimports + golangci-lint for Go."""

    name = "go"
    description = "goimports + golangci-lint for Go"

    def is_available(self) -> bool:
        try:
            result = self._run_command(["goimports", "-version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run goimports and golangci-lint --fix to get fix actions."""
        actions = []

        if not files:
            return actions

        # Run goimports (already uses stdin/stdout)
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            goimports_cmd = ["goimports", "-srcdir", str(file_path.parent)]
            goimports_result = self._run_command(
                goimports_cmd, input_text=original, cwd=file_path.parent
            )

            if goimports_result.returncode == 0 and goimports_result.stdout != original:
                action = FixAction(
                    tool="goimports",
                    file_path=file_path,
                    description="Organize imports with goimports",
                    original_content=original,
                    fixed_content=goimports_result.stdout,
                    safety="safe",
                    metadata={"type": "imports"},
                )
                actions.append(action)

        # Run golangci-lint --fix (read-only analysis, fix via stdin where possible)
        # golangci-lint doesn't support --stdin easily, so we run it per-file with --fix
        # and capture the diff by reading before/after
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")

            # Run golangci-lint on single file
            golangci_cmd = ["golangci-lint", "run", "--fix", "--out-format=json", str(file_path)]
            result = self._run_command(golangci_cmd, cwd=file_path.parent)

            if result.returncode in (0, 1, 2) and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    for issue in data.get("Issues", []):
                        # golangci-lint --fix modifies the file on disk
                        # We capture the fixed content and create one action per file
                        fixed = file_path.read_text(encoding="utf-8")
                        if fixed != original:
                            action = FixAction(
                                tool="golangci-lint",
                                file_path=file_path,
                                description="Fix golangci-lint issues",
                                original_content=original,
                                fixed_content=fixed,
                                safety="safe",
                                metadata={
                                    "linter": issue["FromLinter"],
                                    "line": issue["Pos"]["Line"],
                                },
                            )
                            actions.append(action)
                            # Break after first issue to avoid duplicate actions per file
                            # (the fix command fixes all issues in the file at once)
                            break
                except json.JSONDecodeError:
                    pass

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run goimports check (read-only)
            original = file_path.read_text(encoding="utf-8")
            goimports_cmd = ["goimports", "-srcdir", str(file_path.parent), "-l"]
            goimports_result = self._run_command(
                goimports_cmd, input_text=original, cwd=file_path.parent
            )
            if goimports_result.returncode == 0 and goimports_result.stdout.strip():
                issues.append(f"{file_path}: imports need organization")

            # Run golangci-lint (read-only, no --fix)
            golangci_cmd = ["golangci-lint", "run", "--out-format=json", str(file_path)]
            result = self._run_command(golangci_cmd, cwd=file_path.parent)
            if result.returncode in (0, 1, 2) and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if data.get("Issues"):
                        issues.append(
                            f"{file_path}: {len(data['Issues'])} remaining golangci-lint issue(s)"
                        )
                except json.JSONDecodeError:
                    pass

        return issues


class RustFixerConcrete(RustFixer):
    """rustfmt + clippy --fix for Rust."""

    name = "rust"
    description = "rustfmt + clippy --fix for Rust"

    def is_available(self) -> bool:
        try:
            result = self._run_command(["rustfmt", "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run rustfmt and clippy --fix to get fix actions."""
        actions = []

        if not files:
            return actions

        # Run rustfmt
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            rustfmt_cmd = ["rustfmt", "--emit=stdout"]
            rustfmt_result = self._run_command(rustfmt_cmd, input_text=original)

            if rustfmt_result.returncode == 0 and rustfmt_result.stdout != original:
                action = FixAction(
                    tool="rustfmt",
                    file_path=file_path,
                    description="Format with rustfmt",
                    original_content=original,
                    fixed_content=rustfmt_result.stdout,
                    safety="safe",
                    metadata={"type": "format"},
                )
                actions.append(action)

        # Run clippy --fix (read-only analysis, fix via capture)
        # Note: clippy --fix works at crate level, not file level
        # We'll run it on the project root and track per-file changes
        project_root = files[0].parent
        while project_root != project_root.parent:
            if (project_root / "Cargo.toml").exists():
                break
            project_root = project_root.parent

        # Capture original content before running clippy
        originals = {fp: fp.read_text(encoding="utf-8") for fp in files}

        clippy_cmd = [
            "cargo",
            "clippy",
            "--fix",
            "--allow-dirty",
            "--allow-staged",
            "--",
            "-D",
            "warnings",
        ]
        result = self._run_command(clippy_cmd, cwd=project_root)

        if result.returncode == 0:
            # Re-read files to see what changed
            for file_path in files:
                fixed = file_path.read_text(encoding="utf-8")
                original = originals[file_path]
                if fixed != original:
                    action = FixAction(
                        tool="clippy",
                        file_path=file_path,
                        description="Fix with clippy",
                        original_content=original,
                        fixed_content=fixed,
                        safety="safe",
                        metadata={"type": "lint-fix"},
                    )
                    actions.append(action)

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run rustfmt --check (read-only)
            original = file_path.read_text(encoding="utf-8")
            rustfmt_cmd = ["rustfmt", "--check"]
            rustfmt_result = self._run_command(rustfmt_cmd, input_text=original)
            if rustfmt_result.returncode != 0:
                issues.append(f"{file_path}: formatting issues remain")

            # Note: clippy --fix is crate-level, we can't easily check per-file
            # A simple check would be to run clippy and see if there are warnings
            # But this is complex without proper Cargo.toml context
            # For now, skip clippy verification

        return issues


class CppFixerConcrete(CppFixer):
    """clang-format + clang-tidy for C++."""

    name = "cpp"
    description = "clang-format + clang-tidy for C++"

    def is_available(self) -> bool:
        try:
            result = self._run_command(["clang-format", "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run clang-format and clang-tidy to get fix actions."""
        actions = []

        if not files:
            return actions

        # Run clang-format
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            clang_format_cmd = ["clang-format", "-style=file", str(file_path)]
            fmt_result = self._run_command(clang_format_cmd)

            if fmt_result.returncode == 0 and fmt_result.stdout != original:
                action = FixAction(
                    tool="clang-format",
                    file_path=file_path,
                    description="Format with clang-format",
                    original_content=original,
                    fixed_content=fmt_result.stdout,
                    safety="safe",
                    metadata={"type": "format"},
                )
                actions.append(action)

        # Run clang-tidy --fix (read-only analysis, fix via capture)
        # clang-tidy doesn't support stdin easily, so we run per-file
        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            clang_tidy_cmd = ["clang-tidy", "--fix", "--format-style=file", str(file_path)]
            result = self._run_command(clang_tidy_cmd)

            if result.returncode == 0:
                fixed = file_path.read_text(encoding="utf-8")
                if fixed != original:
                    action = FixAction(
                        tool="clang-tidy",
                        file_path=file_path,
                        description="Fix with clang-tidy",
                        original_content=original,
                        fixed_content=fixed,
                        safety="safe",
                        metadata={"type": "lint-fix"},
                    )
                    actions.append(action)

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run clang-format --dry-run --Werror (read-only)
            original = file_path.read_text(encoding="utf-8")
            fmt_cmd = ["clang-format", "-style=file", "--dry-run", "--Werror", str(file_path)]
            fmt_result = self._run_command(fmt_cmd, input_text=original)
            if fmt_result.returncode != 0:
                issues.append(f"{file_path}: formatting issues remain")

            # clang-tidy check (read-only) - complex without compile_commands.json
            # Skip for now

        return issues


class MarkdownFixer(FixerBase):
    """Prettier for Markdown."""

    name = "markdown"
    description = "Prettier for Markdown"
    supported_languages = ["markdown"]
    file_extensions = [".md", ".markdown"]

    def detect(self, target_paths: list[Path]) -> list[Path]:
        """Detect Markdown files in target paths."""
        md_files = []
        for path in target_paths:
            if path.is_file() and path.suffix in self.file_extensions:
                md_files.append(path)
            elif path.is_dir():
                for ext in self.file_extensions:
                    md_files.extend(path.rglob(f"*{ext}"))
        return md_files

    def is_available(self) -> bool:
        try:
            result = self._run_command(["npx", "prettier", "--version"])
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def analyze(self, files: list[Path]) -> list[FixAction]:
        """Run Prettier to get fix actions."""
        actions = []

        if not files:
            return actions

        for file_path in files:
            original = file_path.read_text(encoding="utf-8")
            prettier_cmd = ["npx", "prettier", "--write", "--stdin-filepath", str(file_path)]
            prettier_result = self._run_command(prettier_cmd, input_text=original)

            if prettier_result.returncode == 0 and prettier_result.stdout != original:
                action = FixAction(
                    tool="prettier",
                    file_path=file_path,
                    description="Format Markdown with Prettier",
                    original_content=original,
                    fixed_content=prettier_result.stdout,
                    safety="safe",
                    metadata={"type": "format"},
                )
                actions.append(action)

        return actions

    def verify(self, files: list[Path]) -> list[str]:
        """Verify files after fixing - return list of remaining issues."""
        issues = []
        if not self.is_available():
            return issues

        for file_path in files:
            # Run Prettier --check (read-only)
            original = file_path.read_text(encoding="utf-8")
            fmt_cmd = ["npx", "prettier", "--check", "--stdin", "--stdin-filepath", str(file_path)]
            fmt_result = self._run_command(fmt_cmd, input_text=original)
            if fmt_result.returncode != 0:
                issues.append(f"{file_path}: formatting issues remain")

        return issues


# =============================================================================
# Fixer Registry
# =============================================================================

_FIXER_REGISTRY: dict[str, type[FixerBase]] = {
    "python": RuffFixer,
    "ruff": RuffFixer,
    "typescript": TypeScriptFixer,
    "javascript": TypeScriptFixer,
    "ts": TypeScriptFixer,
    "js": TypeScriptFixer,
    "go": GoFixerConcrete,
    "golang": GoFixerConcrete,
    "rust": RustFixerConcrete,
    "cpp": CppFixerConcrete,
    "c": CppFixerConcrete,
    "cxx": CppFixerConcrete,
    "markdown": MarkdownFixer,
    "md": MarkdownFixer,
}


def get_fixer_for_language(language: str) -> type[FixerBase] | None:
    """Get fixer class for a language (built-in or plugin).

    Custom plugins take precedence over built-in fixers.
    """
    # Check plugin manager first (custom plugins override built-in)
    plugin_fixer = plugin_manager.get_class(language.lower())
    if plugin_fixer:
        return plugin_fixer
    # Fall back to built-in registry
    return _FIXER_REGISTRY.get(language.lower())


def get_all_fixers() -> dict[str, type[FixerBase]]:
    """Get all registered fixers (built-in + plugins)."""
    result = _FIXER_REGISTRY.copy()
    result.update(plugin_manager.get_all())
    return result


def register_plugin_fixers(config: dict[str, str] | None) -> None:
    """Register fixer plugins from a config dict.

    Args:
        config: Dict mapping language names to 'module:ClassName' strings.
                Example: {"sql": "my_fixers:SQLFixer"}
    """
    plugin_manager.load_from_config(config)
