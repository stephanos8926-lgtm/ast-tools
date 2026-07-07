"""governance.yaml schema, loader, and validator."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class GovernanceError(Exception):
    """Raised on governance config errors."""


class LayerDef:
    """A single architectural layer definition."""

    def __init__(self, name: str, data: dict[str, Any]) -> None:
        self.name = name
        self.description = data.get("description", "")
        self.tags = data.get("tags", [])


class GovernanceRule:
    """A single governance rule."""

    def __init__(self, pattern: str, layer: str, **kwargs: Any) -> None:
        self.pattern = pattern
        self.layer = layer
        self.extra = kwargs


class GovernanceConfig:
    """Parsed governance configuration."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.version = data.get("version", 1)
        self.layers = {
            layer_data["name"]: LayerDef(layer_data["name"], layer_data)
            for layer_data in data.get("layers", [])
        }
        self.mappings = [
            GovernanceRule(**m) for m in data.get("mappings", [])
        ]
        self.layer_rules: dict[str, dict[str, Any]] = data.get("layer_rules", {})
        self.tag_rules: list[dict[str, Any]] = data.get("tag_rules", [])
        self.exceptions: list[dict[str, Any]] = data.get("exceptions", [])
        self.raw = data

    def get_layer_for_file(self, filepath: str) -> str | None:
        """Determine layer of a file from its path using glob patterns."""
        from fnmatch import fnmatch

        for rule in self.mappings:
            if fnmatch(filepath, rule.pattern):
                return rule.layer
        return None


DEFAULT_GOVERNANCE = {
    "version": 1,
    "layers": [
        {"name": "infrastructure", "description": "Database, external APIs, low-level utilities", "tags": ["db", "cache", "config"]},
        {"name": "domain", "description": "Business logic, domain models", "tags": ["model", "service"]},
        {"name": "application", "description": "Use cases, application services", "tags": ["usecase", "workflow"]},
        {"name": "presentation", "description": "CLI, API, UI", "tags": ["cli", "api", "web"]},
    ],
    "mappings": [
        {"pattern": "**/database/**", "layer": "infrastructure"},
        {"pattern": "**/domain/**", "layer": "domain"},
        {"pattern": "**/usecase/**", "layer": "application"},
        {"pattern": "**/api/**", "layer": "presentation"},
        {"pattern": "**/cli/**", "layer": "presentation"},
    ],
    "layer_rules": {
        "infrastructure": {"allowed_deps": []},
        "domain": {"allowed_deps": ["infrastructure"]},
        "application": {"allowed_deps": ["infrastructure", "domain"]},
        "presentation": {"allowed_deps": ["infrastructure", "domain", "application"]},
    },
    "tag_rules": [],
    "exceptions": [],
}


def find_governance_file(cwd: str | Path | None = None) -> Path | None:
    """Find governance.yaml in cwd or parent dirs."""
    root = Path(cwd or os.getcwd()).resolve()
    for _ in range(5):
        candidate = root / "governance.yaml"
        if candidate.exists():
            return candidate
        parent = root.parent
        if parent == root:
            break
        root = parent
    return None


def load_governance(path: Path | None = None) -> GovernanceConfig | None:
    """Load governance.yaml, return None if not found."""
    path = path or find_governance_file()
    if not path or not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise GovernanceError("governance.yaml must be a mapping")
        return GovernanceConfig(data)
    except yaml.YAMLError as e:
        raise GovernanceError(f"Invalid YAML in {path}: {e}")


def validate_schema(data: dict[str, Any]) -> list[str]:
    """Validate governance.yaml structure. Return list of errors."""
    errors: list[str] = []
    if not isinstance(data.get("layers"), list):
        errors.append("'layers' must be a list")
    for i, layer in enumerate(data.get("layers", [])):
        if "name" not in layer:
            errors.append(f"layers[{i}]: missing 'name'")
    if not isinstance(data.get("mappings"), list):
        errors.append("'mappings' must be a list")
    for i, m in enumerate(data.get("mappings", [])):
        if "pattern" not in m or "layer" not in m:
            errors.append(f"mappings[{i}]: requires 'pattern' and 'layer'")
    return errors


def init_governance_file(path: Path | None = None) -> Path:
    """Create default governance.yaml."""
    import yaml

    target = path or Path(os.getcwd()) / "governance.yaml"
    if target.exists():
        return target
    target.write_text(yaml.dump(DEFAULT_GOVERNANCE, default_flow_style=False))
    return target
