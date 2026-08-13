"""
AST-Tools Context Injection Plugin for Hermes Agent

Injects ast-tools documentation and capabilities into the LLM context
when the user's query relates to code structure analysis, AST manipulation,
or structural code search.
"""

from hermes_cli.plugins import PluginContext


def register(ctx: PluginContext):
    """Register ast-tools context injection hooks."""
    ctx.register_hook("pre_llm_call", inject_ast_tools_context)
    ctx.register_hook("on_session_start", inject_session_onboarding)


def inject_ast_tools_context(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs
) -> dict | None:
    """
    Inject ast-tools documentation into LLM context when relevant.
    
    Detects when user is asking about:
    - AST manipulation
    - Code structure analysis
    - Symbol references
    - Dependency analysis
    - Structural search
    
    Args:
        session_id: Current session identifier
        user_message: User's current message/query
        conversation_history: List of previous messages
        is_first_turn: Whether this is the first turn in session
        model: Current LLM model name
        platform: Platform (cli, telegram, discord, etc.)
    
    Returns:
        dict with "context" key if injection needed, None otherwise
    """
    # Keywords that trigger context injection
    ast_keywords = [
        "ast ", "ast-grep", "astedit", "ast edit", "ast read", "ast_read",
        "abstract syntax tree", "parse tree", "code structure",
        "symbol", "reference", "dependency", "import analysis",
        "structural", "code search", "grep", "structural grep",
        "libcst", "concrete syntax tree", "cst",
        "impact analysis", "call graph", "type hierarchy",
        "module imports", "fan-in", "fan-out",
        "semantic search", "codebase summary"
    ]
    
    # Check if query is relevant
    if not any(kw in user_message.lower() for kw in ast_keywords):
        return None
    
    # Build context
    context = build_ast_tools_context(user_message)
    
    if context:
        return {"context": context}
    return None


def build_ast_tools_context(query: str) -> str:
    """
    Build context string for ast-tools capabilities.
    
    Provides a concise overview of available tools and usage patterns.
    Limited to ~1000 tokens to avoid context bloat.
    """
    return """
## AST-Tools MCP Server Capabilities

**Structural Code Analysis & Editing** — 55 MCP tools available.

### Core AST Tools
| Tool | What it does |
|------|-------------|
| `ast_grep` | Structural search with AST patterns (Python/JS/TS/Rust/Go/Java/C++) |
| `ast_read` | Extract API surface (classes, functions, imports + line numbers) |
| `ast_edit` | Surgical AST edits via libcst — **always dry_run=true first!** |
| `ast_generate_stub` | Generate .pyi stub files or interface summaries |
| `ast_refactor_extract_interface` | Extract ABC/Protocol from a class |
| `ast_capsule` | Export code as self-contained capsule with deps |
| `ast_query` | Smart router — auto-selects best tool for your query |
| `ts_edit` | TypeScript structural editing (TSX/JSX support) |

### Analysis & Impact
| Tool | What it does |
|------|-------------|
| `structural_analysis` | Call graphs, type hierarchies, references, dependencies |
| `impact_analysis` | **Use before refactoring** — shows affected files + risk |
| `module_imports` | Fan-in/fan-out import graph, circular dep detection |
| `find_references` | All usages of a symbol across the codebase |
| `blast_radius_v2` | Unified blast radius (import + hierarchy + call graph) |
| `class_hierarchy` | MRO, bases, subclasses, method categories |
| `transitive_dependents` | Full transitive dependency chain |
| `circular_dependencies` | Detect circular imports |
| `dependency_chain` | Trace dependency paths end-to-end |
| `external_dependencies` | Find third-party imports |
| `api_surface_diff` | Compare API surfaces between versions |

### Knowledge Graph (KG)
| Tool | What it does |
|------|-------------|
| `kg_query` | Natural language graph traversal — find related symbols |
| `kg_shortest_path` | Shortest path between two symbols |
| `kg_neighborhood` | All symbols within N hops of a given symbol |

### Co-Change Analysis
| Tool | What it does |
|------|-------------|
| `co_change_diff` | Diff-level co-change patterns |
| `co_change_history` | Historical co-change frequency |
| `co_change_hotspots` | Files that change together most often |
| `co_change_predict` | Predict what else needs changing given a file |

### Dead Code & Code Quality
| Tool | What it does |
|------|-------------|
| `dead_code_detection` | Find unused code |
| `dead_code_enhanced` | Deeper dead code analysis with cross-ref tracing |
| `code_validate_syntax` | Syntax check files |
| `codebase_summary` | Architecture overview (<500 tokens) |
| `project_info` | Full project manifest with modules and symbols |
| `repo_skeleton` | File tree + type detection + dep graph |
| `file_related_suggest` | Find related files by import/test/dir patterns |

### LSP Integration
| Tool | What it does |
|------|-------------|
| `lsp_definition` | Go-to-definition |
| `lsp_references` | Find references via LSP |
| `lsp_hover` | Type/signature on hover |
| `lsp_symbols` | Document symbols |
| `lsp_call_hierarchy_in` | Incoming calls |
| `lsp_call_hierarchy_out` | Outgoing calls |
| `lsp_available_languages` | Which LSP servers are running |
| `lsp_check_server` | Check LSP server health |

### Semantic Search & Index
| Tool | What it does |
|------|-------------|
| `semantic_search` | Vector + FTS5 hybrid — search by meaning |
| `search_symbols` | FTS5 keyword search of indexed symbols |
| `find_symbol_definition` | Lookup by qualified name |
| `list_symbols` | All symbols in a file |
| `refresh_index` | Index (incremental via SHA256) |
| `index_status` | Stats: files, symbols, edges, embeddings |
| `reindex_path` | Re-index a specific path |
| `watch_add` / `watch_status` | File watcher for auto-reindex |

### Best Practice Workflows

**Making changes:** `impact_analysis` → `blast_radius_v2` → `ast_edit` (dry_run!) → `ast_edit` (apply) → `code_validate_syntax`

**Understanding code:** `codebase_summary` → `ast_read` → `module_imports` → `kg_query`

**Finding code:** `semantic_search` → `ast_grep` (refine) → `ast_read` (full context)

**Debugging deps:** `circular_dependencies` → `external_dependencies` → `dependency_chain`

**Tip:** Use Context7 for library docs — say "use context7" before asking about external APIs.
"""


def inject_session_onboarding(session_id: str, **kwargs) -> dict:
    """Inject compact ast-tools index at session start."""
    return {
        "context": """
## AST-Tools Quick Index (55 tools available)

**Core:** ast_grep (structural search), ast_read (API surface), ast_edit (surgical edits—dry_run FIRST!), semantic_search (inject_context=True)

**Analysis:** impact_analysis (before API changes), module_imports (before splits), blast_radius_v2 (unified impact), circular_dependencies, class_hierarchy, transitive_dependents

**Advanced:** kg_query (semantic graph traversal), co_change_predict (what else needs changing), lsp_* (IDE-grade code nav), dead_code_enhanced, api_surface_diff

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