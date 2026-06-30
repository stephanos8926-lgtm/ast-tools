# AST-Tools Plugin Enhancement Specification

**Version:** 1.1.0 (enhancement spec)  
**Date:** 2026-07-26  
**Author:** Lucien (RapidWebs)  
**Status:** Spec approved, ready for implementation

---

## Overview

This document specifies enhancements to the ast-tools Hermes plugins to improve AI behavioral training, reduce misuse patterns, and provide better onboarding for new sessions.

**Current plugins:**
- `ast-tools-context` (171 lines) — static context injection on keyword detection
- `ast-tools-tokens` (111 lines) — token usage tracking + context pressure warnings

**Enhancements:**
1. `on_session_start` hook — compact tool index injection
2. Tool error correction — behavioral training for ast-tools misuse
3. Verification-before-completion integration — cross-project quality gate

---

## Enhancement 1: on_session_start Hook

### Problem

When a session starts, the AI has no immediate awareness of ast-tools capabilities. It must either:
- Wait for a relevant query to trigger `pre_llm_call` context injection
- Discover tools mid-task (inefficient, leads to reinvention)

### Solution

Add `on_session_start` hook to inject a **compact tool index** (~200 tokens) at session start.

**Design principles:**
- **Compact:** ~200 tokens, not 1500. Full docs on demand ("ast-tools help").
- **Actionable:** Mention key gotchas (dry_run first, impact_analysis before API changes)
- **Non-intrusive:** If session isn't about ast-tools, the 200 tokens are negligible overhead

### Specification

**File:** `hermes-plugins/ast-tools-context/__init__.py`

**Add:**
```python
def register(ctx: PluginContext):
    """Register ast-tools context injection hooks."""
    ctx.register_hook("pre_llm_call", inject_ast_tools_context)
    ctx.register_hook("on_session_start", inject_session_onboarding)


def inject_session_onboarding(session_id: str, **kwargs) -> dict | None:
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
"""
    }
```

**Plugin.yaml update:**
```yaml
hooks:
  - on_session_start
  - pre_llm_call
```

### Token Budget

- **Current:** 0 tokens at session start, ~1000 on first ast-tools query
- **Enhanced:** ~200 tokens at session start, ~1000 on detailed queries
- **Net impact:** +200 tokens baseline (negligible for 262K context window)

### Success Metrics

- AI uses ast_edit with dry_run=true on first attempt (currently: often forgets)
- AI runs impact_analysis before proposing API changes (currently: sometimes skips)
- Reduced "I didn't know ast-tools could do that" mid-task discoveries

---

## Enhancement 2: Tool Error Correction

### Problem

When ast-tools calls fail (wrong params, misuse patterns), the AI:
- Gets an error message from the tool
- Often retries with the SAME mistake
- Wastes 2-3 tool calls learning what the error message already said

**Example:**
```
❌ User: ast_edit(file="foo.py", operation="rename", old="bar", new="baz")
❌ Tool error: "Invalid operation 'rename'. Valid: replace_node, insert_after, rename_function..."
❌ User: ast_edit(file="foo.py", operation="rename", ...)  # Same mistake!
```

### Solution

Add `post_tool_call` hook that detects ast-tools errors and injects **behavioral corrections**.

**Design principles:**
- **Scoped:** Only for ast-tools errors (not all tools — performance + scope boundary)
- **Specific:** Not generic "something went wrong" — exact fix for the exact error
- **Actionable:** Shows correct usage pattern, not just "this is wrong"

### Specification

**File:** `hermes-plugins/ast-tools-tokens/__init__.py`

**Add:**
```python
def register(ctx: PluginContext):
    """Register ast-tools token management hooks."""
    ctx.register_hook("post_tool_call", track_ast_tools_usage)
    ctx.register_hook("pre_llm_call", check_context_pressure)
    ctx.register_hook("post_tool_call", correct_ast_tools_errors)  # NEW


# Error pattern database
AST_TOOLS_ERROR_CORRECTIONS = {
    "ast_edit": {
        "Invalid operation": """
**Correct usage:** ast_edit operations are specific:
- rename_function: {"function": "old_name", "new_name": "new_name"}
- replace_node: {"pattern": "old", "replacement": "new"}
- insert_after: {"anchor": "func", "code": "new code"}
- add_parameter: {"function": "foo", "param": "bar", "type": "str"}
See: docs/AST_EDIT_OPERATIONS.md for full list.
""",
        "dry_run": "⚠️ Always run dry_run=true FIRST to preview changes. Then re-run with dry_run=false.",
    },
    "semantic_search": {
        "k exceeds": "k=50 is large. Use k=10 + diversity_limit=5 for broad results, or add lang='python' filter.",
        "no results": "Try broader query or remove kind/lang filters. FTS5 needs keyword matches for recall.",
    },
    "impact_analysis": {
        "symbol not found": "Use find_references first to locate symbol, then impact_analysis on the file.",
    },
}


def correct_ast_tools_errors(tool_name: str, params: dict, result: str, **kwargs):
    """Inject behavioral corrections for ast-tools misuse."""
    if not tool_name.startswith("mcp_ast_tools_"):
        return  # Not our concern
    
    # Check for error patterns
    tool_key = tool_name.replace("mcp_ast_tools_", "")
    
    if "error" in result.get("status", "").lower() or "Error:" in result:
        correction = get_correction_for_error(tool_key, result)
        if correction:
            return {
                "context": f"\n⚠️ **AST-Tools Usage Correction:**\n{correction}\n"
            }
    
    return None


def get_correction_for_error(tool_key: str, result: str) -> str | None:
    """Match error pattern to correction."""
    for pattern, correction in AST_TOOLS_ERROR_CORRECTIONS.get(tool_key, {}).items():
        if pattern.lower() in result.lower():
            return correction
    
    # Generic fallback for unknown errors
    if tool_key in AST_TOOLS_ERROR_CORRECTIONS:
        return f"Check docs for {tool_key} usage. Common issues: wrong params, missing required fields."
    
    return None
```

### Error Patterns to Correct

| Tool | Error Pattern | Correction |
|------|--------------|------------|
| `ast_edit` | "Invalid operation" | List valid operations with examples |
| `ast_edit` | Missing `dry_run` | "Always dry_run=true first" |
| `semantic_search` | "k exceeds diversity_limit" | "Use k=10 + diversity_limit=5" |
| `semantic_search` | "No results" | "Try broader query or remove filters" |
| `impact_analysis` | "Symbol not found" | "Run find_references first" |
| `ast_grep` | "Invalid pattern syntax" | "Use $VAR for single node, $$$VAR for multiple" |
| `refresh_index` | "Parser not found" | "Specify lang='python' or check file extension" |

### Performance Impact

- **Negligible:** Only fires on ast-tools errors (rare)
- **Check cost:** ~1ms string matching in post_tool_call
- **Benefit:** Prevents 2-3 wasted tool calls per error

### Success Metrics

- AI corrects misuse on 2nd attempt (currently: 3-4 attempts)
- Reduced repeated error patterns across sessions
- Faster task completion for ast-tools-heavy workflows

---

## Enhancement 3: Verification-Before-Completion Integration

### Problem

The `verification-before-completion` skill exists but is not automatically enforced. The AI:
- Claims tasks "done" without running verification
- Trusts docs over source code
- Presents problems without verifying they exist

**Example (2026-07-26):** I claimed "Phase 10A tools not implemented" based on PHASE10A_SYNTHESIS.md — but code_validate.py (704 lines, 62 tests) was already registered in __init__.py.

### Solution

**Two-pronged approach:**

1. **Session-level injection:** Add verification reminder to `on_session_start` hook
2. **Soul file integration:** Already done (patched SOUL.md)

### Specification

**Add to `inject_session_onboarding()`:**
```python
# Append to the context injected at session start
context += """
⚠️ **Verification-before-completion active:**
- Before claiming done → run pytest/ruff/make test, show output
- Before claiming tools exist → ls src/ + grep __init__.py
- Never trust docs over source code
"""
```

**Already completed:** SOUL.md patched with verification-before-completion integration (see Reality Check Protocol section).

### Cross-Project Applicability

This enhancement is **NOT ast-tools-specific**. It's a cross-project quality gate.

**Implementation:** Add to a NEW plugin `verification-gate` OR inject via Hermes skill auto-loading.

**Recommended:** Create `hermes-plugins/verification-gate/` plugin:
```python
def register(ctx: PluginContext):
    ctx.register_hook("on_session_start", inject_verification_reminder)


def inject_verification_reminder(session_id: str, **kwargs) -> dict:
    return {
        "context": """
⚠️ **Verification-before-completion Skill Active**

**Before claiming ANY task done:**
1. Identify verification: What command proves this claim?
2. Run it completely: Full output, no shortcuts
3. Check fake-done patterns: stubs, hardcoded returns, TODOs
4. Confirm honestly: "✅ pytest → 42 passed" or "❌ 4 failed — fixing"

**Critical:** Never trust docs over source. Verify in code first.
"""
    }
```

### Performance Impact

- **Negligible:** One-time context injection at session start (~200 tokens)
- **Benefit:** Prevents "fake-done" claims, reduces rework

### Success Metrics

- 100% of completion claims include verification evidence
- Zero "I claimed it done but tests fail" incidents
- Reduced Steven corrections ("verify it first")

---

## Implementation Plan

### Phase 1: Enhance Existing Plugins (P0 — < 1 hour)

**Files:**
- `hermes-plugins/ast-tools-context/__init__.py`
- `hermes-plugins/ast-tools-tokens/__init__.py`
- `hermes-plugins/ast-tools-context/plugin.yaml`
- `hermes-plugins/ast-tools-tokens/plugin.yaml`

**Tasks:**
1. Add `on_session_start` hook to ast-tools-context
2. Add error correction logic to ast-tools-tokens
3. Update both plugin.yaml files
4. Test: Start new session, verify compact index appears
5. Test: Trigger ast_edit error, verify correction injected

### Phase 2: Create Verification-Gate Plugin (P0 — 30 min)

**Files:**
- `hermes-plugins/verification-gate/__init__.py` (NEW)
- `hermes-plugins/verification-gate/plugin.yaml` (NEW)

**Tasks:**
1. Create plugin directory structure
2. Implement `on_session_start` hook with verification reminder
3. Install plugin: `cp -r verification-gate ~/.hermes/plugins/`
4. Test: Start new session, verify reminder appears

### Phase 3: Documentation (P1 — 1 hour)

**Files:**
- `docs/TROUBLESHOOTING.md` (NEW)
- `docs/PHASE10A_SYNTHESIS.md` (UPDATE)
- `docs/PLUGIN_ENHANCEMENTS.md` (this spec → final docs)

**Tasks:**
1. Write TROUBLESHOOTING.md (common issues + fixes)
2. Update PHASE10A_SYNTHESIS.md (clarify code_validate done, 2 tools pending)
3. Convert this spec to final PLUGIN_ENHANCEMENTS.md

### Phase 4: Testing (P0 — 30 min)

**Test scenarios:**
1. Start fresh session → verify compact index + verification reminder
2. Run `ast_edit` with invalid operation → verify correction
3. Claim task "done" without tests → verify reminder fires
4. Run `semantic_search` with k=50 → verify diversity warning

---

## Gotchas & Risks

### Risk 1: Context Bloat

**Mitigation:** Keep session-start injection to ~200 tokens. Full docs on demand only.

### Risk 2: Annoyance Factor

**Mitigation:** If Steven says "this is too verbose," reduce or remove. Plugins can be uninstalled.

### Risk 3: Error Pattern Matching

**Mitigation:** Start with 5-7 common error patterns. Expand based on observed mistakes.

### Risk 4: Cross-Tool Contamination

**Mitigation:** Error correction explicitly checks `tool_name.startswith("mcp_ast_tools_")` — only fires for our tools.

---

## Acceptance Criteria

**Phase 1 (ast-tools plugins enhanced):**
- [ ] New session shows compact tool index (~200 tokens)
- [ ] ast_edit error injects "valid operations" correction
- [ ] semantic_search k-too-large injects diversity warning
- [ ] plugin.yaml files updated with new hooks

**Phase 2 (verification-gate plugin):**
- [ ] Plugin created and installed
- [ ] New session shows verification reminder
- [ ] Reminder includes 4-step ritual summary

**Phase 3 (documentation):**
- [ ] TROUBLESHOOTING.md exists (50+ lines, 10+ common issues)
- [ ] PHASE10A_SYNTHESIS.md updated (code_validate done, 2 tools pending)
- [ ] PLUGIN_ENHANCEMENTS.md final version written

**Phase 4 (testing):**
- [ ] All 4 test scenarios pass
- [ ] No performance regression (session start < 1s overhead)
- [ ] No false positives on error corrections

---

## Future Enhancements (P2 — Post-Launch)

1. **Dynamic context injection** — Call `semantic_search(query)` from plugin and inject actual project symbols (not static docs)
2. **Watcher auto-start** — Add `watch_add(path=".")` to server startup
3. **Session-aware injection** — Track what user is working on, boost related symbols
4. **Auto-context on tool errors** — Inject relevant docs when ANY tool fails (not just ast-tools)

**Not pursuing:**
- Inject corrections for non-ast-tools (out of scope, performance penalty)
- Blocking tool calls (Hermes has no `pre_tool_call` blocking hook)

---

## Appendix: Plugin Structure Reference

```
hermes-plugins/
├── ast-tools-context/
│   ├── __init__.py          # Main plugin code
│   └── plugin.yaml          # Metadata + hooks
├── ast-tools-tokens/
│   ├── __init__.py
│   └── plugin.yaml
└── verification-gate/       # NEW
    ├── __init__.py
    └── plugin.yaml
```

**Installation:**
```bash
cp -r hermes-plugins/* ~/.hermes/plugins/
hermes gateway restart  # Or: systemctl --user restart hermes-gateway
```

**Testing:**
```bash
# Start new session to trigger on_session_start
hermes

# Trigger ast_edit error
mcp_ast_tools_ast_edit(file="test.py", operation="invalid", ...)

# Verify correction appears in next turn
```