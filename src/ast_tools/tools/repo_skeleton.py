"""MCP tool: Intelligent project skeleton with type detection and analysis."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# TOML parsing: stdlib in 3.11+, tomli for 3.10
try:
    import tomllib  # py311+
except ImportError:
    try:
        import tomli as tomllib  # py310 via pip
    except ImportError:
        tomllib = None  # type: ignore[assignment]



INDICATORS: dict[str, list[tuple[str, int]]] = {
    "python": [
        ("pyproject.toml", 3),
        ("setup.py", 2),
        ("setup.cfg", 1),
        ("*.py", 1),
        ("src/__init__.py", 2),
    ],
    "node": [
        ("package.json", 3),
        ("*.js", 1),
        ("*.ts", 1),
        ("tsconfig.json", 1),
    ],
    "go": [("go.mod", 3), ("*.go", 1)],
    "rust": [("Cargo.toml", 3), ("*.rs", 1)],
}


def _detect_project_type(root: Path) -> tuple[str, float, list[str]]:
    """Detect project type using scoring-based indicator system."""
    scores: dict[str, int] = {}
    indicators_found: dict[str, list[str]] = {}

    for proj_type, checks in INDICATORS.items():
        score = 0
        found: list[str] = []
        for pattern, weight in checks:
            if pattern.startswith("*."):
                ext = pattern[1:]
                matches = list(root.rglob("*" + ext))
                if matches:
                    score += weight
                    found.append(f"{len(matches)}× {pattern}")
            elif pattern.startswith("src/"):
                if (root / pattern).exists():
                    score += weight
                    found.append(pattern)
            else:
                if (root / pattern).exists():
                    score += weight
                    found.append(pattern)
        if score > 0:
            scores[proj_type] = score
            indicators_found[proj_type] = found

    if not scores:
        return "unknown", 0.0, []

    winner = max(scores, key=scores.get)  # type: ignore[arg-type]
    winning_score = scores[winner]
    confidence = min(1.0, winning_score / 5.0)
    return winner, confidence, indicators_found.get(winner, [])


def _build_ascii_tree(root: Path, max_depth: int = 5) -> str:
    """Build ASCII directory tree with box-drawing characters."""
    lines: list[str] = []
    root_name = root.name or str(root)

    def _scan(path: Path, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth:
            lines.append(f"{prefix}└── ...")
            return
        try:
            items = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
        except PermissionError:
            lines.append(f"{prefix}└── [permission denied]")
            return

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            marker = "└── " if is_last else "├── "
            if item.is_dir():
                lines.append(f"{prefix}{marker}{item.name}/")
                extension = "    " if is_last else "│   "
                _scan(item, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{marker}{item.name}")

    lines.append(f"{root_name}/")
    _scan(root)
    return "\n".join(lines)


def _parse_python_deps(root: Path) -> dict[str, list[str]]:
    """Parse Python dependencies from pyproject.toml or requirements.txt."""
    deps: dict[str, list[str]] = {"direct": [], "dev": []}

    pyproject = root / "pyproject.toml"
    if pyproject.exists() and tomllib is not None:
        try:
            with open(pyproject, "rb") as f:
                config = tomllib.load(f)
            project = config.get("project", {})
            deps["direct"] = project.get("dependencies", [])
            opt_deps = project.get("optional-dependencies", {})
            for group, group_deps in opt_deps.items():
                deps["dev"].extend(group_deps)
            return deps
        except Exception:
            pass

    # Fallback to requirements.txt
    req_file = root / "requirements.txt"
    if req_file.exists():
        try:
            text = req_file.read_text()
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    deps["direct"].append(line)
        except Exception:
            pass

    return deps


def _parse_node_deps(root: Path) -> dict[str, list[str]]:
    """Parse Node.js dependencies from package.json."""
    deps: dict[str, list[str]] = {"direct": [], "dev": []}
    pkg = root / "package.json"
    if not pkg.exists():
        return deps
    try:
        config = json.loads(pkg.read_text())
        deps["direct"] = list(config.get("dependencies", {}).keys())
        deps["dev"] = list(config.get("devDependencies", {}).keys())
    except Exception:
        pass
    return deps


def _parse_go_deps(root: Path) -> dict[str, list[str]]:
    """Parse Go dependencies from go.mod."""
    deps: dict[str, list[str]] = {"direct": [], "dev": []}
    gomod = root / "go.mod"
    if not gomod.exists():
        return deps
    try:
        in_require = False
        for line in gomod.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("require (") or stripped == "require":
                in_require = True
                continue
            if in_require and stripped == ")":
                break
            if in_require and stripped:
                parts = stripped.split()
                if parts:
                    deps["direct"].append(parts[0])
    except Exception:
        pass
    return deps


def _parse_rust_deps(root: Path) -> dict[str, list[str]]:
    """Parse Rust dependencies from Cargo.toml."""
    deps: dict[str, list[str]] = {"direct": [], "dev": []}
    cargo = root / "Cargo.toml"
    if not cargo.exists() or tomllib is None:
        return deps
    try:
        with open(cargo, "rb") as f:
            config = tomllib.load(f)
        deps["direct"] = list(config.get("dependencies", {}).keys())
        deps["dev"] = list(config.get("dev-dependencies", {}).keys())
    except Exception:
        pass
    return deps

def _build_dep_graph(root: Path, project_type: str, deps: dict[str, list[str]]) -> dict[str, list[str]]:
    """Builds the dependency graph based on project type and identified dependencies."""
    dep_graph: dict[str, list[str]] = {}

    if project_type == "python":
        # Main dependencies typically go under "src/"
        if deps.get("direct"):
            dep_graph["src/"] = deps["direct"]
        # Dev dependencies typically go under "tests/"
        if deps.get("dev"):
            dep_graph["tests/"] = deps["dev"]
    elif project_type == "node":
        # Node.js dependencies typically go under "src/"
        if deps.get("direct"):
            dep_graph["src/"] = deps["direct"]
        if deps.get("dev"):
            # For Node.js, dev dependencies might also be conceptually under src/ or be managed differently.
            # For simplicity, mapping to src/ as per instruction.
            # A more sophisticated approach might differentiate or exclude dev deps from graph.
            if "src/" in dep_graph:
                dep_graph["src/"].extend(deps["dev"])
            else:
                dep_graph["src/"] = deps["dev"]
    # Add other project types if needed in the future

    # Remove duplicates and sort for consistent output
    for dir_path in dep_graph:
        dep_graph[dir_path] = sorted(list(set(dep_graph[dir_path])))

    return dep_graph


def _collect_structure(
    root: Path,
    include_tests: bool = True,
    include_configs: bool = True,
) -> dict[str, Any]:
    """Collect project structure information."""
    directories: list[dict[str, Any]] = []
    key_files: list[dict[str, Any]] = []
    entry_points: list[str] = []
    test_files: list[str] = []
    config_files: list[str] = []

    config_extensions = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}
    entry_file_names = {"main.py", "app.py", "__main__.py", "cli.py", "index.js", "index.ts", "main.go", "main.rs"}

    for root_dir, dirs, files in os.walk(root):
        # Skip hidden dirs and common non-project dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".venv", "venv", "target", "dist", "build", ".eggs", ".git", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".hg", ".svn"}]

        # Limit file count per directory for performance
        max_files_per_dir = 200
        if len(files) > max_files_per_dir:
            files = files[:max_files_per_dir]

        current = Path(root_dir)
        try:
            rel = current.relative_to(root)
        except ValueError:
            continue
        rel_str = "." if rel == Path(".") else str(rel)

        if rel_str == ".":
            dir_type = "root"
        elif rel.name == "src" and not any(p.name == "src" for p in rel.parents):
            dir_type = "src"
        elif rel.name.startswith("test"):
            dir_type = "tests"
        elif rel.name.startswith("doc"):
            dir_type = "docs"
        elif rel.name in {"config", "configs", "cfg"}:
            dir_type = "config"
        else:
            dir_type = "package"

        dir_file_count = len(files)
        directories.append({"path": rel_str, "type": dir_type, "file_count": dir_file_count})

        for fname in files:
            fpath = current / fname
            try:
                frel = str(fpath.relative_to(root))
            except ValueError:
                continue

            role = None
            if fname in entry_file_names or (fname == "__init__.py" and dir_type == "src"):
                role = "entry_point"
                entry_points.append(frel)
            elif fname.startswith("test_") or fname.endswith(("_test.py", "_test.rs", "_test.go")):
                role = "test"
                if include_tests:
                    test_files.append(frel)
            elif fname in {"pyproject.toml", "setup.py", "setup.cfg", "package.json", "go.mod", "Cargo.toml"}:
                role = "build_config"
                config_files.append(frel)
            elif fname in {"README.md", "LICENSE", "CONTRIBUTING.md", "CHANGELOG.md"}:
                role = "documentation"
            elif fname in {"Dockerfile", "docker-compose.yml", ".env.example", ".gitignore"}:
                role = "config"
                config_files.append(frel)
            elif Path(fname).suffix in config_extensions and include_configs:
                role = "config"
                config_files.append(frel)

            if role:
                key_files.append({"path": frel, "role": role})

    return {
        "directories": directories,
        "key_files": key_files,
        "entry_points": entry_points,
        "test_files": test_files,
        "config_files": config_files,
    }


def _tool_repo_skeleton(params: dict[str, Any]) -> dict[str, Any]:
    """Generate intelligent project skeleton with type detection, key file identification,
    ASCII directory tree, and dependency graph.

    Args:
        root_path: Project root directory (required)
        max_depth: Max directory depth for tree (default: 5)
        include_tests: Include test files in output (default: True)
        include_configs: Include config files in output (default: True)
        generate_deps: Parse and include dependencies (default: True)

    Returns:
        Dict with project_type, confidence, structure, dependencies, tree_ascii, summary
    """
    root_path_str = params.get("root_path") or params.get("path", ".")
    max_depth = params.get("max_depth", 5)
    include_tests = params.get("include_tests", True)
    include_configs = params.get("include_configs", True)
    generate_deps = params.get("generate_deps", True)

    root = Path(root_path_str).expanduser().resolve()
    if not root.exists():
        return {"error": f"Path does not exist: {root_path_str}", "error_code": "NOT_FOUND"}
    if not root.is_dir():
        return {"error": f"Path is not a directory: {root_path_str}", "error_code": "NOT_A_DIR"}

    # Detect project type
    project_type, confidence, detected_indicators = _detect_project_type(root)

    # Collect structure
    structure = _collect_structure(root, include_tests, include_configs)

    # Build ASCII tree
    tree_ascii = _build_ascii_tree(root, max_depth)

    # Parse dependencies
    dependencies: dict[str, list[str]] = {"direct": [], "dev": []}
    dependency_graph: dict[str, list[str]] = {}
    if generate_deps:
        if project_type == "python":
            dependencies = _parse_python_deps(root)
        elif project_type == "node":
            dependencies = _parse_node_deps(root)
        elif project_type == "go":
            dependencies = _parse_go_deps(root)
        elif project_type == "rust":
            dependencies = _parse_rust_deps(root)

        # Build dependency graph
        dependency_graph = _build_dep_graph(root, project_type, dependencies)

    # Build summary
    total_dirs = len(structure["directories"])
    total_files = sum(d["file_count"] for d in structure["directories"])
    summary_parts = [
        f"{project_type.capitalize()} project ({project_type} layout) with {total_dirs} directories and {total_files} files.",
    ]
    n_key_files = len(structure["key_files"])
    if n_key_files:
        summary_parts.append(f"Detected {n_key_files} key files.")
    if structure["entry_points"]:
        summary_parts.append(f"Entry points: {', '.join(structure['entry_points'][:3])}")
    if dependencies["direct"]:
        summary_parts.append(f"Runtime deps: {len(dependencies['direct'])} packages.")
    if dependencies["dev"]:
        summary_parts.append(f"Dev deps: {len(dependencies['dev'])} packages.")
    if confidence < 0.5:
        summary_parts.append("Project type detection uncertain.")
    summary = " ".join(summary_parts)

    return {
        "project_type": project_type,
        "confidence": round(confidence, 2),
        "detected_indicators": detected_indicators,
        "structure": {
            "directories": structure["directories"],
            "key_files": structure["key_files"],
            "entry_points": sorted(set(structure["entry_points"])),
            "test_files": sorted(set(structure["test_files"])),
            "config_files": sorted(set(structure["config_files"])),
        },
        "dependencies": dependencies,
        "tree_ascii": tree_ascii,
        "files": sorted(set(f["path"] for f in structure["key_files"])),
        "summary": summary,
        "dependencies_graph": dependency_graph, # Add the dependency graph
    }
