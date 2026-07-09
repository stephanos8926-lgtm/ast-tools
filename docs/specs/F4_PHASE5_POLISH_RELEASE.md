# F4 LSP Server — Phase 5: Polish, CI/CD, Testing & Release

**Phase:** 5 of 5
**Duration:** 2 days
**Dependencies:** Phase 1-4 complete
**Status:** Planned

---

## Scope

Final polish: comprehensive testing, CI/CD pipeline, performance benchmarks, documentation, and release preparation.

---

## Deliverables

### 1. Comprehensive Test Suite

#### Unit Tests (`tests/lsp/unit/`)
| Test File | Coverage |
|-----------|----------|
| `test_language_router.py` | Language → fixer mapping, plugin precedence |
| `test_diagnostic_publisher.py` | Diagnostic conversion, debouncing, limits |
| `test_code_action_provider.py` | Action kinds, lazy resolve, safety levels |
| `test_llm_client.py` | Local/remote fallback, timeout, diff parsing |
| `test_formatting_handler.py` | Full/range formatting, TextEdit generation |
| `test_semantic_actions.py` | Refactor action generation |
| `test_config_watcher.py` | Hot-reload on config change |

#### Integration Tests (`tests/lsp/integration/`)
| Test File | Coverage |
|-----------|----------|
| `test_lsp_protocol.py` | Full initialize → shutdown lifecycle |
| `test_diagnostics_flow.py` | didOpen → publishDiagnostics → codeAction → apply |
| `test_fix_all_flow.py` | Fix all safe/unsafe, convergence |
| `test_formatting_flow.py` | Formatting requests, on-save |
| `test_multi_language.py` | Python + TS + Go in same workspace |
| `test_custom_plugin.py` | Custom fixer plugin loaded via config |
| `test_llm_fix_flow.py` | LLM fix action → resolve → apply |
| `test_config_hot_reload.py` | Config change → server reloads without restart |

#### Fixture-Based Tests
```
tests/lsp/fixtures/
├── python/
│   ├── simple.py
│   ├── with_errors.py
│   └── custom_fixer.py
├── typescript/
│   ├── simple.ts
│   └── with_errors.ts
├── go/
│   └── simple.go
├── rust/
│   └── simple.rs
└── workspace/
    ├── pyproject.toml
    ├── ast-tools.yaml
    ├── python/
    │   └── main.py
    ├── typescript/
    │   └── index.ts
    └── go/
        └── main.go
```

### 2. Performance Benchmarks (`tests/lsp/benchmarks/`)

```python
# benchmark_lsp.py
"""Performance benchmarks for LSP server."""

async def benchmark_initialize():
    """Time from process start to initialize response."""
    pass

async def benchmark_code_action():
    """Time for codeAction on 100-line file."""
    pass

async def benchmark_diagnostics():
    """Time for full diagnostic publish on 1000-line file."""
    pass

async def benchmark_fix_all():
    """Time for fix all on 50-file project."""
    pass

async def benchmark_memory():
    """Memory usage idle vs active."""
    pass
```

**Targets:**
| Metric | Target |
|--------|--------|
| Initialize response | < 500ms |
| codeAction (quickfix) | < 200ms |
| codeAction (fixAll resolve) | < 1s |
| Diagnostics (push) | < 500ms |
| Memory (idle) | < 150MB |
| Memory (100 files) | < 500MB |
| CPU (idle) | < 1% |

### 3. CI/CD Pipeline (`.github/workflows/`)

#### `lsp-tests.yml`
```yaml
name: LSP Tests
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra lsp,llm-local,llm-remote
      - run: uv run pytest tests/lsp/unit -x -v
  
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra lsp,llm-local,llm-remote
      - run: uv run pytest tests/lsp/integration -x -v
  
  benchmarks:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra lsp,llm-local
      - run: uv run pytest tests/lsp/benchmarks --benchmark-only
      - uses: actions/upload-artifact@v4
        with:
          name: lsp-benchmarks
          path: benchmark-results.json

  editor-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra lsp
      - run: uv run pytest tests/lsp/editor -x -v
```

#### `release.yml`
```yaml
name: Release
on:
  push:
    tags: ['v*']
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
      - run: uv run pytest tests/ -x
  
  publish-pypi:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
      - uses: pypa/gh-action-pypi-publish@release/v1
  
  publish-vscode:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd packages/vscode-ast-tools && npm ci && npm run compile && npm run package
      - uses: actions/upload-artifact@v4
        with:
          name: vscode-extension
          path: packages/vscode-ast-tools/*.vsix
  
  docker:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t rapidwebs/ast-tools:${{ github.ref_name }} -f Dockerfile.lsp .
      - run: docker push rapidwebs/ast-tools:${{ github.ref_name }}
```

### 4. Docker Image (`Dockerfile.lsp`)

```dockerfile
FROM python:3.12-slim

# Install system deps for llama.cpp
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ast-tools with LSP extras
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system "ast-tools[lsp,llm-local]@."

# Model cache directory
ENV AST_TOOLS_MODEL_CACHE=/models
RUN mkdir -p /models

EXPOSE 8767

ENTRYPOINT ["ast-tools", "lsp"]
```

### 5. Documentation Finalization

| Document | Status |
|----------|--------|
| `docs/lsp/architecture.md` | Server architecture, data flow |
| `docs/lsp/configuration.md` | Complete config reference |
| `docs/lsp/troubleshooting.md` | Common issues, debugging |
| `docs/lsp/performance.md` | Benchmarks, tuning |
| `docs/lsp/custom-fixers.md` | Writing custom fixer plugins |
| `docs/lsp/llm-integration.md` | Local/remote LLM setup |
| `docs/editors/vscode.md` | VS Code setup |
| `docs/editors/neovim.md` | Neovim setup |
| `docs/editors/zed.md` | Zed setup |
| `CHANGELOG.md` | LSP release notes |

### 6. Example Configurations

`examples/ast-tools.yaml`:
```yaml
# Full example configuration
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
    fix_on_save: true
  llm:
    enabled: true
    prefer_local: true
    local_backend: "llama.cpp"
    local_model_path: "~/.cache/ast-tools/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    remote_provider: "openrouter"
    remote_model: "qwen/qwen-2.5-coder-32b-instruct"
fix:
  safety_level: "safe"
  max_iterations: 10
  custom_fixers:
    sql: "my_project.fixers:SQLFixer"
plugins:
  custom_fixers:
    sql: "my_project.fixers:SQLFixer"
```

---

## Tests Required

| Category | Count | Status |
|----------|-------|--------|
| Unit tests | 25+ | Planned |
| Integration tests | 12+ | Planned |
| Benchmarks | 5 | Planned |
| Editor tests | 4 | Planned |

---

## Acceptance Criteria

- [ ] All unit tests pass (25+)
- [ ] All integration tests pass (12+)
- [ ] Benchmarks meet targets
- [ ] CI/CD runs on every PR
- [ ] Release workflow publishes to PyPI, VS Code Marketplace, Docker Hub
- [ ] Documentation complete and published
- [ ] Example config works out of the box
- [ ] Docker image runs and serves LSP
- [ ] All Phase 1-5 tests pass together
- [ ] No regressions in existing ast-tools CLI/MCP functionality