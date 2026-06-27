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