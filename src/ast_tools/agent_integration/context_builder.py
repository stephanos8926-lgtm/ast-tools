"""Context builder — build AST-tools context blocks for LLM prompts.

Extracted from the Hermes ast-tools-context plugin (pre_llm_call hook).
Zero Hermes dependency — pure functions usable by any agent framework.

Usage:
    from ast_tools.agent_integration import build_ast_tools_context, detect_ast_query

    if detect_ast_query(user_message):
        context = build_ast_tools_context(user_message)
        # inject context into LLM prompt
"""

# ── Keywords that trigger context injection ─────────────────────────────

KEYWORDS = [
    "ast ",
    "ast-grep",
    "astedit",
    "ast edit",
    "ast read",
    "ast_read",
    "abstract syntax tree",
    "parse tree",
    "code structure",
    "symbol",
    "reference",
    "dependency",
    "import analysis",
    "structural",
    "code search",
    "grep",
    "structural grep",
    "libcst",
    "concrete syntax tree",
    "cst",
    "impact analysis",
    "call graph",
    "type hierarchy",
    "module imports",
    "fan-in",
    "fan-out",
    "semantic search",
    "codebase summary",
]


def detect_ast_query(message: str) -> bool:
    """Detect if a user message relates to AST-tools capabilities.

    Args:
        message: The user's message text.

    Returns:
        True if the message contains AST-tool related keywords.
    """
    lower = message.lower()
    return any(kw in lower for kw in KEYWORDS)


def build_ast_tools_context(query: str = "") -> str:  # noqa: ARG001
    """Build a concise context block describing AST-tools capabilities.

    Args:
        query: Optional query to tailor context (currently unused,
               preserved for future semantic matching).

     # noqa: ARG001

    Returns:
        A formatted markdown string describing available tools.
        Limited to ~1000 tokens to avoid context bloat.
    """
    return """## AST-Tools MCP Server Capabilities

**Structural Code Analysis & Editing** — 55+ MCP tools available.

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

### Knowledge Graph & Co-Change
| Tool | What it does |
|------|-------------|
| `kg_query` | Natural language graph traversal |
| `kg_shortest_path` | Shortest path between two symbols |
| `kg_neighborhood` | All symbols within N hops |
| `co_change_predict` | What else needs changing given a file |

### Semantic Search & Index
| Tool | What it does |
|------|-------------|
| `semantic_search` | Vector + FTS5 hybrid — search by meaning |
| `search_symbols` | FTS5 keyword search |
| `find_symbol_definition` | Lookup by qualified name |
| `refresh_index` | Incremental indexing via SHA256 |

### Quick Workflows
- **Making changes:** `impact_analysis` → `blast_radius_v2` → `ast_edit` (dry_run!) → `code_validate_syntax`
- **Understanding code:** `codebase_summary` → `ast_read` → `module_imports`
- **Finding code:** `semantic_search` → `ast_grep` (refine) → `ast_read`
"""
