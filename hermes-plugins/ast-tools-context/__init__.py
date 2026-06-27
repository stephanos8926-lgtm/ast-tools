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

**Structural Code Analysis & Editing** available via 26 MCP tools:

### Core Tools

**ast_grep** - Structural code search using AST patterns
- Pattern: `def $FUNC($$$ARGS)` matches any function definition
- Pattern: `call($OBJ, $METHOD)` matches method calls with 2 args
- Supports: Python, JS/TS, Rust, Go, Java, C/C++, and 20+ languages
- Returns: Matches with file, line, column, code snippet

**ast_read** - Structural context extraction
- Input: File path
- Output: Imports, classes, functions, variables (all with line numbers)
- Use: Understand code structure before making changes

**ast_edit** - Surgical AST-based modifications
- Operations: replace_node, insert_after, insert_before, remove_node, 
             rename_function, add_parameter, change_signature
- Uses libcst for lossless transformations (preserves formatting/comments)
- Always use `dry_run: true` first!

**ast_generate_stub** - Generate .pyi stub files
- Creates type stubs from existing code
- Use for library interface documentation

### Analysis Tools

**structural_analysis** - Comprehensive code analysis
- Call graphs (who calls whom)
- Type hierarchies (class inheritance)
- Symbol references and usage

**impact_analysis** - Change impact assessment
- Input: File path or symbol name
- Output: List of affected files/code locations
- **Use before making changes!**

**module_imports** - Import dependency analysis
- Fan-in: Which modules import this one?
- Fan-out: Which modules does this one import?
- Circular dependency detection

**find_references** - Cross-file symbol search
- Find all usages of a symbol across the codebase

### Search & Discovery

**semantic_search** - Vector + FTS5 hybrid search
- Search code by meaning, not just keywords
- Retrieves most relevant code sections

**search_symbols** - Full-text symbol search
- Search through indexed symbol names

**find_symbol_definition** - Find symbol by qualified name
- Input: "module.func" or "Class.method"
- Output: File path and line number

**list_symbols** - List all symbols in a file
- Returns: All functions, classes, variables with locations

### Index Management

**refresh_index** - Index/re-index a project
- Incremental (only changed files)
- Content hashing for change detection

**index_status** - Get index statistics
- Number of symbols, files, embeddings

### Usage Patterns

**For code search:**
1. Start with `semantic_search` for conceptual queries
2. Refine with `ast_grep` for structural patterns
3. Verify with `ast_read` to see full context

**For making changes:**
1. Analyze with `structural_analysis` to understand dependencies
2. Check impact with `impact_analysis`
3. Preview edit with `ast_edit` (dry_run=true)
4. Apply edit (dry_run=false)
5. Verify with `ast_read`

**For understanding code:**
1. Get overview with `codebase_summary`
2. Extract structure with `ast_read`
3. Find dependencies with `module_imports`
4. Locate usages with `find_references`

**Tip:** Use Context7 (say "use context7") for library documentation when working with external APIs.
"""


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