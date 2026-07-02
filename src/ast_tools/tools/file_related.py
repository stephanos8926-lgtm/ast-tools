"""MCP tool: Smart related file suggestions using AST import analysis, test patterns, and heuristics."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


def _find_git_root(path: Path) -> Path | None:
    """Walk up from path to find git repository root."""
    for parent in path.parents:
        if (parent / ".git").exists():
            return parent
    return None


def _file_stem(file_path: Path) -> str:
    """Get the stem of a file, stripping test_ prefix or _test suffix."""
    stem = file_path.stem
    if stem.startswith("test_"):
        return stem[5:]
    if stem.endswith("_test"):
        return stem[:-5]
    return stem


def _find_test_files(
    target_path: Path,
    workspace: Path,
    stem: str,
    max_suggestions: int,
) -> list[dict[str, Any]]:
    """Find test files related to the target file."""
    suggestions: list[dict[str, Any]] = []
    seen = set()

    # Check multiple test patterns
    patterns = [
        workspace / f"tests/test_{stem}.py",
        workspace / f"tests/test_{stem}.rs",
        workspace / f"tests/test_{stem}.go",
        target_path.parent / f"test_{target_path.stem}.py",
        target_path.parent / f"{stem}_test.py",
        workspace / f"test_{stem}.py",
        workspace / f"{stem}_test.py",
    ]

    for pattern_path in patterns:
        resolved = pattern_path.resolve()
        if resolved.exists() and resolved.is_file() and str(resolved) not in seen:
            suggestions.append({
                "path": str(resolved),
                "reason": "test_file",
                "confidence": 0.95,
                "explanation": f"Test file matches pattern: {pattern_path.relative_to(workspace)}",
            })
            seen.add(str(resolved))
            if len(suggestions) >= max_suggestions:
                break

    return suggestions


def _find_source_from_test(
    target_path: Path,
    workspace: Path,
    stem: str,
    max_suggestions: int,
) -> list[dict[str, Any]]:
    """If the target is a test file, find the corresponding source file."""
    suggestions: list[dict[str, Any]] = []

    # Try common source locations
    source_candidates = [
        workspace / "src" / f"{stem}.py",
        workspace / f"{stem}.py",
        workspace / "lib" / f"{stem}.py",
        target_path.parent.parent / f"{stem}.py",  # tests/ → ../stem.py
    ]

    for src in source_candidates:
        resolved = src.resolve()
        if resolved.exists() and resolved != target_path.resolve():
            suggestions.append({
                "path": str(resolved),
                "reason": "test_file",
                "confidence": 0.90,
                "explanation": "Source file corresponding to test file",
            })
            if len(suggestions) >= max_suggestions:
                break

    return suggestions


def _find_siblings(
    target_path: Path,
    max_suggestions: int,
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    """Find files in the same directory."""
    suggestions: list[dict[str, Any]] = []
    parent = target_path.parent
    if not parent.exists():
        return suggestions

    try:
        files = sorted(
            [p for p in parent.iterdir() if p.is_file() and p.suffix == ".py" and p != target_path.resolve()],
            key=lambda x: x.name,
        )
    except PermissionError:
        return suggestions

    for f in files:
        resolved = str(f.resolve())
        if resolved not in existing_paths:
            suggestions.append({
                "path": resolved,
                "reason": "sibling",
                "confidence": 0.55,
                "explanation": f"Same directory ({parent.name}/)",
            })
            existing_paths.add(resolved)
            if len(suggestions) >= max_suggestions:
                break

    return suggestions


def _find_name_matches(
    stem: str,
    workspace: Path,
    target_path: Path,
    max_suggestions: int,
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    """Find files with the same stem in different directories."""
    suggestions: list[dict[str, Any]] = []
    try:
        pattern = f"**/{stem}.py"
        matches = sorted(workspace.glob(pattern))
    except (PermissionError, OSError):
        return suggestions

    for match_path in matches:
        resolved = str(match_path.resolve())
        if resolved not in existing_paths and match_path.resolve() != target_path.resolve():
            try:
                rel = match_path.relative_to(workspace)
            except ValueError:
                rel = match_path
            suggestions.append({
                "path": resolved,
                "reason": "name_match",
                "confidence": 0.45,
                "explanation": f"Same stem name: {rel}",
            })
            existing_paths.add(resolved)
            if len(suggestions) >= max_suggestions:
                break

    return suggestions


def _parse_imports(file_content: str) -> list[str]:
    """Parse import statements from Python file content."""
    imports: list[str] = []

    for line in file_content.splitlines():
        line = line.strip()

        # import X
        m = re.match(r"^import\s+([a-zA-Z_][a-zA-Z0-9_.]*)", line)
        if m:
            imports.append(m.group(1))

        # from X import Y
        m = re.match(r"^from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import", line)
        if m:
            imports.append(m.group(1))

        # from . import Y (relative)
        m = re.match(r"^from\s+\.(.+?)\s+import", line)
        if m:
            imports.append(m.group(1))

    return imports


def _resolve_import_to_path(
    import_module: str,
    target_dir: Path,
    workspace: Path,
) -> list[Path]:
    """Resolve a Python import string to one or more file paths."""
    candidates: list[Path] = []

    # Convert dotted to path
    module_path = import_module.replace(".", "/")

    # Try various locations
    locations = [
        workspace / "src" / f"{module_path}.py",
        workspace / "src" / module_path / "__init__.py",
        workspace / f"{module_path}.py",
        workspace / module_path / "__init__.py",
        target_dir / f"{module_path}.py",
        target_dir / module_path / "__init__.py",
    ]

    for loc in locations:
        resolved = loc.resolve()
        if resolved.exists():
            candidates.append(resolved)

    return candidates


def _find_imported_by(
    target_path: Path,
    workspace: Path,
    target_stem: str,
    max_suggestions: int,
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    """Find files that import FROM the target file."""
    suggestions: list[dict[str, Any]] = []

    # Patterns to look for in import statements
    target_name = target_path.stem
    module_path = None

    # Try to determine module path from workspace-relative path
    try:
        rel = target_path.relative_to(workspace)
        parts = list(rel.parts)
        # Remove file extension from last part
        if parts:
            parts[-1] = parts[-1].replace(".py", "")
        # Remove 'src' prefix for module path
        if parts and parts[0] == "src":
            parts = parts[1:]
        if parts:
            module_path = ".".join(parts)
    except ValueError:
        module_path = target_name

    search_patterns: list[str] = []
    if module_path:
        search_patterns.append(module_path)
        search_patterns.append(module_path.split(".")[-1])

    # Scan workspace Python files for imports of the target
    try:
        for pyfile in sorted(workspace.rglob("*.py")):
            if pyfile.resolve() == target_path.resolve():
                continue
            resolved_path = str(pyfile.resolve())
            if resolved_path in existing_paths:
                continue

            try:
                content = pyfile.read_text()
            except (PermissionError, OSError):
                continue

            for pattern in search_patterns:
                if pattern in content:
                    # Check if it's an actual import statement
                    for line in content.splitlines():
                        s = line.strip()
                        if re.match(rf"^\s*(from\s+{re.escape(pattern)}|import\s+{re.escape(pattern)})", s):
                            rel_path = pyfile.relative_to(workspace)
                            suggestions.append({
                                "path": resolved_path,
                                "reason": "imported_by",
                                "confidence": 0.80,
                                "explanation": f"Imports from this file: {s[:60]}{'...' if len(s) > 60 else ''}",
                            })
                            existing_paths.add(resolved_path)
                            if len(suggestions) >= max_suggestions:
                                return suggestions
                            break
                    break  # Only one match per file

    except (PermissionError, OSError):
        pass

    return suggestions


def _find_imports_this(
    target_path: Path,
    workspace: Path,
    max_suggestions: int,
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    """Find files that the target file imports."""
    suggestions: list[dict[str, Any]] = []

    try:
        content = target_path.read_text()
    except (PermissionError, OSError):
        return suggestions

    imported_modules = _parse_imports(content)
    for mod in imported_modules:
        resolved_paths = _resolve_import_to_path(mod, target_path.parent, workspace)
        for rp in resolved_paths:
            resolved_str = str(rp)
            if resolved_str not in existing_paths and rp != target_path.resolve():
                suggestions.append({
                    "path": resolved_str,
                    "reason": "imports_this",
                    "confidence": 0.75,
                    "explanation": f"Imported by this file: {mod}",
                })
                existing_paths.add(resolved_str)
                if len(suggestions) >= max_suggestions:
                    return suggestions

    return suggestions


def _tool_file_related_suggest(params: dict[str, Any]) -> dict[str, Any]:
    """Suggest files related to a given file based on imports, test patterns, and directory structure.

    Args:
        file_path: Path to the file to find related files for (required)
        workspace: Project root directory (optional, auto-detected from git root)
        max_suggestions: Maximum number of suggestions to return (default: 5)
        include_tests: Include test file suggestions (default: True)
        include_imports: Include import-based suggestions (default: True)

    Returns:
        Dict with file path and list of suggestions with reasons and confidence scores.
    """
    raw_path = params.get("file_path", "")
    max_suggestions = params.get("max_suggestions", 5)
    include_tests = params.get("include_tests", True)
    include_imports = params.get("include_imports", True)

    if not raw_path:
        return {"error": "file_path is required", "error_code": "MISSING_PARAM"}

    target_path = Path(raw_path).expanduser().resolve()
    if not target_path.exists():
        return {"error": f"File does not exist: {raw_path}", "error_code": "NOT_FOUND"}
    if not target_path.is_file():
        return {"error": f"Path is not a file: {raw_path}", "error_code": "NOT_A_FILE"}

    # Determine workspace
    raw_workspace = params.get("workspace")
    if raw_workspace:
        workspace = Path(raw_workspace).expanduser().resolve()
    else:
        git_root = _find_git_root(target_path)
        if git_root:
            workspace = git_root
        else:
            workspace = target_path.parent

    stem = _file_stem(target_path)
    all_suggestions: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    # Strategy 1: Test file detection
    if include_tests:
        if stem != target_path.stem:
            # File is a test file — find source
            src_results = _find_source_from_test(target_path, workspace, _file_stem(target_path), max_suggestions)
            for s in src_results:
                if s["path"] not in seen_paths:
                    all_suggestions.append(s)
                    seen_paths.add(s["path"])
        else:
            # Normal file — find test files
            test_results = _find_test_files(target_path, workspace, stem, max_suggestions)
            for s in test_results:
                if s["path"] not in seen_paths:
                    all_suggestions.append(s)
                    seen_paths.add(s["path"])

    # Strategy 2: Import relationships
    if include_imports:
        remaining = max_suggestions - len(all_suggestions)
        if remaining > 0:
            imported_by = _find_imported_by(target_path, workspace, stem, remaining, seen_paths)
            for s in imported_by:
                if s["path"] not in seen_paths:
                    all_suggestions.append(s)
                    seen_paths.add(s["path"])

        remaining = max_suggestions - len(all_suggestions)
        if remaining > 0:
            imports_this = _find_imports_this(target_path, workspace, remaining, seen_paths)
            for s in imports_this:
                if s["path"] not in seen_paths:
                    all_suggestions.append(s)
                    seen_paths.add(s["path"])

    # Strategy 3: Same-directory siblings
    remaining = max_suggestions - len(all_suggestions)
    if remaining > 0:
        siblings = _find_siblings(target_path, remaining, seen_paths)
        for s in siblings:
            if s["path"] not in seen_paths:
                all_suggestions.append(s)
                seen_paths.add(s["path"])

    # Strategy 4: Name matching
    remaining = max_suggestions - len(all_suggestions)
    if remaining > 0:
        name_matches = _find_name_matches(stem, workspace, target_path, remaining, seen_paths)
        for s in name_matches:
            if s["path"] not in seen_paths:
                all_suggestions.append(s)
                seen_paths.add(s["path"])

    # Deduplicate by path (keep highest confidence first)
    seen_dedup: dict[str, dict[str, Any]] = {}
    for s in all_suggestions:
        p = s["path"]
        if p not in seen_dedup:
            seen_dedup[p] = s

    final_suggestions = sorted(seen_dedup.values(), key=lambda x: -x["confidence"])[:max_suggestions]

    return {
        "file": str(target_path),
        "suggestions": final_suggestions,
    }
