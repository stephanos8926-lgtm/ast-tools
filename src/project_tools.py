#!/usr/bin/env python3
"""Project intelligence tools — scan codebases and generate project.json manifests."""

import ast
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Project root detection ───────────────────────────────────────────────

_PROJECT_MARKERS = (".git", "pyproject.toml", "setup.py", "setup.cfg", "package.json")


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
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".tox", ".eggs", "build", "dist", ".mypy_cache", ".pytest_cache",
        ".idea", ".vscode", "site-packages",
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
                    methods.append({
                        "name": item.name,
                        "line": item.lineno,
                    })
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "methods": methods,
            })
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append({
                "name": node.name,
                "line": node.lineno,
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    variables.append({
                        "name": target.id,
                        "line": node.lineno,
                    })

    return {
        "classes": classes,
        "functions": functions,
        "variables": variables,
        "docstring": ast.get_docstring(tree),
    }


def _detect_test_framework(project_root: Path) -> tuple[str, int, str]:
    """Detect test framework and count test files."""
    test_files = []
    for p in _scan_python_files(project_root):
        if "test" in p.name.lower() or "tests" in p.parts:
            test_files.append(p)

    # Check which framework is used
    framework = "unknown"
    test_command = "pytest"

    if (project_root / "pytest.ini").exists() or (project_root / "pyproject.toml").exists():
        content = ""
        for cfg in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"):
            fp = project_root / cfg
            if fp.exists():
                content += fp.read_text(errors="replace")
        if "pytest" in content:
            framework = "pytest"
            test_command = "python3 -m pytest"
    elif (project_root / "package.json").exists():
        framework = "jest"
        test_command = "npm test"

    return framework, len(test_files), test_command


def _detect_entry_points(project_root: Path) -> list[str]:
    """Find likely entry points (CLI scripts, main modules)."""
    entry_points = []
    # Check pyproject.toml for [project.scripts]
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            scripts = data.get("project", {}).get("scripts", {})
            entry_points.extend(scripts.values())
        except Exception:
            pass
    # Check for common entry point patterns
    for name in ("cli.py", "main.py", "app.py", "manage.py", "server.py", "__main__.py"):
        for p in _scan_python_files(project_root):
            if p.name == name:
                rel = p.relative_to(project_root)
                entry_points.append(str(rel))
    return list(dict.fromkeys(entry_points))  # dedupe, preserve order


def _extract_languages(project_root: Path) -> dict[str, dict[str, int]]:
    """Count files by language (extension)."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".rs": "rust",
        ".go": "go", ".java": "java", ".c": "c", ".cpp": "cpp",
        ".h": "c", ".rb": "ruby", ".php": "php",
    }
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox"}
    counts: dict[str, dict[str, int]] = {}
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in ext_map:
                lang = ext_map[ext]
                counts.setdefault(lang, {"files": 0, "lines": 0})
                counts[lang]["files"] += 1
                try:
                    lines = len(Path(dirpath, fn).read_text(errors="replace").splitlines())
                    counts[lang]["lines"] += lines
                except OSError:
                    pass
    return counts


# ─── Main API ─────────────────────────────────────────────────────────────

def generate_project_json(cwd: str | Path) -> dict[str, Any]:
    """Generate project.json data by scanning the codebase."""
    root = find_project_root(cwd)
    languages = _extract_languages(root)
    framework, test_count, test_cmd = _detect_test_framework(root)
    entry_points = _detect_entry_points(root)

    # Scan symbols from Python files
    modules: list[dict[str, Any]] = []
    symbol_index: dict[str, dict[str, Any]] = {}

    for py_file in _scan_python_files(root):
        rel = py_file.relative_to(root)
        symbols = _extract_symbols_from_file(py_file)
        lines = len(py_file.read_text(errors="replace").splitlines())
        if symbols["classes"] or symbols["functions"]:
            modules.append({
                "path": str(rel),
                "lines": lines,
                "classes": [c["name"] for c in symbols["classes"]],
                "functions": [f["name"] for f in symbols["functions"]],
            })
        for cls in symbols["classes"]:
            symbol_index[cls["name"]] = {"file": str(rel), "line": cls["line"], "type": "class"}
        for fn in symbols["functions"]:
            symbol_index[fn["name"]] = {"file": str(rel), "line": fn["line"], "type": "function"}

    project_data = {
        "name": root.name,
        "version": "0.1.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "generator": "ast-tools-project-v1",
        "languages": languages,
        "entry_points": entry_points,
        "test_framework": framework,
        "test_files": test_count,
        "test_command": test_cmd,
        "modules": modules,
        "indices": {
            "symbols": "references/symbol_index.json",
        },
    }

    return project_data


def project_info(cwd: str | Path) -> dict[str, Any]:
    """Return project intelligence: read existing or auto-generate."""
    existing = read_project_json(cwd)
    if existing:
        return existing
    return generate_project_json(cwd)


def project_init(cwd: str | Path) -> dict[str, Any]:
    """Generate project.json + references and write to disk."""
    root = find_project_root(cwd)
    data = generate_project_json(cwd)

    # Write project.json
    write_project_json(root, data)

    # Write references
    refs_dir = root / "references"
    refs_dir.mkdir(exist_ok=True)

    # Symbol index — map every symbol to file:line + collect references
    symbol_index: dict[str, dict[str, Any]] = {}
    for mod in data.get("modules", []):
        for cls in mod.get("classes", []):
            symbol_index[cls] = {"file": mod["path"], "type": "class"}
        for fn in mod.get("functions", []):
            symbol_index[fn] = {"file": mod["path"], "type": "function"}

    # Dependency graph — import relationships between modules
    dep_graph: dict[str, list[str]] = {}
    for py_file in _scan_python_files(root):
        rel = str(py_file.relative_to(root))
        deps = []
        try:
            source = py_file.read_text(errors="replace")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    # Resolve relative imports to module path
                    mod_path = node.module.replace(".", "/")
                    candidate = root / f"{mod_path}.py"
                    if not candidate.exists():
                        candidate = root / mod_path / "__init__.py"
                    if candidate.exists():
                        deps.append(str(candidate.relative_to(root)))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_path = alias.name.replace(".", "/")
                        candidate = root / f"{mod_path}.py"
                        if not candidate.exists():
                            candidate = root / mod_path / "__init__.py"
                        if candidate.exists():
                            deps.append(str(candidate.relative_to(root)))
        except (SyntaxError, OSError):
            pass
        dep_graph[rel] = sorted(set(deps))

    # Write references
    refs_dir = root / "references"
    refs_dir.mkdir(exist_ok=True)

    symbol_file = refs_dir / "symbol_index.json"
    symbol_file.write_text(json.dumps(symbol_index, indent=2) + "\n", encoding="utf-8")

    dep_file = refs_dir / "dependency_graph.json"
    dep_file.write_text(json.dumps(dep_graph, indent=2) + "\n", encoding="utf-8")

    return data


def project_verify(cwd: str | Path) -> dict[str, Any]:
    """Compare generated vs committed project.json. Returns diff info."""
    root = find_project_root(cwd)
    generated = generate_project_json(cwd)
    committed_file = root / "project.json"

    if not committed_file.exists():
        return {"status": "missing", "message": "project.json does not exist", "generated": generated}

    try:
        committed = json.loads(committed_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "error", "message": f"Cannot read committed project.json: {e}"}

    # Compare key fields (ignore 'generated' timestamp)
    diffs = []
    for key in ("name", "version", "languages", "modules", "entry_points", "test_files", "test_framework"):
        gen_val = generated.get(key)
        com_val = committed.get(key)
        if gen_val != com_val:
            diffs.append({"field": key, "committed": com_val, "generated": gen_val})

    return {
        "status": "ok" if not diffs else "stale",
        "diffs": diffs,
        "committed": committed,
        "generated": generated,
    }


# ─── CLI entry point ─────────────────────────────────────────────────────

def cli_main() -> int:
    """CLI dispatch for project commands."""
    import argparse

    parser = argparse.ArgumentParser(description="AST Tools — Project Intelligence")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("project-init", help="Generate project.json + references")
    p_init.add_argument("cwd", nargs="?", default=".", help="Project root directory")

    p_update = sub.add_parser("project-update", help="Refresh project.json and indices")
    p_update.add_argument("cwd", nargs="?", default=".", help="Project root directory")

    p_verify = sub.add_parser("project-verify", help="Verify project.json is up to date")
    p_verify.add_argument("cwd", nargs="?", default=".", help="Project root directory")
    p_verify.add_argument("--quiet", "-q", action="store_true", help="Suppress output")

    p_info = sub.add_parser("project-info", help="Print project.json (read or generate)")
    p_info.add_argument("cwd", nargs="?", default=".", help="Project root directory")

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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
