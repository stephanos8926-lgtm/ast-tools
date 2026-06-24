# Phase 8B Specification: MCP Integration + Hermes Plugins

**Version:** 1.0  
**Date:** 2026-07-24  
**Status:** Specification Complete

---

## 1. Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES AGENT                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Plugins   │  │    Hooks    │  │     Skills          │  │
│  │ ast-tools-  │  │ pre_llm_call│  │ ast-tools-workflow  │  │
│  │ context     │  │ post_tool   │  │ mcp-tool-discovery  │  │
│  │ ast-tools-  │  │             │  │                     │  │
│  │ tokens      │  │             │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │             │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   AST-TOOLS MCP SERVER                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              semantic_search tool                   │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │ ContextInject│  │ Token Budget │                 │    │
│  │  │     ion      │  │  Enforcer    │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│          ┌───────────────┼───────────────┐                   │
│          ▼               ▼               ▼                   │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│   │  SQLite    │  │  sqlite-   │  │  FTS5      │            │
│   │  Symbols   │  │  vec       │  │  Index     │            │
│   └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. ContextInjector API Surface in semantic_search

### 2.1 Modified Tool Signature

```python
async def _tool_semantic_search(
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None,
    db_path: Optional[str] = None,
    inject_context: bool = True,           # NEW: Enable context injection
    token_budget: int = 4096,              # NEW: Token budget for context
    diversity_limit: int = 3,              # NEW: Max symbols per file
    session_id: Optional[str] = None,      # NEW: Session tracking
) -> dict:
```

### 2.2 Response Format (Enhanced)

```python
{
    "symbols": [...],                    # Original search results
    "injected_context": {                # NEW: Injected context
        "markdown": str,                 # Formatted markdown for LLM
        "token_count": int,              # Tokens used
        "symbols_injected": int,         # Number of symbols included
        "budget_remaining": int,         # Tokens left in budget
        "diversity_applied": bool        # Whether diversity was enforced
    },
    "context_pressure": {                # NEW: Context pressure info
        "level": "normal|warning|critical",
        "current_tokens": int,
        "threshold_percent": int,
        "recommendation": str
    }
}
```

### 2.3 Integration Flow

```
User Query → semantic_search
    │
    ▼
[If inject_context=True]
    │
    ▼
Generate query embedding
    │
    ▼
Vector search (k*2) + FTS5 search (k*2)
    │
    ▼
RRF Fusion → Top-k symbols
    │
    ▼
ContextInjector.select(symbols, token_budget, diversity_limit)
    │
    ├── Relevance scoring (6 factors)
    ├── Diversity enforcement (max 3/file)
    ├── Token budget check
    └── Markdown formatting
    │
    ▼
Return enhanced response with injected_context + context_pressure
```

---

## 3. Hermes Plugin Specifications

### 3.1 Plugin: ast_tools_context

**Purpose:** Automatically inject AST-Tools documentation into LLM context when code analysis queries are detected.

**Metadata:**
```yaml
name: ast_tools_context
version: 1.0.0
description: Auto-inject AST-Tools docs for code queries
author: AST-Tools Team
hooks: ["pre_llm_call"]
```

**Hook: pre_llm_call**
```python
async def pre_llm_call(session_id: str, user_message: str, 
                       conversation_history: list, is_first_turn: bool,
                       model: str, platform: str, **kwargs) -> dict:
    """
    Inject AST-Tools context when query matches code analysis patterns.
    
    Detection keywords: ast, tree-sitter, code search, refactor, 
    find references, impact analysis, structural analysis, 
    ast_grep, ast_edit, ast_read, semantic search
    """
    # 1. Check if query triggers injection
    if not _should_inject(user_message):
        return None
    
    # 2. Build context from plugin's documentation
    context = build_ast_tools_context()
    
    # 3. Return injection
    return {"context": context}
```

**Token Budget:** ~1000 tokens per injection  
**Frequency:** Once per session (cached after first injection)  
**Fallback:** If injection fails, log warning, continue without context

### 3.2 Plugin: ast_tools_tokens

**Purpose:** Track token usage for ast-tools operations and provide context pressure warnings.

**Metadata:**
```yaml
name: ast_tools_tokens
version: 1.0.0
description: Token budget tracking for ast-tools operations
author: AST-Tools Team
hooks: ["post_tool_call", "pre_llm_call"]
```

**Hook: post_tool_call**
```python
async def post_tool_call(tool_name: str, params: dict, result: str, **kwargs):
    """
    Track token usage after ast-tools tool execution.
    """
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    
    # Estimate tokens from result
    tokens = estimate_tokens(result)
    
    # Update session budget
    session_budget = get_session_budget()
    session_budget.consume(tokens)
    
    # Check pressure
    if session_budget.pressure_level() == "critical":
        logger.warning("Context pressure critical: %d/%d tokens", 
                      session_budget.used, session_budget.limit)
```

**Hook: pre_llm_call**
```python
async def pre_llm_call(..., **kwargs) -> dict:
    """
    Inject context pressure warning if budget exceeded.
    """
    budget = get_session_budget()
    if budget.pressure_level() in ("warning", "critical"):
        warning = build_pressure_warning(budget)
        return {"context": warning}
    return None
```

**Token Budgets by Model:**
```python
AST_TOOLS_TOKEN_BUDGETS = {
    "default": 4096,
    "gpt-4o": 8192,
    "claude-3-5-sonnet": 8192,
    "gemini-1.5-pro": 32768,
    "nemotron-3-ultra": 4096,
}
```

### 3.3 Plugin: ast_tools_policy (Future)

**Purpose:** Enforce usage policies for ast-tools operations.

**Planned Features:**
- Rate limiting per session
- Cost tracking for embedding generation
- Access control for sensitive operations (ast_edit)
- Audit logging for compliance

**Status:** Placeholder for Phase 10

---

## 4. Hook Integration Points

### 4.1 Hermes Hook Events Used

| Hook Event | Used By | Purpose |
|------------|---------|---------|
| `pre_llm_call` | ast_tools_context, ast_tools_tokens | Inject context/warnings before LLM call |
| `post_tool_call` | ast_tools_tokens | Track token usage after tool execution |
| `on_session_start` | (future) | Initialize session budgets |
| `on_session_end` | (future) | Persist session metrics |

### 4.2 Hook Configuration (Hermes config.yaml)

```yaml
hooks:
  - event: "pre_llm_call"
    match: ".*"  # All LLM calls
    command: "~/.hermes/plugins/ast_tools_context/__init__.py"
  - event: "post_tool_call"
    match: "mcp_ast_tools_*"  # Only ast-tools tools
    command: "~/.hermes/plugins/ast_tools_tokens/__init__.py"
```

### 4.3 Plugin Registration

```python
# In ~/.hermes/plugins/ast_tools_context/__init__.py
def register(ctx):
    """Register plugin hooks with Hermes."""
    ctx.hooks.register("pre_llm_call", pre_llm_call_handler)
    logger.info("ast_tools_context plugin registered")

# In ~/.hermes/plugins/ast_tools_tokens/__init__.py
def register(ctx):
    """Register plugin hooks with Hermes."""
    ctx.hooks.register("post_tool_call", post_tool_call_handler)
    ctx.hooks.register("pre_llm_call", pre_llm_call_handler)
    logger.info("ast_tools_tokens plugin registered")
```

---

## 5. Token Budget Enforcement

### 5.1 Budget Allocation Strategy

```
Total Model Context Window
├── System Prompt & Instructions    (~500 tokens)
├── Conversation History            (variable)
├── Injected Context (ast-tools)    (~1000 tokens, capped)
├── Tool Results                    (variable)
└── Available for Response          (remaining)
```

### 5.2 Budget Tiers by Model

| Model | Context Window | AST-Tools Budget | Pressure Thresholds |
|-------|----------------|------------------|---------------------|
| Default | 4,096 | 1,024 (25%) | Warn: 50%, Critical: 80% |
| GPT-4o / Claude-3.5 | 8,192 | 2,048 (25%) | Warn: 50%, Critical: 80% |
| Gemini-1.5-Pro | 32,768 | 8,192 (25%) | Warn: 50%, Critical: 80% |

### 5.3 Enforcement Algorithm

```python
class TokenBudgetEnforcer:
    def __init__(self, model: str):
        self.limit = AST_TOOLS_TOKEN_BUDGETS.get(model, 4096)
        self.used = 0
        self.injected = 0
    
    def can_inject(self, estimated_tokens: int) -> bool:
        """Check if injection fits within budget."""
        return (self.used + self.injected + estimated_tokens) <= self.limit
    
    def reserve_injection(self, tokens: int):
        """Reserve tokens for context injection."""
        self.injected += tokens
    
    def consume_tool_result(self, tokens: int):
        """Consume tokens from tool result."""
        self.used += tokens
    
    def pressure_level(self) -> str:
        """Return pressure level: normal, warning, critical."""
        ratio = (self.used + self.injected) / self.limit
        if ratio >= 0.8:
            return "critical"
        elif ratio >= 0.5:
            return "warning"
        return "normal"
    
    def get_recommendation(self) -> str:
        level = self.pressure_level()
        if level == "critical":
            return "Use /compress or start new session"
        elif level == "warning":
            return "Consider focusing queries or using /compress"
        return "Budget healthy"
```

### 5.4 Integration in semantic_search

```python
# In semantic_search.py
async def _tool_semantic_search(..., token_budget: int = 4096, ...):
    enforcer = TokenBudgetEnforcer(model)  # Get from context
    
    # Get search results
    symbols = await hybrid_search(...)
    
    # Inject context if budget allows
    injected_context = None
    if inject_context and enforcer.can_inject(estimated_context_tokens):
        injected_context = ContextInjector().format_context(
            symbols, 
            budget=token_budget - enforcer.used,
            diversity_limit=diversity_limit
        )
        enforcer.reserve_injection(injected_context["token_count"])
    
    return {
        "symbols": symbols,
        "injected_context": injected_context,
        "context_pressure": {
            "level": enforcer.pressure_level(),
            "current_tokens": enforcer.used + enforcer.injected,
            "threshold_percent": 50,
            "recommendation": enforcer.get_recommendation()
        }
    }
 ```

---

## 6. Fallback Behavior

### 6.1 Graceful Degradation Strategy

| Failure Scenario | Fallback Behavior | User Impact |
|------------------|-------------------|-------------|
| Embedding generation fails | Use FTS5-only search | Reduced semantic relevance |
| sqlite-vec unavailable | Fallback to FTS5 + BM25 | No vector search |
| Context injection exceeds budget | Skip injection, return symbols only | No auto-context |
| Plugin hook fails | Log error, continue without plugin | Silent degradation |
| Token estimation error | Use conservative estimate (len/4) | Slightly inaccurate budgets |

### 6.2 Implementation Patterns

```python
# Embedding fallback
try:
    query_emb = generate_embedding(query)
    vec_results = search_similar(conn, query_emb, k=k*2)
except Exception as e:
    logger.warning(f"Vector search failed, using FTS5 only: {e}")
    vec_results = []

# Plugin hook fallback
try:
    context = await plugin_hook_pre_llm_call(...)
except Exception as e:
    logger.error(f"Plugin hook failed: {e}")
    context = None  # Continue without injection

# Budget enforcement fallback
if not enforcer.can_inject(estimated):
    # Instead of failing, reduce injection scope
    injected_context = ContextInjector().format_context(
        symbols[:max_symbols], budget=reduced_budget
    )
```

### 6.3 Health Checks

```python
async def health_check() -> dict:
    """Verify all integration components are operational."""
    checks = {
        "sqlite_connection": check_sqlite(),
        "sqlite_vec": check_sqlite_vec(),
        "fts5_index": check_fts5(),
        "embedding_model": check_embedding_model(),
        "plugin_hooks": check_plugin_registration(),
    }
    return {
        "healthy": all(checks.values()),
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
 ```

---

## 7. Security Considerations

### 7.1 Threat Model

| Asset | Threat | Mitigation |
|-------|--------|------------|
| Source code | Exfiltration via context injection | Read-only access, no network egress |
| API keys | Leakage in tool results | Redaction in token tracker, no logging |
| File system | Arbitrary read via ast_grep | Path validation, workspace jail |
| Code execution | Injection via ast_edit | libcst validation, dry-run default |

### 7.2 Security Controls

**Input Validation:**
```python
# All tool inputs validated before processing
def validate_search_params(query: str, path: str) -> bool:
    # Path must be within workspace
    if not is_within_workspace(path):
        raise SecurityError("Path outside workspace")
    # Query length limited
    if len(query) > 1000:
        raise ValidationError("Query too long")
    return True
```

**Context Injection Safety:**
- Injected context is read-only documentation
- No executable code in injected context
- Token limits prevent context stuffing attacks
- Session-scoped, not persisted across sessions

**Plugin Security:**
- Plugins run in Hermes sandbox
- No direct file system access from plugins
- Hook handlers timeout at 5 seconds
- No network calls from plugin hooks

**Data Handling:**
- Embeddings generated locally (no external API)
- SQLite database file permissions: 600
- No telemetry without explicit opt-in
- Session data purged on session end

### 7.3 Compliance Considerations

| Requirement | Status | Notes |
|-------------|--------|-------|
| GDPR | Compliant | No personal data processed |
| SOC2 | Partial | Audit logging in Phase 10 |
| HIPAA | Not evaluated | Would need BAA for healthcare |
| Source code IP | Protected | Local processing only |

---

## 8. Implementation Checklist

### Phase 8B Core (Week 1)
- [ ] Modify semantic_search.py to accept new parameters
- [ ] Integrate ContextInjector into search flow
- [ ] Add TokenBudgetEnforcer class
- [ ] Implement fallback logic for all failure modes
- [ ] Write integration tests

### Phase 8B Plugins (Week 1)
- [ ] Complete ast_tools_context plugin
- [ ] Complete ast_tools_tokens plugin
- [ ] Add hook registration
- [ ] Test with Hermes Agent

### Phase 8B Validation (Week 2)
- [ ] End-to-end testing with real queries
- [ ] Performance benchmarking
- [ ] Token budget accuracy verification
- [ ] Fallback behavior testing
- [ ] Security review

---

## 9. Success Criteria

| Metric | Target |
|--------|--------|
| Context injection accuracy | >90% relevant symbols |
| Token budget accuracy | ±10% of actual |
| Fallback success rate | 100% (no crashes) |
| Search latency overhead | <50ms for injection |
| Plugin load time | <100ms |
| Memory overhead | <50MB |

---

## 10. References

- Phase 8A Spec: `docs/phase8-context-injection-spec.md`
- Phase 8A Forward Audit: `docs/phase8-forward-audit.md`
- Phase 8A Reverse Audits: `docs/phase8-reverse-audit-1.md`, `docs/phase8-reverse-audit-2.md`
- Phase 8A Synthesis: `docs/phase8-synthesis-plan.md`
- Phase 9 Spec: `docs/phase9-spec.md`
- Market Analysis: `docs/MARKET_ANALYSIS.md`
- Distribution Package: `DISTRIBUTION_PACKAGE.md`