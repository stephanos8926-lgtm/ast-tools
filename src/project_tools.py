#!/usr/bin/env python3
"""Project intelligence tools — scan codebases and generate project.json manifests."""

import ast
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Project root detection ───────────────────────────────────────────────

_PROJECT_MARKERS = (".git", "pyproject.toml", "setup.py", "setup.cfg", "package.json")


# ─── File hash caching ───────────────────────────────────────────────────


def _compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file's contents."""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_file_hashes(project_root: Path) -> dict[str, str]:
    """Load stored file hashes from references/.file_hashes.json."""
    hashes_file = project_root / "references" / ".file_hashes.json"
    if hashes_file.exists():
        try:
            return json.loads(hashes_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_file_hashes(project_root: Path, hashes: dict[str, str]) -> None:
    """Save file hashes to references/.file_hashes.json."""
    refs_dir = project_root / "references"
    refs_dir.mkdir(exist_ok=True)
    hashes_file = refs_dir / ".file_hashes.json"
    hashes_file.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")


def _get_changed_files(project_root: Path) -> tuple[set[str], set[str]]:
    """Compare current files vs stored hashes.

    Returns:
        (changed_files, deleted_files) — sets of relative paths.
    """
    stored = _load_file_hashes(project_root)
    current_files = set()
    changed: set[str] = set()

    for py_file in _scan_python_files(project_root):
        rel = str(py_file.relative_to(project_root))
        current_files.add(rel)
        current_hash = _compute_file_hash(py_file)
        if stored.get(rel) != current_hash:
            changed.add(rel)

    deleted = set(stored.keys()) - current_files
    return changed, deleted


def find_project_root(cwd: str | Path) -> Path:
    """Walk up from cwd looking for a project root marker."""
    path = Path(cwd).resolve()
    for _ in range(5):
        for marker in _PROJECT_MARKERS:
            if (path / marker).exists():
                return path
        parent = path.parent
        if parent == path:
            break
        path = parent
    return Path(cwd).resolve()


# ─── project.json read/write ─────────────────────────────────────────────


def read_project_json(cwd: str | Path) -> dict[str, Any] | None:
    """Find and read project.json from cwd up to 3 levels up."""
    path = Path(cwd).resolve()
    for _ in range(4):
        candidate = path / "project.json"
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "name" in data:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None


def write_project_json(project_root: Path, data: dict[str, Any]) -> Path:
    """Write project.json to the project root."""
    target = project_root / "project.json"
    target.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return target


# ─── Codebase scanning ───────────────────────────────────────────────────


def _scan_python_files(project_root: Path) -> list[Path]:
    """Find all Python files, skipping common non-project dirs."""
    skip_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".eggs",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "site-packages",
        "references",
    }
    results = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py"):
                results.append(Path(dirpath) / fn)
    return sorted(results)


def _extract_symbols_from_file(file_path: Path) -> dict[str, Any]:
    """Extract classes, functions, and top-level variables from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return {}

    classes = []
    functions = []
    variables = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    methods.append(
                        {
                            "name": item.name,
                            "line": item.lineno,
                        }
                    )
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "methods": methods,
                }
            )
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                }
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    variables.append(
                        {
                            "name": target.id,
                            "line": node.lineno,
                        }
                    )

    return {
        "classes": classes,
        "functions": functions,
        "variables": variables,
        "docstring": ast.get_docstring(tree),
    }


def _detect_test_framework(project_root: Path) -> tuple[str, int, str]:
    """Detect test framework and count test files.

    Detection order:
    1. conftest.py presence → pytest
    2. pyproject.toml / pytest.ini / setup.cfg / tox.ini with "pytest" → pytest
    3. requirements.txt with pytest → pytest
    4. Test files that import pytest → pytest
    5. Test files that import unittest → unittest
    6. package.json with jest → jest
    7. Fallback → unknown
    """
    test_files = []
    for p in _scan_python_files(project_root):
        if "test" in p.name.lower() or "tests" in p.parts:
            test_files.append(p)

    framework = "unknown"
    test_command = "pytest"

    # 1. conftest.py presence — strong pytest signal
    if (project_root / "conftest.py").exists():
        framework = "pytest"
        test_command = "python3 -m pytest"
        return framework, len(test_files), test_command

    # Also check tests/ dir for conftest.py
    for conftest in project_root.rglob("conftest.py"):
        if conftest.parent.name == "tests" or "tests" in conftest.parts:
            framework = "pytest"
            test_command = "python3 -m pytest"
            return framework, len(test_files), test_command

    # 2. Config files with pytest reference
    content = ""
    for cfg in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"):
        fp = project_root / cfg
        if fp.exists():
            content += fp.read_text(errors="replace")
    if "pytest" in content:
        framework = "pytest"
        test_command = "python3 -m pytest"
        return framework, len(test_files), test_command

    # 3. requirements.txt with pytest
    req_file = project_root / "requirements.txt"
    if req_file.exists():
        req_content = req_file.read_text(errors="replace")
        if "pytest" in req_content.lower():
            framework = "pytest"
            test_command = "python3 -m pytest"
            return framework, len(test_files), test_command

    # 4. Test files that import pytest
    for tf in test_files:
        try:
            tf_content = tf.read_text(errors="replace")
            if "import pytest" in tf_content or "from pytest" in tf_content:
                framework = "pytest"
                test_command = "python3 -m pytest"
                return framework, len(test_files), test_command
            if "import unittest" in tf_content:
                framework = "unittest"
                test_command = "python3 -m unittest"
                return framework, len(test_files), test_command
        except OSError:
            pass

    # 5. package.json with jest
    if (project_root / "package.json").exists():
        try:
            pkg = json.loads((project_root / "package.json").read_text(errors="replace"))
            deps = pkg.get("dependencies", {}) or {}
            dev_deps = pkg.get("devDependencies", {}) or {}
            if "jest" in deps or "jest" in dev_deps:
                framework = "jest"
                test_command = "npm test"
                return framework, len(test_files), test_command
        except (json.JSONDecodeError, OSError):
            pass

    return framework, len(test_files), test_command


def _detect_entry_points(project_root: Path) -> list[str]:
    """Find likely entry points (CLI scripts, main modules).

    Detection methods:
    1. [project.scripts] from pyproject.toml
    2. Common filename patterns (cli.py, main.py, app.py, etc.)
    3. AST-based: if __name__ == '__main__' blocks
    4. AST-based: def main() or def cli_main() functions
    5. AST-based: argparse imports (heuristic for CLI tools)
    6. AST-based: sys.argv usage
    7. AST-based: Click decorators (@click.command, @click.group)
    """
    entry_points: list[str] = []
    seen: set[str] = set()

    def _add(entry: str):
        if entry not in seen:
            seen.add(entry)
            entry_points.append(entry)

    # 1. Check pyproject.toml for [project.scripts]
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            scripts = data.get("project", {}).get("scripts", {})
            for script_val in scripts.values():
                _add(script_val)
        except Exception:
            pass

    # 2. Common filename patterns
    common_names = ("cli.py", "main.py", "app.py", "manage.py", "server.py", "__main__.py")
    for p in _scan_python_files(project_root):
        if p.name in common_names:
            rel = str(p.relative_to(project_root))
            _add(rel)

    # 3-7. AST-based detection across all Python files
    for py_file in _scan_python_files(project_root):
        try:
            source = py_file.read_text(errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        rel = str(py_file.relative_to(project_root))
        has_main_guard = False
        has_main_func = False
        has_argparse = False
        has_click = False
        has_sys_argv = False

        for node in ast.walk(tree):
            # 3. if __name__ == '__main__'
            if isinstance(node, ast.If):
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value == "__main__"
                ):
                    has_main_guard = True

            # 4. def main() or def cli_main()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in (
                "main",
                "cli_main",
            ):
                has_main_func = True

            # 5. import argparse
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "argparse":
                        has_argparse = True

            # 6. sys.argv usage
            if isinstance(node, ast.Attribute) and (
                isinstance(node.value, ast.Name) and node.value.id == "sys" and node.attr == "argv"
            ):
                has_sys_argv = True

            # 7. Click decorators
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    dec_str = ast.dump(dec)
                    if "click.command" in dec_str or "click.group" in dec_str:
                        has_click = True

        # Add findings
        if has_main_guard:
            _add(f"{rel}#if-__name__")
        if has_main_func:
            _add(f"{rel}#main")
        if has_argparse:
            _add(f"{rel}#argparse")
        if has_click:
            _add(f"{rel}#click")
        if has_sys_argv and not has_argparse:
            _add(f"{rel}#sys.argv")

    return entry_points


def _extract_languages(project_root: Path) -> dict[str, Any]:
    """Count files by language (extension), split into code and config.

    Returns a dict with two top-level keys:
        "code": {lang: {files: N, lines: N}}  — programming languages
        "config": {lang: {files: N, lines: N}} — config/doc files
    Plus a flat "all" key for backward compatibility.
    """
    code_ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".rb": "ruby",
        ".php": "php",
    }
    config_ext_map = {
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
        ".sh": "shell",
        ".txt": "text",
        ".cfg": "config",
        ".ini": "config",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
    }
    # Special filenames (no extension or unusual)
    special_file_map = {
        "dockerfile": "docker",
        "makefile": "make",
        "gemfile": "ruby",
        "rakefile": "ruby",
    }
    skip_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".eggs",
        "build",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "site-packages",
        "references",
    }
    code_counts: dict[str, dict[str, int]] = {}
    config_counts: dict[str, dict[str, int]] = {}
    all_counts: dict[str, dict[str, int]] = {}

    def _add(counts, lang, filepath):
        counts.setdefault(lang, {"files": 0, "lines": 0})
        counts[lang]["files"] += 1
        try:
            lines = len(Path(filepath).read_text(errors="replace").splitlines())
            counts[lang]["lines"] += lines
        except OSError:
            pass

    # Generated files to skip (not project source code)
    skip_files = {"project.json", "package.json", "setup.py", "setup.cfg"}

    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            if fn.lower() in skip_files:
                continue
            fp = Path(dirpath) / fn
            fn_lower = fn.lower()
            ext = os.path.splitext(fn)[1].lower()

            if fn_lower in special_file_map:
                lang = special_file_map[fn_lower]
                _add(all_counts, lang, fp)
                _add(config_counts, lang, fp)
            elif ext in code_ext_map:
                lang = code_ext_map[ext]
                _add(all_counts, lang, fp)
                _add(code_counts, lang, fp)
            elif ext in config_ext_map:
                lang = config_ext_map[ext]
                _add(all_counts, lang, fp)
                _add(config_counts, lang, fp)

    return {
        "all": all_counts,
        "code": code_counts,
        "config": config_counts,
    }


# ─── Main API ─────────────────────────────────────────────────────────────


def generate_project_json(cwd: str | Path, diff: bool = False) -> dict[str, Any]:
    """Generate project.json data by scanning the codebase.

    Args:
        cwd: Project root or subdirectory.
        diff: If True, compare current symbols vs last-written symbol_index.json
              and include an "added"/"removed"/"modified" section.
    """
    root = find_project_root(cwd)
    languages = _extract_languages(root)
    framework, test_count, test_cmd = _detect_test_framework(root)
    entry_points = _detect_entry_points(root)

    # Incremental scanning: only re-parse changed files
    _changed_files, deleted_files = _get_changed_files(root)
    stored_hashes = _load_file_hashes(root)

    # Scan symbols from Python files
    modules: list[dict[str, Any]] = []
    symbol_index: dict[str, dict[str, Any]] = {}

    for py_file in _scan_python_files(root):
        rel = py_file.relative_to(root)
        symbols = _extract_symbols_from_file(py_file)
        lines = len(py_file.read_text(errors="replace").splitlines())
        if symbols["classes"] or symbols["functions"]:
            modules.append(
                {
                    "path": str(rel),
                    "lines": lines,
                    "classes": [c["name"] for c in symbols["classes"]],
                    "functions": [f["name"] for f in symbols["functions"]],
                }
            )
        for cls in symbols["classes"]:
            symbol_index[cls["name"]] = {"file": str(rel), "line": cls["line"], "type": "class"}
        for fn in symbols["functions"]:
            symbol_index[fn["name"]] = {"file": str(rel), "line": fn["line"], "type": "function"}

    # Update file hashes after successful scan
    new_hashes = dict(stored_hashes)
    for py_file in _scan_python_files(root):
        rel = str(py_file.relative_to(root))
        new_hashes[rel] = _compute_file_hash(py_file)
    # Remove hashes for deleted files
    for deleted in deleted_files:
        new_hashes.pop(deleted, None)
    _save_file_hashes(root, new_hashes)

    project_data = {
        "name": root.name,
        "version": "0.1.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "generator": "ast-tools-project-v1",
        "languages": languages.get("all", languages),
        "code_languages": languages.get("code", {}),
        "config_languages": languages.get("config", {}),
        "entry_points": entry_points,
        "test_framework": framework,
        "test_files": test_count,
        "test_command": test_cmd,
        "modules": modules,
        "indices": {
            "symbols": "references/symbol_index.json",
        },
    }

    # Change detection: compare vs last symbol_index.json
    if diff:
        diff_result = _compute_symbol_diff(root, symbol_index)
        project_data["diff"] = diff_result

    return project_data


def _compute_symbol_diff(
    project_root: Path,
    current_symbols: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compare current symbols vs last-written symbol_index.json.

    Returns dict with added/removed/modified symbol entries.
    """
    index_file = project_root / "references" / "symbol_index.json"
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []

    if index_file.exists():
        try:
            old_index = json.loads(index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            old_index = {}
    else:
        old_index = {}

    old_names = set(old_index.keys())
    new_names = set(current_symbols.keys())

    for name in sorted(new_names - old_names):
        entry = current_symbols[name]
        added.append(
            {"name": name, "file": entry["file"], "line": entry["line"], "type": entry["type"]}
        )

    for name in sorted(old_names - new_names):
        entry = old_index[name]
        removed.append(
            {
                "name": name,
                "file": entry.get("file", "?"),
                "line": entry.get("line", 0),
                "type": entry.get("type", "?"),
            }
        )

    for name in sorted(old_names & new_names):
        old = old_index[name]
        new = current_symbols[name]
        if old.get("file") != new.get("file") or old.get("line") != new.get("line"):
            modified.append(
                {
                    "name": name,
                    "type": new.get("type", "?"),
                    "old": {"file": old.get("file", "?"), "line": old.get("line", 0)},
                    "new": {"file": new.get("file", "?"), "line": new.get("line", 0)},
                }
            )

    return {"added": added, "removed": removed, "modified": modified}


def project_info(cwd: str | Path) -> dict[str, Any]:
    """Return project intelligence: read existing or auto-generate."""
    existing = read_project_json(cwd)
    if existing:
        return existing
    return generate_project_json(cwd)


def project_info_summary(cwd: str | Path) -> dict[str, Any]:
    """Return a compact project summary (<500 tokens).

    Returns a dict with: name, version, languages, module_count, symbol_count,
    entry_points, test_framework, top-level module list.

    This reads existing project.json if available, or generates a fresh scan.
    """
    data = project_info(cwd)

    # Count symbols
    symbol_count = 0
    modules: list[str] = []
    for mod in data.get("modules", []):
        path = mod.get("path", "")
        modules.append(path)
        symbol_count += len(mod.get("classes", [])) + len(mod.get("functions", []))

    languages = data.get("languages", {})
    # Handle new nested format {all:..., code:..., config:...} or flat
    if isinstance(languages, dict) and "all" in languages:
        lang_summary = languages["all"]
    elif isinstance(languages, dict) and ("code" in languages or "config" in languages):
        code_langs = languages.get("code", {})
        config_langs = languages.get("config", {})
        lang_summary = {**code_langs, **config_langs}
    elif isinstance(languages, dict):
        lang_summary = languages
    else:
        lang_summary = {}

    # Limit modules list to top 15 to stay under token budget
    MAX_MODULES = 15
    if len(modules) > MAX_MODULES:
        shown = modules[:MAX_MODULES]
        module_list = [*shown, f"... +{len(modules) - MAX_MODULES} more"]
    else:
        module_list = modules

    # Limit entry points to top 5
    entry_points = data.get("entry_points", [])
    if len(entry_points) > 5:
        entry_points = [*entry_points[:5], f"... +{len(data.get('entry_points', [])) - 5} more"]

    return {
        "name": data.get("name", "?"),
        "version": data.get("version", "0.1.0"),
        "languages": lang_summary,
        "module_count": len(modules),
        "symbol_count": symbol_count,
        "entry_points": entry_points,
        "test_framework": data.get("test_framework", "unknown"),
        "test_files": data.get("test_files", 0),
        "modules": module_list,
    }


def _detect_source_roots(root: Path) -> list[Path]:
    """Detect Python import source roots for the project.

    Returns list of directories that serve as Python package roots.
    Checks: src/ layout, flat layout, pyproject.toml package_dir config.
    """
    roots = [root]  # Default: project root is the import root

    # Check for src/ layout: src/<package>/__init__.py
    src_dir = root / "src"
    if src_dir.is_dir():
        for child in src_dir.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                roots.append(src_dir)
                break

    # Check pyproject.toml for package_dir
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            pkg_dir = data.get("tool", {}).get("setuptools", {}).get("packages.find", {})
            if isinstance(pkg_dir, dict):
                where = pkg_dir.get("where", [])
                if "src" in where and src_dir not in roots:
                    roots.append(src_dir)
        except Exception:
            pass

    return roots


def _build_import_map(root: Path, source_roots: list[Path]) -> dict[str, Path]:
    """Build a mapping from import module name to actual file path.

    For example, with src/ layout:
        "mypkg.core" → root/src/mypkg/core.py
        "mypkg" → root/src/mypkg/__init__.py
    """
    import_map: dict[str, Path] = {}
    for sr in source_roots:
        for dirpath, _dirnames, filenames in os.walk(sr):
            # Skip non-package directories
            rel_dir = Path(dirpath).relative_to(sr)
            parts = rel_dir.parts
            # Build module path from directory structure
            for fn in filenames:
                if fn.endswith(".py"):
                    mod_parts = list(parts)
                    mod_parts.append(fn[:-3])  # strip .py
                    mod_name = ".".join(mod_parts)
                    fp = Path(dirpath) / fn
                    if mod_name not in import_map:
                        import_map[mod_name] = fp
                        # Also map __init__.py as the package
                        if fn == "__init__.py" and len(mod_parts) > 1:
                            pkg_name = ".".join(mod_parts[:-1])
                            if pkg_name not in import_map:
                                import_map[pkg_name] = fp
    return import_map


def _resolve_import_to_file(
    module_name: str,
    source_roots: list[Path],
    import_map: dict[str, Path],
    project_root: Path,
    current_package: str | None = None,
    level: int = 0,
) -> str | None:
    """Resolve an import module name to a relative file path.

    Returns path relative to project_root, or None if not found.
    """
    if level > 0 and current_package:
        parts = current_package.split(".")
        if level > len(parts):
            return None
        base_parts = parts[: len(parts) - (level - 1)]
        if module_name:
            abs_name = ".".join(base_parts + module_name.split("."))
        else:
            abs_name = ".".join(base_parts)
    else:
        abs_name = module_name

    # Look in import map first
    resolved_path = import_map.get(abs_name)
    if resolved_path is not None:
        try:
            return str(resolved_path.relative_to(project_root))
        except ValueError:
            pass

    # Fallback: filesystem check in each source root
    mod_path = abs_name.replace(".", "/")
    for sr in source_roots:
        candidate = sr / f"{mod_path}.py"
        if candidate.exists():
            try:
                return str(candidate.relative_to(project_root))
            except ValueError:
                pass
        candidate = sr / mod_path / "__init__.py"
        if candidate.exists():
            try:
                return str(candidate.relative_to(project_root))
            except ValueError:
                pass

    return None


def _get_current_package(file_path: Path, root: Path, source_roots: list[Path]) -> str | None:
    """Determine the Python package name for a file.

    For src/layout with file src/mypkg/core.py, returns "mypkg".
    """
    rel = file_path.relative_to(root)
    parts = rel.parts

    # Check if the file is under a source root
    for sr in source_roots:
        try:
            rel_to_sr = file_path.relative_to(sr)
            sr_parts = rel_to_sr.parts
            if file_path.name == "__init__.py":
                return ".".join(sr_parts[:-1]) if len(sr_parts) > 1 else None
            else:
                return ".".join(sr_parts[:-1]) if len(sr_parts) > 1 else None
        except ValueError:
            continue

    # Flat layout: use directory structure
    if len(parts) > 1:
        return ".".join(parts[:-1])
    return None


def project_init(cwd: str | Path) -> dict[str, Any]:
    """Generate project.json + references and write to disk.

    Improved import resolution:
    - Detects source roots (src/ layout, flat layout)
    - Handles relative imports (from . import x, from ..core import y)
    - Builds import name → file path mapping for accurate dependency resolution
    """
    root = find_project_root(cwd)
    data = generate_project_json(cwd)

    # Write project.json
    write_project_json(root, data)

    # Detect source roots and build import map for dependency resolution
    source_roots = _detect_source_roots(root)
    import_map = _build_import_map(root, source_roots)

    # Write references
    refs_dir = root / "references"
    refs_dir.mkdir(exist_ok=True)

    # Symbol index — map every symbol to file:line + collect references
    symbol_index: dict[str, dict[str, Any]] = {}
    for py_file in _scan_python_files(root):
        rel = str(py_file.relative_to(root))
        symbols = _extract_symbols_from_file(py_file)
        for cls in symbols["classes"]:
            symbol_index[cls["name"]] = {"file": rel, "line": cls["line"], "type": "class"}
        for fn in symbols["functions"]:
            symbol_index[fn["name"]] = {"file": rel, "line": fn["line"], "type": "function"}

    # Dependency graph — import relationships between modules
    dep_graph: dict[str, list[str]] = {}
    for py_file in _scan_python_files(root):
        rel = str(py_file.relative_to(root))
        deps: list[str] = []
        try:
            source = py_file.read_text(errors="replace")
            tree = ast.parse(source, filename=str(py_file))
            current_package = _get_current_package(py_file, root, source_roots)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is not None:
                    if node.level and node.level > 0:
                        # Relative import
                        mod_name = node.module if node.module else ""
                        resolved = _resolve_import_to_file(
                            mod_name,
                            source_roots,
                            import_map,
                            root,
                            current_package=current_package,
                            level=node.level,
                        )
                        if resolved and resolved not in deps:
                            deps.append(resolved)
                        # Also resolve individual imported names
                        if node.names:
                            for alias in node.names:
                                sub_mod = f"{mod_name}.{alias.name}" if mod_name else alias.name
                                sub_resolved = _resolve_import_to_file(
                                    sub_mod,
                                    source_roots,
                                    import_map,
                                    root,
                                    current_package=current_package,
                                    level=node.level,
                                )
                                if sub_resolved and sub_resolved not in deps:
                                    deps.append(sub_resolved)
                    else:
                        # Absolute import
                        mod_name = node.module
                        # Try full module path first
                        resolved = _resolve_import_to_file(mod_name, source_roots, import_map, root)
                        if resolved and resolved not in deps:
                            deps.append(resolved)
                        # Also try parent package for "from pkg.sub import name"
                        if node.names and "." in mod_name:
                            parent = mod_name.rsplit(".", 1)[0]
                            parent_resolved = _resolve_import_to_file(
                                parent, source_roots, import_map, root
                            )
                            if parent_resolved and parent_resolved not in deps:
                                deps.append(parent_resolved)

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        resolved = _resolve_import_to_file(
                            alias.name, source_roots, import_map, root
                        )
                        if resolved and resolved not in deps:
                            deps.append(resolved)
        except (SyntaxError, OSError):
            pass
        dep_graph[rel] = sorted(set(deps))

    # Write references
    symbol_file = refs_dir / "symbol_index.json"
    symbol_file.write_text(json.dumps(symbol_index, indent=2) + "\n", encoding="utf-8")

    dep_file = refs_dir / "dependency_graph.json"
    dep_file.write_text(json.dumps(dep_graph, indent=2) + "\n", encoding="utf-8")

    return data


def project_verify(cwd: str | Path, full: bool = False) -> dict[str, Any]:
    """Compare generated vs committed project.json. Returns diff info.

    Args:
        cwd: Project root directory.
        full: If True, include full committed and generated JSON in output.
              Default: False (diffs only, compact output).

    Returns:
        Compact dict with status, diffs, and optional full copies.
    """
    root = find_project_root(cwd)
    generated = generate_project_json(cwd)
    committed_file = root / "project.json"

    if not committed_file.exists():
        result: dict[str, Any] = {
            "status": "missing",
            "message": "project.json does not exist",
            "diffs": [],
        }
        if full:
            result["generated"] = generated
        return result

    try:
        committed = json.loads(committed_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {
            "status": "error",
            "message": f"Cannot read committed project.json: {e}",
            "diffs": [],
        }

    # Compare top-level fields (ignore 'generated' timestamp and 'generator')
    diffs: list[dict[str, Any]] = []
    for key in (
        "name",
        "version",
        "languages",
        "code_languages",
        "config_languages",
        "modules",
        "entry_points",
        "test_files",
        "test_framework",
    ):
        gen_val = generated.get(key)
        com_val = committed.get(key)
        if gen_val != com_val:
            # For modules, do a structural diff (added/removed/changed)
            if key == "modules" and isinstance(gen_val, list) and isinstance(com_val, list):
                gen_modules = {m["path"]: m for m in gen_val}
                com_modules = {m["path"]: m for m in com_val}
                gen_paths = set(gen_modules.keys())
                com_paths = set(com_modules.keys())
                added = sorted(gen_paths - com_paths)
                removed = sorted(com_paths - gen_paths)
                changed = []
                for path in sorted(gen_paths & com_paths):
                    if gen_modules[path] != com_modules[path]:
                        changed.append(
                            {
                                "path": path,
                                "committed": com_modules[path],
                                "generated": gen_modules[path],
                            }
                        )
                diffs.append(
                    {
                        "field": key,
                        "added": added,
                        "removed": removed,
                        "changed": changed,
                    }
                )
            else:
                diffs.append({"field": key, "committed": com_val, "generated": gen_val})

    status = "ok" if not diffs else "stale"
    result = {"status": status, "diffs": diffs}
    if status == "stale":
        result["summary"] = f"{len(diffs)} field(s) changed"
    if full:
        result["committed"] = committed
        result["generated"] = generated
    return result


# ─── CLI entry point ─────────────────────────────────────────────────────


def cli_main() -> int:
    """CLI dispatch for project commands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="ast-tools",
        description="AST Tools — Project Intelligence & Structural Code Analysis",
        epilog="Run 'ast-tools <command> --help' for more info on a specific command.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ast-tools 0.1.0",
        help="Show the version and exit.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_init = sub.add_parser(
        "project-init",
        help="Generate project.json + references for a codebase",
        description="Scan a Python codebase and generate a project.json manifest file along with reference indices (symbol index, dependency graph, file hashes).",
    )
    p_init.add_argument(
        "cwd", nargs="?", default=".", help="Project root directory (default: current directory)"
    )

    p_update = sub.add_parser(
        "project-update",
        help="Refresh project.json and indices",
        description="Re-scan the codebase and regenerate project.json and all reference files. This is a full refresh — same as project-init.",
    )
    p_update.add_argument(
        "cwd", nargs="?", default=".", help="Project root directory (default: current directory)"
    )

    p_verify = sub.add_parser(
        "project-verify",
        help="Verify project.json is up to date",
        description="Compare the generated project.json against the committed one and report any differences. Exit code 0 = up to date, 1 = stale or missing.",
    )
    p_verify.add_argument(
        "cwd", nargs="?", default=".", help="Project root directory (default: current directory)"
    )
    p_verify.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress output, only set exit code"
    )

    p_info = sub.add_parser(
        "project-info",
        help="Print project.json (read existing or generate)",
        description="Read and display the project.json manifest. If no manifest exists, auto-generate one by scanning the codebase.",
    )
    p_info.add_argument(
        "cwd", nargs="?", default=".", help="Project root directory (default: current directory)"
    )

    p_summary = sub.add_parser(
        "project-summary",
        help="Print a compact project summary (<500 tokens)",
        description="Return a compact project summary optimized for LLM context. Includes: name, version, languages, module count, symbol count, entry points, test framework, and top modules.",
    )
    p_summary.add_argument(
        "cwd", nargs="?", default=".", help="Project root directory (default: current directory)"
    )

    args = parser.parse_args()

    if args.command == "project-init":
        data = project_init(args.cwd)
        print(json.dumps(data, indent=2, default=str))
        return 0
    elif args.command == "project-update":
        data = project_init(args.cwd)  # Update = re-generate
        print(json.dumps(data, indent=2, default=str))
        return 0
    elif args.command == "project-verify":
        result = project_verify(args.cwd)
        if args.quiet:
            return 0 if result["status"] == "ok" else 1
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["status"] == "ok" else 1
    elif args.command == "project-info":
        data = project_info(args.cwd)
        print(json.dumps(data, indent=2, default=str))
        return 0
    elif args.command == "project-summary":
        data = project_info_summary(args.cwd)
        print(json.dumps(data, default=str))
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
