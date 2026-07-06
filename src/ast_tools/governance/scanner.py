"""Governance scanner — imports vs. rules comparison engine."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ast_tools.tools.dependency import build_import_graph as build_dep_graph
from ast_tools.tools.module_imports import _build_import_graph

if TYPE_CHECKING:
    from ast_tools.governance.schema import GovernanceConfig


@dataclass
class Violation:
    """A single governance violation."""

    file: str
    layer: str
    import_target: str
    target_layer: str | None
    rule_type: str  # "layer" or "tag"
    severity: str = "error"  # "error" or "warn"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "layer": self.layer,
            "import_target": self.import_target,
            "target_layer": self.target_layer,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "message": self.message or self._default_message(),
        }

    def _default_message(self) -> str:
        if self.target_layer:
            return (
                f"{self.file} (layer: {self.layer}) imports "
                f"{self.import_target} (layer: {self.target_layer}) "
                f"— not in allowed deps"
            )
        return (
            f"{self.file} (layer: {self.layer}) imports "
            f"{self.import_target} — unclassified dependency"
        )


def _is_exception(
    filepath: str, import_target: str, exceptions: list[dict[str, Any]]
) -> str | None:
    """Check if a file+import pair matches an exception.

    Returns severity override or None.
    """
    for exc in exceptions:
        pattern = exc.get("pattern", "")
        if fnmatch.fnmatch(filepath, pattern):
            return exc.get("severity", "error")
    return None


def _detect_file_layer(
    filepath: str, config: GovernanceConfig
) -> str | None:
    """Determine layer for a file, checking all mapping patterns."""
    rel = str(Path(filepath).as_posix())
    for rule in config.mappings:
        if fnmatch.fnmatch(rel, rule.pattern):
            return rule.layer
    return None


def _normalize_import(import_path: str, project_root: Path) -> str:
    """Convert an import to a normalized module path."""
    imp = import_path.replace("/", ".").replace(".py", "")
    # Remove leading project name if present
    parts = imp.split(".")
    return ".".join(parts)


def scan_project(
    project_root: str | Path,
    config: GovernanceConfig,
    max_files: int = 5000,
) -> list[Violation]:
    """Scan a project for governance violations.

    Args:
        project_root: Root directory of the project.
        config: Parsed governance configuration.
        max_files: Maximum files to scan (safety limit).

    Returns:
        List of Violation objects.
    """
    root = Path(project_root).resolve()
    violations: list[Violation] = []

    # Build import graph using existing infrastructure
    try:
        import_graph = _build_import_graph(root, max_files)
    except Exception:
        # Fallback to alternative implementation
        try:
            import_graph = build_dep_graph(str(root))
        except Exception:
            return [Violation(
                file="",
                layer="",
                import_target="",
                target_layer=None,
                rule_type="error",
                severity="error",
                message="Failed to build import graph",
            )]

    layer_rules = config.layer_rules
    exceptions = config.exceptions
    layer_names = list(config.layers.keys())

    # Build layer index for quick lookup
    {name: i for i, name in enumerate(layer_names)}

    for module_path, deps in import_graph.items():
        # Convert module path to file path
        file_path = module_path.replace(".", "/") + ".py"
        file_layer = _detect_file_layer(file_path, config)

        if file_layer is None:
            continue  # Unmapped files aren't governed

        allowed_deps = layer_rules.get(file_layer, {}).get("allowed_deps", None)
        forbidden_deps = layer_rules.get(file_layer, {}).get("forbidden_deps", [])

        for dep in deps:
            dep_path = dep.replace(".", "/") + ".py"
            dep_layer = _detect_file_layer(dep_path, config)

            # Check exception list first
            exc_severity = _is_exception(file_path, dep, exceptions)
            if exc_severity == "warn":
                # Exception with warning severity — still report but softer
                pass  # fall through to check

            # Layer rule check
            if allowed_deps is not None:
                if dep_layer and dep_layer not in allowed_deps:
                    violations.append(Violation(
                        file=file_path,
                        layer=file_layer,
                        import_target=dep,
                        target_layer=dep_layer,
                        rule_type="layer",
                        severity=exc_severity or "error",
                    ))
                elif dep_layer is None:
                    # Unclassified dependency — warn if strict
                    pass

            # Forbidden deps check
            if dep_layer and dep_layer in forbidden_deps:
                violations.append(Violation(
                    file=file_path,
                    layer=file_layer,
                    import_target=dep,
                    target_layer=dep_layer,
                    rule_type="layer",
                    severity=exc_severity or "error",
                    message=(
                        f"{file_path} (layer: {file_layer}) imports "
                        f"forbidden layer {dep_layer} via {dep}"
                    ),
                ))

    return violations
