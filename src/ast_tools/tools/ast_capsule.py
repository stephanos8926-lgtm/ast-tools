"""ast_capsule tool — One-shot consolidated symbol overview.

Inspired by code-intel-plugin's code_capsule.
Combines: signature + docstring + references + imports + callers in one call.
"""

from typing import Any


def _tool_ast_capsule(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get a complete, consolidated overview of a symbol in one call.
    
    Combines multiple data points that would normally require 4-5 separate tool calls:
    - Symbol signature and docstring
    - File location and line numbers
    - Import statements
    - References/usages
    - Caller/callee relationships
    - Related symbols
    
    Args:
        symbol_name: Name of the symbol (function, class, method, variable)
        file_path: Optional file path to search in (default: current directory)
        language: Optional language filter (python, typescript, etc.)
        include_callers: Include functions that call this symbol (default: True)
        include_callees: Include functions this symbol calls (default: True)
        include_docs: Include docstrings and type hints (default: True)
    
    Returns:
        Consolidated capsule with all symbol information
    """
    symbol_name = args.get("symbol_name")
    
    if not symbol_name:
        return {
            "error": "symbol_name is required",
            "example": "ast_capsule(symbol_name='authenticate', file_path='src/auth.py')",
        }
    
    file_path = args.get("file_path", ".")
    language = args.get("language", "python")
    include_callers = args.get("include_callers", True)
    include_callees = args.get("include_callees", True)
    include_docs = args.get("include_docs", True)
    
    capsule = {
        "symbol": symbol_name,
        "file": file_path,
        "language": language,
        "sections": {},
        "summary": [],
    }
    
    # 1. Get basic symbol info (signature, location, docs)
    try:
        from .ast_read import _tool_ast_read
        
        read_result = _tool_ast_read({
            "file": file_path,
            "include_private": False,
            "include_imports": True,
        })
        
        if "error" in read_result:
            capsule["sections"]["read_error"] = read_result["error"]
        else:
            # Extract relevant symbol from file
            symbol_info = _extract_symbol_from_read(read_result, symbol_name)
            if symbol_info:
                capsule["sections"]["definition"] = symbol_info
                
                if include_docs and symbol_info.get("docstring"):
                    capsule["sections"]["documentation"] = {
                        "docstring": symbol_info["docstring"],
                        "signature": symbol_info.get("signature"),
                    }
                
                if symbol_info.get("imports"):
                    capsule["sections"]["imports"] = symbol_info["imports"]
            
            capsule["summary"].append(f"📍 Found in {file_path}")
            
    except ImportError:
        capsule["sections"]["read_error"] = "ast_read not available"
    
    # 2. Get references/usages
    if include_callers:
        try:
            from .find_references import _tool_find_references
            
            refs_result = _tool_find_references({
                "symbol": symbol_name,
                "file_path": file_path,
            })
            
            # Fix B: Check actual return shape - "references" not "matches"
            if refs_result.get("references"):
                capsule["sections"]["references"] = {
                    "count": refs_result.get("count", len(refs_result["references"])),
                    "locations": refs_result["references"][:10],
                }
                capsule["summary"].append(f"🔗 Found {refs_result.get('count', len(refs_result['references']))} references")
            elif "error" not in refs_result:
                capsule["sections"]["references"] = {"count": 0, "note": "No references found"}
            else:
                capsule["sections"]["references_error"] = refs_result["error"]
                
        except ImportError:
            capsule["sections"]["references_error"] = "find_references not available"
    
    # 3. Get callers (who calls this symbol)
    try:
        from .structural_analysis import _tool_structural_analysis
        
        analysis_result = _tool_structural_analysis({
            "file_path": file_path,
            "symbol_name": symbol_name,
            "analysis_type": "callers",
        })
        
        if "callers" in analysis_result:
            capsule["sections"]["callers"] = {
                "count": len(analysis_result["callers"]),
                "list": analysis_result["callers"][:10],
            }
            capsule["summary"].append(f"⬆️ Called by {len(analysis_result['callers'])} functions")
            
    except (ImportError, KeyError):
        # structural_analysis might not have callers analysis
        pass
    
    # 4. Get callees (what this symbol calls)
    if include_callees:
        try:
            # Try structural analysis for callees
            from .structural_analysis import _tool_structural_analysis
            
            analysis_result = _tool_structural_analysis({
                "file_path": file_path,
                "symbol_name": symbol_name,
                "analysis_type": "callees",
            })
            
            if "callees" in analysis_result:
                capsule["sections"]["callees"] = {
                    "count": len(analysis_result["callees"]),
                    "list": analysis_result["callees"][:10],
                }
                capsule["summary"].append(f"⬇️ Calls {len(analysis_result['callees'])} functions")
                
        except (ImportError, KeyError):
            pass
    
    # 5. Get impact analysis (what breaks if this changes)
    try:
        from .impact_analysis import _tool_impact_analysis
        
        impact_result = _tool_impact_analysis({
            "target": symbol_name,  # Fixed: use 'target'
            "cwd": file_path,
        })
        
        if "affected_files" in impact_result:
            capsule["sections"]["impact"] = {
                "affected_files": impact_result["affected_files"],
                "risk_level": impact_result.get("risk_level", impact_result.get("risk", "unknown")),
            }
            capsule["summary"].append(f"⚠️ Impact: {impact_result.get('risk', 'unknown')} risk")
            
    except (ImportError, KeyError, TypeError) as e:
        # Impact analysis may not be available or params may differ
        capsule["sections"]["impact_note"] = f"Impact analysis unavailable: {type(e).__name__}"
    
    # 6. Generate quick summary
    if not capsule["summary"]:
        capsule["summary"].append("ℹ️ Limited information available")
    
    # 7. Add quick actions
    capsule["quick_actions"] = [
        {"action": "edit", "tool": "ast_edit", "hint": "Modify this symbol"},
        {"action": "rename", "tool": "ast_edit", "hint": "Rename across all references"},
        {"action": "test", "tool": "find_references", "hint": "Find tests for this symbol"},
        {"action": "validate", "tool": "code_validate_syntax", "hint": "Check syntax"},
    ]
    
    return capsule


def _extract_symbol_from_read(read_result: dict, symbol_name: str) -> dict | None:
    """Extract a specific symbol's info from ast_read result."""
    # Look in functions, classes, etc.
    for category in ["functions", "classes", "methods", "variables"]:
        if category in read_result:
            for item in read_result[category]:
                if item.get("name") == symbol_name:
                    return item
    
    return None


# Export for MCP server registration
ast_capsule_tool = {
    "name": "ast_capsule",
    "description": """Get a complete, consolidated overview of a symbol in one call.

Combines what would normally require 4-5 separate tool calls:
- Symbol signature, location, and docstring
- Import statements
- References and usages across the codebase
- Caller/callee relationships
- Impact analysis (what breaks if this changes)
- Quick action recommendations

Perfect for:
- Understanding a symbol quickly
- Pre-refactoring reconnaissance
- Code review preparation
- Onboarding to a new codebase

Example:
  ast_capsule(symbol_name='authenticate', file_path='src/auth.py')
  → Returns everything you need to know about 'authenticate' in one response""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol_name": {
                "type": "string",
                "description": "Name of the symbol (function, class, method, variable)",
            },
            "file_path": {
                "type": "string",
                "description": "File path to search in (default: current directory)",
                "default": ".",
            },
            "language": {
                "type": "string",
                "description": "Programming language",
                "default": "python",
                "enum": ["python", "typescript", "javascript", "rust", "go", "java", "cpp", "c"],
            },
            "include_callers": {
                "type": "boolean",
                "description": "Include functions that call this symbol",
                "default": True,
            },
            "include_callees": {
                "type": "boolean",
                "description": "Include functions this symbol calls",
                "default": True,
            },
            "include_docs": {
                "type": "boolean",
                "description": "Include docstrings and type hints",
                "default": True,
            },
        },
        "required": ["symbol_name"],
    },
    "handler": _tool_ast_capsule,
}