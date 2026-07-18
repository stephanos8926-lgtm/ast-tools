"""Tool categories for the discovery system.

Maps every registered tool to a semantic category for routing and search.
"""
# ─── Category Definitions ──────────────────────────────────────────────────
# CODE_ANALYSIS:  Structural code analysis (tree-sitter, libcst, AST)
# SEARCH:        Finding code by pattern, symbol, or semantic meaning
# REFACTOR:      Code modification and transformation
# INDEX:         Database indexing and management
# LSP:           Language Server Protocol integrations
# GRAPH:         Knowledge graph and dependency analysis
# FIX:           Auto-fix, linting, formatting
# CURATOR:       Code review and audit tools
# WATCH:         File watching and auto-indexing
# META:          Tool discovery and introspection

TOOL_CATEGORIES: dict[str, str] = {
    # ── CODE_ANALYSIS ──────────────────────────────────────────────────────
    "ast_grep": "CODE_ANALYSIS",
    "ast_read": "CODE_ANALYSIS",
    "ast_edit": "REFACTOR",
    "ast_query": "CODE_ANALYSIS",
    "ast_capsule": "CODE_ANALYSIS",
    "ast_generate_stub": "CODE_ANALYSIS",
    "ast_refactor_extract_interface": "REFACTOR",
    "code_validate_syntax": "CODE_ANALYSIS",
    "codebase_summary": "CODE_ANALYSIS",
    "repo_skeleton": "CODE_ANALYSIS",
    "project_info": "CODE_ANALYSIS",
    "module_imports": "CODE_ANALYSIS",
    "structural_analysis": "CODE_ANALYSIS",
    "ts_edit": "REFACTOR",

    # ── SEARCH ─────────────────────────────────────────────────────────────
    "search_symbols": "SEARCH",
    "semantic_search": "SEARCH",
    "find_references": "SEARCH",
    "find_symbol_definition": "SEARCH",
    "list_symbols": "SEARCH",
    "file_related_suggest": "SEARCH",
    "list_embedding_models": "SEARCH",
    "switch_embedding_model": "SEARCH",
    "get_embedding_model_info": "SEARCH",
    "rerank_results": "SEARCH",

    # ── REFACTOR ───────────────────────────────────────────────────────────
    "impact_analysis": "CODE_ANALYSIS",
    "blast_radius_v2": "CODE_ANALYSIS",
    "circular_dependencies": "CODE_ANALYSIS",
    "dependency_chain": "CODE_ANALYSIS",
    "external_dependencies": "CODE_ANALYSIS",
    "transitive_dependents": "CODE_ANALYSIS",
    "dead_code_detection": "CODE_ANALYSIS",
    "dead_code_enhanced": "CODE_ANALYSIS",
    "co_change_diff": "CODE_ANALYSIS",
    "co_change_history": "CODE_ANALYSIS",
    "co_change_hotspots": "CODE_ANALYSIS",
    "co_change_predict": "CODE_ANALYSIS",
    "api_surface_diff": "CODE_ANALYSIS",

    # ── INDEX ──────────────────────────────────────────────────────────────
    "refresh_index": "INDEX",
    "reindex_path": "INDEX",
    "index_status": "INDEX",
    "watch_add": "WATCH",
    "watch_status": "WATCH",

    # ── GRAPH ──────────────────────────────────────────────────────────────
    "kg_query": "GRAPH",
    "kg_neighborhood": "GRAPH",
    "kg_shortest_path": "GRAPH",
    "class_hierarchy": "GRAPH",
    "suggest_modules": "CODE_ANALYSIS",

    # ── LSP ────────────────────────────────────────────────────────────────
    "lsp_definition": "LSP",
    "lsp_references": "LSP",
    "lsp_hover": "LSP",
    "lsp_symbols": "LSP",
    "lsp_call_hierarchy_in": "LSP",
    "lsp_call_hierarchy_out": "LSP",
    "lsp_diagnostics": "LSP",
    "lsp_format": "FIX",
    "lsp_code_actions": "REFACTOR",
    "lsp_rename": "REFACTOR",
    "lsp_signature_help": "LSP",
    "lsp_workspace_symbols": "LSP",
    "lsp_completion": "LSP",
    "lsp_completion_detail": "LSP",
    "lsp_available_languages": "LSP",
    "lsp_check_server": "LSP",

    # ── FIX ────────────────────────────────────────────────────────────────
    "fix_code": "FIX",
    "fix_check": "FIX",
    "llm_suggest_fix": "FIX",
    "code_validate_syntax": "CODE_ANALYSIS",

    # ── CURATOR ────────────────────────────────────────────────────────────
    "curator_audit": "CURATOR",
    "curator_status": "CURATOR",
    "curator_summary": "CURATOR",

    # ── META (discovery tools) ─────────────────────────────────────────────
    "search_tools": "META",
    "call_tool": "META",
    "tool_info": "META",
}
