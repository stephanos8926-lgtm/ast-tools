# AST-Tools Plugin Implementation Plan

**Created:** 2026-07-26  
**Status:** Ready to execute  
**Total Effort:** ~2 hours (P0 + P1)  
**Priority:** P0 (do before launch)

---

## Executive Summary

**Goal:** Enhance ast-tools Hermes plugins to improve AI behavioral training and reduce misuse patterns.

**Three enhancements:**
1. **on_session_start hook** — Compact tool index (~200 tokens) at session start
2. **Tool error correction** — Behavioral corrections for ast-tools misuse
3. **Verification gate** — Cross-project quality gate (load verification-before-completion skill)

**Files to create/modify:**
- Modify: `hermes-plugins/ast-tools-context/__init__.py`
- Modify: `hermes-plugins/ast-tools-tokens/__init__.py`
- Modify: `hermes-plugins/ast-tools-context/plugin.yaml`
- Modify: `hermes-plugins/ast-tools-tokens/plugin.yaml`
- Create: `hermes-plugins/verification-gate/__init__.py`
- Create: `hermes-plugins/verification-gate/plugin.yaml`
- Create: `docs/TROUBLESHOOTING.md`
- Update: `docs/PHASE10A_SYNTHESIS.md`

**SOUL.md:** Already patched ✅

---

## Phase 1: Enhance ast-tools-context Plugin

**File:** `hermes-plugins/ast-tools-context/__init__.py`

### Step 1.1: Add on_session_start hook

**Add after line 14 (after pre_llm_call registration):**
```python
ctx.register_hook("on_session_start", inject_session_onboarding)
```

### Step 1.2: Implement inject_session_onboarding function

**Add at end of file (after build_ast_tools_context function):**
```python


def inject_session_onboarding(session_id: str, **kwargs) -> dict:
    """Inject compact ast-tools index at session start."""
    return {
        "context": """
## AST-Tools Quick Index (29 tools available)

**Core:** ast_grep (structural search), ast_read (API surface), ast_edit (surgical edits—dry_run FIRST!), semantic_search (inject_context=True)

**Analysis:** impact_analysis (before API changes), module_imports (before splits), structural_analysis (callers/callees), find_references (before renaming)

**Gotchas:** 
- ast_edit: Always dry_run=true before applying
- semantic_search: inject_context=True (default), token_budget=4096, diversity_limit=3
- refresh_index: incremental via SHA256 hashing, watcher auto-enabled

**Full reference:** Say "ast-tools help" or "show me ast_edit examples"

⚠️ **Verification-before-completion active:**
- Before claiming done → run pytest/ruff/make test, show output
- Before claiming tools exist → ls src/ + grep __init__.py
- Never trust docs over source code
"""
    }
```

### Step 1.3: Update plugin.yaml

**Edit:** `hermes-plugins/ast-tools-context/plugin.yaml`

**Change:**
```yaml
hooks:
  - on_session_start
  - pre_llm_call
```

---

## Phase 2: Enhance ast-tools-tokens Plugin

**File:** `hermes-plugins/ast-tools-tokens/__init__.py`

### Step 2.1: Add error correction hook

**Add after line 26 (after post_tool_call registration):**
```python
    ctx.register_hook("post_tool_call", correct_ast_tools_errors)
```

### Step 2.2: Add error pattern database

**Add at top of file (after imports, before AST_TOOLS_TOKEN_BUDGETS):**
```python

# Error pattern → correction mapping
AST_TOOLS_ERROR_CORRECTIONS = {
    "ast_edit": {
        "Invalid operation": """
**Correct usage:** ast_edit operations are specific:
- `rename_function`: {"function": "old_name", "new_name": "new_name"}
- `replace_node`: {"pattern": "old", "replacement": "new"}
- `insert_after`: {"anchor": "func", "code": "new code"}
- `add_parameter`: {"function": "foo", "param": "bar", "type": "str"}
See: docs/AST_EDIT_OPERATIONS.md for full list. Always dry_run=true first!
""",
        "dry_run": "⚠️ Always run dry_run=true FIRST to preview changes. Then re-run with dry_run=false.",
    },
    "semantic_search": {
        "k exceeds": "⚠️ k=50 is large. Use k=10 + diversity_limit=5 for broad results, or add lang='python' filter.",
        "no results": "Try broader query or remove kind/lang filters. FTS5 needs keyword matches for recall.",
    },
    "ast_grep": {
        "Invalid pattern": "Use $VAR for single node, $$$VAR for multiple nodes. Example: def $FUNC($$$ARGS)",
    },
    "impact_analysis": {
        "symbol not found": "Use find_references first to locate symbol, then impact_analysis on the file.",
    },
}
```

### Step 2.3: Add error correction function

**Add at end of file (after check_context_pressure function):**
```python


def correct_ast_tools_errors(tool_name: str, params: dict, result: str, **kwargs):
    """Inject behavioral corrections for ast-tools misuse."""
    if not tool_name.startswith("mcp_ast_tools_"):
        return  # Not our concern — skip non-ast-tools
    
    # Extract tool key
    tool_key = tool_name.replace("mcp_ast_tools_", "")
    
    # Check for error patterns
    if "error" in result.get("status", "").lower() or "Error:" in result:
        correction = _get_correction_for_error(tool_key, result)
        if correction:
            return {
                "context": f"\n⚠️ **AST-Tools Usage Correction:**\n{correction}\n"
            }
    
    return None


def _get_correction_for_error(tool_key: str, result: str) -> str | None:
    """Match error pattern to correction from database."""
    corrections = AST_TOOLS_ERROR_CORRECTIONS.get(tool_key, {})
    
    for pattern, correction in corrections.items():
        if pattern.lower() in result.lower():
            return correction
    
    # Generic fallback for unknown errors on known tools
    if tool_key in AST_TOOLS_ERROR_CORRECTIONS:
        return f"Check docs for {tool_key} usage. Common issues: wrong params, missing required fields."
    
    return None
```

### Step 2.4: Update plugin.yaml

**Edit:** `hermes-plugins/ast-tools-tokens/plugin.yaml`

**Change:**
```yaml
hooks:
  - post_tool_call
  - pre_llm_call
```

(Note: no change needed — already has post_tool_call, we're just using it differently)

---

## Phase 3: Create verification-gate Plugin

**Directory:** `hermes-plugins/verification-gate/`

### Step 3.1: Create __init__.py

**File:** `hermes-plugins/verification-gate/__init__.py`

```python
"""
Verification Gate Plugin for Hermes Agent

Injects verification-before-completion reminder at session start.
Cross-project quality gate — not ast-tools specific.
"""

from hermes_cli.plugins import PluginContext


def register(ctx: PluginContext):
    """Register verification gate hook."""
    ctx.register_hook("on_session_start", inject_verification_reminder)


def inject_verification_reminder(session_id: str, **kwargs) -> dict:
    """Inject verification-before-completion reminder."""
    return {
        "context": """
⚠️ **Verification-before-completion Skill Active**

**Before claiming ANY task done:**
1. **Identify verification** — What command/test proves this claim?
2. **Run it completely** — Full output, no grep-for-PASS shortcuts
3. **Check fake-done patterns** — stubs, hardcoded returns, TODOs, UI that doesn't respond
4. **Confirm honestly** — "✅ pytest → 42 passed" or "❌ 4 failed — fixing"

**Critical rules:**
- Never trust docs over source code
- Before claiming tools exist → ls src/ + grep __init__.py
- git log --oneline -- <file> is the ONLY source of truth
- Session compaction lies — verify in code first
"""
    }
```

### Step 3.2: Create plugin.yaml

**File:** `hermes-plugins/verification-gate/plugin.yaml`

```yaml
name: verification-gate
description: Injects verification-before-completion reminder at session start
version: 1.0.0
author: RapidWebs (Lucien)
license: MIT
tags:
  - verification
  - quality-gate
  - completion
  - cross-project
hooks:
  - on_session_start
requirements: []
```

---

## Phase 4: Install & Test Plugins

### Step 4.1: Install plugins

```bash
cd ~/Workspaces/ast-tools/hermes-plugins
cp -r ast-tools-context ast-tools-tokens verification-gate ~/.hermes/plugins/
```

### Step 4.2: Restart Hermes gateway

```bash
# From workstation (not server)
systemctl --user restart hermes-gateway
# Or if that blocks: write script + execute
echo '#!/bin/bash
sleep 2
systemctl --user restart hermes-gateway' > /tmp/restart_gw.sh
chmod +x /tmp/restart_gw.sh
bash /tmp/restart_gw.sh
```

### Step 4.3: Test scenarios

**Test 1: Session start injection**
```bash
hermes
# Look for: "AST-Tools Quick Index" + "Verification-before-completion active"
```

**Test 2: ast_edit error correction**
```bash
# In Hermes session:
mcp_ast_tools_ast_edit file="test.py" operation="rename" ...
# Should see: "⚠️ AST-Tools Usage Correction: Correct usage: rename_function..."
```

**Test 3: semantic_search diversity warning**
```bash
# In Hermes session:
mcp_ast_tools_semantic_search query="auth" k=50
# Should see: "⚠️ k=50 is large. Use k=10 + diversity_limit=5..."
```

**Test 4: Verification reminder**
```bash
# In Hermes session, claim task "done" without tests
# Should see: "⚠️ Verification-before-completion Skill Active" reminder
```

---

## Phase 5: Documentation

### Step 5.1: Create TROUBLESHOOTING.md

**File:** `docs/TROUBLESHOOTING.md`

```markdown
# AST-Tools Troubleshooting Guide

## Common Issues

### "Parser not found for language X"

**Cause:** tree-sitter parser not installed for that language.

**Fix:**
```bash
npx tree-sitter init
npx tree-sitter add <language>
```

Or specify `lang="python"` explicitly for Python files.

### "No results from semantic_search"

**Causes:**
1. Index not built yet — run `refresh_index(project_path=".", embeddings=True)`
2. Query too abstract — FTS5 needs keyword matches
3. Embeddings not generated — reindex with `embeddings=True`

**Fix:**
```bash
# Reindex with embeddings
mcp_ast_tools_refresh_index project_path="." embeddings=True
# Try more concrete query
mcp_ast_tools_semantic_search query="websocket authentication handler" k=10
```

### "Invalid pattern syntax" in ast_grep

**Cause:** Pattern uses wrong metavariable syntax.

**Fix:**
- `$VAR` ← matches single node (identifier, expression, statement)
- `$$$VAR` ← matches multiple nodes (argument list, statement sequence)

Example:
```
# Match any function: def $FUNC($$$ARGS): $$$BODY
# Match 2-arg call: call($OBJ, $METHOD)
```

### ast_edit produces no changes

**Cause:** Pattern doesn't match, or dry_run=true (expected).

**Fix:**
1. Check dry_run output for "No matches found"
2. Simplify pattern — start broad, narrow down
3. Use ast_read to verify target code structure

### High token usage warnings

**Cause:** ast-tools results are large (ast_grep with many matches, structural_analysis on big files).

**Fix:**
- Add `limit=10` to search queries
- Use `inject_context=False` if injecting full context
- Say "/compress" to manually compress conversation

### Watcher daemon not starting

**Cause:** watch_add not called at server startup.

**Fix:** Add to server __main__.py:
```python
from ast_tools.tools.watcher import watch_add
watch_add(paths=["."])
```

### Fake-done patterns detected

**Symptoms:** Code "looks done" but tests fail.

**Checklist:**
- [ ] Stub implementations (`pass`, `return True`)
- [ ] Hardcoded mock returns
- [ ] TODOs/FIXMEs in core logic
- [ ] UI renders but doesn't respond
- [ ] Feature defined but not wired up

**Fix:** Run verification ritual before claiming done:
1. Identify verification (what proves this?)
2. Run it completely (full output)
3. Check fake-done patterns
4. Confirm honestly (show evidence)

## Getting Help

- Say "ast-tools help" for full reference
- Load skill: `skill_view("ast-tools-usage")`
- Check docs: `docs/AST_TOOLS_USAGE.md`
```

### Step 5.2: Update PHASE10A_SYNTHESIS.md

**File:** `docs/PHASE10A_SYNTHESIS.md`

**Find and replace:**
```markdown
## Tool Status

| Tool | Status | Notes |
|------|--------|-------|
| code_validate_syntax | Planned | ... |
| repo_skeleton | Planned | ... |
| file_related_suggest | Planned | ... |
```

**Change to:**
```markdown
## Tool Status (Updated 2026-07-26)

| Tool | Status | Notes |
|------|--------|-------|
| code_validate_syntax | ✅ **DONE** | 704 lines, 62 tests passing, registered line 91 in __init__.py |
| repo_skeleton | ❌ NOT STARTED | Phase 10A remaining work |
| file_related_suggest | ❌ NOT STARTED | Phase 10A remaining work |

**Correction note (2026-07-26):** Initial synthesis incorrectly listed code_validate_syntax as "planned" — it was already implemented and tested. This was caught by verification-before-completion skill. **Never trust docs over source.**
```

---

## Acceptance Criteria Checklist

### Phase 1 (ast-tools-context enhanced)
- [ ] __init__.py has on_session_start hook registered
- [ ] inject_session_onboarding function implemented
- [ ] plugin.yaml includes on_session_start hook
- [ ] New session shows compact tool index

### Phase 2 (ast-tools-tokens enhanced)
- [ ] __init__.py has error correction hook registered
- [ ] AST_TOOLS_ERROR_CORRECTIONS database defined
- [ ] correct_ast_tools_errors function implemented
- [ ] ast_edit error injects correction
- [ ] semantic_search k-too-large injects warning

### Phase 3 (verification-gate created)
- [ ] hermes-plugins/verification-gate/__init__.py exists
- [ ] hermes-plugins/verification-gate/plugin.yaml exists
- [ ] Plugin installed to ~/.hermes/plugins/
- [ ] New session shows verification reminder

### Phase 4 (testing)
- [ ] Test 1: Session start injection works
- [ ] Test 2: ast_edit error correction works
- [ ] Test 3: semantic_search warning works
- [ ] Test 4: Verification reminder appears
- [ ] No performance regression (< 1s overhead)

### Phase 5 (documentation)
- [ ] docs/TROUBLESHOOTING.md created (50+ lines)
- [ ] docs/PHASE10A_SYNTHESIS.md updated
- [ ] SOUL.md already patched ✅

---

## Rollback Plan

If plugins cause issues:

```bash
# Uninstall plugins
rm -rf ~/.hermes/plugins/ast-tools-context
rm -rf ~/.hermes/plugins/ast-tools-tokens
rm -rf ~/.hermes/plugins/verification-gate

# Restart gateway
systemctl --user restart hermes-gateway

# Restore originals from backup (if needed)
cd ~/Workspaces/ast-tools
git checkout hermes-plugins/
```

---

## Next Steps After Implementation

1. **Run full test suite** → `pytest tests/ -q` → verify 304 tests still passing
2. **Ruff check** → `ruff check .` → fix any new errors
3. **Commit** → `git add -A && git commit -m "feat: enhance plugins with on_session_start + error correction"`
4. **Push** → `git push origin master`
5. **Update todo** → Mark tasks 19, 21, 22 as complete or update with new actions

---

## Questions or Blockers

If you hit issues:
- Check Hermes logs: `journalctl --user -u hermes-gateway -n 50`
- Verify plugin syntax: `python3 -m py_compile ~/.hermes/plugins/*/__.py`
- Check hook registration: `python3 -c "from hermes_cli.plugins import load_plugins; load_plugins(); print('OK')"`

Ready to execute?