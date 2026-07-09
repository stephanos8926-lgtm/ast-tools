"""
Configuration for the auto-fix pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib


@dataclass
class FixerConfig:
    """Configuration for a specific fixer."""

    enabled: bool = True
    args: list[str] = field(default_factory=list)
    config_file: str | None = None
    safety_override: dict[str, str] = field(default_factory=dict)


@dataclass
class FixConfig:
    """Main configuration for the fix pipeline."""

    # Global settings
    max_iterations: int = 10
    safety_level: str = "safe"  # safe, unsafe, display_only
    check_only: bool = False
    diff_only: bool = False
    verbose: bool = False
    parallel: bool = True
    workers: int = 4

    # Language-specific fixer configs
    fixers: dict[str, FixerConfig] = field(default_factory=dict)

    # File patterns
    include_patterns: list[str] = field(default_factory=lambda: ["**/*"])
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "**/__pycache__/**",
            "**/.git/**",
            "**/node_modules/**",
            "**/target/**",
            "**/build/**",
            "**/dist/**",
            "**/.venv/**",
            "**/venv/**",
        ]
    )

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> "FixConfig":
        """Create FixConfig from TOML data."""
        fixers = {}
        for name, fixer_data in data.get("fixers", {}).items():
            fixers[name] = FixerConfig(
                enabled=fixer_data.get("enabled", True),
                args=fixer_data.get("args", []),
                config_file=fixer_data.get("config_file"),
                safety_override=fixer_data.get("safety_override", {}),
            )

        return cls(
            max_iterations=data.get("max_iterations", 10),
            safety_level=data.get("safety_level", "safe"),
            check_only=data.get("check_only", False),
            diff_only=data.get("diff_only", False),
            verbose=data.get("verbose", False),
            parallel=data.get("parallel", True),
            workers=data.get("workers", 4),
            fixers=fixers,
            include_patterns=data.get("include_patterns", ["**/*"]),
            exclude_patterns=data.get(
                "exclude_patterns",
                [
                    "**/__pycache__/**",
                    "**/.git/**",
                    "**/node_modules/**",
                    "**/target/**",
                    "**/build/**",
                    "**/dist/**",
                    "**/.venv/**",
                    "**/venv/**",
                ],
            ),
        )

    @classmethod
    def load_from_file(cls, path: Path) -> "FixConfig":
        """Load config from a TOML file."""
        if not path.exists():
            return cls()  # Return defaults

        with open(path, "rb") as f:
            data = tomllib.load(f)

        # Look for [tool.ast-tools.fix] section
        fix_data = data.get("tool", {}).get("ast-tools", {}).get("fix", {})
        return cls.from_toml(fix_data)

    @classmethod
    def load_from_project(cls, project_root: Path) -> "FixConfig":
        """Load config from project root, searching for config files."""
        config_files = [
            project_root / "pyproject.toml",
            project_root / "ast-fix.toml",
            project_root / ".ast-fix.toml",
        ]

        for config_file in config_files:
            if config_file.exists():
                return cls.load_from_file(config_file)

        return cls()  # Return defaults if no config found

    def get_fixer_config(self, name: str) -> FixerConfig:
        """Get config for a specific fixer."""
        return self.fixers.get(name, FixerConfig())


def load_fix_config(project_root: Path) -> FixConfig:
    """Load fix configuration from project."""
    return FixConfig.load_from_project(project_root)
