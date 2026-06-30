# Specifications History

This document contains all historical specifications consolidated.

---

## phase8b-spec

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
---

## phase8-context-injection-spec

# Phase 8: Context Injection Hooks — Specification

## Overview

Automatic injection of relevant code context into LLM prompts based on what the agent is working on. Makes semantic search *actually useful* by providing the right symbols at the right time without manual effort.

## Interface Contracts

### 1. ContextInjector Class

```python
class ContextInjector:
    """Manages context injection for ast-tools MCP server."""
    
    def __init__(
        self,
        db_path: Path,
        model_context_window: int = 32000,  # Target model's context
        max_context_symbols: int = 10,      # Max symbols to inject
        diversity_limit: int = 3,           # Max symbols per file
        protect_last_n_messages: int = 2    # Never evict these
    )
    
    def inject_context(
        self,
        query: Optional[str] = None,
        current_file: Optional[str] = None,
        working_symbols: list[str] = None,  # Symbols user is actively working with
        existing_context_tokens: int = 0    # Tokens already used in conversation
    ) -> ContextInjectionResult
    
    def calculate_relevance_score(
        self,
        symbol: Symbol,
        query_embedding: Optional[np.ndarray] = None,
        current_file: Optional[str] = None,
        recency_weight: float = 0.15,
        usage_weight: float = 0.15,
        kind_weight: float = 0.10,
        proximity_weight: float = 0.10,
        callgraph_weight: float = 0.10,
        semantic_weight: float = 0.40
    ) -> float
```

### 2. ContextInjectionResult

```python
@dataclass
class ContextInjectionResult:
    injected_symbols: list[Symbol]
    injection_reasons: dict[str, str]  # symbol_id -> reason
    total_tokens: int
    budget_remaining: int
    eviction_warnings: list[str]  # If we had to cut symbols
    markdown_context: str  # Formatted for LLM consumption
```

### 3. MCP Tool Integration

Tools that trigger context injection:
- `semantic_search(query)` → Inject top-N relevant symbols
- `ast_read(file)` → Inject related symbols (callers, callees, same class)
- `structural_analysis(symbol)` → Inject dependency chain
- `find_references(symbol)` → Inject usage examples

### 4. Hermes Hook Integration

**pre_tool_call hook** (shell script):
- Reads current conversation context
- Calls context injector
- Appends `## Relevant Context` to tool input

**post_tool_call hook** (optional):
- Track which symbols were actually used
- Update usage frequency counts

## Relevance Scoring Formula

```
relevance_score = (
    semantic_similarity * 0.40 +    # Cosine distance (embedding)
    recency_score * 0.15 +          # Decay over 30 days
    usage_frequency * 0.15 +        # Log-scaled reference count
    kind_boost * 0.10 +             # class/function > variable
    file_proximity * 0.10 +         # Same file or imported
    callgraph_depth * 0.10          # Caller/callee relationship
)
```

**Individual Scores:**
- `semantic_similarity`: 0.0-1.0 (cosine)
- `recency_score`: exp(-days_since_indexed / 30)
- `usage_frequency`: log(1 + references_count) / log(1 + max_refs)
- `kind_boost`: 1.0 (class/function), 0.7 (method), 0.4 (variable)
- `file_proximity`: 1.0 (same file), 0.5 (imported file), 0.0 (unrelated)
- `callgraph_depth`: 1.0 (direct caller/callee), 0.5 (2 hops), 0.0 (unrelated)

## Token Budget Management

**Budget Tiers:**
- **8K models** (Gemma-2B, Phi-3): 5 symbols (~1.5K tokens)
- **32K models** (Gemma-7B, Mistral): 10 symbols (~3K tokens)
- **128K+ models** (Gemini, Claude): 20 symbols (~6K tokens)

**Token Estimation:**
```python
def estimate_tokens(symbol: Symbol) -> int:
    # Rough estimate:
    # - Signature: ~50 tokens
    # - Docstring: ~100 tokens
    # - Example usage: ~150 tokens
    # Total: ~300 tokens per symbol
    return 300
```

**Dynamic Adjustment:**
```python
available_budget = (
    model_context_window 
    - existing_context_tokens 
    - (protect_last_n_messages * 500)  # Reserve for conversation
)
max_symbols = min(
    max_context_symbols,
    available_budget // 300  # 300 tokens per symbol
)
```

## Staleness Prevention

**Decay Mechanisms:**
1. **Temporal Decay**: Score reduces by 10% per day after 7 days
2. **Repetition Decay**: If symbol injected 3+ times in session, reduce by 20%
3. **Diversity Forcing**: Max 3 symbols per file (enforced during selection)

**Tracking:**
```python
@dataclass
class InjectionHistory:
    session_id: str
    injected_symbol_ids: list[str]
    injection_counts: dict[str, int]  # symbol_id -> count
    last_injection_time: dict[str, datetime]
```

## Output Format

```markdown
## Context: Relevant Symbols (injected by ast-tools)

### `src/auth.py:42` — `AuthService` (class)
```python
class AuthService:
    """Handles user authentication and session management."""
    def login(self, username: str, password: str) -> Token: ...
    def logout(self, token: str) -> None: ...
```
**Relevance:** 0.87 (semantic: 0.92, recency: 0.8, usage: 0.9)
**Why included:** Top semantic match for "authentication", called by current file

### `src/routes.py:15` — `login_handler` (function)
```python
async def login_handler(request: Request) -> Response:
    """HTTP handler for login endpoint."""
    ...
```
**Relevance:** 0.74 (semantic: 0.65, proximity: 1.0, callgraph: 0.9)
**Why included:** Calls `AuthService.login`, in same file as working context

---
*Injected 2/10 symbols • 600/3000 tokens • 2 files represented*
Budget: 32K context window (Gemma-7B)
```

## Impact Analysis

**Files to Create:**
1. `src/ast_tools/context/__init__.py` — Package init
2. `src/ast_tools/context/injector.py` — ContextInjector class (~400 lines)
3. `src/ast_tools/context/history.py` — InjectionHistory tracking (~150 lines)
4. `src/ast_tools/context/formatters.py` — Markdown output formatting (~100 lines)
5. `src/ast_tools/tools/context_tools.py` — MCP tool wrappers (~100 lines)

**Files to Modify:**
1. `src/ast_tools/tools/semantic_search.py` — Add context injection to results
2. `src/ast_tools/tools/ast_read.py` — Inject related symbols
3. `src/ast_tools/tools/structural_analysis.py` — Inject dependency context
4. `src/ast_tools/tools/__init__.py` — Register new context tools
5. `~/.hermes/config.yaml` — Add pre_tool_call hook for context injection
6. `~/.hermes/scripts/context-injector-hook.sh` — Shell hook script

**Dependencies:**
- `numpy` — For embedding math (already in requirements)
- `sqlite-vec` — For vector similarity (in-progress)
- Conan Tokens — For accurate token counting

**Breaking Changes:** None. Context injection is additive.

## Configuration

**Project-level** (`.ast-tools/context.yaml`):
```yaml
enabled: true
model_context_window: 32000
max_symbols: 10
diversity_limit: 3
weights:
  semantic: 0.40
  recency: 0.15
  usage: 0.15
  kind: 0.10
  proximity: 0.10
  callgraph: 0.10
exclude_kinds: [variable, constant]  # Don't inject variables
```

**Hermes config** (`~/.hermes/config.yaml`):
```yaml
hooks:
  - event: pre_tool_call
    match: "semantic_search"
    command: "/home/sysop/.hermes/scripts/context-injector-hook.sh"
```

---

## Next Steps

1. **Forward Audit** — Validate feasibility, check for circular imports, verify sqlite-vec integration points
2. **Reverse Audit** — Identify missing edge cases, performance concerns, token counting accuracy
3. **Synthesis** — Combine into implementation plan
4. **Sign-off** — User approval
5. **TDD Implementation** — Red-green-refactor
6. **Adversarial Audit** — Security, edge cases, failure modes
---

## phase9-spec

# Phase 9 Specification: Schema Enrichments

**Version:** 1.0  
**Date:** 2026-07-24  
**Status:** Specification Complete  
**Mode:** HIGH (20+ files, public API, schema migration, performance-critical)

---

## 1. Executive Summary

Phase 9 extends the AST-Tools semantic database with **four major capabilities**:

1. **Callgraph Edges** — Track function calls, imports, inheritance, and implementation relationships
2. **Dependency Metrics** — Compute fan-in/fan-out, detect circular dependencies, identify SPOFs
3. **Embedding Similarity** — Precomputed cosine similarity matrix with KNN graph for "find similar code"
4. **Performance Optimization** — Index build targets (<60min for 1M files), query latency targets (p50 <50ms)

**Impact:** Transforms AST-Tools from structural search → **architectural understanding**. Users can now ask "what depends on this?", "show me similar implementations", "find circular dependencies".

---

## 2. Callgraph Edges

### 2.1 Edge Types

| Type | Description | Example |
|------|-------------|---------|
| `calls` | Function/method invocation | `foo()` → `foo` |
| `imports` | Module import relationship | `from foo import bar` → `bar` |
| `inherits` | Class inheritance | `class Child(Parent)` → `Parent` |
| `implements` | Protocol/interface implementation | `class MyMapper(Mapping)` → `Mapping` |

### 2.2 Database Schema

```sql
CREATE TABLE callgraph_edges (
    id INTEGER PRIMARY KEY,
    source_symbol_id INTEGER NOT NULL,
    target_symbol_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('calls', 'imports', 'inherits', 'implements')),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (target_symbol_id) REFERENCES symbols(id),
    UNIQUE(source_symbol_id, target_symbol_id, edge_type)
);

CREATE INDEX idx_callgraph_source ON callgraph_edges(source_symbol_id);
CREATE INDEX idx_callgraph_target ON callgraph_edges(target_symbol_id);
CREATE INDEX idx_callgraph_type ON callgraph_edges(edge_type);
```

### 2.3 Extraction Algorithm

**Calls:**
- AST traversal: `ast.Call` nodes
- Resolve name to symbol via scope analysis
- Handle chained calls: `obj.method()` → `method` on `obj`'s class
- Handle async calls: `await foo()` → same as sync

**Imports:**
- AST: `ast.Import`, `ast.ImportFrom`
- Resolve to imported symbols
- Track star imports: `from foo import *` → all symbols in `foo`
- Track relative imports: `from . import sibling`

**Inherits:**
- AST: `ast.ClassDef.bases`
- Resolve base class names to symbols
- Handle multiple inheritance: `class C(A, B)` → edges to both A and B

**Implements:**
- Detect protocol/interface classes (ABC, Protocol, TypedDict)
- Match method signatures (structural typing)
- Infer from type hints: `x: Mapping` → implements `Mapping`

### 2.4 New API Endpoints

```python
# New MCP tools
mcp_ast_tools_callgraph(symbol: str, edge_type: Optional[str] = None, direction: str = "out") -> dict
    # Returns adjacency list for symbol
    # direction: "out" (callees), "in" (callers), "both"

mcp_ast_tools_callgraph_callees(symbol: str) -> list[Symbol]
    # What does this symbol call?

mcp_ast_tools_callgraph_callers(symbol: str) -> list[Symbol]
    # What calls this symbol? (fan-in)

mcp_ast_tools_detect_cycles(start_symbol: Optional[str] = None, max_depth: int = 10) -> list[list[str]]
    # Find circular dependencies via DFS
    # Returns list of cycles (each cycle is list of symbol names)
```

---

## 3. Dependency Metrics

### 3.1 Metrics Definitions

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Fan-in** | Count of symbols that depend ON this symbol | High = widely used, critical |
| **Fan-out** | Count of symbols this symbol depends ON | High = many dependencies, fragile |
| **SPOF Score** | `fan_in / (fan_in + fan_out)` normalized to [0,1] | High = single point of failure |
| **Instability** | `fan_out / (fan_in + fan_out)` | High = unstable (changes propagate) |
| **Centrality** | PageRank over callgraph | High = architecturally central |

### 3.2 Database Schema

```sql
CREATE TABLE dependency_metrics (
    symbol_id INTEGER PRIMARY KEY,
    fan_in INTEGER DEFAULT 0,
    fan_out INTEGER DEFAULT 0,
    sPOF_score REAL DEFAULT 0.0,
    instability REAL DEFAULT 0.0,
    centrality REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE INDEX idx_dependency_spof ON dependency_metrics(sPOF_score DESC);
CREATE INDEX idx_dependency_instability ON dependency_metrics(instability DESC);
```

### 3.3 Computation Algorithm

**Fan-in/Fan-out:**
```python
# From callgraph_edges table
fan_in = SELECT COUNT(*) FROM callgraph_edges WHERE target_symbol_id = ?
fan_out = SELECT COUNT(*) FROM callgraph_edges WHERE source_symbol_id = ?
```

**SPOF Score:**
```python
spof_score = fan_in / (fan_in + fan_out) if (fan_in + fan_out) > 0 else 0.0
```

**Centrality (PageRank):**
```python
# Use networkx or custom implementation
# Damping factor: 0.85
# Max iterations: 100
# Convergence threshold: 1e-6
```

### 3.4 New API Endpoints

```python
mcp_ast_tools_dependencies(symbol: str, include_transitive: bool = False, max_depth: int = 3) -> dict
    # Returns fan-in, fan-out, and dependency tree
    # include_transitive: include indirect dependencies
    # max_depth: limit traversal depth

mcp_ast_tools_spof_analysis(project_root: Optional[str] = None, threshold: float = 0.8) -> list[Symbol]
    # Identify symbols with SPOF score > threshold
    # Returns sorted list (highest SPOF first)
```

---

## 4. Embedding Similarity

### 4.1 Embedding Model

**Model:** `BAAI/bge-small-en-v1.5`  
**Dimensions:** 384  
**Platform:** CPU-only (no CUDA required)  
**Library:** `sentence-transformers`  
**License:** MIT

**Why this model:**
- Small enough for CPU inference (~100ms per symbol)
- 384-dim vectors fit in memory (1M symbols × 384 × 4 bytes = 1.5GB)
- High quality for code semantics (trained on code + natural language)
- Compatible with sqlite-vec F32_BLOB storage

### 4.2 Database Schema

```sql
-- Embeddings stored in existing symbols table (Phase 8)
ALTER TABLE symbols ADD COLUMN embeddings BLOB;  -- F32_BLOB, 384 dimensions

-- Similarity cache (precomputed)
CREATE TABLE embedding_similarity (
    symbol_id_1 INTEGER NOT NULL,
    symbol_id_2 INTEGER NOT NULL,
    cosine_similarity REAL NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id_1, symbol_id_2),
    FOREIGN KEY (symbol_id_1) REFERENCES symbols(id),
    FOREIGN KEY (symbol_id_2) REFERENCES symbols(id)
);

-- KNN graph: top-k similar symbols for each symbol
CREATE TABLE knn_graph (
    symbol_id INTEGER NOT NULL,
    neighbor_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    similarity REAL NOT NULL,
    PRIMARY KEY (symbol_id, neighbor_id),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (neighbor_id) REFERENCES symbols(id)
);

CREATE INDEX idx_embedding_sim ON embedding_similarity(symbol_id_1, cosine_similarity DESC);
CREATE INDEX idx_knn_symbol ON knn_graph(symbol_id, rank);
```

### 4.3 Similarity Computation

**Cosine Similarity:**
```python
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**KNN Graph Construction:**
```python
# For each symbol, find top-k most similar
k = 10
for symbol_id in all_symbols:
    emb = get_embedding(symbol_id)
    similarities = [(other_id, cosine(emb, other_emb)) 
                    for other_id, other_emb in all_embeddings 
                    if other_id != symbol_id]
    top_k = sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
    save_to_knn_graph(symbol_id, top_k)
```

**Performance Optimization:**
- **Approximate Nearest Neighbors (ANN):** Use `faiss` or `hnswlib` for faster search
- **Batch computation:** Compute similarities in batches (10K symbols/batch)
- **Incremental updates:** Only recompute when symbols change

### 4.4 New API Endpoints

```python
mcp_ast_tools_similar(symbol: str, k: int = 10, min_similarity: float = 0.7) -> list[Symbol]
    # Find k most similar symbols with similarity >= threshold
    # Returns symbols with similarity scores

mcp_ast_tools_embeddings_compute(symbols: Optional[list[str]] = None, batch_size: int = 100) -> dict
    # Compute embeddings for all symbols (or specified subset)
    # Returns progress, errors, timing info

mcp_ast_tools_embeddings_batch(batch_id: str) -> dict
    # Check status of batch embedding computation
```

---

## 5. Performance Targets

### 5.1 Index Build Targets

| Metric | Target | Stretch |
|--------|--------|---------|
| Callgraph extraction (10K files) | <10 min | <5 min |
| Dependency metrics (10K symbols) | <2 min | <1 min |
| Embedding computation (10K symbols) | <20 min | <10 min |
| KNN graph (10K symbols) | <30 min | <15 min |
| **Total (1M files)** | **<60 min** | **<30 min** |

### 5.2 Query Latency Targets

| Query Type | p50 | p95 | p99 |
|------------|-----|-----|-----|
| Callgraph lookup (callees/callers) | <10ms | <50ms | <100ms |
| Dependency metrics | <5ms | <20ms | <50ms |
| Similarity search (k=10) | <50ms | <200ms | <500ms |
| Cycle detection (max_depth=10) | <100ms | <500ms | <1s |

### 5.3 Memory Targets

| Component | Peak Memory |
|-----------|-------------|
| Callgraph in memory | <100MB |
| Embeddings (1M symbols) | <1.5GB |
| KNN graph (1M symbols × 10 neighbors) | <100MB |
| **Total peak** | **<2GB** |

---

## 6. Migration Strategy

### 6.1 Migration 009

**File:** `src/ast_tools/db/migrations/009_schema_enrichments.py`

**Steps:**
1. Create `callgraph_edges` table
2. Create `dependency_metrics` table
3. Create `embedding_similarity` table
4. Create `knn_graph` table
5. Add `embeddings` column to `symbols` (if not exists from Phase 8)
6. Create indexes
7. Populate initial data (optional, can be done post-migration)

**Rollback:**
```sql
DROP TABLE IF EXISTS knn_graph;
DROP TABLE IF EXISTS embedding_similarity;
DROP TABLE IF EXISTS dependency_metrics;
DROP TABLE IF EXISTS callgraph_edges;
-- Note: Cannot drop embeddings column from symbols (SQLite limitation)
```

### 6.2 Backward Compatibility

**Guarantees:**
- Old queries continue to work (no breaking changes to existing tables)
- New tools are additive (no removal of existing tools)
- Migration is reversible (except embeddings column)

**Breaking Changes:**
- None (fully backward compatible)

---

## 7. Security Considerations

### 7.1 Threat Model

| Asset | Threat | Mitigation |
|-------|--------|------------|
| Source code | Exfiltration via callgraph | Read-only access, no network egress |
| Embeddings | Model poisoning | Use official pretrained models only |
| Dependency graph | Supply chain confusion | Clear provenance tracking |

### 7.2 Input Validation

- All symbol names validated against allowlist (alphanumeric + `_`)
- File paths restricted to workspace root
- Query parameters sanitized (SQL injection prevention via parameterized queries)
- Batch sizes limited (max 10K symbols/request)

---

## 8. Testing Strategy

### 8.1 Unit Tests

- Migration 009: Schema validation, FK constraints
- Callgraph builder: Edge extraction accuracy
- Dependency tracker: Fan-in/out, cycle detection
- Similarity engine: Cosine similarity, KNN graph

### 8.2 Integration Tests

- End-to-end tool calls (MCP endpoints)
- Performance benchmarks
- Memory profiling

### 8.3 Acceptance Criteria

- [ ] 90%+ code coverage
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance targets met
- [ ] No memory leaks (>2GB peak)

---

## 9. References

- Phase 8 Spec: `docs/phase8-context-injection-spec.md`
- Phase 8B Spec: `docs/phase8b-spec.md`
- Phase 9 Plan: `docs/plans/phase9-implementation-plan.md`
- sqlite-vec Docs: https://github.com/asg017/sqlite-vec
- BGE Model: https://huggingface.co/BAAI/bge-small-en-v1.5
- PageRank: https://en.wikipedia.org/wiki/PageRank

---

**End of Specification**
---

## refactor-modular-v1

# AST-Tools Refactoring Spec — Modular Architecture

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Refactor monolithic `ast_tools_server.py` (1900+ lines, 11 tools) into a modular package structure with separated concerns.

**Architecture:** Professional Python package with src layout, one tool per module, shared utilities extracted.

**Tech Stack:** Python 3.13+, libcst, pytest, ruff, MCP SDK.

---

## Problem Statement

The current `ast_tools_server.py` is 1900+ lines with:
- Tool definitions mixed with handlers
- 11 tools in a single file
- No separation between MCP protocol and business logic
- Hard to test individual tools in isolation
- Interface extractor added as separate module (good pattern to continue)

## Goals

1. **One tool per module** — Each MCP tool lives in its own file under `src/ast_tools/tools/`
2. **Clean separation of concerns** — Server setup, tool registration, tool logic, utilities
3. **Professional package structure** — src layout, proper `__init__.py`, testable modules
4. **Backward compatibility** — All existing tests must pass unchanged
5. **Enable indexer addition** — Structure must accommodate semantic codebase database feature

## Compatibility Rules

- All existing tool signatures must remain unchanged
- All existing tests must pass without modification
- MCP tool names must not change (backward compatible with clients)
- Server entry point (`python -m ast_tools_server`) must work identically

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/__init__.py` | Create | Package root, exports server + tools |
| `src/ast_tools/server.py` | Create | MCP server setup, tool registration only |
| `src/ast_tools/tools/__init__.py` | Create | Tool package, re-exports all tools |
| `src/ast_tools/tools/ast_grep.py` | Create | Structural search tool |
| `src/ast_tools/tools/ast_edit.py` | Create | AST-based editing tool |
| `src/ast_tools/tools/ast_read.py` | Create | Structural context extraction |
| `src/ast_tools/tools/ast_generate_stub.py` | Create | Stub generation tool |
| `src/ast_tools/tools/ast_refactor_extract_interface.py` | Create | Interface extraction (move from interface_extractor.py) |
| `src/ast_tools/tools/structural_analysis.py` | Create | Call graphs, type hierarchies |
| `src/ast_tools/tools/project_info.py` | Create | Project manifest generation |
| `src/ast_tools/tools/codebase_summary.py` | Create | Architecture overview |
| `src/ast_tools/tools/find_references.py` | Create | Cross-file symbol search |
| `src/ast_tools/tools/impact_analysis.py` | Create | Change impact analysis |
| `src/ast_tools/tools/module_imports.py` | Create | Import graph analysis |
| `src/ast_tools/utils/__init__.py` | Create | Utilities package |
| `src/ast_tools/utils/annotations.py` | Create | AST annotation helpers, function signatures |
| `src/ast_tools/utils/cache.py` | Create | Content-hash caching (prep for semantic DB) |
| `src/ast_tools_server.py` | Keep | Entry point shim for backward compat |
| `tests/test_e2e.py` | Modify | Update imports to new structure |
| `tests/test_tools/` | Create | Per-tool test directory |

## Acceptance Criteria

- [ ] All 114 existing tests pass
- [ ] No test file modifications needed (backward compatible imports)
- [ ] Server starts identically: `python -m ast_tools_server`
- [ ] Each tool module independently testable
- [ ] Lint passes (ruff + pyright)
- [ ] Package installable: `pip install -e .`
- [ ] Entry point works: `python -c "from ast_tools import server"`

---

## Implementation Order

**Sequential phases** (shared files, dependencies):

1. **Phase 1**: Package structure + extract utils
2. **Phase 2**: Extract simple tools (codebase_summary, project_info)
3. **Phase 3**: Extract core tools (ast_read, ast_edit, ast_grep)
4. **Phase 4**: Extract remaining tools
5. **Phase 5**: Server refactor + tests

**Parallel dispatch pattern:** Within each phase, tools that don't share files can be extracted simultaneously.
---

## semantic-db-phase1-v1

# Semantic Database — Phase 1 Spec

**Version:** 1.0  
**Date:** 2026-06-23  
**Mode:** MEDIUM (plan-and-audit skill)

---

## Problem Statement

**Current state:** ast-tools has 11 powerful structural analysis tools, but each operates on-demand without persistent knowledge of the codebase. Users must re-parse files on every tool call.

**Missing capability:** No persistent symbol index, no cross-file symbol resolution without re-parsing, no incremental updates when files change.

**Impact:** 
- Slower repeated queries on same codebase
- Cannot efficiently answer "show me all symbols in this project"
- No cached AST for large files
- No file change detection → stale results

---

## Goals

| ID | Priority | Description |
|----|----------|-------------|
| G1 | **MUST** | Persistent SQLite symbol database with FTS5 search |
| G2 | **MUST** | Content-hash based cache invalidation |
| G3 | **MUST** | Incremental indexing (only reindex changed files) |
| G4 | **SHOULD** | Python `ast` parser + tree-sitter multi-language support |
| G5 | **SHOULD** | Pickle cache for parsed ASTs (50x speedup) |
| G6 | **COULD** | File watcher for automatic reindexing (Phase 2) |

---

## Compatibility & Behavior Rules

1. **Backward compatibility:** All 11 existing ast-tools MCP tools continue to work unchanged
2. **Database location:** `~/.cache/ast-tools/codebase.db` (user cache dir, not in project)
3. **WAL mode:** Enabled by default for concurrent reads
4. **Content-hash invalidation:** SHA256, cache key = `(file_path, content_hash, python_version)`
5. **Indexing scope:** Configurable via `--include` / `--exclude` patterns (default: `**/*.py`, exclude `**/__pycache__/**`)
6. **Atomic writes:** All DB updates wrapped in transactions
7. **Migration support:** Schema versioning with auto-migration on open

---

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/indexer/__init__.py` | Create | Indexer package root |
| `src/ast_tools/indexer/parser.py` | Create | AST + tree-sitter parser abstraction |
| `src/ast_tools/indexer/extractor.py` | Create | Symbol & edge extraction from AST |
| `src/ast_tools/indexer/cache.py` | Create | Pickle cache with content-hash invalidation |
| `src/ast_tools/database/__init__.py` | Create | Database package root |
| `src/ast_tools/database/schema.py` | Create | Schema definition + migrations |
| `src/ast_tools/database/queries.py` | Create | Query functions (search, lookup, traverse) |
| `src/ast_tools/database/connection.py` | Create | Connection management (WAL, pragmas) |
| `src/ast_tools/tools/search_symbols.py` | Create | MCP tool: FTS5 + BM25 search |
| `src/ast_tools/tools/find_symbol_definition.py` | Create | MCP tool: exact match lookup |
| `src/ast_tools/tools/list_symbols.py` | Create | MCP tool: all symbols in file |
| `src/ast_tools/tools/index_status.py` | Create | MCP tool: cache stats, indexed file count |
| `src/ast_tools/tools/refresh_index.py` | Create | MCP tool: force reindex |
| `tests/indexer/` | Create | Indexer unit tests |
| `tests/database/` | Create | Database unit tests |
| `tests/tools/test_semantic_tools.py` | Create | MCP tool integration tests |

---

## Acceptance Criteria

- [ ] **G1:** SQLite DB created at `~/.cache/ast-tools/codebase.db`, FTS5 search working
- [ ] **G2:** Content-hash invalidation verified (edit file → reindex → new hash)
- [ ] **G3:** Incremental indexing: 10-file change reindexes only 10 files (not all)
- [ ] **G4:** Python `ast` parser extracts functions, classes, methods, imports
- [ ] **G5:** Pickle cache shows 10x+ speedup on second parse
- [ ] **G6:** Deferred to Phase 2 (watchdog integration)
- [ ] All new tools appear in `list_tools()` MCP call
- [ ] All tests pass (new tests + existing 114)
- [ ] Schema migrations tested (v1 → v2 simulation)

---

## Test Plan

### Unit Tests (Indexer)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/indexer/test_parser.py` | 8 | Python `ast` parsing, tree-sitter fallback, error handling |
| `tests/indexer/test_extractor.py` | 12 | Symbol extraction (functions, classes, imports), edge extraction |
| `tests/indexer/test_cache.py` | 10 | Content-hash invalidation, pickle roundtrip, LRU eviction |

### Unit Tests (Database)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/database/test_schema.py` | 6 | Migrations, versioning, rollback |
| `tests/database/test_queries.py` | 15 | FTS5 search, symbol lookup, edge traversal |
| `tests/database/test_connection.py` | 5 | WAL mode, concurrent reads, connection pooling |

### Integration Tests (MCP Tools)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/tools/test_semantic_tools.py` | 20 | End-to-end MCP tool calls via server fixture |

### Performance Benchmarks

| Benchmark | Target |
|-----------|--------|
| Index 10K LOC codebase | <5 seconds |
| Search symbol (FTS5) | <50ms |
| Incremental reindex (10 files) | <500ms |
| AST cache hit | <1ms (vs 50ms parse) |

---

## Rollback Plan

Each phase is one commit. Rollback:

```bash
# Undo Phase 1
git revert HEAD
# OR remove last commit entirely
git reset --hard HEAD~1
```

**No breaking changes:** Existing tools+tests remain untouched → rollback safe.

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| tree-sitter | ^0.22 | Multi-language parsing |
| tree-sitter-python | ^0.21 | Python grammar |
| tree-sitter-typescript | ^0.21 | TypeScript grammar |
| watchdog | ^6.0 | File watching (Phase 2) |

**Existing (already in pyproject.toml):**
- `libcst` (AST editing)
- `anyio` (async)
- `mcp` (server SDK)

---

## Design Decisions

### 1. SQLite over NoSQL
**Why:** Mature, single-file, FTS5 built-in, no external service, ACID.
**Rejected:** Pickle-only (no querying), PostgreSQL (overkill), Chroma (embeddings not needed yet).

### 2. Content-Hash over Mtime
**Why:** Git operations don't always update mtime, content-hash guarantees correctness.
**Trade-off:** Slower (must read file), but correctness > speed.

### 3. Hybrid Parsing (ast + tree-sitter)
**Why:** Python `ast` gives deepest Python analysis (decorators, call extraction), tree-sitter adds multi-language.
**Rejected:** Tree-sitter-only (less precise for Python), ast-only (single language).

### 4. Separate Packages (indexer/, database/)
**Why:** Separation of concerns, testable in isolation, reusable in Phase 2 plugin.
**Rejected:** Single monolithic `indexer.py` (hard to test, violates SRP).

### 5. Cache in ~/.cache (not project dir)
**Why:** Persists across projects, doesn't pollute git, follows XDG spec.
**Rejected:** Project-local `.ast-tools-cache/` (per-project duplication).

---

## Out of Scope (Future Phases)

- **Phase 2:** File watcher (watchdog), auto-reindex
- **Phase 3:** Embeddings + vector search (sqlite-vec)
- **Phase 4:** Cross-project symbol resolution
- **Phase 5:** Graph-based queries (DAG traversal, cycle detection)

---

## Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Time to first symbol search | N/A (no index) | <100ms |
| Time to subsequent search | Full parse (~500ms) | <50ms (indexed) |
| Index 10K LOC codebase | N/A | <5s |
| Incremental reindex (10 files) | N/A | <500ms |
| Test coverage (new code) | 0% | >85% |

---

## Review Feedback

**Pending forward + reverse audits.**

---

**Next Step:** Implementation plan (docs/plans/semantic-db-phase1-v1.md)
---

## semantic-db-phase2-v2

# Semantic Database — Phase 2 Spec: Vector Embeddings + Semantic Search

**Version:** 2.0  
**Date:** 2026-07-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Phase 1 Reference:** `docs/specs/semantic-db-phase1-v1.md` (✅ COMPLETE)

---

## Problem Statement

**Current state (Phase 1):** Symbolic search only — FTS5 keyword matching + exact name lookup. Can find `authenticate_user` when searching "authenticate", but cannot find it when searching "login validation" or "password check".

**Missing capability:** Semantic similarity search — find code by *meaning*, not just by keyword matching in names/docstrings.

**Impact:**
- Cannot discover code without knowing exact function names
- No "find similar patterns" capability
- No "what handles authentication?" queries
- No cross-project code pattern discovery

---

## Goals

| ID | Priority | Description |
|----|----------|-------------|
| G1 | **MUST** | Local transformer embedding model (CPU-only, <400MB RAM) |
| G2 | **MUST** | sqlite-vec extension for vector similarity search |
| G3 | **MUST** | Generate embeddings for all symbols (docstring + signature) |
| G4 | **MUST** | Hybrid search: FTS5 (keyword) + vector (semantic) fusion |
| G5 | **SHOULD** | Incremental embedding (only re-embed changed symbols) |
| G6 | **COULD** | Query embedding caching (avoid re-compute same queries) |

---

## Model Selection (CPU Constraint: 4GB RAM)

**Primary:** `bge-small-en-v1.5`
- Dimensions: 384
- Model size: ~130MB
- RAM usage: ~300MB during inference
- Speed: ~50-100 embeddings/sec on CPU
- Quality: Strong for technical text (trained on StackExchange, GitHub, arXiv)
- License: MIT (commercial OK)

**Fallback:** `all-MiniLM-L6-v2`
- Dimensions: 384
- Model size: ~80MB
- RAM usage: ~200MB
- Speed: ~80-150 embeddings/sec
- Quality: Slightly lower but very fast

**Library:** `sentence-transformers` (wraps HuggingFace, easy CPU inference)

---

## Vector Store Architecture

**Option Selected:** `sqlite-vec` extension (pure SQLite, no external DB)

**Why:**
- No new infrastructure (keeps Phase 1 SQLite-only architecture)
- <1ms query time for <100K vectors
- Same connection, same transactions, same WAL mode
- Pure C extension (no Python overhead)
- Active maintenance, stable API

**Schema Extension:**
```sql
CREATE VIRTUAL TABLE symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Storage:** BLOB in main `symbols` table + `symbols_vec` virtual table for indexing

---

## Hybrid Search Strategy

**Reciprocal Rank Fusion (RRF):**
```
RRF_score(doc) = Σ (1 / (rank_i(doc) + k))  for each result list i
```

**Process:**
1. Generate query embedding (384-dim vector)
2. Vector search: top-2k results by cosine similarity
3. FTS5 search: top-2k results by BM25
4. RRF fusion: combine rankings
5. Return top-k fused results

**k value:** 1.5 (standard for RRF, balances keyword vs semantic)

---

## File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/ast_tools/embeddings/__init__.py` | Create | Embeddings package root |
| `src/ast_tools/embeddings/model.py` | Create | Transformer model loading, embedding generation |
| `src/ast_tools/embeddings/store.py` | Create | sqlite-vec integration, batch insert |
| `src/ast_tools/database/queries.py` | Patch | Add `generate_symbol_embedding`, `semantic_search` |
| `src/ast_tools/database/schema.py` | Patch | Add `symbols_vec` virtual table, migration |
| `src/ast_tools/tools/semantic_search.py` | Create | MCP tool: hybrid search (FTS5 + vector) |
| `src/ast_tools/indexer/extractor.py` | Patch | Call embedding generation during symbol extraction |
| `src/ast_tools/indexer/cache.py` | Patch | Track embedding hash (re-embed if docstring changes) |
| `tests/embeddings/test_model.py` | Create | Model loading, embedding generation tests |
| `tests/embeddings/test_store.py` | Create | sqlite-vec insert/search tests |
| `tests/tools/test_semantic_search.py` | Create | MCP tool integration tests |
| `docs/research/embeddings-phase2-research.md` | Created by subagent | Model comparison, benchmarks |
| `docs/specs/semantic-db-phase2-v2.md` | This file | Interface contracts, architecture |
| `docs/plans/semantic-db-phase2-v2.md` | Phase 2 Plan | Task breakdown, dependencies |

---

## Acceptance Criteria

- [ ] **G1:** Model loads on CPU, <400MB RAM, generates embeddings in <20ms each
- [ ] **G2:** `sqlite-vec` installed, `symbols_vec` table created, cosine similarity search working
- [ ] **G3:** All existing symbols have embeddings (batch generation for Phase 1 data)
- [ ] **G4:** `semantic_search(query, k=10)` returns fused results (keyword + semantic)
- [ ] **G5:** Incremental embedding: editing docstring triggers re-embed, unchanged symbols skipped
- [ ] **G6:** Query caching: same query twice = second is instant (from cache)
- [ ] New `semantic_search` tool appears in `list_tools()` MCP call
- [ ] All tests pass (existing 185 + new ~40 embedding tests = 225+ total)
- [ ] Schema migration tested (v1 → v2 with backfill)

---

## Compatibility & Behavior Rules

1. **Backward compatibility:** All 16 existing ast-tools MCP tools continue to work unchanged
2. **Embedding trigger:** Generate on symbol insert/update (if docstring or signature changes)
3. **Lazy generation:** If model not loaded, `semantic_search` returns error with install instructions
4. **Batch generation:** `refresh_index --embeddings` backfills all missing embeddings
5. **Model cache:** Downloaded model cached at `~/.cache/ast-tools/models/bge-small-en-v1.5/`
6. **Graceful degradation:** If sqlite-vec not installed, tool fails with clear error (not silent)
7. **Dimension validation:** Embedding dimension hard-coded to 384 (schema-level constraint)

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Embedding generation | <20ms/symbol | BGE-small on i3 CPU |
| Vector search (10K symbols) | <5ms | sqlite-vec cosine similarity |
| Hybrid search (fused) | <50ms | FTS5 + vector + RRF fusion |
| Batch backfill (10K symbols) | <5min | ~3-4 hours for 100K symbols |
| RAM overhead | <400MB | Model + embeddings in memory |
| Disk overhead | ~4MB per 10K symbols | 384 floats = 1.5KB per symbol |

---

## Test Plan

### Unit Tests (Embeddings)

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/embeddings/test_model.py` | 8 | Model loading, CPU inference, embedding shape validation |
| `tests/embeddings/test_store.py` | 10 | sqlite-vec insert, cosine search, batch operations |

### Integration Tests

| Test File | Tests | Description |
|-----------|-------|-------------|
| `tests/tools/test_semantic_search.py` | 12 | Hybrid search, edge cases, ranking validation |
| `tests/indexer/test_extractor.py` | +4 | Embedding generation during extraction (incremental) |
| `tests/database/test_schema.py` | +3 | Migration v1→v2, schema validation |

### Performance Tests

| Test | Metric | Target |
|------|--------|--------|
| Generate 100 embeddings | Total time | <2s |
| Search 10K symbols | Query latency | <50ms |
| Backfill 10K symbols | Batch time | <5min |

---

## Security & Privacy

1. **Local-only:** No API calls, all embeddings generated locally (no data leaves machine)
2. **Model integrity:** Verify model checksum on download (SHA256)
3. **No PII in embeddings:** Only docstrings + signatures (no file contents, no comments)
4. **Sandboxed:** sqlite-vec is pure C, no arbitrary code execution

---

## Migration Plan (v1 → v2)

**Step 1: Schema migration**
```sql
-- Add symbols_vec virtual table
CREATE VIRTUAL TABLE symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Step 2: Batch backfill**
```python
# In refresh_index tool
if args.embeddings:
    backfill_embeddings(conn, model, batch_size=100)
```

**Step 3: Incremental updates**
- Modify `insert_symbol()` to generate embedding automatically
- Check `embedding_hash` in file_cache (skip if unchanged)

**Rollback:** If migration fails, restore from WAL checkpoint (pre-migration state)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model too slow on CPU | Medium | High | Fallback to MiniLM (faster, lower quality) |
| sqlite-vec install fails | Low | High | Provide pre-built wheel, fallback to numpy brute-force |
| RAM exhaustion (4GB limit) | Low | High | Batch embedding gen (100 symbols/batch), clear model after batch |
| Hybrid search ranking wrong | Medium | Medium | Tune RRF k-value, add user feedback mechanism |
| Migration corrupts DB | Low | Critical | WAL mode + checkpoint before migration, test on copy first |

---

## Success Metrics

- **Precision@10:** >0.75 for semantic queries (e.g., "auth" → auth-related functions)
- **Recall@10:** >0.60 for semantic queries (finds 60% of relevant symbols in top 10)
- **Latency:** <50ms p95 for hybrid search queries
- **Coverage:** 100% of symbols have embeddings (after backfill)
- **Adoption:** `semantic_search` used in >50% of symbol lookup queries (after 1 month)

---

## Definition of Done

- [ ] All 12 acceptance criteria met
- [ ] All tests passing (225+ total)
- [ ] Schema migration tested (v1→v2→rollback→v2)
- [ ] Performance targets met (embedding gen <20ms, search <50ms)
- [ ] Documentation updated (README, tool docs, Phase 2 report)
- [ ] Forward + reverse audits completed
- [ ] Adversarial audit completed (security, edge cases)
- [ ] All commits pushed to master

---

**Next Phase:** Phase 2 Plan (`docs/plans/semantic-db-phase2-v2.md`) — task breakdown, dependencies, timeline
