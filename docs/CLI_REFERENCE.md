# rw-ast-tools CLI Reference

**Complete guide to the `ast` command-line interface.**

---

## Quick Start

```bash
# Install (if not already installed)
cd ast-tools
source .venv/bin/activate
pip install -e .

# Usage
ast <command> [options]
```

---

## Commands Overview

| Command | Description | Example |
|---------|-------------|---------|
| [`ast search`](#ast-search) | Semantic search across codebase | `ast search "auth handler"` |
| [`ast navigate`](#ast-navigate) | Jump to symbol definition | `ast navigate SessionManager` |
| [`ast blast-radius`](#ast-blast-radius) | Impact analysis | `ast blast-radius src/auth.py:42` |
| [`ast find-dead`](#ast-find-dead) | Enhanced dead code detection | `ast find-dead --format table` |
| [`ast summary`](#ast-summary) | Codebase overview | `ast summary --format markdown` |
| [`ast symbols`](#ast-symbols) | List symbols in file | `ast symbols src/auth.py` |
| [`ast refs`](#ast-refs) | Find all references | `ast refs authenticate` |
| [`ast callers`](#ast-callers) | Who calls this symbol | `ast callers process_payment` |
| [`ast callees`](#ast-callees) | What does this symbol call | `ast callees main --file-path src/main.py` |
| [`ast deps`](#ast-deps) | Import dependencies | `ast deps src/api/handlers.py` |
| [`ast browse`](#ast-browse) | Browse all symbols | `ast browse --kind function` |

---

## Common Options

All commands support these global options:

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--project-root` | `-p` | Project root directory | `.` (current dir) |
| `--format` | `-f` | Output format | `table` |
| `--help` | `-h` | Show help for command | — |

**Output Formats:**
- `table` — Human-readable tabular format
- `json` — Machine-readable JSON (for scripting)
- `markdown` — Markdown format (for documentation)

---

## Command Reference

### `ast search`

**Semantic search across codebase** — find code by meaning, not just keywords.

```bash
ast search <query> [options]
```

**Arguments:**
- `<query>` — Natural language search query (e.g., "authentication handler")

**Options:**
- `--limit`, `-n` — Max results (default: 10)
- `--format`, `-f` — Output format (table/json/markdown)

**Examples:**
```bash
# Search for authentication code
ast search "authentication handler"

# Search with JSON output for scripting
ast search "database connection" --format json --limit 5

# Search for classes only
ast search "service class" --format markdown
```

**How it works:** Uses hybrid FTS5 + vector search on the semantic database. Requires project to be indexed (`refresh_index` tool).

---

### `ast navigate`

**Jump to symbol definition** — find where a symbol is defined.

```bash
ast navigate <symbol> [options]
```

**Arguments:**
- `<symbol>` — Symbol name (function, class, method, etc.)

**Options:**
- `--format`, `-f` — Output format (concise/json/markdown)

**Examples:**
```bash
# Find where SessionManager is defined
ast navigate SessionManager

# Get JSON output
ast navigate AuthService --format json

# Markdown output for documentation
ast navigate APIHandler --format markdown
```

**Output (concise format):**
```
src/auth/session.py:42 — class
```

---

### `ast blast-radius`

**Impact analysis** — see what code will be affected by a change.

```bash
ast blast-radius <file:line> [options]
```

**Arguments:**
- `<file:line>` — File path with optional line number

**Options:**
- `--line`, `-l` — Line number (if not in file:line format)
- `--format`, `-f` — Output format

**Examples:**
```bash
# Analyze impact of changing line 42
ast blast-radius src/auth.py:42

# Analyze entire file
ast blast-radius src/auth.py

# JSON output for CI/CD
ast blast-radius src/api/handlers.py --format json
```

**Use case:** **Mandatory** before changing public APIs or shared utilities.

---

### `ast find-dead`

**Enhanced dead code detection** — find unused code with 6 false-positive reduction strategies.

```bash
ast find-dead [options]
```

**Options:**
- `--basic` — Use basic dead code detection (no FP reduction)
- `--entry-points` — Comma-separated entry point files (auto-detected if omitted)
- `--format`, `-f` — Output format

**Examples:**
```bash
# Find dead code with enhanced detection
ast find-dead

# Specify entry points for better accuracy
ast find-dead --entry-points "main.py,cli.py"

# JSON output for CI integration
ast find-dead --format json

# Only show high-confidence dead code
ast find-dead --format json | jq '.dead_functions[] | select(.confidence == "high")'
```

**False Positive Reductions:**
1. Polymorphism tracking (interface implementations)
2. Framework decorators (Flask, FastAPI, Celery, etc.)
3. Entry point analysis (reachable from main/cli)
4. SCC clusters (mutually recursive functions)
5. `__all__` exports check
6. Confidence scoring (High/Medium/Low)

---

### `ast summary`

**Codebase overview** — get a compact project summary.

```bash
ast summary [options]
```

**Options:**
- `--format`, `-f` — Output format (concise/json/markdown)

**Examples:**
```bash
# Quick summary
ast summary

# JSON for metadata extraction
ast summary --format json

# Markdown for README
ast summary --format markdown
```

**Output (concise):**
```
|ast-tools v0.2.0 — 134 source files, 77 tools, 71 test files
```

**Output (markdown):**
```markdown
# 📦 ast-tools

**Version:** 0.1.0  
**Test framework:** pytest

## Languages
- **Python:** 97 files, 22,798 lines
- **Markdown:** 70 files, 24,485 lines

## Top Modules
- `src/ast_tools/tools/semantic_search.py` — 475 lines, 6 funcs
...
```

---

### `ast symbols`

**List symbols in file** — show all symbols defined in a specific file.

```bash
ast symbols <file> [options]
```

**Arguments:**
- `<file>` — File path to analyze

**Options:**
- `--kind` — Filter by kind (function/class/method/all, default: all)
- `--format`, `-f` — Output format

**Examples:**
```bash
# List all symbols in a file
ast symbols src/auth/middleware.py

# Only functions
ast symbols src/api/handlers.py --kind function

# JSON output for tooling
ast symbols src/utils.py --format json
```

---

### `ast refs`

**Find references** — find all usages of a symbol across the codebase.

```bash
ast refs <symbol> [options]
```

**Arguments:**
- `<symbol>` — Symbol name to find references for

**Options:**
- `--file-path` — Limit to specific file
- `--format`, `-f` — Output format

**Examples:**
```bash
# Find all references to a function
ast refs authenticate_user

# Limit to specific file
ast refs UserService --file-path src/services/user.py

# Markdown for documentation
ast refs APIHandler --format markdown
```

**Use case:** Before renaming or removing any symbol.

---

### `ast callers`

**Find callers** — see which functions/methods call this symbol.

```bash
ast callers <symbol> [options]
```

**Arguments:**
- `<symbol>` — Symbol name to find callers for

**Options:**
- `--max-files`, `-n` — Max files to search (default: 100)
- `--format`, `-f` — Output format

**Examples:**
```bash
# Find who calls process_payment
ast callers process_payment

# Search more files
ast callers helper_function --max-files 200

# JSON for analysis
ast callers main_handler --format json
```

**How it works:** Uses AST-based call graph analysis to find all call sites.

---

### `ast callees`

**Find callees** — see what functions this symbol calls.

```bash
ast callees <symbol> --file-path <file> [options]
```

**Arguments:**
- `<symbol>` — Symbol name
- `--file-path` — File containing the symbol (required)

**Options:**
- `--format`, `-f` — Output format

**Examples:**
```bash
# Find what main() calls
ast callees main --file-path src/main.py

# Find what a method calls
ast callees process_request --file-path src/api/handlers.py
```

**Use case:** Understanding function dependencies before refactoring.

---

### `ast deps`

**Show dependencies** — analyze import fan-in/fan-out for a file.

```bash
ast deps <file> [options]
```

**Arguments:**
- `<file>` — File path to analyze

**Options:**
- `--format`, `-f` — Output format

**Examples:**
```bash
# Analyze dependencies
ast deps src/api/handlers.py

# JSON for dependency graph
ast deps src/auth/middleware.py --format json
```

**Output:**
```
Dependencies of `src/api/handlers.py`

Fan-out (imports): 5
Fan-in (imported by): 12

Imports:
  flask                                src/api/handlers.py:2
  src.utils.helpers                    src/api/handlers.py:5

Imported by (12):
  src/main.py:3
  tests/test_api.py:5
  ...
```

---

### `ast browse`

**Browse symbols** — explore all symbols in the project with filters.

```bash
ast browse [options]
```

**Options:**
- `--kind` — Filter by kind (function/class/method/variable/all)
- `--lang` — Filter by language (python/javascript/typescript/rust/go/all)
- `--limit`, `-n` — Max results (default: 50)
- `--format`, `-f` — Output format

**Examples:**
```bash
# Browse all functions
ast browse --kind function

# Browse Python classes only
ast browse --kind class --lang python

# JSON for tooling
ast browse --limit 100 --format json

# Markdown for documentation
ast browse --kind function --format markdown
```

**Use case:** Exploring unfamiliar codebases, generating documentation.

---

## Workflows

### Workflow 1: Safe Refactoring

```bash
# 1. Find all references
ast refs old_function_name

# 2. Check who calls it
ast callers old_function_name

# 3. Analyze impact
ast blast-radius src/module.py:42

# 4. Find truly dead code (if removing)
ast find-dead --entry-points "main.py,cli.py"

# 5. Rename (using ast_edit MCP tool or manually)
# ...

# 6. Verify no broken references
ast refs old_function_name  # Should return nothing
```

---

### Workflow 2: Understanding New Codebase

```bash
# 1. Get project overview
ast summary --format markdown

# 2. Browse key symbols
ast browse --kind class --limit 20

# 3. Search for specific concepts
ast search "authentication"
ast search "database connection"

# 4. Understand dependencies
ast deps src/main.py

# 5. Trace call chains
ast callers main_function
ast callees main_function --file-path src/main.py
```

---

### Workflow 3: Dead Code Cleanup

```bash
# 1. Find dead code
ast find-dead --format json > dead-code.json

# 2. Filter to high-confidence only
jq '.dead_functions[] | select(.confidence == "high")' dead-code.json

# 3. Verify truly unused (check callers)
ast callers unused_function

# 4. Check if exported
ast refs unused_function | grep "__all__"

# 5. Remove (if safe)
# ... manual edit or use ast_edit ...

# 6. Re-run tests to verify nothing broke
pytest tests/
```

---

### Workflow 4: Pre-Commit Verification

```bash
# Before committing changes:

# 1. Impact analysis on changed files
ast blast-radius src/changed_file.py

# 2. Check for introduced dead code
ast find-dead --entry-points "main.py"

# 3. Verify public API changes
ast refs changed_public_function

# 4. Summary of changes
git diff --stat
ast summary --format concise
```

---

## Scripting Examples

### Bash Script: Dead Code Report

```bash
#!/bin/bash
# Generate dead code report

PROJECT_ROOT="${1:-.}"
OUTPUT_FILE="${2:-dead-code-report.md}"

echo "# Dead Code Report" > $OUTPUT_FILE
echo "Generated: $(date)" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

# Get summary
ast -p "$PROJECT_ROOT" find-dead --format json | \
  jq -r '"## Summary\n- Functions: \(.summary.total_dead_functions)\n- Classes: \(.summary.total_dead_classes)"' >> $OUTPUT_FILE

echo "" >> $OUTPUT_FILE
echo "## High Confidence Functions" >> $OUTPUT_FILE
ast -p "$PROJECT_ROOT" find-dead --format json | \
  jq -r '.dead_functions[] | select(.confidence == "high") | "- \(.name) (`\(.file)`)"' >> $OUTPUT_FILE

echo "Report saved to $OUTPUT_FILE"
```

### Python Script: CI Integration

```python
#!/usr/bin/env python3
"""CI check: Fail if high-confidence dead code exists."""

import json
import subprocess
import sys

result = subprocess.run(
    ["ast", "find-dead", "--format", "json"],
    capture_output=True,
    text=True,
)

data = json.loads(result.stdout)
high_conf_dead = [
    f for f in data["dead_functions"]
    if f["confidence"] == "high"
]

if high_conf_dead:
    print(f"❌ Found {len(high_conf_dead)} high-confidence dead functions:")
    for func in high_conf_dead[:10]:
        print(f"  - {func['name']} ({func['file']})")
    sys.exit(1)
else:
    print("✅ No high-confidence dead code found")
    sys.exit(0)
```

---

## Troubleshooting

### "No results found" from `ast search`

**Cause:** Semantic database not indexed.

**Fix:**
```bash
cd ~/Workspaces/ast-tools
source .venv/bin/activate
hermes mcp call ast-tools refresh_index '{"project_path": ".", "force": true}'
```

### "File not found" errors

**Cause:** Running from wrong directory.

**Fix:**
```bash
# Use --project-root to specify project location
ast -p /path/to/project summary
```

### Slow performance on large projects

**Cause:** Searching too many files.

**Fix:**
```bash
# Limit search scope
ast callers my_function --max-files 50

# Use specific file paths
ast deps src/specific/file.py
```

### JSON parsing errors

**Cause:** Output includes non-JSON text (errors, warnings).

**Fix:**
```bash
# Check stderr separately
ast find-dead --format json 2>stderr.log
cat stderr.log  # Check for errors

# Use jq safely
ast find-dead --format json 2>/dev/null | jq '.dead_functions'
```

---

## Performance Benchmarks

| Command | Project Size | Time | Memory |
|---------|-------------|------|--------|
| `ast summary` | 100 files | ~0.5s | ~20MB |
| `ast browse` | 100 files | ~1s | ~30MB |
| `ast find-dead` | 100 files | ~2s | ~50MB |
| `ast callers` | 100 files | ~1s | ~30MB |
| `ast search` | 100 files | ~0.5s* | ~40MB |

*Requires indexed database. First call after index: ~2-3s.

---

## Advanced: Direct Database Queries

For power users, you can query the semantic database directly:

```python
from ast_tools.database.connection import get_connection
from ast_tools.database.queries import search_symbols, find_symbol_definition

# Connect to database
conn = get_connection("/path/to/project/.ast-tools/cache.db")

# Search symbols
symbols = search_symbols(conn, query="auth", kind="class", limit=10)

# Find definition
symbol = find_symbol_definition(conn, "AuthService")
```

**Note:** This bypasses the CLI and MCP layer — use for custom tooling.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (no results, invalid args) |
| `2` | CLI usage error (missing required arg) |

---

## See Also

- **MCP Tools**: [`docs/AST_TOOLS_QUICKSTART.md`](AST_TOOLS_QUICKSTART.md)
- **Enhanced Dead Code**: [`docs/ENHANCED_DEAD_CODE.md`](ENHANCED_DEAD_CODE.md)
- **Usage Rules**: [`docs/USAGE_RULES.md`](USAGE_RULES.md)
- **Skill Documentation**: `~/.hermes/skills/software-development/ast-tools-usage/SKILL.md`

---

**Last updated:** 2026-07-31  
**Version:** v0.2.0 (77 tools, 943 tests)
**Maintained by:** Steven Page + Lucien (RapidWebs Lead Digital Architect)