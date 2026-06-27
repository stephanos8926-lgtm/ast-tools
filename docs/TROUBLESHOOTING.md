# AST-Tools Troubleshooting Guide

**Last updated:** 2026-07-26  
**Version:** v0.2.0 (29 tools)

---

## Quick Reference

| Problem | Most Likely Cause | First Thing to Try |
|---------|------------------|-------------------|
| "Parser not found" | tree-sitter parser missing | `npx tree-sitter add <language>` |
| "No results" from semantic_search | Index not built or query too abstract | `refresh_index(embeddings=True)` + concrete query |
| "Invalid pattern" in ast_grep | Wrong metavariable syntax | Use `$VAR` (single) or `$$$VAR` (multiple) |
| ast_edit produces no changes | Pattern mismatch or dry_run=true | Check dry_run output, simplify pattern |
| High token warnings | Results too large | Add `limit=10`, use `inject_context=False` |
| Watcher not starting | watch_add not called at startup | Add `watch_add(paths=["."])` to server main |
| "Fake-done" code | Stubs, TODOs, unwired features | Run verification ritual (see below) |

---

## Common Issues

### "Parser not found for language X"

**Symptom:**
```
Error: Parser not found for language 'typescript'
```

**Cause:** tree-sitter parser not installed for that language.

**Fix:**
```bash
# Install parser globally
npx tree-sitter init
npx tree-sitter add typescript

# Or specify language explicitly for Python
mcp_ast_tools_ast_grep pattern="def $FUNC($$$ARGS)" lang="python"
```

**Supported languages (pre-indexed):** Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, Ruby, Swift, Kotlin, Scala, PHP, R, SQL, Bash, JSON, YAML, HTML, CSS, Markdown

---

### "No results" from semantic_search

**Symptom:**
```json
{"results": [], "count": 0}
```

**Possible causes:**

1. **Index not built yet**
   ```bash
   mcp_ast_tools_refresh_index project_path="." embeddings=True
   ```

2. **Query too abstract** — FTS5 needs keyword matches
   ```bash
   # Bad: "authentication"
   # Good: "websocket authentication handler"
   mcp_ast_tools_semantic_search query="websocket authentication handler" k=10
   ```

3. **Embeddings not generated**
   ```bash
   mcp_ast_tools_refresh_index project_path="." embeddings=True
   ```

4. **Wrong language filter**
   ```bash
   # If no Python files match, try without filter
   mcp_ast_tools_semantic_search query="auth" k=10  # Remove lang="python"
   ```

**Debugging steps:**
```bash
# Check index status
mcp_ast_tools_index_status

# Try FTS5-only search (no embeddings)
mcp_ast_tools_search_symbols query="websocket" k=10

# Verify file is indexed
mcp_ast_tools_list_symbols file="src/auth/websocket.py"
```

---

### "Invalid pattern syntax" in ast_grep

**Symptom:**
```
Error: Invalid pattern syntax: def $FUNC($ARGS)
```

**Cause:** Pattern uses wrong metavariable syntax.

**Syntax rules:**
- `$VAR` ← matches **single** node (identifier, expression, statement)
- `$$$VAR` ← matches **multiple** nodes (argument list, statement sequence)

**Examples:**
```
# ✅ Match any function definition
def $FUNC($$$ARGS): $$$BODY

# ✅ Match method call with 2 arguments
call($OBJ, $METHOD)

# ✅ Match if statement
if $COND: $$$THEN

# ❌ Wrong: $ARGS should be $$$ARGS (multiple args)
def $FUNC($ARGS): pass
```

**Fix:**
```bash
# Correct pattern
mcp_ast_tools_ast_grep pattern='def $FUNC($$$ARGS): $$$BODY' lang="python"
```

---

### ast_edit produces no changes

**Symptom:**
```json
{"status": "success", "changes": [], "file": "src/foo.py"}
```

**Possible causes:**

1. **dry_run=true** (expected — preview mode)
   ```bash
   # First run: preview
   mcp_ast_tools_ast_edit file="src/foo.py" operation="rename_function" ... dry_run=true
   # Second run: apply
   mcp_ast_tools_ast_edit file="src/foo.py" operation="rename_function" ... dry_run=false
   ```

2. **Pattern doesn't match**
   ```bash
   # Read file structure first
   mcp_ast_tools_ast_read file="src/foo.py"
   # Simplify pattern
   mcp_ast_tools_ast_grep pattern="def $FUNC(...)" path="src/foo.py"
   ```

3. **Wrong operation format**
   ```bash
   # ✅ Correct: rename_function
   {"operation": "rename_function", "params": {"function": "old_name", "new_name": "new_name"}}
   
   # ❌ Wrong: generic "rename"
   {"operation": "rename", ...}
   ```

**Available operations:**
- `replace_node` — Replace AST node matching pattern
- `insert_after` — Insert code after anchor
- `insert_before` — Insert code before anchor
- `remove_node` — Remove AST node
- `rename_function` — Rename function (all references)
- `add_parameter` — Add parameter to function
- `change_signature` — Modify function signature

See `docs/AST_EDIT_OPERATIONS.md` for full reference.

---

### High token usage warnings

**Symptom:**
```
⚠️ Context Pressure Alert
Current usage: ~45,000 tokens (85% of window)
Compression will fire soon if usage continues
```

**Cause:** ast-tools results are large (ast_grep with many matches, structural_analysis on big files).

**Fixes:**

1. **Add `limit` parameter to search queries**
   ```bash
   mcp_ast_tools_ast_grep pattern="def $FUNC(...)" path="src/" limit=10
   mcp_ast_tools_semantic_search query="auth" k=10 diversity_limit=3
   ```

2. **Use `inject_context=False`** (if injecting full context)
   ```bash
   mcp_ast_tools_semantic_search query="auth" inject_context=False
   ```

3. **Manually compress conversation**
   ```
   /compress focus: "authentication implementation"
   ```

4. **Use focused queries**
   ```bash
   # Bad: broad
   mcp_ast_tools_semantic_search query="code" k=50
   
   # Good: specific
   mcp_ast_tools_semantic_search query="websocket authentication handler" k=10 lang="python"
   ```

---

### Watcher daemon not starting

**Symptom:**
- File changes don't trigger reindex
- `watch_status` shows "not running"

**Cause:** `watch_add` not called at server startup.

**Fix:** Add to server `__main__.py`:
```python
from ast_tools.tools.watcher import watch_add

# In main() or startup sequence:
watch_add(paths=["."])
logger.info("File watcher started for %s", ".")
```

**Verify:**
```bash
mcp_ast_tools_watch_status
# Expected: {"status": "running", "paths": ["."], "debounce_ms": 100}
```

---

### Fake-done patterns detected

**Symptoms:** Code "looks done" but tests fail or features don't work.

**Common fake-done patterns:**

1. **Stub implementations**
   ```python
   def authenticate(user, password):
       pass  # ❌ Stub
   ```

2. **Hardcoded mock returns**
   ```python
   def get_user(user_id):
       return {"id": 1, "name": "Test"}  # ❌ Always returns same value
   ```

3. **TODOs/FIXMEs in core logic**
   ```python
   def validate_token(token):
       # TODO: implement actual validation
       return True  # ❌ Always passes
   ```

4. **UI renders but doesn't respond**
   - Widget present in JSX/Textual
   - No event handler wired up
   - Click does nothing

5. **Feature defined but not wired up**
   - Function exists
   - Not called from entry point (CLI, API route, WebSocket handler)

**Verification ritual (from verification-before-completion skill):**

Before claiming ANY task done:

1. **Identify verification** — What command/test proves this claim?
   - New function? → Write test that calls it
   - API endpoint? → `curl http://localhost:8000/endpoint`
   - UI feature? → Interact with it, verify response

2. **Run it completely** — Full output, no grep-for-PASS shortcuts
   ```bash
   # Bad: grep for PASS
   pytest tests/ | grep PASS
   
   # Good: full output
   pytest tests/test_auth.py -v
   ```

3. **Check fake-done patterns** — Scan for stubs, TODOs, hardcoded returns

4. **Confirm honestly**
   ```
   ✅ Verification passed: pytest → 42 passed, 0 failed
   # OR
   ❌ Failed: 38 passed, 4 failed — fixing before claiming done
   ```

**Critical rules:**
- **Never trust docs over source code** — PHASE10A_SYNTHESIS.md claimed "planned", but code_validate.py (704 lines, 62 tests) already existed
- **Before claiming tools exist** → `ls src/` + grep `__init__.py`
- **git log --oneline -- <file> is the ONLY source of truth** — session compaction lies

---

## Getting Help

### Built-in references

- Say **"ast-tools help"** for full tool reference
- Load skill: `skill_view("ast-tools-usage")`
- Check docs: `docs/AST_TOOLS_USAGE.md`

### Code inspection

```bash
# Read tool source
mcp_ast_tools_ast_read file="src/ast_tools/tools/semantic_search.py"

# Find tool registration
grep -n "register_tool" src/ast_tools/tools/__init__.py

# Check test coverage
pytest tests/test_semantic_search.py --cov --cov-report=term-missing
```

### Plugin debugging

```bash
# Check plugin syntax
python3 -m py_compile ~/.hermes/plugins/ast-tools-context/__init__.py

# List loaded plugins (in Hermes Python)
from hermes_cli.plugins import get_all_plugins
print([p.name for p in get_all_plugins()])

# Check Hermes logs
journalctl --user -u hermes-gateway -n 50
```

---

## Rollback Procedures

### If ast-tools breaks after update

```bash
# Rollback to last known good commit
cd ~/Workspaces/ast-tools
git log --oneline -10
git checkout <commit-sha>

# Or: uninstall plugins
rm -rf ~/.hermes/plugins/ast-tools-context
rm -rf ~/.hermes/plugins/ast-tools-tokens

# Restart Hermes session
exit  # or close terminal
hermes  # new session loads without plugins
```

### If server won't start

```bash
# Check Python syntax
find src/ -name "*.py" -exec python3 -m py_compile {} \;

# Check imports
python3 -c "import ast_tools; print('OK')"

# Run unit tests
cd ~/Workspaces/ast-tools
uv run pytest tests/ -q
```

---

## Known Limitations

1. **TypeScript validation** requires `tsc` installed globally
2. **Rust validation** requires Rust toolchain (`rustc`)
3. **Go validation** requires Go installed + `go.mod` in project
4. **Large files** (>500K chars) may timeout — use `limit` params
5. **Cross-file imports** — import analysis requires full project index
6. **Embeddings** — `bge-small-en-v1.5` is CPU-only (no GPU acceleration)

---

## Performance Tuning

### Indexing speed

- **First index:** ~10K symbols/minute
- **Incremental:** ~1K files/second (SHA256 skip unchanged)

**Speed up:**
```bash
# Exclude large directories
mcp_ast_tools_refresh_index project_path="." exclude=["node_modules", ".git", "venv"]

# Skip embeddings for text-only search
mcp_ast_tools_refresh_index project_path="." embeddings=False
```

### Query performance

- **FTS5-only:** <10ms
- **Vector search:** <50ms
- **Hybrid fusion:** <100ms

**Optimize:**
```bash
# Add language filter
mcp_ast_tools_semantic_search query="auth" lang="python" k=10

# Reduce k
mcp_ast_tools_ast_grep pattern="def $FUNC(...)" limit=10

# Use diversity limit
mcp_ast_tools_semantic_search query="auth" diversity_limit=3
```

---

## Reporting Bugs

When reporting issues, include:

1. **Command run** (exact syntax)
2. **Full error output** (not summarized)
3. **File path** (if file-specific)
4. **Project structure** (for import/index issues)
5. **ast-tools version** (`git rev-parse HEAD`)
6. **Hermes version** (`hermes --version`)

Example:
```bash
# Version info
git -C ~/Workspaces/ast-tools rev-parse HEAD
hermes --version

# Error reproduction
mcp_ast_tools_semantic_search query="websocket" k=10
# (paste full output)
```

---

## Changelog

### v0.2.0 (2026-07-26)

- Added 29 tools (up from 11 in v0.1.0)
- Hermes plugins: ast-tools-context, ast-tools-tokens
- verification-gate plugin (cross-project quality gate)
- semantic_search with inject_context, token_budget, diversity_limit
- 6-factor RRF fusion (semantic + FTS5 + callgraph + metrics + recency + usage)
- 304 tests passing

### v0.1.0 (2026-06-01)

- Initial release: 11 core tools
- Phase 0-9 complete
- Basic semantic search + FTS5

---

**Need more help?** Load the `ast-tools-usage` skill or ask "show me ast_edit examples".