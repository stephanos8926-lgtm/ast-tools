"""MCP tool: Smart related file suggestions using AST import analysis, test patterns, and heuristics."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

from .structural_analysis import _ast_find_callers


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


# Directories to always skip during file scanning (performance)
_SKIP_DIRS = frozenset({
    ".venv", "venv", "env", ".env",
    "node_modules", "bower_components",
    "__pycache__", ".pytest_cache",
    ".git", ".hg", ".svn",
    "build", "dist", ".eggs", "*.egg-info",
    ".mypy_cache", ".ruff_cache",
    "target",  # Rust
    ".dub",  # D
})


def _is_skip_dir(path: Path) -> bool:
    """Check if a directory should be skipped (dotfiles or known skip dirs)."""
    return any(part.startswith(".") or part in _SKIP_DIRS for part in path.parts)


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


def _find_call_graph(
    target_path: Path,
    workspace: Path,
    max_suggestions: int,
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    """Find files that call functions defined in the target file.

    Uses `_ast_find_callers` from structural_analysis to find callers of
    each function/class method defined in the target file.

    Returns suggestions with reason='call_graph' and confidence 0.55-0.60.
    """
    suggestions: list[dict[str, Any]] = []

    try:
        source = target_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(target_path))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return suggestions

    # Collect all function/class method names defined in the target file
    defined_symbols: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_symbols.add(node.name)
        elif isinstance(node, ast.ClassDef):
            # For classes, also track their methods as "ClassName.method_name"
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_symbols.add(f"{node.name}.{child.name}")

    # For each defined symbol, find callers
    project_root_str = str(workspace)
    caller_to_funcs: dict[str, set[str]] = {}  # file path -> set of called functions

    for sym in defined_symbols:
        try:
            callers = _ast_find_callers(sym, project_root_str, max_files=100, max_depth=50)
        except Exception:
            continue
        for caller in callers:
            caller_file = caller.get("file", "")
            if not caller_file:
                continue
            full_path = str((workspace / caller_file).resolve())
            if full_path not in caller_to_funcs:
                caller_to_funcs[full_path] = set()
            caller_to_funcs[full_path].add(sym)

    # Build suggestions from caller map
    for file_path, called_symbols in caller_to_funcs.items():
        if file_path == str(target_path.resolve()):
            continue
        if file_path in existing_paths:
            continue

        # Build a clean explanation
        symbols_sorted = sorted(called_symbols)
        quoted = [f"'{s}'" for s in symbols_sorted]
        if len(quoted) <= 3:
            explanation = "Calls " + " or ".join(quoted)
        else:
            explanation = "Calls " + " or ".join(quoted[:3]) + f" and {len(quoted) - 3} more"

        suggestions.append({
            "path": file_path,
            "reason": "call_graph",
            "confidence": 0.55,
            "explanation": explanation,
        })
        existing_paths.add(file_path)

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

    # Scan workspace Python files for imports of the target — use os.walk to skip dirs
    try:
        for root_dir, dirs, files in os.walk(workspace):
            # Skip .venv, hidden dirs, and known non-project dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")
                       and d not in _SKIP_DIRS
                       and d not in {"node_modules", "__pycache__",
                                     ".venv", "venv", "target", "build",
                                     "dist", ".eggs", ".git"}]
            for fname in sorted(files):
                if not fname.endswith(".py"):
                    continue
                pyfile = Path(root_dir) / fname
                if pyfile.resolve() == target_path.resolve():
                    continue
                resolved_path = str(pyfile.resolve())
                if resolved_path in existing_paths:
                    continue

                try:
                    content = pyfile.read_text(encoding="utf-8")
                except (PermissionError, OSError, UnicodeDecodeError):
                    continue

                for pattern in search_patterns:
                    if pattern in content:
                        # Check if it's an actual import statement
                        for line in content.splitlines():
                            s = line.strip()
                            if re.match(rf"^\s*(from\s+{re.escape(pattern)}|import\s+{re.escape(pattern)})", s):
                                pyfile.relative_to(workspace)
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
        content = target_path.read_text(encoding="utf-8")
    except (PermissionError, OSError, UnicodeDecodeError):
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
        workspace = git_root or target_path.parent

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

    # Strategy 5: Call graph analysis
    remaining = max_suggestions - len(all_suggestions)
    if remaining > 0:
        call_graph = _find_call_graph(target_path, workspace, remaining, seen_paths)
        for s in call_graph:
            # _find_call_graph already deduplicates via seen_paths
            all_suggestions.append(s)

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
