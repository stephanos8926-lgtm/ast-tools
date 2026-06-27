# ast-tools

Structural code analysis and editing MCP server for Python, JavaScript, TypeScript, Rust, Go, Java, C, and C++.

## Overview

**ast-tools** provides 11 production-ready tools for structural code operations:

| Tool | Purpose |
|------|---------|
| `ast_grep` | Structural code search via AST patterns |
| `ast_edit` | Surgical AST-based edits (libcst) |
| `ast_read` | Extract API surface from files |
| `ast_generate_stub` | Generate .pyi type stubs |
| `ast_refactor_extract_interface` | Extract ABC/Protocol from class |
| `structural_analysis` | Call graphs, type hierarchies, refs, deps |
| `project_info` | Project manifest (project.json) |
| `codebase_summary` | High-level architecture overview |
| `find_references` | Find all symbol usages across codebase |
| `impact_analysis` | Change impact + risk assessment |
| `module_imports` | Module-level fan-in/fan-out import analysis |

---

## New in v0.2.0 (Phase 8-9) — 2026-07-24

### Phase 8: Context Injection + Semantic Search

**semantic_search** tool with intelligent context injection:

```python
semantic_search(
    query="websocket session authentication",
    k=10,
    inject_context=True,      # Auto-inject formatted markdown
    token_budget=8192,        # Respect model context window
    diversity_limit=3,        # Max 3 symbols per file
    lang="python",
    kind="function"
)
```

**6-factor Reciprocal Rank Fusion:**
- Semantic similarity (40%) — Cosine distance
- Recency (15%) — Git commit timestamp decay
- Usage frequency (15%) — Access patterns
- Kind relevance (10%) — Function/class boosting
- Proximity (10%) — Distance from entry points
- Callgraph centrality (10%) — PageRank score

**Hermes Plugins** (auto-enabled):
- **ast_tools_context** — Injects docs on code queries (`pre_llm_call` hook)
- **ast_tools_tokens** — Token budget tracking + 50%/80% pressure alerts

See `DISTRIBUTION_PACKAGE.md` for full plugin documentation.

### Phase 9: Schema Enrichments — Architectural Intelligence

**New tables (schema v5):**
- `dependency_metrics` — fan_in, fan_out, SPOF_score, instability, PageRank
- `embedding_similarity` — Pre-computed cosine similarities
- `knn_graph` — k-nearest-neighbor edges for similarity traversal
- `audit_log` — Provenance tracking

**New tools:**
- `callgraph_edges(view="materialized")` — Fast caller/callee lookups
- `dependency_metrics` — SPOF detection, centrality scoring
- `embedding_similarity(top_k=10, min_score=0.7)` — Code clone detection
- `knn_graph` — "Find code like this" navigation
- `secret_sanitizer` — Detects API keys, passwords, tokens, .env paths

**Performance:**
- FTS5 queries: <10ms
- Vector search: <50ms (CPU, no GPU)
- Hybrid fusion: <100ms total

See `docs/PHASE9_COMPLETE.md` for full details.

## Installation

### Production Install (uv)
```bash
uv pip install ast-tools
```

### Development Install
```bash
cd ~/Workspaces/ast-tools
uv sync --all-extras  # Installs dev dependencies (pytest, ruff, pre-commit, etc.)
uv run pytest        # Run test suite (373 tests)
uv run ruff check src/ tests/  # Lint
uv run ruff format src/ tests/  # Format
uv build             # Build package
```

### Pre-commit Hooks
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Usage

### As MCP Server (Hermes Agent)

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  ast-tools:
    command: ["python3", "-m", "ast_tools_server"]
    cwd: "/home/sysop/Workspaces/ast-tools"
```

### Command Line

```bash
# Project overview
python3 -m ast_tools_server project-info

# Codebase summary
python3 -m ast_tools_server codebase-summary

# Find references
python3 -m ast_tools_server find-references symbol_name

# Impact analysis
python3 -m ast_tools_server impact-analysis src/module.py
```

### Python API

```python
from ast_tools.tools.ast_grep import _tool_ast_grep
from ast_tools.tools.ast_read import _tool_ast_read
from ast_tools.tools.impact_analysis import _tool_impact_analysis

# Search for all function definitions
result = _tool_ast_grep({
    "pattern": "def $FUNC($$$ARGS)",
    "path": "src/",
    "lang": "python"
})

# Extract API surface
result = _tool_ast_read({
    "file": "src/core/agent.py",
    "include_private": True
})

# Analyze change impact
result = _tool_impact_analysis({
    "target": "src/core/worker.py"
})
```

## Development

### Run Tests

```bash
python3 -m pytest           # All tests
python3 -m pytest -v        # Verbose
python3 -m pytest tests/test_e2e.py  # Specific file
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Project Structure

```
ast-tools/
├── src/
│   ├── ast_tools_server.py          # MCP server (445 lines)
│   ├── ast_tools/
│   │   ├── tools/                   # 11 tool implementations
│   │   │   ├── __init__.py          # Registry
│   │   │   ├── ast_grep.py
│   │   │   ├── ast_edit.py
│   │   │   ├── ast_read.py
│   │   │   ├── structural_analysis.py
│   │   │   ├── find_references.py
│   │   │   ├── impact_analysis.py
│   │   │   ├── module_imports.py
│   │   │   ├── ast_generate_stub.py
│   │   │   ├── ast_refactor_extract_interface.py
│   │   │   ├── project_info.py
│   │   │   └── codebase_summary.py
│   │   └── utils/
│   │       ├── file_utils.py
│   │       └── impact.py
│   └── project_tools.py
├── tests/
│   ├── conftest.py
│   ├── test_e2e.py
│   ├── test_phase3_polish.py
│   └── test_project_tools.py
├── docs/
│   ├── PROJECT_STATE.md
│   ├── PHASE_SUMMARIES.md
│   └── REFACTORING_JOURNAL.md
└── pyproject.toml
```

## Test Coverage

**373 tests** — all passing ✅

- `test_e2e.py`: 32 tests (E2E tool + CLI)
- `test_phase3_polish.py`: 17 tests (error codes, CLI polish)
- `test_project_tools.py`: 65 tests (project info, impact analysis)

## Architecture

### Design Principles

1. **Registry Pattern** — Tools self-register via `@register_tool()`
2. **Thin Server** — Server only defines schemas + dispatches
3. **Extracted Tools** — All logic in `src/ast_tools/tools/`
4. **Shared Utils** — Common helpers in `src/ast_tools/utils/`

### Adding a Tool

1. Create `src/ast_tools/tools/new_tool.py`
2. Implement with `@register_tool("new_tool")`
3. Add schema to `server.list_tools()`
4. Write tests
5. Run `python3 -m pytest`

## License

MIT — RapidWebs Enterprise, LLC

## Contact

Steven Albert Page <steven@rapidwebs.io>