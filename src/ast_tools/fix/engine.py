"""Core fix engine with convergence loop and safety classification."""

import hashlib
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .config import FixConfig
from .fixers import (
    FixAction,
    FixerBase,
    get_fixer_for_language,
    register_plugin_fixers,
)
from .fixers import FixerConfig as FixersFixerConfig
from ast_tools.config.unified import RUNTIME

console = Console()
logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Safety classification for fixes."""

    SAFE = "safe"  # Always apply: formatting, import sorting, unused imports
    UNSAFE = "unsafe"  # Requires explicit flag: type hints, semantic changes
    DISPLAY_ONLY = "display_only"  # Show but never auto-apply: architecture violations


@dataclass
class FixResult:
    """Result of a fix operation."""

    success: bool
    actions_applied: list[FixAction] = field(default_factory=list)
    actions_skipped: list[FixAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    iterations: int = 0
    converged: bool = False
    execution_time: float = 0.0

    @property
    def files_changed(self) -> int:
        """Number of unique files changed."""
        return len({a.file_path for a in self.actions_applied})

    @property
    def total_fixes(self) -> int:
        """Total number of fixes applied."""
        return len(self.actions_applied)


@dataclass
class FixContext:
    """Context for a fix operation."""

    project_root: Path
    target_paths: list[Path]
    languages: set[str]
    config: FixConfig
    safety_level: SafetyLevel = SafetyLevel.SAFE
    check_only: bool = False
    diff_only: bool = False
    verbose: bool = False
    max_iterations: int = RUNTIME.fix_max_iterations
    timeout: int = RUNTIME.timeout_fixer
    max_file_size: int = RUNTIME.max_file_size_fix
    create_backups: bool = True  # Create .bak files before modifying


class FixEngine:
    """Main orchestration engine for the auto-fix pipeline."""

    def __init__(self, context: FixContext, plugin_fixers: dict[str, str] | None = None):
        self.context = context
        self.fixers: list[FixerBase] = []
        # Load custom fixer plugins if provided
        if plugin_fixers:
            register_plugin_fixers(plugin_fixers)
        self._init_fixers()
        # Track file content hashes per iteration for oscillation detection
        self._file_hashes: dict[Path, list[str]] = {}
        # Track backup directory
        self._backup_dir: Path | None = None

    def _init_fixers(self):
        """Initialize fixers based on detected languages."""
        for lang in self.context.languages:
            fixer_class = get_fixer_for_language(lang)
            if fixer_class:
                # Get config for this fixer
                fixer_config = self.context.config.get_fixer_config(lang)
                # Convert to fixers.FixerConfig
                fixers_config = FixersFixerConfig(
                    enabled=fixer_config.enabled,
                    args=fixer_config.args,
                    config_file=fixer_config.config_file,
                    safety_override=fixer_config.safety_override,
                )
                self.fixers.append(fixer_class(fixers_config))

    def _get_backup_base(self) -> Path:
        """Return the base backup directory under user config dir."""
        from ast_tools.config.loader import get_config_dir
        return get_config_dir() / "backups"

    def _create_backup_dir(self):
        """Create a timestamped backup directory under ~/.ast-tools/backups/."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = self.context.project_root.name
        # Base: ~/.ast-tools/backups/<project>/<timestamp>/
        base = self._get_backup_base()
        self._backup_dir = base / project_name / timestamp
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._prune_old_backups()

    def _prune_old_backups(self):
        """Remove backups older than retention_days for this project."""
        retention_days = self._get_retention_days()
        cutoff = datetime.now() - timedelta(days=retention_days)
        base = self._get_backup_base()
        project_name = self.context.project_root.name
        project_dir = base / project_name
        if not project_dir.exists():
            return
        count = 0
        for backup_dir in sorted(project_dir.iterdir()):
            if not backup_dir.is_dir():
                continue
            try:
                ts = datetime.strptime(backup_dir.name, "%Y%m%d_%H%M%S")
                if ts < cutoff:
                    shutil.rmtree(backup_dir, ignore_errors=True)
                    count += 1
            except ValueError:
                # Not a timestamp-named dir, skip
                continue
        if count:
            logger.debug(f"Pruned {count} old backup dir(s) from {project_dir}")

    @staticmethod
    def _get_retention_days_from_cfg(config: "FixContext") -> int:
        """Read backup_retention_days from config, default 7."""
        try:
            return config.backup_retention_days
        except (AttributeError, TypeError):
            return 7

    def _get_retention_days(self) -> int:
        return self._get_retention_days_from_cfg(self.context.config)

    def _backup_file(self, file_path: Path) -> bool:
        """Create a backup of the file under ~/.ast-tools/backups/."""
        if not self.context.create_backups or not self._backup_dir:
            return False
        try:
            # Compute relative path to preserve directory structure
            rel_path = file_path.relative_to(self.context.project_root)
            backup_path = self._backup_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            return True
        except Exception:
            return False

    def _check_file_safety(self, file_path: Path) -> tuple[bool, str | None]:
        """Check if file is safe to process."""
        try:
            # Check if it's a symlink
            if file_path.is_symlink():
                return False, f"Symlink detected: {file_path}"

            # Check if it's within project_root (no path traversal)
            try:
                file_path.resolve().relative_to(self.context.project_root.resolve())
            except ValueError:
                return False, f"Path outside project root: {file_path}"

            # Check file size
            stat = file_path.stat()
            if stat.st_size > self.context.max_file_size:
                return (
                    False,
                    f"File too large ({stat.st_size} bytes > {self.context.max_file_size}): {file_path}",
                )

            # Check if binary (contains null bytes in first 512 bytes)
            with open(file_path, "rb") as f:
                header = f.read(512)
                if b"\x00" in header:
                    return False, f"Binary file detected: {file_path}"

            # Check if writable
            if not file_path.is_file() or not (stat.st_mode & 0o200):
                return False, f"Not a writable regular file: {file_path}"

            return True, None
        except Exception as e:
            return False, f"Safety check failed: {e}"

    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file content."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _check_oscillation(self, file_path: Path, current_hash: str) -> bool:
        """Check if file is oscillating (same hash seen before in different iteration)."""
        if file_path not in self._file_hashes:
            self._file_hashes[file_path] = []
        # Check if we've seen this hash before in a different iteration
        if current_hash in self._file_hashes[file_path][:-1]:  # Exclude current iteration
            return True
        self._file_hashes[file_path].append(current_hash)
        return False

    def run(self) -> FixResult:
        """Run the full fix pipeline with convergence loop."""
        # Initialize backup directory if needed
        if self.context.create_backups:
            self._create_backup_dir()

        start_time = time.time()
        all_actions: list[FixAction] = []
        all_errors: list[str] = []
        all_skipped: list[FixAction] = []
        iteration = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Running auto-fix pipeline...", total=self.context.max_iterations
            )

            while iteration < self.context.max_iterations:
                iteration += 1
                progress.update(
                    task,
                    advance=1,
                    description=f"Iteration {iteration}/{self.context.max_iterations}",
                )

                # Phase 1: Collect all fix actions
                iteration_actions = self._collect_fix_actions()

                if not iteration_actions:
                    # No more fixes to apply
                    break

                # Phase 2: Filter by safety level
                safe_actions = [a for a in iteration_actions if a.safety == "safe"]
                unsafe_actions = [a for a in iteration_actions if a.safety == "unsafe"]

                actions_to_apply = safe_actions
                if self.context.safety_level == SafetyLevel.UNSAFE:
                    actions_to_apply.extend(unsafe_actions)

                if self.context.check_only or self.context.diff_only:
                    # In check/diff mode, just report what would be done
                    for action in actions_to_apply:
                        if self.context.diff_only:
                            self._show_diff(action)
                        all_actions.append(action)
                    break

                # Phase 3: Apply fixes
                applied, skipped, errors = self._apply_fixes(actions_to_apply)
                all_actions.extend(applied)
                all_skipped.extend(skipped)
                all_errors.extend(errors)

                if not applied:
                    # Nothing applied this iteration
                    break

                # Phase 4: Check for oscillation
                oscillating_files = []
                for action in applied:
                    file_hash = self._get_file_hash(action.file_path)
                    if self._check_oscillation(action.file_path, file_hash):
                        oscillating_files.append(str(action.file_path))

                if oscillating_files:
                    warning = f"Oscillation detected in files: {', '.join(oscillating_files)}. Stopping to prevent infinite loop."
                    if self.context.verbose:
                        console.print(f"  [red]⚠[/red] {warning}")
                    all_errors.append(warning)
                    break

                # Phase 5: Verify convergence
                remaining_issues = self._verify_all()
                if not remaining_issues:
                    # Converged - no more issues
                    break

            progress.update(task, completed=self.context.max_iterations)

        execution_time = time.time() - start_time

        return FixResult(
            success=len(all_errors) == 0,
            actions_applied=all_actions,
            actions_skipped=all_skipped,
            errors=all_errors,
            iterations=iteration,
            converged=iteration < self.context.max_iterations,
            execution_time=execution_time,
        )

    def _collect_fix_actions(self) -> list[FixAction]:
        """Collect fix actions from all fixers."""
        all_actions = []

        # Load .gitignore patterns if available
        gitignore_spec = self._load_gitignore_spec()

        for fixer in self.fixers:
            if not fixer.is_available():
                if self.context.verbose:
                    console.print(f"  [yellow]⚠[/yellow] {fixer.name}: not available, skipping")
                continue

            # Detect files for this fixer
            files = fixer.detect(self.context.target_paths)
            if not files:
                continue

            # Apply safety checks to filter files
            safe_files = []
            for file_path in files:
                is_safe, reason = self._check_file_safety(file_path)
                if not is_safe:
                    if self.context.verbose:
                        console.print(f"  [yellow]⊘[/yellow] Skipping {file_path}: {reason}")
                    continue

                # Check .gitignore patterns
                if gitignore_spec and gitignore_spec.match_file(
                    str(file_path.relative_to(self.context.project_root))
                ):
                    if self.context.verbose:
                        console.print(
                            f"  [yellow]⊘[/yellow] Skipping {file_path}: matched .gitignore pattern"
                        )
                    continue

                safe_files.append(file_path)

            if not safe_files:
                continue

            # Get fix actions
            try:
                actions = fixer.analyze(safe_files)
                all_actions.extend(actions)
            except Exception as e:
                all_errors = getattr(self, "_collect_errors", [])
                all_errors.append(f"{fixer.name}: {e}")
                self._collect_errors = all_errors

        return all_actions

    def _load_gitignore_spec(self):
        """Load .gitignore patterns as a pathspec spec."""
        try:
            import pathspec

            gitignore_path = self.context.project_root / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path) as f:
                    lines = f.read().splitlines()
                # Filter out comments and empty lines
                patterns = [
                    line for line in lines if line.strip() and not line.strip().startswith("#")
                ]
                return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        except ImportError:
            if self.context.verbose:
                console.print(
                    "  [yellow]⚠[/yellow] pathspec not available, .gitignore patterns not respected"
                )
        except Exception:
            pass
        return None

    def _apply_fixes(
        self, actions: list[FixAction]
    ) -> tuple[list[FixAction], list[FixAction], list[str]]:
        """Apply fix actions, handling conflicts."""
        applied = []
        skipped = []
        errors = []

        # Group by file to handle conflicts
        by_file: dict[Path, list[FixAction]] = {}
        for action in actions:
            by_file.setdefault(action.file_path, []).append(action)

        for file_path, file_actions in by_file.items():
            # Sort by position to apply in order
            file_actions.sort(key=lambda a: a.metadata.get("position", 0))

            # Create backup before any modifications
            if self.context.create_backups:
                self._backup_file(file_path)

            # Apply each action
            for action in file_actions:
                try:
                    fixer = self._get_fixer_for_tool(action.tool)
                    if fixer and fixer.apply_fix(action):
                        applied.append(action)
                        if self.context.verbose:
                            console.print(
                                f"  [green]✓[/green] {action.tool}: {action.description} in {action.file_path}"
                            )
                    else:
                        skipped.append(action)
                        if self.context.verbose:
                            console.print(
                                f"  [yellow]⊘[/yellow] {action.tool}: {action.description} in {action.file_path} (skipped)"
                            )
                except Exception as e:
                    errors.append(f"{action.tool} on {action.file_path}: {e}")
                    if self.context.verbose:
                        console.print(
                            f"  [red]✗[/red] {action.tool}: {action.description} in {action.file_path} - {e}"
                        )

        return applied, skipped, errors

    def _verify_all(self) -> list[str]:
        """Verify all fixers - return remaining issues."""
        all_issues = []
        for fixer in self.fixers:
            files = fixer.detect(self.context.target_paths)
            if files:
                try:
                    issues = fixer.verify(files)
                    all_issues.extend(issues)
                except Exception:
                    pass
        return all_issues

    def _get_fixer_for_tool(self, tool: str) -> FixerBase | None:
        """Get fixer instance for a tool name."""
        for fixer in self.fixers:
            if fixer.name == tool or tool in tool:
                return fixer
        return None

    def _show_diff(self, action: FixAction):
        """Show diff for a fix action."""
        import difflib

        orig_lines = action.original_content.splitlines(keepends=True)
        fixed_lines = action.fixed_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            orig_lines,
            fixed_lines,
            fromfile=f"a/{action.file_path}",
            tofile=f"b/{action.file_path}",
        )
        console.print("".join(diff))
