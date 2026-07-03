# ADR-0011: PyPI Name Decision + Publishing Pipeline

**Date:** 2026-07-02

**Status:** Proposed

## Context

The PyPI name `ast-tools` is taken by an unrelated toolbox (v0.1.8). A new name is required for public release. The importable package name (Python `import ast_tools`) and the CLI entry point (`ast`) remain unchanged — only the PyPI *distribution* name changes.

## Candidates

Six names were evaluated:

| Candidate | Type | Availability (PyPI) | Conflicts / Closest Match | Descriptive | Short |
|---|---|---|---|---|---|
| `rw-ast-tools` | `-mcp` suffix | **404 — AVAILABLE** | No close conflicts | ✅ "ast" + "tools" + "mcp" | Moderately long |
| `codegraph-mcp` | `-mcp` suffix | **404 — AVAILABLE** | `code-graph-mcp` exists (competitor) | ✅ | Moderately long |
| `astrix` | Abstract | **200 — TAKEN** | `astrix-openclaw-scanner` (v0.1.3) | Partial | ✅ |
| `codeintel-mcp` | `-mcp` suffix | **404 — AVAILABLE** | `code-intel-mcp` exists (competitor) | ✅ | Moderately long |
| `elara` | Abstract | **200 — TAKEN** | `elara` (key-value DB, completely unrelated) | ❌ | ✅ |
| `struct` | Abstract | **404 — AVAILABLE** | Collides with stdlib `struct` module | ❌ | ✅ |

### Methodology

Availability was checked via `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/<name>/json`:
- **HTTP 200** = package exists on PyPI (taken).
- **HTTP 404** = package does not exist on PyPI (available).

## Decision

**Recommended PyPI name: `rw-ast-tools`**

### Rationale

1. **Available:** Confirmed 404 (not found) on PyPI — no naming conflict.
2. **Descriptive:** The name communicates three things at a glance:
   - `ast` — Abstract Syntax Tree / code analysis domain
   - `tools` — it's a toolbox, not a library
   - `mcp` — it's an MCP (Model Context Protocol) server
3. **No close competitor conflicts:** Unlike `codegraph-mcp` (conflicts with `code-graph-mcp`, an actively maintained MCP + AST server) or `codeintel-mcp` (conflicts with `code-intel-mcp`), `rw-ast-tools` has no similarly-named package in the same space.
2. **PyPI name ≠ CLI name:** The CLI entry points remain `ast-tools`, `ast-tools-server`, and `ast-tools-project` (defined in `[project.scripts]` in `pyproject.toml`). The PyPI distribution name has zero impact on daily CLI usage.
5. **Migration clarity:** Adding `-mcp` makes it obvious this is a renamed successor to the original `ast-tools` package, easing discoverability for existing users.

### Other candidates rejected

- **`codegraph-mcp` / `codeintel-mcp`:** Both available, but `code-graph-mcp` and `code-intel-mcp` are already established packages in the same MCP code-analysis space. Publishing a near-identical name would cause user confusion.
- **`astrix`:** Taken by an unrelated security scanner project.
- **`elara`:** Taken by a key-value database. Also not descriptive of the project's purpose.
- **`struct`:** Available but collides with Python's standard library `struct` module, causing poor search-engine discoverability and potential confusion.

## Migration Path

The PyPI name change involves only the distribution metadata. Source code imports (`import ast_tools`) and CLI invocation (`ast`) are unchanged.

### 1. `pyproject.toml` — name field

Changed:

```toml
[project]
name = "rw-ast-tools"   # was: "ast-tools"
```

All other fields (version, description, dependencies, `[project.scripts]`) remain unchanged. The actual CLI entry points are:

```toml
[project.scripts]
ast-tools = "ast_tools.cli:main"
ast-tools-server = "ast_tools_server:main"
ast-tools-project = "project_tools:cli_main"
```

### 2. Documentation updates

| File | Change |
|---|---|
| `README.md` | Update install commands: `pip install rw-ast-tools` |
| `pyproject.toml` | Done (above) |
| `docs/` (all) | Audit for `ast-tools` → `rw-ast-tools` references |
| `CONTRIBUTING.md` | Update any build/publish instructions referencing old name |

### 3. No code changes required

- **Import path:** `import ast_tools` — unchanged (the source tree stays `src/ast_tools/`)
- **CLI:** `ast-tools`, `ast-tools-server`, `ast-tools-project` — unchanged (entry point names in `[project.scripts]`)
- **Internal references:** Code uses the `ast_tools` package, not the PyPI name

## Publishing Pipeline

### 3-Step Workflow

```bash
# Step 1: Update package name in pyproject.toml
#   name = "rw-ast-tools"   (already done)

# Step 2: Build the package
uv build

# Step 3: Publish to PyPI
uv publish --token $PYPI_TOKEN
```

The utility script `scripts/publish.sh` automates steps 2–3 with error handling.

### `scripts/publish.sh`

```bash
#!/bin/bash
set -e

if [ -z "$PYPI_TOKEN" ]; then
  echo "Error: PYPI_TOKEN environment variable is not set."
  exit 1
fi

cd "$(dirname "$0")/.."

echo "==> Building package with uv..."
uv build

echo "==> Publishing to PyPI..."
uv publish --token "$PYPI_TOKEN"

echo "Done. CLI remains: ast"
```

### Build Output

`uv build` produces both a source distribution (`.tar.gz`) and a wheel (`.whl`) in `dist/`:

```
dist/ast_tools_mcp-0.1.0.tar.gz
dist/ast_tools_mcp-0.1.0-py3-none-any.whl
```

Note that `uv` normalizes the package name internally (`rw-ast-tools` → `rw_ast_tools` in filenames), but the published name on PyPI is `rw-ast-tools`.

### Prerequisites

1. A PyPI API token with upload permissions for the `rw-ast-tools` project (create at https://pypi.org/manage/account/token/)
2. `uv` installed (project build system)
3. The `PYPI_TOKEN` environment variable set before running the publish script

## Next Steps

1. [ ] Merge this ADR and associated changes
2. [ ] Register `rw-ast-tools` on PyPI (first `uv publish` creates the project automatically)
3. [ ] Update all documentation references from `ast-tools` to `rw-ast-tools`
4. [ ] Create a GitHub release matching the published version
5. [ ] Add PyPI badge to README after first publish
