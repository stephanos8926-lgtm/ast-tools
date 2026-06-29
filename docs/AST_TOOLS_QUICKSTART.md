# AST-Tools Usage Guide

**Quick Reference for Structural Code Analysis**

---

## What is AST-Tools?

AST-Tools is an MCP server with **26 structural code analysis tools** that understand your code's syntax tree, not just text patterns. Think of it as "code intelligence" — it knows the difference between a function call and a variable named the same thing.

---

## When to Use AST-Tools

| Task | Tool |
|------|------|
| **"Find code by what it does"** | `semantic_search` (vector + keyword hybrid) |
| **"Find all functions matching a pattern"** | `ast_grep` (structural AST search) |
| **"What does this file contain?"** | `ast_read` (extract API surface) |
| **"Rename this function safely"** | `ast_edit` (surgical AST transformation) |
| **"What breaks if I change this?"** | `impact_analysis` (change risk assessment) |
| **"Where is this symbol defined?"** | `find_symbol_definition` |
| **"Who uses this function?"** | `find_references` |
| **"What does this module import?"** | `module_imports` (fan-in/fan-out) |

---

## Core Tools (Top 5)

### 1. `ast_grep` — Structural Pattern Search

Search code using AST patterns, not regex. Understands syntax, not just text.

```json
{
  "pattern": "def $FUNC($$$ARGS)",
  "lang": "python",
  "path": "src/",
  "limit": 10
}
```

**Common patterns:**
- `def $FUNC($$$ARGS)` — any function definition
- `class $NAME: $$$BODY` — any class
- `$OBJ.$METHOD($$$ARGS)` — method calls
- `async def $NAME` — async functions

**Returns:** File, line, column, matched code snippet

---

### 2. `ast_read` — Extract File Structure

Understand a file's API surface before editing.

```json
{
  "file": "src/auth/middleware.py",
  "include_private": false,
  "include_imports": true
}
```

**Returns:**
- All imports (with line numbers)
- All classes (with bases, methods)
- All functions (with signatures)
- All top-level variables

**Use case:** Always call this **before** editing a file you're unfamiliar with.

---

### 3. `ast_edit` — Surgical Code Modifications

Make precise AST-based edits that preserve formatting and comments.

```json
{
  "file": "src/utils.py",
  "operation": "rename_function",
  "params": {
    "old_name": "old_func",
    "new_name": "new_func"
  },
  "dry_run": true
}
```

**Operations:**
- `rename_function` / `rename_class`
- `add_parameter` (with default value)
- `change_signature`
- `replace_node` (swap entire AST node)
- `insert_after` / `insert_before`
- `remove_node`

**⚠️ CRITICAL:** Always use `dry_run: true` first to preview changes!

---

### 4. `impact_analysis` — Change Risk Assessment

Find all code affected by a change **before** you make it.

```json
{
  "file_path": "src/api/handlers.py",
  "line": 42
}
```

**Returns:**
- Direct dependents (files that import this)
- Transitive dependents (call chain)
- Risk level (low/medium/high/critical)
- Affected test files

**Use case:** Mandatory before changing **public APIs** or **shared utilities**.

---

### 5. `semantic_search` — Search by Meaning

Find code using natural language, not keywords.

```json
{
  "query": "authentication middleware handler",
  "k": 10,
  "inject_context": true,
  "token_budget": 4096
}
```

**Features:**
- Hybrid FTS5 (keyword) + vector (semantic) search
- Returns LLM-ready context with `inject_context: true`
- Respects `token_budget` for context window limits
- `diversity_limit` prevents over-representing one file

**Use case:** "Where's the websocket handler?" → finds `session_websocket()` even if you didn't know the name.

---

## Complete Workflow Examples

### Workflow 1: Safe Refactoring

**Goal:** Rename a function across the entire codebase

```json
// Step 1: Find all references
{
  "tool": "find_references",
  "args": {"symbol": "old_function_name"}
}

// Step 2: Assess impact
{
  "tool": "impact_analysis",
  "args": {"file_path": "src/utils.py", "line": 25}
}

// Step 3: Preview rename (DRY RUN)
{
  "tool": "ast_edit",
  "args": {
    "file": "src/utils.py",
    "operation": "rename_function",
    "params": {"old_name": "old_function_name", "new_name": "new_function_name"},
    "dry_run": true
  }
}

// Step 4: Apply rename (after reviewing dry run)
{
  "tool": "ast_edit",
  "args": {
    "file": "src/utils.py",
    "operation": "rename_function",
    "params": {"old_name": "old_function_name", "new_name": "new_function_name"},
    "dry_run": false
  }
}
```

---

### Workflow 2: Understanding Unknown Code

**Goal:** Figure out how authentication works in a new codebase

```json
// Step 1: Get project overview
{
  "tool": "codebase_summary"
}

// Step 2: Search for auth-related code
{
  "tool": "semantic_search",
  "args": {"query": "authentication middleware handler", "k": 10}
}

// Step 3: Extract structure of key file
{
  "tool": "ast_read",
  "args": {"file": "src/auth/middleware.py", "include_private": true}
}

// Step 4: Find who uses it
{
  "tool": "find_references",
  "args": {"symbol": "AuthMiddleware"}
}
```

---

### Workflow 3: Finding Structural Patterns

**Goal:** Find all async functions that take a `session` parameter

```json
{
  "tool": "ast_grep",
  "args": {
    "pattern": "async def $NAME($$$PRE, session, $$$POST)",
    "lang": "python",
    "path": "src/",
    "limit": 20
  }
}
```

**Returns:** All matches with file locations and code snippets.

---

## Language Support

| Language | tree-sitter | Notes |
|----------|-------------|-------|
| **Python** | ✅ Full | Best supported (ast_edit uses libcst) |
| **JavaScript** | ✅ Full | ES6+ supported |
| **TypeScript** | ✅ Full | Type annotations preserved |
| **Rust** | ✅ Full |  |
| **Go** | ✅ Full |  |
| **Java** | ✅ Full |  |
| **C/C++** | ✅ Full |  |
| **C#** | ✅ Full |  |
| **Ruby** | ✅ Pattern search only | ast_edit Python-only |
| **PHP** | ✅ Pattern search only | ast_edit Python-only |
| **Swift** | ✅ Pattern search only | ast_edit Python-only |
| **Kotlin** | ✅ Pattern search only | ast_edit Python-only |

**Note:** `ast_grep`, `semantic_search`, and analysis tools work for all languages. `ast_edit` (surgical modifications) is **Python-only** (uses libcst).

---

## Indexing

AST-Tools uses a **semantic database** (SQLite + sqlite-vec) to index your codebase.

### First-Time Setup

```json
{
  "tool": "refresh_index",
  "args": {"project_path": ".", "force": true, "embeddings": true}
}
```

This indexes:
- All Python files (symbols, signatures, docstrings)
- Generates embeddings for semantic search
- Builds call graph (who calls whom)

### Incremental Updates

```json
// Only reindex changed files (SHA256 content hashing)
{
  "tool": "refresh_index",
  "args": {"project_path": ".", "force": false}
}

// Check index status
{
  "tool": "index_status"
}
```

**Returns:** Symbol count, file count, embedding count, last updated.

---

## Tool Parameters Reference

### `ast_grep`

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pattern` | string | ✅ Yes | — | AST pattern (e.g., `def $FUNC`) |
| `lang` | string | ✅ Yes | — | Language (python, javascript, typescript, etc.) |
| `path` | string | No | `.` | Directory to search |
| `limit` | int | No | 50 | Max results |

### `ast_read`

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | string | ✅ Yes | — | File path |
| `include_private` | bool | No | `false` | Include `_` prefixed symbols |
| `include_imports` | bool | No | `true` | Include import statements |

### `ast_edit`

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | string | ✅ Yes | — | File to edit |
| `operation` | string | ✅ Yes | — | Operation type (see below) |
| `params` | object | ✅ Yes | — | Operation-specific params |
| `dry_run` | bool | No | `true` | Preview without applying |

**Operations:**
- `rename_function`: `{old_name, new_name}`
- `rename_class`: `{old_name, new_name}`
- `add_parameter`: `{function, param_name, default_value}`
- `replace_node`: `{target, replacement}`
- `insert_after`: `{target, content}`
- `insert_before`: `{target, content}`
- `remove_node`: `{target}`

### `impact_analysis`

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_path` | string | ✅ Yes | — | File to analyze |
| `line` | int | No | — | Specific line (optional) |
| `project_root` | string | No | `.` | Project root directory |

### `semantic_search`

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | ✅ Yes | — | Natural language query |
| `k` | int | No | 10 | Max results |
| `inject_context` | bool | No | `true` | Return LLM-ready markdown |
| `token_budget` | int | No | 4096 | Max tokens for context |
| `diversity_limit` | int | No | 3 | Max symbols per file |
| `lang` | string | No | `python` | Language filter |
| `kind` | string | No | `all` | Symbol kind filter |

---

## Common Mistakes to Avoid

### ❌ Don't: Use regex for code patterns
```bash
# BAD: grep can't distinguish function calls from variables
grep "process_payment" -r src/
```

### ✅ Do: Use structural search
```json
{
  "tool": "ast_grep",
  "args": {"pattern": "call($OBJ, process_payment)", "lang": "python"}
}
```

---

### ❌ Don't: Edit without understanding impact
```json
// BAD: Changing public API without checking who uses it
{
  "tool": "ast_edit",
  "args": {"file": "src/api.py", "operation": "rename_function", ...}
}
```

### ✅ Do: Analyze first, edit second
```json
// Step 1: Check impact
{
  "tool": "impact_analysis",
  "args": {"file_path": "src/api.py"}
}

// Step 2: Find references
{
  "tool": "find_references",
  "args": {"symbol": "old_function_name"}
}

// Step 3: Dry run
{
  "tool": "ast_edit",
  "args": {..., "dry_run": true}
}

// Step 4: Apply (after reviewing)
{
  "tool": "ast_edit",
  "args": {..., "dry_run": false}
}
```

---

### ❌ Don't: Skip dry_run on ast_edit
```json
// BAD: Applying changes without preview
{
  "tool": "ast_edit",
  "args": {"dry_run": false, ...}
}
```

### ✅ Do: Always preview first
```json
// Step 1: Preview
{
  "tool": "ast_edit",
  "args": {"dry_run": true, ...}
}

// Step 2: Review diff, then apply
{
  "tool": "ast_edit",
  "args": {"dry_run": false, ...}
}
```

---

## Verification Commands

Test that AST-Tools is working:

```bash
# Test structural search
hermes mcp call ast-tools ast_grep '{"pattern": "def $FUNC", "lang": "python", "limit": 1}'

# Test semantic search
hermes mcp call ast-tools semantic_search '{"query": "test", "k": 1}'

# Verify tool count (should be 26+)
python3 -c "from ast_tools.tools import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

---

## Troubleshooting

### "No results found" from semantic_search
**Cause:** Index is empty or stale.

**Fix:**
```json
{
  "tool": "refresh_index",
  "args": {"project_path": ".", "force": true, "embeddings": true}
}
```

### "ModuleNotFoundError: sentence_transformers"
**Cause:** Heavy dependencies not installed.

**Fix:**
```bash
cd ~/Workspaces/ast-tools
source .venv/bin/activate
uv pip install sentence-transformers
```

### ast_edit fails on syntax error
**Cause:** File has syntax errors, libcst can't parse.

**Fix:**
```json
{
  "tool": "code_validate_syntax",
  "args": {"language": "python", "file_path": "src/broken.py"}
}
```

Fix the syntax error first, then retry `ast_edit`.

---

## Advanced: ast_grep Pattern Syntax

AST-Tools uses **tree-sitter grep** for structural patterns.

### Variables

| Pattern | Matches |
|---------|---------|
| `$FUNC` | Single identifier (function name) |
| `$NAME` | Single identifier |
| `$$$ARGS` | Zero or more arguments (variadic) |
| `$$$BODY` | Statement block |
| `$_` | Anonymous (match anything, don't capture) |

### Examples

```astgrep
# Match any function definition
def $FUNC($$$ARGS):
    $$$BODY

# Match async functions with 'self' parameter
async def $NAME(self, $$$ARGS):
    $$$BODY

# Match method calls with exactly 2 arguments
call($OBJ, $METHOD, $ARG1, $ARG2)

# Match class inheritance
class $NAME($BASE):
    $$$BODY

# Match decorator usage
@$DECORATOR
def $FUNC():
    $$$BODY

# Match type annotations
def $FUNC($PARAM: $TYPE) -> $RETURN:
    $$$BODY
```

### Language-Specific Patterns

**Python:**
```astgrep
# Match context manager usage
with $EXPR as $VAR:
    $$$BODY

# Match list comprehension
[$EXPR for $VAR in $ITERABLE]
```

**TypeScript:**
```astgrep
# Match async function
async function $NAME($$$ARGS): Promise<$TYPE>

# Match React component
function $NAME(props: $PROPS) {
    return <$JSX />
}
```

---

## Next Steps

1. **Start small:** Try `ast_read` on a file you know well
2. **Search:** Use `semantic_search` to find code by description
3. **Analyze:** Run `impact_analysis` before your next refactor
4. **Edit:** Use `ast_edit` with `dry_run: true` for safe modifications

**Remember:** AST-Tools is your **code intelligence layer** — use it to understand before changing, and verify after.