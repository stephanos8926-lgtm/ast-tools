"""ast_query tool — Smart router: describe intent, get best tool.

Inspired by code-intel-plugin's code_query.
Routes natural language intents to the best ast-tools capability.
"""

import json
from pathlib import Path
from typing import Any


# Intent patterns → tool mapping
_INTENT_PATTERNS = {
    # Symbol discovery
    "find_symbol": ["find", "locate", "where is", "show me", "what does", "list"],
    "find_symbol_keywords": ["function", "class", "method", "variable", "constant", "interface", "type"],
    
    # Usage tracking
    "find_usage": ["used by", "usage", "callers", "references", "who calls", "where used"],
    
    # Structural search
    "structural_search": ["pattern", "structure", "all imports", "all decorators", "all returns"],
    
    # Refactoring
    "refactor": ["rename", "replace", "change", "modify", "update", "refactor"],
    
    # Impact analysis
    "impact": ["impact", "affect", "break", "depend", "dependency", "blast radius"],
    
    # Semantic search
    "semantic": ["similar", "like", "meaning", "concept", "find by meaning"],
    
    # Definition
    "definition": ["definition", "defined", "implementation", "source"],
    
    # Documentation
    "docs": ["document", "docstring", "signature", "overview", "summary"],
    
    # Validation
    "validate": ["validate", "check", "lint", "syntax", "error"],
}


def _detect_intent(query: str) -> str:
    """Detect user intent from natural language query."""
    query_lower = query.lower()
    
    # Score each intent category
    scores = {}
    
    for intent, keywords in _INTENT_PATTERNS.items():
        if intent == "find_symbol_keywords":
            continue
            
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[intent] = score
    
    # Boost with keyword patterns
    if any(kw in query_lower for kw in _INTENT_PATTERNS["find_symbol_keywords"]):
        if "find" in query_lower or "where" in query_lower:
            scores["find_symbol"] = scores.get("find_symbol", 0) + 2
    
    # Return highest scoring intent
    if scores:
        return max(scores, key=scores.get)
    
    return "unknown"


def _tool_ast_query(args: dict[str, Any]) -> dict[str, Any]:
    """
    Smart router: describe what you want, get the best tool recommendation.
    
    Args:
        intent: Natural language description of what you want to do
        file: Optional file path to focus on
        symbol: Optional symbol name to search for
        language: Optional language filter (python, typescript, etc.)
    
    Returns:
        Recommended tool name, parameters, and explanation
    """
    intent = args.get("intent", "")
    file_path = args.get("file")
    symbol = args.get("symbol")
    language = args.get("language")
    
    if not intent and not symbol:
        return {
            "error": "Either 'intent' or 'symbol' must be provided",
            "example": "ast_query(intent='find all callers of authenticate function')",
        }
    
    # Detect intent
    detected_intent = _detect_intent(intent or f"find {symbol}")
    
    # Route to appropriate tool
    routing = {
        "find_symbol": {
            "tool": "ast_read" if file_path else "search_symbols",
            "params": {
                "file": file_path,
                "include_private": False,
            } if file_path else {
                "query": symbol or "",
                "kind": None,
                "lang": language,
            },
            "explanation": "Extracting symbol information from code",
        },
        "find_usage": {
            "tool": "find_references",
            "params": {
                "symbol_name": symbol or "",
                "file_path": file_path or ".",
            },
            "explanation": "Finding all references/usages of a symbol",
        },
        "structural_search": {
            "tool": "ast_grep",
            "params": {
                "pattern": f"$SYMBOL",  # Generic pattern
                "path": file_path or ".",
                "lang": language or "python",
            },
            "explanation": "Searching for structural patterns in code",
            "hint": "Provide a more specific pattern for better results",
        },
        "refactor": {
            "tool": "ast_edit" if "rename" in intent.lower() else "ast_grep",
            "params": {
                "file": file_path,
                "dry_run": True,
            } if file_path else {
                "pattern": "$OLD",
                "path": ".",
                "lang": language or "python",
            },
            "explanation": "Performing structural refactoring",
            "warning": "Always use dry_run=True first to preview changes",
        },
        "impact": {
            "tool": "impact_analysis",
            "params": {
                "symbol_name": symbol or "",
                "file_path": file_path or ".",
            },
            "explanation": "Analyzing impact/dependencies of changes",
        },
        "semantic": {
            "tool": "semantic_search",
            "params": {
                "query": intent or f"find {symbol}",
                "k": 10,
                "lang": language,
            },
            "explanation": "Searching code by semantic meaning",
        },
        "definition": {
            "tool": "find_symbol_definition",
            "params": {
                "symbol_name": symbol or "",
                "file_path": file_path or ".",
            },
            "explanation": "Finding where a symbol is defined",
        },
        "docs": {
            "tool": "ast_read",
            "params": {
                "file": file_path,
                "include_private": False,
                "filter_by_type": ["function", "class"],
            },
            "explanation": "Extracting documentation and signatures",
        },
        "validate": {
            "tool": "code_validate_syntax",
            "params": {
                "file": file_path or ".",
                "lang": language,
            },
            "explanation": "Validating code syntax",
        },
        "unknown": {
            "tool": "semantic_search",
            "params": {
                "query": intent or symbol or "",
                "k": 10,
            },
            "explanation": "Fallback to semantic search",
            "suggestion": "Try being more specific: 'find callers', 'rename function', 'find imports'",
        },
    }
    
    recommendation = routing.get(detected_intent, routing["unknown"])
    
    # Override file/language if provided
    if file_path and "file" in recommendation["params"]:
        recommendation["params"]["file"] = file_path
    
    if language and "lang" in recommendation["params"]:
        recommendation["params"]["lang"] = language
    
    return {
        "detected_intent": detected_intent,
        "confidence": "high" if detected_intent != "unknown" else "low",
        "recommended_tool": recommendation["tool"],
        "recommended_params": recommendation["params"],
        "explanation": recommendation["explanation"],
        "hint": recommendation.get("hint"),
        "warning": recommendation.get("warning"),
        "suggestion": recommendation.get("suggestion"),
        "alternative_tools": _get_alternatives(detected_intent),
    }


def _get_alternatives(intent: str) -> list[str]:
    """Get alternative tools for an intent."""
    alternatives = {
        "find_symbol": ["search_symbols", "list_symbols", "codebase_summary"],
        "find_usage": ["structural_analysis", "lsp_references"],
        "structural_search": ["semantic_search", "search_symbols"],
        "refactor": ["ast_refactor_extract_interface", "impact_analysis"],
        "impact": ["dependency_chain", "circular_dependencies"],
        "semantic": ["search_symbols", "ast_grep"],
        "definition": ["ast_read", "structural_analysis"],
        "docs": ["codebase_summary", "project_info"],
        "validate": ["ast_read", "lint"],
    }
    return alternatives.get(intent, ["semantic_search"])


# Export for MCP server registration
ast_query_tool = {
    "name": "ast_query",
    "description": """Smart router for code intelligence: describe what you want in natural language, get the best tool recommendation.
    
Examples:
- "find all callers of authenticate function" → find_references
- "rename this function everywhere" → ast_edit (with dry_run)
- "what does this file contain?" → ast_read
- "find similar code patterns" → semantic_search
- "what will break if I change this?" → impact_analysis

Saves you from memorizing 39 tool names — just describe your intent!""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "Natural language description of what you want to do (e.g., 'find all callers', 'rename function', 'find imports')",
            },
            "file": {
                "type": "string",
                "description": "Optional file path to focus on",
            },
            "symbol": {
                "type": "string",
                "description": "Optional symbol name to search for",
            },
            "language": {
                "type": "string",
                "description": "Optional language filter (python, typescript, go, rust, etc.)",
                "enum": ["python", "typescript", "javascript", "rust", "go", "java", "cpp", "c"],
            },
        },
        "required": [],
    },
    "handler": _tool_ast_query,
}