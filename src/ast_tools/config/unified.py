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


# ═══════════════════════════════════════════════════════════════════════════════
# Runtime Constants — MUST be first (referenced by all other dataclasses below)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RuntimeConstants:
    """Single source of truth for ALL magic numbers, limits, and defaults.

    Every hardcoded constant in the codebase should be sourced from here.
    Files import: from ast_tools.config.unified import RUNTIME
    """

    # ── File size limits ──
    max_file_size_parse: int = 10 * 1024 * 1024     # 10MB — parser.py
    max_file_size_index: int = 1024 * 1024           # 1MB — indexing
    max_file_size_fix: int = 10 * 1024 * 1024        # 10MB — fix engine

    # ── Database ──
    db_max_retries: int = 3
    db_retry_delay: float = 0.5
    db_backoff_multiplier: float = 2.0

    # ── Timeouts ──
    timeout_fixer: int = 120           # fix engine + fixers
    timeout_git_log: int = 120         # co-change miner
    timeout_llm: int = 30              # LLM fix refinement

    # ── Debounce (ms) ──
    debounce_index: int = 500          # index watcher
    debounce_diagnostics: int = 300    # LSP diagnostics
    debounce_watchdog: int = 100       # watchdog daemon

    # ── Workers / parallelism ──
    workers_fix: int = 4               # fix pipeline
    workers_spectral: int = 4          # spectral analysis
    workers_embeddings: int = 2        # embedding generation workers

    # ── Batch sizes ──
    batch_size_embeddings_default: int = 16    # safe for 4GB RAM
    batch_size_embeddings_standard: int = 32   # standard models
    batch_size_embeddings_large: int = 64      # MiniLM models
    batch_size_embeddings_api: int = 100       # OpenAI/Cohere APIs

    # ── Embedding ──
    embedding_dim: int = 384           # BGE-small / MiniLM
    embedding_model_default: str = "bge-small-en-v1.5"
    embedding_model_minilm: str = "all-MiniLM-L6-v2"

    # ── Reranker models ──
    reranker_model_default: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_fallback_models: list[str] = field(default_factory=lambda: [
        "cross-encoder/ms-marco-TinyBERT-L-2",
        "cross-encoder/ms-marco-MiniLM-L-4",
    ])

    # ── Cache ──
    cache_max_size_mb: int = 1024      # 1GB default

    # ── Fixer limits ──
    fix_max_iterations: int = 10
    fix_backup_retention_days: int = 7

    # ── LSP ──
    lsp_max_diagnostics_per_file: int = 100

    # ── LLM ──
    llm_default_model_path: str = "~/.cache/ast-tools/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"

    # ── Disc space ──
    min_disk_free_mb: int = 500

    # ── CLI browse ──
    browse_max_files: int = 200

    # ── KNNGraph ──
    knn_ef_construction: int = 200
    knn_m: int = 16
    knn_ef_search: int = 50

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML export."""
        return {
            "file_sizes": {
                "max_file_size_parse": self.max_file_size_parse,
                "max_file_size_index": self.max_file_size_index,
                "max_file_size_fix": self.max_file_size_fix,
            },
            "database": {
                "max_retries": self.db_max_retries,
                "retry_delay": self.db_retry_delay,
                "backoff_multiplier": self.db_backoff_multiplier,
            },
            "timeouts": {
                "fixer": self.timeout_fixer,
                "git_log": self.timeout_git_log,
                "llm": self.timeout_llm,
            },
            "debounce": {
                "index": self.debounce_index,
                "diagnostics": self.debounce_diagnostics,
                "watchdog": self.debounce_watchdog,
            },
            "workers": {
                "fix": self.workers_fix,
                "spectral": self.workers_spectral,
            },
            "batch_sizes": {
                "embeddings_default": self.batch_size_embeddings_default,
                "embeddings_standard": self.batch_size_embeddings_standard,
                "embeddings_large": self.batch_size_embeddings_large,
                "embeddings_api": self.batch_size_embeddings_api,
            },
            "embedding": {
                "dim": self.embedding_dim,
                "model_default": self.embedding_model_default,
                "model_minilm": self.embedding_model_minilm,
            },
            "cache": {
                "max_size_mb": self.cache_max_size_mb,
            },
            "fix": {
                "max_iterations": self.fix_max_iterations,
                "backup_retention_days": self.fix_backup_retention_days,
            },
            "lsp": {
                "max_diagnostics_per_file": self.lsp_max_diagnostics_per_file,
            },
            "disk": {
                "min_disk_free_mb": self.min_disk_free_mb,
            },
            "browse": {
                "max_files": self.browse_max_files,
            },
        }


# Singleton instance — import this everywhere
RUNTIME = RuntimeConstants()


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Dataclasses (all can reference RUNTIME above)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RerankerConfig:
    """Configuration for cross-encoder reranker."""

    enabled: bool = True
    model: str = RUNTIME.reranker_model_default
    fallback_models: list[str] = field(
        default_factory=lambda: RUNTIME.reranker_fallback_models
    )
    batch_size: int = RUNTIME.batch_size_embeddings_standard
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
    max_iterations: int = RUNTIME.fix_max_iterations
    safety_level: str = "safe"  # safe, unsafe, display_only
    check_only: bool = False
    diff_only: bool = False
    verbose: bool = False
    parallel: bool = True
    workers: int = RUNTIME.workers_fix
    timeout: int = RUNTIME.timeout_fixer
    max_file_size: int = RUNTIME.max_file_size_fix
    create_backups: bool = True
    backup_retention_days: int = RUNTIME.fix_backup_retention_days

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

    def get_fixer_config(self, name: str) -> FixerConfig:
        """Get config for a specific fixer."""
        return self.fixers.get(name, FixerConfig())


@dataclass
class IndexConfig:
    """Configuration for codebase indexing."""

    db_path: str | None = None  # Resolved relative to project_root or config dir
    project_root: Path | None = None  # Explicit project root if different from CLI/CWD
    watch: bool = True
    debounce_ms: int = RUNTIME.debounce_index
    embeddings: bool = True
    embedding_model: str = RUNTIME.embedding_model_default
    embedding_dim: int = RUNTIME.embedding_dim
    max_file_size: int = RUNTIME.max_file_size_index
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
class LLMConfig:
    """Configuration for LLM-assisted fix refinement."""

    enabled: bool = True
    prefer_local: bool = True
    timeout_seconds: int = RUNTIME.timeout_llm
    max_tokens: int = 2048
    temperature: float = 0.1

    # Local LLM backends
    local_backend: str = "llama.cpp"  # "llama.cpp", "ollama", "vllm"
    local_model_path: str = RUNTIME.llm_default_model_path
    local_n_gpu_layers: int = -1  # -1 = all, 0 = CPU only
    local_n_ctx: int = 8192
    local_host: str = "127.0.0.1"
    local_port: int = 11434  # Ollama default

    # Remote LLM providers
    remote_provider: str = "openrouter"  # "openrouter", "anthropic", "gemini"
    remote_model: str = "qwen/qwen-2.5-coder-32b-instruct"
    remote_fallback_chain: list[str] = field(default_factory=lambda: ["openrouter", "anthropic", "gemini"])
    remote_api_key_env: str = "OPENROUTER_API_KEY"

    # Prompt template
    prompt_template: str = (
        "You are an expert code fixer. Given a diagnostic and code context, "
        "suggest a minimal, correct fix. Return only the unified diff.\n\n"
        "Diagnostic: {diagnostic_message}\n"
        "Rule: {diagnostic_code}\n"
        "File: {file_path}\n"
        "Language: {language}\n"
        "Code context:\n{code_context}\n\n"
        "Fix:"
    )


@dataclass
class DiagnosticConfig:
    """Configuration for diagnostic publishing."""

    enabled: bool = True
    debounce_ms: int = RUNTIME.debounce_diagnostics
    max_diagnostics_per_file: int = RUNTIME.lsp_max_diagnostics_per_file
    push_diagnostics: bool = True  # textDocument/publishDiagnostics
    pull_diagnostics: bool = False  # textDocument/diagnostic (client-initiated)
    include_related_information: bool = True


@dataclass
class FormattingConfig:
    """Configuration for document formatting."""

    enabled: bool = True
    range_formatting: bool = True
    format_on_save: bool = True
    fix_on_save: bool = True


@dataclass
class LSPConfig:
    """Configuration for LSP server."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8767
    code_action_kind: list[str] = field(
        default_factory=lambda: ["quickfix", "refactor", "source"]
    )

    # Sub-configs
    diagnostics: DiagnosticConfig = field(default_factory=DiagnosticConfig)
    formatting: FormattingConfig = field(default_factory=FormattingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    config_watch: bool = True  # Watch config files for hot-reload
    initialization_timeout_ms: int = 5000


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
            max_iterations=data.get("max_iterations", RUNTIME.fix_max_iterations),
            safety_level=data.get("safety_level", "safe"),
            check_only=data.get("check_only", False),
            diff_only=data.get("diff_only", False),
            verbose=data.get("verbose", False),
            parallel=data.get("parallel", True),
            workers=data.get("workers", RUNTIME.workers_fix),
            timeout=data.get("timeout", RUNTIME.timeout_fixer),
            max_file_size=data.get("max_file_size", RUNTIME.max_file_size_fix),
            create_backups=data.get("create_backups", True),
            backup_retention_days=data.get("backup_retention_days", RUNTIME.fix_backup_retention_days),
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
            model=data.get("model", RUNTIME.reranker_model_default),
            fallback_models=data.get(
                "fallback_models",
                RUNTIME.reranker_fallback_models,
            ),
            batch_size=data.get("batch_size", RUNTIME.batch_size_embeddings_standard),
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
            debounce_ms=data.get("debounce_ms", RUNTIME.debounce_index),
            embeddings=data.get("embeddings", True),
            embedding_model=data.get("embedding_model", RUNTIME.embedding_model_default),
            embedding_dim=data.get("embedding_dim", RUNTIME.embedding_dim),
            max_file_size=data.get("max_file_size", RUNTIME.max_file_size_index),
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
        diagnostics_data = data.get("diagnostics", {})
        formatting_data = data.get("formatting", {})
        llm_data = data.get("llm", {})

        return LSPConfig(
            enabled=data.get("enabled", True),
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8767),
            code_action_kind=data.get(
                "code_action_kind", ["quickfix", "refactor", "source"]
            ),
            diagnostics=DiagnosticConfig(
                enabled=diagnostics_data.get("enabled", True),
                debounce_ms=diagnostics_data.get("debounce_ms", RUNTIME.debounce_diagnostics),
                max_diagnostics_per_file=diagnostics_data.get("max_diagnostics_per_file", RUNTIME.lsp_max_diagnostics_per_file),
                push_diagnostics=diagnostics_data.get("push_diagnostics", True),
                pull_diagnostics=diagnostics_data.get("pull_diagnostics", False),
                include_related_information=diagnostics_data.get("include_related_information", True),
            ),
            formatting=FormattingConfig(
                enabled=formatting_data.get("enabled", True),
                range_formatting=formatting_data.get("range_formatting", True),
                format_on_save=formatting_data.get("format_on_save", True),
                fix_on_save=formatting_data.get("fix_on_save", True),
            ),
            llm=LLMConfig(
                enabled=llm_data.get("enabled", True),
                prefer_local=llm_data.get("prefer_local", True),
                timeout_seconds=llm_data.get("timeout_seconds", RUNTIME.timeout_llm),
                max_tokens=llm_data.get("max_tokens", 2048),
                temperature=llm_data.get("temperature", 0.1),
                local_backend=llm_data.get("local_backend", "llama.cpp"),
                local_model_path=llm_data.get("local_model_path", RUNTIME.llm_default_model_path),
                local_n_gpu_layers=llm_data.get("local_n_gpu_layers", -1),
                local_n_ctx=llm_data.get("local_n_ctx", 8192),
                local_host=llm_data.get("local_host", "127.0.0.1"),
                local_port=llm_data.get("local_port", 11434),
                remote_provider=llm_data.get("remote_provider", "openrouter"),
                remote_model=llm_data.get("remote_model", "qwen/qwen-2.5-coder-32b-instruct"),
                remote_fallback_chain=llm_data.get("remote_fallback_chain", ["openrouter", "anthropic", "gemini"]),
                remote_api_key_env=llm_data.get("remote_api_key_env", "OPENROUTER_API_KEY"),
                prompt_template=llm_data.get("prompt_template", LLMConfig().prompt_template),
            ),
            config_watch=data.get("config_watch", True),
            initialization_timeout_ms=data.get("initialization_timeout_ms", 5000),
        )

    @staticmethod
    def _load_diagnostic_config(data: dict[str, Any]) -> DiagnosticConfig:
        return DiagnosticConfig(
            enabled=data.get("enabled", True),
            debounce_ms=data.get("debounce_ms", RUNTIME.debounce_diagnostics),
            max_diagnostics_per_file=data.get("max_diagnostics_per_file", RUNTIME.lsp_max_diagnostics_per_file),
            push_diagnostics=data.get("push_diagnostics", True),
            pull_diagnostics=data.get("pull_diagnostics", False),
            include_related_information=data.get("include_related_information", True),
        )

    @staticmethod
    def _load_formatting_config(data: dict[str, Any]) -> FormattingConfig:
        return FormattingConfig(
            enabled=data.get("enabled", True),
            range_formatting=data.get("range_formatting", True),
            format_on_save=data.get("format_on_save", True),
            fix_on_save=data.get("fix_on_save", True),
        )

    @staticmethod
    def _load_llm_config(data: dict[str, Any]) -> LLMConfig:
        return LLMConfig(
            enabled=data.get("enabled", True),
            prefer_local=data.get("prefer_local", True),
            timeout_seconds=data.get("timeout_seconds", RUNTIME.timeout_llm),
            max_tokens=data.get("max_tokens", 2048),
            temperature=data.get("temperature", 0.1),
            local_backend=data.get("local_backend", "llama.cpp"),
            local_model_path=data.get("local_model_path", RUNTIME.llm_default_model_path),
            local_n_gpu_layers=data.get("local_n_gpu_layers", -1),
            local_n_ctx=data.get("local_n_ctx", 8192),
            local_host=data.get("local_host", "127.0.0.1"),
            local_port=data.get("local_port", 11434),
            remote_provider=data.get("remote_provider", "openrouter"),
            remote_model=data.get("remote_model", "qwen/qwen-2.5-coder-32b-instruct"),
            remote_fallback_chain=data.get("remote_fallback_chain", ["openrouter", "anthropic", "gemini"]),
            remote_api_key_env=data.get("remote_api_key_env", "OPENROUTER_API_KEY"),
            prompt_template=data.get("prompt_template", LLMConfig().prompt_template),
        )

    @staticmethod
    def _load_plugin_config(data: dict[str, Any]) -> PluginConfig:
        return PluginConfig(
            custom_fixers=data.get("custom_fixers", {}),
            fixer_plugins=data.get("fixer_plugins", []),
            search_plugins=data.get("search_plugins", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML export."""
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
                "backup_retention_days": self.fix.backup_retention_days,
            },
            "reranker": {
                "enabled": self.reranker.enabled,
                "model": self.reranker.model,
                "fallback_models": self.reranker.fallback_models,
                "batch_size": self.reranker.batch_size,
                "max_length": self.reranker.max_length,
                "device": self.reranker.device,
                "confidence_threshold": self.reranker.confidence_threshold,
            },
            "index": {
                "watch": self.index.watch,
                "debounce_ms": self.index.debounce_ms,
                "embeddings": self.index.embeddings,
                "embedding_model": self.index.embedding_model,
                "embedding_dim": self.index.embedding_dim,
                "max_file_size": self.index.max_file_size,
            },
            "server": {
                "stdio_enabled": self.server.stdio_enabled,
                "daemon_enabled": self.server.daemon_enabled,
                "daemon_host": self.server.daemon_host,
                "daemon_port": self.server.daemon_port,
                "remote_enabled": self.server.remote_enabled,
                "remote_host": self.server.remote_host,
                "remote_port": self.server.remote_port,
            },
            "mcp": {
                "version": self.mcp.version,
                "token_tracking": self.mcp.token_tracking,
                "context_injection": self.mcp.context_injection,
                "max_tokens": self.mcp.max_tokens,
            },
            "lsp": {
                "enabled": self.lsp.enabled,
                "host": self.lsp.host,
                "port": self.lsp.port,
                "config_watch": self.lsp.config_watch,
            },
        }

    def merge(self, other: "UnifiedConfig") -> "UnifiedConfig":
        """Merge another config into this one (other wins on conflicts)."""
        # Simple merge - in real impl this would be a deep merge
        merged = UnifiedConfig()
        merged.fix = other.fix if other.fix != FixConfig() else self.fix
        return merged


def load_unified(
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


# Backward-compatible alias
load_unified_config = load_unified