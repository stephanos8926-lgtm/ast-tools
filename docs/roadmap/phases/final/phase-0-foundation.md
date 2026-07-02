# Phase 0 Implementation Plan — Foundation & Configuration (FINAL)

> **Status:** ✅ Final — Audited (Forward ✅, Reverse ✅, Adversarial ✅)  
> **Phase:** 0  
> **Timeline:** 1-2 weeks  
> **Dependencies:** None  
> **Finalized:** 2026-07-31  

---

## Audit Results

| Audit | Findings | Resolution |
|-------|----------|------------|
| **Forward** | 6 findings (1 critical, 2 medium, 3 low) | ✅ All incorporated |
| **Reverse** | 10 findings (2 critical, 4 medium, 4 low) | ✅ All incorporated |
| **Adversarial** | 6 findings (1 high, 3 medium, 2 low) | ✅ All incorporated |

### Key Changes from Draft

- Added `pyyaml` and `jsonschema` to `pyproject.toml` dependencies
- Added config migration logic from `~/.cache/ast-tools/` 
- Added XDG compliance for CACHE_HOME and DATA_HOME
- Added file permission hardening (chmod 600 for config files)
- Added atomic write pattern for config file updates
- Added environment variable validation (`AST_TOOLS_HOME`)
- Added deep_merge type safety checks
- Added config validation for ALL config files, not just tokens.yaml
- Added secret pattern filtering in audit log
- Added tests for config module
- Added documentation update plan

---

## Goal

Establish the foundational infrastructure that all subsequent phases build upon: config directory, token management configuration, logging, audit trail, SKILL.md bundle, and config validation.

## Architecture

```mermaid
flowchart TD
    ENV[AST_TOOLS_HOME] --> RESOLVER[Config Dir Resolver]
    XDG[XDG_*_HOME] --> RESOLVER
    RESOLVER --> CONFIG_DIR[~/.ast-tools/ | ${XDG_CONFIG_HOME}/ast-tools]
    
    CONFIG_DIR --> TOKENS[config/tokens.yaml]
    CONFIG_DIR --> SERVER[config/server.yaml]
    CONFIG_DIR --> CACHE[cache/]
    CONFIG_DIR --> LOGS[logs/]
    CONFIG_DIR --> BACKUPS[backups/]
    
    TOKENS --> VALIDATOR[JSON Schema Validator]
    VALIDATOR --> PLUGIN[ast-tools-tokens Plugin]
    PLUGIN --> FALLBACK[Hardcoded Defaults (when no file)]
    
    LOGS --> LOGGER[Structured Logger]
    LOGGER --> ROTATION[Size+Time Rotation]
    LOGGER --> AUDIT[Audit Trail - JSONL]
```

### Security Requirements (From Adversarial Audit)

- Config files: **chmod 600** (user-read-write only)
- Atomic writes: write to `.tmp` → rename over target
- Input validation: `AST_TOOLS_HOME` must resolve to a safe, absolute path
- Audit log: filter common secret patterns (API keys, tokens) before writing
- Symlink protection: resolve symlinks before creating directories

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/ast_tools/config/__init__.py` | ✅ Create | Config module init |
| `src/ast_tools/config/loader.py` | ✅ Create | YAML config loader with validation, env var resolution, XDG support |
| `src/ast_tools/config/tokens_schema.py` | ✅ Create | JSON Schema for tokens.yaml |
| `src/ast_tools/config/validate.py` | ✅ Create | Config validation command |
| `src/ast_tools/logging/__init__.py` | ✅ Create | Logging module init |
| `src/ast_tools/logging/setup.py` | ✅ Create | Logging setup with rotation, log level from server.yaml |
| `src/ast_tools/logging/audit.py` | ✅ Create | Audit trail logger with secret pattern filtering |
| `src/ast_tools/cli.py` | ✅ Modify | Add `config validate`, `config path`, `config init` subcommands |
| `pyproject.toml` | ✅ Modify | Add `pyyaml`, `jsonschema` dependencies |
| `tests/config/test_loader.py` | ✅ Create | Config loader tests |
| `tests/config/test_validate.py` | ✅ Create | Config validation tests |
| `tests/config/test_migration.py` | ✅ Create | Legacy migration tests |
| `tests/logging/test_audit.py` | ✅ Create | Audit logger tests |
| `skills/hermes/ast-tools.skill.md` | ✅ Create | Hermes SKILL.md |
| `skills/claude/CLAUDE.md` | ✅ Create | Claude Code skill file |
| `skills/ast-tools.skill.md` | ✅ Create | Generic cross-platform skill file |
| `hermes-plugins/ast-tools-tokens/__init__.py` | ✅ Modify | Read from tokens.yaml, fall back to hardcoded defaults |
| `hermes-plugins/ast-tools-tokens/plugin.yaml` | ✅ Modify | Bump version to 2.0.0 |
| `docs/CLI_REFERENCE.md` | ✅ Modify | Add config commands |
| `docs/AST_TOOLS_QUICKSTART.md` | ✅ Modify | Add config dir setup |
| `CHANGELOG.md` | ✅ Create | Add Phase 0 entries |
| `CONTRIBUTING.md` | ✅ Create | Contribution guide |

---

## Task Breakdown

### Task 0.1: Config Directory Module

**Objective:** Create the config directory structure and loader.

**Files:** `src/ast_tools/config/`

**Key design decisions:**

```python
def get_config_dir() -> Path:
    """Resolve config directory with env override and XDG compliance."""
    # 1. Env override (highest priority)
    if env_home := os.environ.get("AST_TOOLS_HOME"):
        path = Path(env_home).resolve()
        _validate_safe_path(path)  # Adversarial: prevent path traversal
        return path
    
    # 2. XDG (medium priority)
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "ast-tools"
    
    # 3. Default (lowest priority)
    return Path.home() / ".ast-tools"

def _validate_safe_path(path: Path) -> None:
    """Reject paths with traversal, symlink escape, or non-absolute."""
    resolved = path.resolve()
    if ".." in str(path):
        raise ConfigError(f"Path contains '..': {path}")
    if not path.is_absolute():
        raise ConfigError(f"Path must be absolute: {path}")

def ensure_config_dir(config_dir: Path = None) -> Path:
    """Create config directory structure idempotently."""
    cfg = config_dir or get_config_dir()
    # Resolve symlinks before mkdir (adversarial: prevent symlink recursion)
    cfg = cfg.resolve()
    for subdir in ["config", "cache/models", "cache/tmp", "logs", "backups"]:
        (cfg / subdir).mkdir(parents=True, exist_ok=True)
    return cfg
```

**XDG cache and data compliance:**
```python
def get_cache_dir() -> Path:
    """Return cache directory (XDG_CACHE_HOME or ~/.ast-tools/cache)."""
    if env_home := os.environ.get("AST_TOOLS_HOME"):
        return Path(env_home) / "cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "ast-tools"
    return get_config_dir() / "cache"

def get_data_dir() -> Path:
    """Return data directory (XDG_DATA_HOME or ~/.ast-tools/data)."""
    if env_home := os.environ.get("AST_TOOLS_HOME"):
        return Path(env_home) / "data"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "ast-tools"
    return get_config_dir() / "data"
```

**Migration from ~/.cache/ast-tools/:**
```python
def migrate_legacy() -> bool:
    """Migrate data from ~/.cache/ast-tools/ to new config dir."""
    legacy = Path.home() / ".cache" / "ast-tools"
    if not legacy.exists():
        return False
    
    target = get_data_dir()
    log = get_logger(__name__)
    
    # Migrate database
    legacy_db = legacy / "codebase.db"
    if legacy_db.exists():
        target_db = target / "codebase.db"
        if not target_db.exists():
            shutil.copy2(legacy_db, target_db)
            log.info(f"Migrated database: {legacy_db} → {target_db}")
    
    # Migrate models
    legacy_models = legacy / "models"
    if legacy_models.exists():
        target_models = target / "models"
        if not target_models.exists():
            shutil.copytree(legacy_models, target_models)
            log.info(f"Migrated models: {legacy_models} → {target_models}")
    
    return True
```

**Token budgets config with type-safe deep merge:**
```python
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base with type safety."""
    result = base.copy()
    for key, val in override.items():
        # Type mismatch protection (adversarial audit finding)
        if key in result:
            if isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = _deep_merge(result[key], val)
            elif type(result[key]) != type(val):
                raise ConfigError(
                    f"Type mismatch for '{key}': "
                    f"expected {type(result[key]).__name__}, got {type(val).__name__}"
                )
            else:
                result[key] = val
        else:
            result[key] = val
    return result
```

**Atomic writes (adversarial audit finding):**
```python
def write_config(path: Path, data: dict) -> None:
    """Write config atomically to prevent race conditions."""
    path = path.resolve()
    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(yaml.dump(data, default_flow_style=False))
        tmp_path.chmod(0o600)  # Permission hardening
        tmp_path.rename(path)  # Atomic on same filesystem
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
```

---

### Task 0.2: Logging Framework

**Objective:** Structured logging with rotation and secret-filtered audit trail.

**Files:** `src/ast_tools/logging/setup.py`, `src/ast_tools/logging/audit.py`

**Log level configuration (from server.yaml):**
```yaml
# ~/.ast-tools/config/server.yaml
logging:
  level: INFO              # DEBUG, INFO, WARNING, ERROR
  max_bytes: 104857600     # 100MB per file
  backup_count: 5          # Keep 5 rotated files
  retention_days: 30
```

**Audit log with secret filtering:**
```python
# Secrets patterns to filter from audit log
AUDIT_SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_\-]?key|secret|password|token)\s*[:=]\s*[\'"][^\'"]+[\'"]'),
    re.compile(r'[A-Za-z0-9]{32,}'),  # Potential API keys (32+ chars)
]

def write_audit(action: str, params: dict, result: str, user: str = "agent"):
    """Write to audit log, redacting potential secrets."""
    safe_params = _redact_secrets(params)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "params": safe_params,
        "result": _sanitize(result),
        "user": user,
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

---

### Task 0.3: AST-Tools Tokens Plugin Update

**Objective:** Make `ast-tools-tokens` plugin read from `~/.ast-tools/config/tokens.yaml`.

**Files:**
- Modify: `hermes-plugins/ast-tools-tokens/__init__.py`
- Modify: `hermes-plugins/ast-tools-tokens/plugin.yaml`

**Changes:**
1. Remove hardcoded `AST_TOOLS_TOKEN_BUDGETS` dict
2. Import `load_tokens_config()` from the new config module
3. Fall back to hardcoded defaults if config file doesn't exist
4. Schema validation before merge

---

### Task 0.4: SKILL.md Cross-Platform Bundle

**Objective:** Create platform-agnostic skill files for agents.

**Files:**
- `skills/hermes/ast-tools.skill.md`
- `skills/claude/CLAUDE.md`
- `skills/ast-tools.skill.md`

**Each includes:** frontmatter, tool catalog (43 tools), usage patterns, installation, troubleshooting.

---

### Task 0.5: CLI Config Integration

**Objective:** Add `ast-tools config` subcommand.

**New commands:**
```
ast-tools config validate    — Validate all config files (tokens.yaml, server.yaml if exists)
ast-tools config path        — Print config directory path
ast-tools config init        — Create default config files
ast-tools config show        — Show current configuration (with secrets masked)
```

---

## Test Plan

| Test | What it verifies | Status |
|------|-----------------|--------|
| Config dir creation | `ensure_config_dir()` creates all subdirs | Added |
| tokens.yaml loading without file | Returns defaults, no crash | Added |
| tokens.yaml loading with valid file | Merges user values with defaults | Added |
| tokens.yaml schema rejection | Invalid values produce clear error | Added |
| Deep merge type safety | Type mismatches raise ConfigError | Added (adversarial) |
| Atomic write atomicity | Partial write doesn't corrupt config | Added (adversarial) |
| Config file permissions | Files created with 0o600 | Added (adversarial) |
| Env var validation | Path traversal paths rejected | Added (adversarial) |
| Legacy migration | `~/.cache/ast-tools/` data migrated | Added (reverse) |
| XDG compliance | `XDG_CACHE_HOME` respected | Added (reverse) |
| Audit log secret filtering | API keys redacted from audit entries | Added (adversarial) |
| Plugin fallback | Plugin works without `~/.ast-tools/` | Added |
| Plugin config-driven | Plugin reads tokens.yaml when available | Added |
| Config validate CLI | Command returns correct status | Added |
| SKILL.md rendering | All three skills render as valid markdown | Added |
| CI with new deps | `pip install -e ".[dev]"` works | Added (reverse) |
| All existing tests | `pytest tests/ -q --tb=short` passes | Baseline |

---

## Verification Checklist

- [ ] `~/.ast-tools/` directory created with `config/`, `cache/`, `logs/`, `backups/`
- [ ] XDG variables respected when set (`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`)
- [ ] `AST_TOOLS_HOME` overrides base directory
- [ ] Path traversal in env var is rejected with clear error
- [ ] Config files created with `chmod 600`
- [ ] Atomic writes prevent concurrent-write corruption
- [ ] `tokens.yaml` loaded and merged with defaults
- [ ] Invalid tokens.yaml produces `file:line` error message
- [ ] Type mismatch in config raises clear ConfigError
- [ ] Legacy `~/.cache/ast-tools/` data migrated on first run
- [ ] ast-tools-tokens plugin works with and without config file
- [ ] SKILL.md files render correctly in all target formats
- [ ] `ast-tools config validate` returns clean health report
- [ ] Audit log entries have secrets filtered
- [ ] CLI reference and quickstart updated
- [ ] CHANGELOG.md updated with Phase 0 entries
- [ ] All existing 409 tests still pass
- [ ] `pip install -e ".[dev]"` succeeds with new dependencies