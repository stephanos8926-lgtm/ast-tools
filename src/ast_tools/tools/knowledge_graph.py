"""Knowledge Graph querying MCP tools.

Provides kg_query, kg_shortest_path, and kg_neighborhood tools
that wrap GraphEngine with semantic-search-based symbol resolution.
"""

from pathlib import Path
from typing import Any


def _get_graph_engine():
    """Lazy import GraphEngine to avoid circular dependencies."""
    try:
        from ast_tools.kg.graph_engine import GraphEngine

        return GraphEngine
    except ImportError:
        raise ImportError(
            "GraphEngine is not available. "
            "Please ensure ast_tools.kg.graph_engine is installed."
        )


def _get_db_path_resolver():
    """Lazy import the database path resolver."""
    try:
        from ast_tools.database.connection import get_db_path

        return get_db_path
    except ImportError:
        raise ImportError(
            "Database connection utilities are not available. "
            "Please ensure ast_tools.database.connection is installed."
        )


def _get_symbol_searcher():
    """Lazy import the semantic search function."""
    try:
        from ast_tools.tools.semantic_search import _tool_semantic_search

        return _tool_semantic_search
    except ImportError:
        raise ImportError(
            "Symbol search tool is not available. "
            "Please ensure ast_tools.tools.semantic_search is installed."
        )


def _resolve_db_path(db_path: str | None) -> str:
    """Resolve database path, falling back to default if None."""
    if db_path:
        return db_path
    try:
        get_db_path = _get_db_path_resolver()
        return str(get_db_path())
    except Exception:
        return str(Path.home() / ".cache" / "ast-tools" / "codebase.db")


def _safe_search(search_fn, query: str, k: int = 10) -> list[dict]:
    """Run semantic search and safely extract results list."""
    try:
        result = search_fn({"query": query, "k": k})
        return result.get("results", []) if isinstance(result, dict) else []
    except Exception:
        return []


def _tool_kg_query(args: dict[str, Any]) -> dict[str, Any]:
    """Natural language query against the knowledge graph.

    Uses semantic_search to find the starting symbol, then neighborhood traversal.

    Args:
        query: Natural language query (e.g., 'authentication handler')
        max_depth: How many hops to traverse (default: 2)
        max_nodes: Max nodes to return (default: 50)
        db_path: Override database path (optional)

    Returns:
        dict with query, starting_symbols, neighborhood, total_symbols_found
    """
    query = args.get("query")
    max_depth = args.get("max_depth", 2)
    max_nodes = args.get("max_nodes", 50)
    db_path = args.get("db_path")

    if not query:
        raise ValueError("Query is required.")

    GraphEngine = _get_graph_engine()
    resolved_db_path = _resolve_db_path(db_path)

    starting_symbols = _safe_search(
        _get_symbol_searcher(), query, k=10
    )

    if not starting_symbols:
        return {
            "query": query,
            "starting_symbols": [],
            "neighborhood": {},
            "total_symbols_found": 0,
        }

    start_symbol_id = starting_symbols[0].get("symbol_id")
    if not start_symbol_id:
        return {
            "query": query,
            "starting_symbols": starting_symbols,
            "neighborhood": {},
            "total_symbols_found": len(starting_symbols),
        }

    engine = GraphEngine(db_path=resolved_db_path)
    neighborhood = engine.get_neighborhood(
        start_symbol_id, max_depth=max_depth, max_nodes=max_nodes
    )

    return {
        "query": query,
        "starting_symbols": starting_symbols,
        "neighborhood": neighborhood,
        "total_symbols_found": len(starting_symbols),
    }


def _tool_kg_shortest_path(args: dict[str, Any]) -> dict[str, Any]:
    """Find shortest path between two symbols.

    Uses semantic_search to resolve symbol names to IDs, then
    GraphEngine.shortest_path().

    Args:
        from_symbol: Starting symbol name or query
        to_symbol: Target symbol name or query
        max_depth: Max path length (default: 10)
        db_path: Override database path (optional)

    Returns:
        dict with from, to, path, distance, nodes, edges
        OR if no path: from, to, found=False, message
    """
    from_symbol_query = args.get("from_symbol")
    to_symbol_query = args.get("to_symbol")
    max_depth = args.get("max_depth", 10)
    db_path = args.get("db_path")

    if not from_symbol_query or not to_symbol_query:
        raise ValueError("from_symbol and to_symbol are required.")

    searcher = _get_symbol_searcher()
    resolved_db_path = _resolve_db_path(db_path)

    from_results = _safe_search(searcher, from_symbol_query, k=1)
    to_results = _safe_search(searcher, to_symbol_query, k=1)

    from_symbol_data = from_results[0] if from_results else {}
    to_symbol_data = to_results[0] if to_results else {}

    from_id = from_symbol_data.get("symbol_id")
    to_id = to_symbol_data.get("symbol_id")

    if not from_id:
        return {
            "from": {"symbol": from_symbol_query, "match": None},
            "to": {
                "symbol": to_symbol_query,
                "match": to_symbol_data.get("symbol"),
            },
            "found": False,
            "message": f"Start symbol '{from_symbol_query}' not found.",
        }
    if not to_id:
        return {
            "from": {
                "symbol": from_symbol_query,
                "match": from_symbol_data.get("symbol"),
            },
            "to": {"symbol": to_symbol_query, "match": None},
            "found": False,
            "message": f"Target symbol '{to_symbol_query}' not found.",
        }

    GraphEngine = _get_graph_engine()
    engine = GraphEngine(db_path=resolved_db_path)
    path_data = engine.shortest_path(
        from_id=from_id, to_id=to_id, max_depth=max_depth
    )

    if path_data and path_data.get("distance", -1) >= 0:
        return {
            "from": {
                "symbol": from_symbol_query,
                "match": from_symbol_data.get("symbol"),
            },
            "to": {
                "symbol": to_symbol_query,
                "match": to_symbol_data.get("symbol"),
            },
            "path": path_data.get("path", []),
            "distance": path_data.get("distance"),
            "nodes": path_data.get("nodes", []),
            "edges": path_data.get("edges", []),
        }
    else:
        return {
            "from": {
                "symbol": from_symbol_query,
                "match": from_symbol_data.get("symbol"),
            },
            "to": {
                "symbol": to_symbol_query,
                "match": to_symbol_data.get("symbol"),
            },
            "found": False,
            "message": (
                f"No path found between '{from_symbol_query}' and "
                f"'{to_symbol_query}' within max depth {max_depth}."
            ),
        }


def _tool_kg_neighborhood(args: dict[str, Any]) -> dict[str, Any]:
    """Get all related symbols within N hops of a symbol.

    Args:
        symbol: Symbol name or query to find the center point
        max_depth: How many hops (default: 2)
        max_nodes: Max nodes (default: 50)
        db_path: Override database path (optional)

    Returns:
        dict with symbol, match, max_depth, max_nodes, neighborhood,
        total_symbols_found
    """
    symbol_query = args.get("symbol")
    max_depth = args.get("max_depth", 2)
    max_nodes = args.get("max_nodes", 50)
    db_path = args.get("db_path")

    if not symbol_query:
        raise ValueError("Symbol query is required.")

    resolved_db_path = _resolve_db_path(db_path)
    results = _safe_search(_get_symbol_searcher(), symbol_query, k=1)

    if not results:
        return {
            "symbol": symbol_query,
            "match": None,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "neighborhood": {},
            "total_symbols_found": 0,
            "message": f"Symbol '{symbol_query}' not found.",
        }

    symbol_data = results[0]
    symbol_id = symbol_data.get("symbol_id")

    if not symbol_id:
        return {
            "symbol": symbol_query,
            "match": symbol_data.get("symbol"),
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "neighborhood": {},
            "total_symbols_found": 0,
            "message": f"Symbol '{symbol_query}' has no ID.",
        }

    GraphEngine = _get_graph_engine()
    engine = GraphEngine(db_path=resolved_db_path)
    neighborhood = engine.get_neighborhood(
        symbol_id, max_depth=max_depth, max_nodes=max_nodes
    )

    return {
        "symbol": symbol_query,
        "match": symbol_data.get("symbol"),
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "neighborhood": neighborhood,
        "total_symbols_found": 1,
    }


# ---------------------------------------------------------------------------
# Public tool entry points (aliases for MCP registration)
# ---------------------------------------------------------------------------

def kg_query(args: dict[str, Any]) -> dict[str, Any]:
    """Natural language knowledge graph query — find related symbols."""
    return _tool_kg_query(args)


def kg_shortest_path(args: dict[str, Any]) -> dict[str, Any]:
    """Find shortest path between two symbols via graph traversal."""
    return _tool_kg_shortest_path(args)


def kg_neighborhood(args: dict[str, Any]) -> dict[str, Any]:
    """Get all symbols related to a given symbol within N hops."""
    return _tool_kg_neighborhood(args)
