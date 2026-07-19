# ast-tools Constants & Magic Numbers Audit

**Date:** 2026-07-19
**Scope:** `~/Workspaces/ast-tools/src/ast_tools`
**Purpose:** Identify all magic numbers, hardcoded paths, and constants that should be extracted to configuration

---

## 1. File Size Limits (Duplicated Across 4+ Files)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `10 * 1024 * 1024` (10MB) | `parser.py`, `unified.py` (FixConfig), `unified.py` (IndexConfig), `fix/engine.py` | `max_file_size` in unified config |
| `1024 * 1024` (1MB) | `unified.py` (IndexConfig) | `index.max_file_size` |
| `1024 * 1024 * 1024` (1GB) | `cache.py` (DEFAULT_MAX_SIZE_MB = 1024) | `cache.max_size_mb` |
| `500 * 1024 * 1024` (500MB) | `setup_wizard.py` (disk space check) | `setup.min_disk_mb` |

---

## 2. Timeouts (Duplicated Across 5+ Files)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `120` seconds | `git_miner.py`, `fix/engine.py`, `fix/fixers.py`, `unified.py` (FixConfig) | `timeout` in unified config |
| `30` seconds | `LSPConfig.initialization_timeout_ms = 5000` (5s, not 30s) | - |
| `30` seconds | `LLMConfig.timeout_seconds = 30` | `llm.timeout_seconds` |

---

## 3. Debounce Values (Multiple Inconsistent Values)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `500` ms | `IndexConfig.debounce_ms`, `unified.py` | `index.debounce_ms` |
| `300` ms | `DiagnosticConfig.debounce_ms`, `LSPConfig` | `lsp.diagnostics.debounce_ms` |
| `100` ms | `watchdog/daemon.py`, `server_config.py` (env var default) | `watchdog.debounce_ms` |

---

## 4. Worker/Parallelism Constants

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `4` workers | `FixConfig.workers`, `unified.py`, `fix/config.py`, `spectral.py` | `fix.workers` / `index.workers` |
| `4` max_workers_par | `spectral.py` line 1657 | `spectral.max_workers` |

---

## 5. Batch Sizes (Inconsistent)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `32` | `refresh_index.py`, `model_registry.py`, `unified.py` (RerankerConfig), `spectral.py`, `reranker/__init__.py` | `embeddings.batch_size` / `reranker.batch_size` |
| `16` | `model.py` (comment), `provider.py` | `embeddings.batch_size` (small) |
| `64` | `model_registry.py` (some models) | `embeddings.batch_size` (large) |
| `100` | `model_registry.py` (some models) | `embeddings.batch_size` (xlarge) |

---

## 6. Embedding Dimensions (Hardcoded 384 in 39+ Places)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `384` | `embeddings/model.py`, `model_registry.py`, `unified.py`, `schema.py`, `knn_builder.py`, `migration_009.py`, `symbols.py`, `remote_inference.py`, `benchmarks/phase9_benchmark.py` | `index.embedding_dim` (single source) |

---

## 7. Embedding Models (Hardcoded Strings)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `bge-small-en-v1.5` | `IndexConfig.embedding_model`, `schema.py`, `migration_009.py`, `model_registry.py` | `index.embedding_model` |
| `all-MiniLM-L6-v2` | `embeddings/model.py`, `switch_model.py`, `curator/setup_wizard.py` | `embeddings.model` |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | `RerankerConfig.model` | `reranker.model` |
| `cross-encoder/ms-marco-TinyBERT-L-2` | `RerankerConfig.fallback_models` | `reranker.fallback_models` |

---

## 8. Hardcoded Paths (Not Using Config System)

| Pattern | Files | Should Be Config |
|---------|-------|------------------|
| `~/.cache/ast-tools/` | `unified.py` (8 refs), `loader.py`, `indexer/cache.py`, `embeddings/model.py` | `config.get_cache_dir()` |
| `~/.ast-tools/cache/` | `unified.py` (4 refs), `project_registry.py` (2), `curator/daemon.py`, `curator/doctor.py`, `curator/vacuum.py`, `curator/setup_wizard.py` | `config.get_config_dir()` + `/cache/codebase.db` |
| `~/.cache/ast-tools/models/` | `unified.py` (LLMConfig.local_model_path), `embeddings/model.py` | `config.get_models_dir()` |

---

## 9. Port Numbers (Hardcoded)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `8765` | `ServerConfig.daemon_port` | `server.daemon_port` |
| `8766` | `ServerConfig.remote_port` | `server.remote_port` |
| `8767` | `LSPConfig.port` | `lsp.port` |
| `11434` | `LLMConfig.local_port` | `llm.local_port` |
| `8766` | `remote_inference.py` (API server) | `remote_inference.port` |

---

## 10. Database Connection Constants

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `10` max_connections | `remote_inference.py` | `remote_inference.max_connections` |
| `WAL` journal mode | `connection.py` (hardcoded) | `database.journal_mode` |
| `foreign_keys=ON` | `connection.py` (hardcoded) | `database.foreign_keys` |

---

## 11. Retry/Backoff Constants

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `3` MAX_RETRIES | `connection.py` | `database.max_retries` |
| `0.5` RETRY_DELAY | `connection.py` | `database.retry_delay` |
| `2.0` BACKOFF_MULTIPLIER | `connection.py` | `database.backoff_multiplier` |

---

## 12. Cache Constants

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `1024` MB (1GB) | `indexer/cache.py` DEFAULT_MAX_SIZE_MB | `cache.max_size_mb` |

---

## 13. Token Limits (Duplicated in tokens_schema.py + config)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| Various (1024, 2048, 4096, 16384, 32768) | `tokens_schema.py` (15 tools), `MCPConfig.max_tokens = 8192` | `mcp.token_limits` |

---

## 14. Embedding Token Limits (Magic Numbers)

| Value | Files | Should Be Config |
|-------|-------|------------------|
| `4096`, `16384`, `2048`, `32768`, `8192` | `tokens_schema.py` | `mcp.token_limits` |

---

## 15. Other Magic Numbers

| Value | Location | Should Be Config |
|-------|----------|------------------|
| `10` max_iterations | `FixConfig` | `fix.max_iterations` |
| `100` max_diagnostics_per_file | `DiagnosticConfig` | `lsp.diagnostics.max_per_file` |
| `100` max_tokens (LSP) | `LLMConfig.max_tokens = 2048` | `llm.max_tokens` |
| `0.1` temperature | `LLMConfig.temperature` | `llm.temperature` |
| `-1` local_n_gpu_layers | `LLMConfig.local_n_gpu_layers` | `llm.local_n_gpu_layers` |
| `8192` local_n_ctx | `LLMConfig.local_n_ctx` | `llm.local_n_ctx` |
| `8192` max_tokens (MCP) | `MCPConfig.max_tokens` | `mcp.max_tokens` |
| `10` min_cluster_size | `SpectralConfig.min_cluster_size` | `spectral.min_cluster_size` |
| `4` max_workers_par | `spectral.py` | `spectral.max_workers` |
| `1657` KB | `spectral.py` line 1656 | - |
| `200` files limit | `cli.py` line 470 | `browse.max_files` |

---

## Summary: Recommended Configuration Structure

```yaml
# ast-tools.yaml (user config) or pyproject.toml [tool.ast-tools]

database:
  path: null                    # defaults to <project>/.ast-tools/cache/codebase.db
  journal_mode: "WAL"
  foreign_keys: true
  max_retries: 3
  retry_delay: 0.5
  backoff_multiplier: 2.0

index:
  project_root: null            # defaults to CWD
  db_path: null                 # defaults to <project>/.ast-tools/cache/codebase.db
  watch: true
  debounce_ms: 500
  embeddings: true
  embedding_model: "bge-small-en-v1.5"
  embedding_dim: 384
  max_file_size: 1048576        # 1MB for indexing
  batch_size: 32
  exclude_patterns: [...]

embeddings:
  model: "bge-small-en-v1.5"
  fallback_models: []
  batch_size: 32
  max_batch_size: 64
  cache_dir: null
  device: "auto"
  max_file_size: 10485760       # 10MB for embedding generation

reranker:
  enabled: true
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  fallback_models: [...]
  batch_size: 32
  max_length: 512
  device: "auto"
  confidence_threshold: 0.0
  blend_weights: [0.5, 0.3, 0.2]

fix:
  max_iterations: 10
  safety_level: "safe"
  workers: 4
  timeout: 120
  max_file_size: 10485760       # 10MB
  create_backups: true
  backup_retention_days: 7

mcp:
  max_tokens: 8192
  token_tracking: true
  context_injection: true
  token_limits:
    ast_grep: {max_input: 4096, max_output: 16384}
    ast_read: {max_input: 2048, max_output: 32768}
    # ...

server:
  stdio_enabled: true
  daemon_enabled: false
  daemon_host: "127.0.0.1"
  daemon_port: 8765
  remote_enabled: false
  remote_host: "127.0.0.1"
  remote_port: 8766

lsp:
  enabled: true
  host: "127.0.0.1"
  port: 8767
  diagnostics:
    enabled: true
    debounce_ms: 300
    max_diagnostics_per_file: 100
  formatting:
    enabled: true
    range_formatting: true
    format_on_save: true
    fix_on_save: true
  llm:
    enabled: true
    timeout_seconds: 30
    max_tokens: 2048
    temperature: 0.1

watchdog:
  debounce_ms: 100
  enabled: true

cache:
  max_size_mb: 1024

spectral:
  min_cluster_size: 2
  max_workers: 4

browse:
  max_files: 200

setup:
  min_disk_mb: 500
  recommended_disk_mb: 500

paths:
  config_dir: "~/.ast-tools"
  cache_dir: "~/.cache/ast-tools"
  models_dir: "~/.cache/ast-tools/models"
```

---

## Migration Priority

| Priority | Area | Effort |
|----------|------|--------|
| **P0** | Embedding dimension (384) - single source in `IndexConfig.embedding_dim` | Low |
| **P0** | File size limits (10MB/1MB) - already in unified config but duplicated | Low |
| **P0** | Paths (~/.ast-tools, ~/.cache/ast-tools) - already using `get_config_dir()`/`get_cache_dir()` | Done |
| **P1** | Debounce values (500/300/100) - inconsistent across subsystems | Medium |
| **P1** | Batch sizes (16/32/64/100) - inconsistent | Medium |
| **P1** | Worker counts (4 everywhere) - should be per-subsystem | Medium |
| **P2** | Timeout (120s) - in 5 files | Medium |
| **P2** | Port numbers - already in config but some hardcoded in code | Low |
| **P2** | Embedding model strings - already in config | Done |
| **P3** | Token limits - in tokens_schema.py + config | Medium |
| **P3** | Retry/backoff - already in config but not used everywhere | Medium |

---

## Files That Need Updates

1. **`parser.py`** - Use `config.index.max_file_size` instead of `MAX_FILE_SIZE`
2. **`git_miner.py`** - Use `config.fix.timeout` instead of hardcoded 120
3. **`fix/engine.py`** - Use `config.fix.timeout`, `config.fix.workers`
4. **`fix/fixers.py`** - Use `config.fix.timeout`
5. **`spectral.py`** - Use `config.spectral.max_workers`
5. **`model_registry.py`** - Use `config.embeddings.batch_size` per model
6. **`provider.py`** - Use `config.embeddings.batch_size`
7. **`cache.py`** - Use `config.cache.max_size_mb`
8. **`connection.py`** - Already uses constants, just ensure they're from config
9. **`watchdog/daemon.py`** - Use `config.watchdog.debounce_ms`
10. **`diagnostic_publisher.py`** - Use `config.lsp.diagnostics.debounce_ms`
11. **`cli.py`** - Use `config.browse.max_files`
12. **`remote_inference.py`** - Use `config.remote_inference.*`

---

*Generated by architectural audit using ast-tools semantic search + ast_grep*