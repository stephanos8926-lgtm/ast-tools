"""
Unified configuration schema for ast-tools.

Supports loading from:
1. pyproject.toml [tool.ast-tools] section (project-level)
2. ast-tools.yaml in config dir (user-level)
3. CLI overrides (highest priority)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

from .loader import get_config_dir


@dataclass
class RerankerConfig:
    """Configuration for cross-encoder reranker."""

    enabled: bool = True
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    fallback_models: list[str] = field(
        default_factory=lambda: [
            "cross-encoder/ms-marco-TinyBERT-L-2",
            "cross-encoder/ms-marco-MiniLM-L-4",
        ]
    )
    batch_size: int = 32
    max_length: int = 512
    device: str = "auto"  # auto, cpu, cuda, mps
    cache_dir: str | None = None
    confidence_threshold: float = 0.0
    blend_weights: tuple[float, float, float] = (0.5, 0.3, 0.2)  # max, avg_top3, median


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
    timeout: int = 120
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    create_backups: bool = True

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


@dataclass
class IndexConfig:
    """Configuration for codebase indexing."""

    db_path: str | None = None  # Resolved relative to project_root or config dir
    project_root: Path | None = None  # Explicit project root if different from CLI/CWD
    watch: bool = True
    debounce_ms: int = 500
    embeddings: bool = True
    embedding_model: str = "bge-small-en-v1.5"
    embedding_dim: int = 384
    max_file_size: int = 1024 * 1024  # 1MB for indexing
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


@dataclass
class ServerConfig:
    """Configuration for MCP server modes."""

    # stdio mode
    stdio_enabled: bool = True

    # daemon mode
    daemon_enabled: bool = False
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765

    # remote/streamable HTTP mode
    remote_enabled: bool = False
    remote_host: str = "127.0.0.1"
    remote_port: int = 8766
    remote_bearer_token: str | None = None


@dataclass
class MCPConfig:
    """Configuration for MCP server."""

    name: str = "ast-tools"
    version: str = "0.2.0"
    description: str = "MCP server for structural code analysis and editing"
    tools_enabled: list[str] | None = None  # None = all
    tools_disabled: list[str] = field(default_factory=list)
    token_tracking: bool = True
    context_injection: bool = True
    max_tokens: int = 8192


@dataclass
class LSPConfig:
    """Configuration for LSP server."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8767
    code_action_kind: list[str] = field(
        default_factory=lambda: ["quickfix", "refactor", "source"]
    )


@dataclass
class PluginConfig:
    """Configuration for plugin system."""

    fixer_plugins: list[str] = field(default_factory=list)
    search_plugins: list[str] = field(default_factory=list)
    custom_fixers: dict[str, str] = field(default_factory=dict)  # lang -> module:Class


@dataclass
class UnifiedConfig:
    """Complete unified configuration for ast-tools."""

    fix: FixConfig = field(default_factory=FixConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    lsp: LSPConfig = field(default_factory=LSPConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)

    # Metadata
    config_version: int = 1

    @classmethod
    def from_pyproject_toml(cls, path: Path | None = None) -> "UnifiedConfig":
        """Load config from pyproject.toml [tool.ast-tools] section."""
        if path is None:
            # Search up from cwd
            path = Path.cwd()
            while path != path.parent:
                toml_path = path / "pyproject.toml"
                if toml_path.exists():
                    break
                path = path.parent
            else:
                return cls()

        if not path.exists():
            return cls()

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cls()

        ast_tools_data = data.get("tool", {}).get("ast-tools", {})
        return cls.from_dict(ast_tools_data)

    @classmethod
    def from_ast_tools_yaml(cls, path: Path | None = None) -> "UnifiedConfig":
        """Load config from ast-tools.yaml in config directory."""
        import yaml

        if path is None:
            path = get_config_dir() / "ast-tools.yaml"

        if not path.exists():
            return cls()

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return cls()

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedConfig":
        """Create config from dict."""
        return cls(
            fix=cls._load_fix_config(data.get("fix", {})),
            reranker=cls._load_reranker_config(data.get("reranker", {})),
            index=cls._load_index_config(data.get("index", {})),
            server=cls._load_server_config(data.get("server", {})),
            mcp=cls._load_mcp_config(data.get("mcp", {})),
            lsp=cls._load_lsp_config(data.get("lsp", {})),
            plugins=cls._load_plugin_config(data.get("plugins", {})),
            config_version=data.get("config_version", 1),
        )

    @staticmethod
    def _load_fix_config(data: dict[str, Any]) -> FixConfig:
        fixers = {}
        for name, fixer_data in data.get("fixers", {}).items():
            fixers[name] = FixerConfig(
                enabled=fixer_data.get("enabled", True),
                args=fixer_data.get("args", []),
                config_file=fixer_data.get("config_file"),
                safety_override=fixer_data.get("safety_override", {}),
            )

        return FixConfig(
            max_iterations=data.get("max_iterations", 10),
            safety_level=data.get("safety_level", "safe"),
            check_only=data.get("check_only", False),
            diff_only=data.get("diff_only", False),
            verbose=data.get("verbose", False),
            parallel=data.get("parallel", True),
            workers=data.get("workers", 4),
            timeout=data.get("timeout", 120),
            max_file_size=data.get("max_file_size", 10 * 1024 * 1024),
            create_backups=data.get("create_backups", True),
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

    @staticmethod
    def _load_reranker_config(data: dict[str, Any]) -> RerankerConfig:
        return RerankerConfig(
            enabled=data.get("enabled", True),
            model=data.get("model", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            fallback_models=data.get(
                "fallback_models",
                [
                    "cross-encoder/ms-marco-TinyBERT-L-2",
                    "cross-encoder/ms-marco-MiniLM-L-4",
                ],
            ),
            batch_size=data.get("batch_size", 32),
            max_length=data.get("max_length", 512),
            device=data.get("device", "auto"),
            cache_dir=data.get("cache_dir"),
            confidence_threshold=data.get("confidence_threshold", 0.0),
            blend_weights=tuple(
                data.get("blend_weights", [0.5, 0.3, 0.2])
            ),
        )

    @staticmethod
    def _load_index_config(data: dict[str, Any]) -> IndexConfig:
        return IndexConfig(
            db_path=data.get("db_path"),
            watch=data.get("watch", True),
            debounce_ms=data.get("debounce_ms", 500),
            embeddings=data.get("embeddings", True),
            embedding_model=data.get("embedding_model", "bge-small-en-v1.5"),
            embedding_dim=data.get("embedding_dim", 384),
            max_file_size=data.get("max_file_size", 1024 * 1024),
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

    @staticmethod
    def _load_server_config(data: dict[str, Any]) -> ServerConfig:
        return ServerConfig(
            stdio_enabled=data.get("stdio_enabled", True),
            daemon_enabled=data.get("daemon_enabled", False),
            daemon_host=data.get("daemon_host", "127.0.0.1"),
            daemon_port=data.get("daemon_port", 8765),
            remote_enabled=data.get("remote_enabled", False),
            remote_host=data.get("remote_host", "127.0.0.1"),
            remote_port=data.get("remote_port", 8766),
            remote_bearer_token=data.get("remote_bearer_token"),
        )

    @staticmethod
    def _load_mcp_config(data: dict[str, Any]) -> MCPConfig:
        return MCPConfig(
            name=data.get("name", "ast-tools"),
            version=data.get("version", "0.2.0"),
            description=data.get(
                "description", "MCP server for structural code analysis and editing"
            ),
            tools_enabled=data.get("tools_enabled"),
            tools_disabled=data.get("tools_disabled", []),
            token_tracking=data.get("token_tracking", True),
            context_injection=data.get("context_injection", True),
            max_tokens=data.get("max_tokens", 8192),
        )

    @staticmethod
    def _load_lsp_config(data: dict[str, Any]) -> LSPConfig:
        return LSPConfig(
            enabled=data.get("enabled", True),
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8767),
            code_action_kind=data.get(
                "code_action_kind", ["quickfix", "refactor", "source"]
            ),
        )

    @staticmethod
    def _load_plugin_config(data: dict[str, Any]) -> PluginConfig:
        return PluginConfig(
            fixer_plugins=data.get("fixer_plugins", []),
            search_plugins=data.get("search_plugins", []),
            custom_fixers=data.get("custom_fixers", {}),
        )

    def merge(self, other: "UnifiedConfig") -> "UnifiedConfig":
        """Merge another config into this one (other takes precedence)."""
        # For simplicity, we'll just replace sections that are non-empty in other
        # A more sophisticated merge would be recursive
        if other.fix != FixConfig():
            self.fix = other.fix
        if other.reranker != RerankerConfig():
            self.reranker = other.reranker
        if other.index != IndexConfig():
            self.index = other.index
        if other.server != ServerConfig():
            self.server = other.server
        if other.mcp != MCPConfig():
            self.mcp = other.mcp
        if other.lsp != LSPConfig():
            self.lsp = other.lsp
        if other.plugins != PluginConfig():
            self.plugins = other.plugins
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for saving."""
        return {
            "config_version": self.config_version,
            "fix": {
                "max_iterations": self.fix.max_iterations,
                "safety_level": self.fix.safety_level,
                "check_only": self.fix.check_only,
                "diff_only": self.fix.diff_only,
                "verbose": self.fix.verbose,
                "parallel": self.fix.parallel,
                "workers": self.fix.workers,
                "timeout": self.fix.timeout,
                "max_file_size": self.fix.max_file_size,
                "create_backups": self.fix.create_backups,
                "fixers": {
                    name: {
                        "enabled": fc.enabled,
                        "args": fc.args,
                        "config_file": fc.config_file,
                        "safety_override": fc.safety_override,
                    }
                    for name, fc in self.fix.fixers.items()
                },
                "include_patterns": self.fix.include_patterns,
                "exclude_patterns": self.fix.exclude_patterns,
            },
            "reranker": {
                "enabled": self.reranker.enabled,
                "model": self.reranker.model,
                "fallback_models": self.reranker.fallback_models,
                "batch_size": self.reranker.batch_size,
                "max_length": self.reranker.max_length,
                "device": self.reranker.device,
                "cache_dir": self.reranker.cache_dir,
                "confidence_threshold": self.reranker.confidence_threshold,
                "blend_weights": list(self.reranker.blend_weights),
            },
            "index": {
                "db_path": self.index.db_path,
                "watch": self.index.watch,
                "debounce_ms": self.index.debounce_ms,
                "embeddings": self.index.embeddings,
                "embedding_model": self.index.embedding_model,
                "embedding_dim": self.index.embedding_dim,
                "max_file_size": self.index.max_file_size,
                "exclude_patterns": self.index.exclude_patterns,
            },
            "server": {
                "stdio_enabled": self.server.stdio_enabled,
                "daemon_enabled": self.server.daemon_enabled,
                "daemon_host": self.server.daemon_host,
                "daemon_port": self.server.daemon_port,
                "remote_enabled": self.server.remote_enabled,
                "remote_host": self.server.remote_host,
                "remote_port": self.server.remote_port,
                "remote_bearer_token": self.server.remote_bearer_token,
            },
            "mcp": {
                "name": self.mcp.name,
                "version": self.mcp.version,
                "description": self.mcp.description,
                "tools_enabled": self.mcp.tools_enabled,
                "tools_disabled": self.mcp.tools_disabled,
                "token_tracking": self.mcp.token_tracking,
                "context_injection": self.mcp.context_injection,
                "max_tokens": self.mcp.max_tokens,
            },
            "lsp": {
                "enabled": self.lsp.enabled,
                "host": self.lsp.host,
                "port": self.lsp.port,
                "code_action_kind": self.lsp.code_action_kind,
            },
            "plugins": {
                "fixer_plugins": self.plugins.fixer_plugins,
                "search_plugins": self.plugins.search_plugins,
                "custom_fixers": self.plugins.custom_fixers,
            },
        }


def load_unified_config(
    pyproject_path: Path | None = None,
    yaml_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> UnifiedConfig:
    """
    Load unified config with precedence:
    1. Defaults (lowest)
    2. pyproject.toml [tool.ast-tools]
    3. ast-tools.yaml (user config dir)
    4. CLI overrides (highest)
    """
    config = UnifiedConfig()

    # 1. Load from pyproject.toml
    pyproject_config = UnifiedConfig.from_pyproject_toml(pyproject_path)
    config = config.merge(pyproject_config)

    # 2. Load from ast-tools.yaml
    yaml_config = UnifiedConfig.from_ast_tools_yaml(yaml_path)
    config = config.merge(yaml_config)

    # 3. Apply CLI overrides
    if cli_overrides:
        # Convert flat overrides to nested structure
        # This is a simplified version - a full implementation would use a proper merge
        if "fix" in cli_overrides:
            config.fix = UnifiedConfig._load_fix_config(cli_overrides["fix"])
        if "reranker" in cli_overrides:
            config.reranker = UnifiedConfig._load_reranker_config(cli_overrides["reranker"])
        if "index" in cli_overrides:
            config.index = UnifiedConfig._load_index_config(cli_overrides["index"])
        if "server" in cli_overrides:
            config.server = UnifiedConfig._load_server_config(cli_overrides["server"])
        if "mcp" in cli_overrides:
            config.mcp = UnifiedConfig._load_mcp_config(cli_overrides["mcp"])
        if "lsp" in cli_overrides:
            config.lsp = UnifiedConfig._load_lsp_config(cli_overrides["lsp"])
        if "plugins" in cli_overrides:
            config.plugins = UnifiedConfig._load_plugin_config(cli_overrides["plugins"])

    return config


def save_ast_tools_yaml(config: UnifiedConfig, path: Path | None = None) -> Path:
    """Save unified config to ast-tools.yaml."""
    import yaml

    if path is None:
        path = get_config_dir() / "ast-tools.yaml"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(config.to_dict(), default_flow_style=False, sort_keys=False))
    return path