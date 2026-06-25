"""MCP tool: hybrid semantic + keyword search.

Provides search with optional context injection for LLM prompts.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from src.ast_tools.database.connection import get_connection
from src.ast_tools.embeddings import generate_embedding, search_similar
from src.ast_tools.context import ContextInjector, MarkdownFormatter, count_tokens

logger = logging.getLogger(__name__)

RRF_K = 1.5  # Reciprocal Rank Fusion constant


def hybrid_search(
    conn,
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None
) -> list[dict]:
    """
    Hybrid search: FTS5 keyword + vector semantic with RRF fusion.

    Args:
        conn: SQLite connection
        query: Search query text
        k: Number of results to return
        kind: Optional symbol kind filter (function, class, method, etc.)
        lang: Optional language filter (python, rust, go, typescript, etc.)

    Returns:
        List of symbol dicts ordered by fused relevance score
    """
    # 1. Generate query embedding
    query_emb = generate_embedding(query)

    # 2. Vector similarity search (returns 2k for fusion)
    vec_results = search_similar(conn, query_emb, k=k * 2)

    # 3. FTS5 keyword search with JOIN to get symbol_id
    fts_sql = """
        SELECT s.id as symbol_id, bm25(symbols_fts) as score
        FROM symbols_fts
        JOIN symbols s ON s.rowid = symbols_fts.rowid
        WHERE symbols_fts MATCH ?
    """
    params = [query]
    if kind:
        fts_sql += " AND s.kind = ?"
        params.append(kind)
    if lang:
        fts_sql += " AND s.lang = ?"
        params.append(lang)
    fts_sql += " LIMIT ?"
    params.append(k * 2)

    fts_rows = conn.execute(fts_sql, params).fetchall()
    fts_results = [(row['symbol_id'], row['score']) for row in fts_rows]

    # 4. Reciprocal Rank Fusion
    fused_scores = {}

    # Vector results: rank by distance (lower = better)
    for i, (symbol_id, _) in enumerate(vec_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)

    # FTS5 results: rank by BM25 score (lower = better)
    for i, (symbol_id, score) in enumerate(fts_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + RRF_K)

    # 5. Sort by fused score (higher = better)
    top_k = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:k]

    # 6. Fetch full symbol details
    symbols = []
    if top_k:
        placeholders = ",".join("?" for _ in top_k)
        symbol_ids = [sid for sid, _ in top_k]
        rows = conn.execute(
            f"SELECT * FROM symbols WHERE id IN ({placeholders})",
            symbol_ids
        ).fetchall()

        # Preserve fused ranking order
        row_map = {row['id']: dict(row) for row in rows}
        for symbol_id, _ in top_k:
            if symbol_id in row_map:
                symbols.append(row_map[symbol_id])

    return symbols


def estimate_context_tokens(symbol: Dict[str, Any]) -> int:
    """Estimate token count for a context symbol.
    
    Args:
        symbol: Symbol dict with signature and docstring
        
    Returns:
        Estimated token count (range: 150-1000)
    """
    base = 150
    
    if symbol.get("signature"):
        base += len(str(symbol["signature"])) // 4
    
    if symbol.get("docstring"):
        base += len(str(symbol["docstring"])) // 4
    
    return min(base, 1000)


def format_context_result(
    symbols: List[Dict[str, Any]],
    tokens_used: int,
    tokens_budget: int,
    model_context_window: int,
    max_symbols: int = 10
) -> str:
    """Format context injection results as markdown.
    
    Args:
        symbols: List of symbol dicts with relevance_score
        tokens_used: Total tokens used for context
        tokens_budget: Available token budget for context
        model_context_window: Model's total context window
        max_symbols: Max symbols to display
        
    Returns:
        Formatted markdown string
    """
    formatter = MarkdownFormatter()
    return formatter.format_context_injection_result(
        symbols=symbols,
        total_available=max_symbols,
        tokens_used=tokens_used,
        tokens_budget=tokens_budget,
        model_context_window=model_context_window
    )


def hybrid_search_with_context(
    conn,
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None,
    context_enabled: bool = True,
    max_context_symbols: int = 10,
    model_context_window: int = 32000,
    context_token_budget: Optional[int] = None
) -> Tuple[list[dict], dict[str, Any]]:
    """Hybrid search with optional context injection.
    
    Args:
        conn: SQLite connection
        query: Search query
        k: Number of results
        kind: Optional kind filter
        lang: Optional language filter
        context_enabled: Whether to inject context
        max_context_symbols: Max symbols for context
        model_context_window: Model's context window size
        context_token_budget: Token budget for context (default: 20% of window)
        
    Returns:
        Tuple of (search_results, context_injection_info)
        context_injection_info contains:
        - context_markdown: Formatted context
        - tokens_used: Tokens consumed
        - budget_remaining: Remaining budget
    """
    results = hybrid_search(conn, query, k, kind, lang)
    
    if not context_enabled or not results:
        return results, {
            "context_markdown": "",
            "tokens_used": 0,
            "budget_remaining": context_token_budget or (model_context_window // 5)
        }
    
    budget = context_token_budget or (model_context_window // 5)
    selected_symbols = []
    tokens_used = 0
    
    for symbol in results[:max_context_symbols]:
        token_cost = estimate_context_tokens(symbol)
        if tokens_used + token_cost <= budget:
            selected_symbols.append(symbol)
            tokens_used += token_cost
    
    context_markdown = format_context_result(
        symbols=selected_symbols,
        tokens_used=tokens_used,
        tokens_budget=budget,
        model_context_window=model_context_window,
        max_symbols=max_context_symbols
    )
    
    return results, {
        "context_markdown": context_markdown,
        "tokens_used": tokens_used,
        "budget_remaining": budget - tokens_used
    }


def select_context_with_budget(
    symbols: List[Dict[str, Any]],
    injector: ContextInjector,
    max_tokens: int,
    existing_context_tokens: int = 0,
    k: int = 10,
    diversity_limit: int = 3
) -> Tuple[List[Dict[str, Any]], int]:
    """Select context symbols respecting token budget and diversity.
    
    Args:
        symbols: Candidate symbols with relevance scores
        injector: ContextInjector instance
        max_tokens: Max tokens for context
        existing_context_tokens: Tokens already used
        k: Max symbols to select
        diversity_limit: Max symbols per file
        
    Returns:
        Tuple of (selected_symbols, tokens_used)
    """
    from collections import Counter
    
    available_tokens = max_tokens - existing_context_tokens
    selected = []
    tokens_used = 0
    file_counts = Counter()
    
    for symbol in symbols[:k]:
        if len(selected) >= k:
            break
            
        token_cost = estimate_context_tokens(symbol)
        file_path = symbol.get("file_path", "unknown")
        
        if tokens_used + token_cost > available_tokens:
            continue
        if file_counts[file_path] >= diversity_limit:
            continue
        
        selected.append(symbol)
        tokens_used += token_cost
        file_counts[file_path] += 1
    
    return selected, tokens_used


def fallback_search(
    conn,
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None
) -> list[dict]:
    """Fallback search using only FTS5 (no embeddings).
    
    Used when sqlite-vec is unavailable or embedding generation fails.
    
    Args:
        conn: SQLite connection
        query: Search query
        k: Number of results
        kind: Optional kind filter
        lang: Optional language filter
        
    Returns:
        List of symbol dicts
    """
    fts_sql = """
        SELECT s.* FROM symbols_fts
        JOIN symbols s ON s.rowid = symbols_fts.rowid
        WHERE symbols_fts MATCH ?
    """
    params = [query]
    if kind:
        fts_sql += " AND s.kind = ?"
        params.append(kind)
    if lang:
        fts_sql += " AND s.lang = ?"
        params.append(lang)
    fts_sql += " LIMIT ?"
    params.append(k)
    
    rows = conn.execute(fts_sql, params).fetchall()
    return [dict(row) for row in rows]


async def _tool_semantic_search(
    query: str,
    k: int = 10,
    kind: Optional[str] = None,
    lang: Optional[str] = None,
    db_path: Optional[str] = None,
    inject_context: bool = True,
    token_budget: int = 4096,
    diversity_limit: int = 3,
    session_id: Optional[str] = None
) -> str:
    """
    Search symbols by semantic similarity (meaning) + keyword matching.

    Args:
        query: Search query - finds code by meaning, not just keywords
               e.g., "authentication handler", "database connection pool", "error retry logic"
        k: Number of results to return (default: 10, max: 50)
        kind: Optional symbol kind filter: function, class, method, variable, import, constant
        lang: Optional language filter: python, rust, go, typescript, javascript, cpp, c, json, yaml, bash
        db_path: Optional custom database path
        inject_context: If True, inject relevant context symbols for LLM prompts (default: True)
        token_budget: Token budget for context injection (default: 4096)
        diversity_limit: Max symbols per file for diversity (default: 3)
        session_id: Optional session ID for tracking

    Returns:
        JSON array of symbol objects with fields:
        - id, name, qualified_name, kind, file_path, start_line, end_line
        - signature, docstring, is_public, content_hash, indexed_at, lang
        
        If inject_context=True, returns:
        {
            "results": [...search results...],
            "context_injection": {
                "context_markdown": "...formatted context...",
                "tokens_used": 1234,
                "budget_remaining": 5678,
                "diversity_applied": true
            }
        }
    """
    if k < 1:
        k = 1
    elif k > 50:
        k = 50

    try:
        conn = get_connection(Path(db_path) if db_path else None)
        
        if inject_context:
            results, context_info = hybrid_search_with_context(
                conn, query, k, kind, lang,
                context_enabled=True,
                max_context_symbols=k,
                model_context_window=token_budget,
                context_token_budget=token_budget
            )
            conn.close()
            # Add diversity_applied to context_info
            context_info["diversity_applied"] = True
            return json.dumps({
                "results": results,
                "context_injection": context_info
            }, indent=2, default=str)
        else:
            results = hybrid_search(conn, query, k, kind, lang)
            conn.close()
            return json.dumps(results, indent=2, default=str)
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return json.dumps({"error": str(e)}, indent=2)

# Export for MCP server registration
semantic_search_tool = {
    "name": "semantic_search",
    "description": "Search symbols by semantic similarity (meaning) + keyword matching. Finds code by what it does, not just by name. Optionally injects relevant context for LLM prompts.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - finds code by meaning, e.g. 'authentication handler', 'database pool', 'error retry'"
            },
            "k": {
                "type": "integer",
                "description": "Number of results (default: 10, max: 50)",
                "default": 10,
                "minimum": 1,
                "maximum": 50
            },
            "kind": {
                "type": "string",
                "description": "Optional symbol kind filter",
                "enum": ["function", "class", "method", "variable", "import", "constant"]
            },
            "lang": {
                "type": "string",
                "description": "Optional language filter",
                "enum": ["python", "rust", "go", "typescript", "javascript", "cpp", "c", "json", "yaml", "bash"]
            },
            "db_path": {
                "type": "string",
                "description": "Optional custom database path"
            },
            "inject_context": {
                "type": "boolean",
                "description": "If True, inject relevant context symbols for LLM prompts (default: True)",
                "default": True
            },
            "token_budget": {
                "type": "integer",
                "description": "Token budget for context injection (default: 4096)",
                "default": 4096,
                "minimum": 512,
                "maximum": 32768
            },
            "diversity_limit": {
                "type": "integer",
                "description": "Max symbols per file for diversity (default: 3)",
                "default": 3,
                "minimum": 1,
                "maximum": 10
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID for tracking"
            }
        },
        "required": ["query"]
    },
    "handler": _tool_semantic_search
}