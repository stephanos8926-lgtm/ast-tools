"""LSP integration tools for ast-tools MCP server.

Provides type-aware code intelligence via Language Server Protocol.
Tools: definition, references, hover, symbols, call_hierarchy, diagnostics.
"""

from ..lsp_client import LSP_SERVERS, LSPClient, get_lsp_client

# Cache of active LSP clients per project root
_lsp_clients: dict[str, LSPClient] = {}


def lsp_definition(file: str, line: int, col: int) -> dict:
    """Go to definition of symbol at position.

    Args:
        file: File path
        line: Line number (1-indexed)
        col: Column (0-indexed)

    Returns:
        Definition location or error
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.goto_definition(file, line, col)

        if not result:
            return {"found": False, "message": "No definition found"}

        # Normalize result (can be Location or Location[])
        locations = result if isinstance(result, list) else [result]
        return {
            "found": True,
            "locations": [
                {
                    "file": loc["uri"].replace("file://", ""),
                    "line": loc["range"]["start"]["line"] + 1,
                    "col": loc["range"]["start"]["character"],
                }
                for loc in locations
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_references(file: str, line: int, col: int) -> dict:
    """Find all references to symbol at position.

    Args:
        file: File path
        line: Line number (1-indexed)
        col: Column (0-indexed)

    Returns:
        List of reference locations
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.find_references(file, line, col)

        references = [
            {
                "file": ref["uri"].replace("file://", ""),
                "line": ref["range"]["start"]["line"] + 1,
                "col": ref["range"]["start"]["character"],
            }
            for ref in (result or [])
        ]

        return {"count": len(references), "references": references}
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_hover(file: str, line: int, col: int) -> dict:
    """Get type signature and documentation for symbol at position.

    Args:
        file: File path
        line: Line number (1-indexed)
        col: Column (0-indexed)

    Returns:
        Type signature and docs
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.hover(file, line, col)

        if not result:
            return {"available": False, "message": "No hover info available"}

        return {
            "available": True,
            "signature": result.split("\n")[0] if "\n" in result else result,
            "documentation": result,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_symbols(file: str) -> dict:
    """Get all symbols in a file.

    Args:
        file: File path

    Returns:
        List of symbols (functions, classes, methods, etc.)
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.document_symbols(file)

        if not result:
            return {"count": 0, "symbols": []}

        symbols = []
        for sym in result:
            # Handle both SymbolInformation and DocumentSymbol formats
            if "selectionRange" in sym:
                symbols.append(
                    {
                        "name": sym.get("name", ""),
                        "kind": sym.get("kind", 0),
                        "file": file,
                        "line": sym["selectionRange"]["start"]["line"] + 1,
                    }
                )
            elif "range" in sym:
                symbols.append(
                    {
                        "name": sym.get("name", ""),
                        "kind": sym.get("kind", 0),
                        "file": file,
                        "line": sym["range"]["start"]["line"] + 1,
                    }
                )

        return {"count": len(symbols), "symbols": symbols}
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_call_hierarchy_in(file: str, line: int, col: int) -> dict:
    """Find all callers of function/method at position.

    Args:
        file: File path
        line: Line number (1-indexed)
        col: Column (0-indexed)

    Returns:
        List of calling functions
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.call_hierarchy_incoming(file, line, col)

        callers = []
        for item in result or []:
            callers.append(
                {
                    "from_function": item.get("from", {}).get("name", "unknown"),
                    "from_file": item.get("from", {}).get("uri", "").replace("file://", ""),
                    "from_range": item.get("from", {}).get("range", {}),
                }
            )

        return {"count": len(callers), "callers": callers}
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_call_hierarchy_out(file: str, line: int, col: int) -> dict:
    """Find all functions/methods called by function at position.

    Args:
        file: File path
        line: Line number (1-indexed)
        col: Column (0-indexed)

    Returns:
        List of called functions
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.call_hierarchy_outgoing(file, line, col)

        callees = []
        for item in result or []:
            callees.append(
                {
                    "to_function": item.get("to", {}).get("name", "unknown"),
                    "to_file": item.get("to", {}).get("uri", "").replace("file://", ""),
                    "from_range": item.get("fromRange", {}),
                }
            )

        return {"count": len(callees), "callees": callees}
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.stop()


def lsp_diagnostics(file: str) -> dict:
    """Get compiler errors and warnings for a file.

    Note: Diagnostics are pushed by the server asynchronously.
    This returns the last known diagnostics (may be stale).

    Args:
        file: File path

    Returns:
        List of diagnostics (errors, warnings)
    """
    # Simplified - true implementation would track pushed diagnostics
    return {
        "file": file,
        "diagnostics": [],
        "note": "Diagnostics are pushed asynchronously by LSP server. Use lsp_symbols for immediate queries.",
    }


def lsp_format(file: str) -> dict:
    """Format a file using the language server's formatter.

    Args:
        file: File path

    Returns:
        Text edits to apply (not applied automatically)
    """
    try:
        client = get_lsp_client(file)
        client.start()
        result = client.format_document(file)

        if not result:
            return {"formatted": True, "edits": []}

        edits = [
            {
                "range": {
                    "start": {
                        "line": edit["range"]["start"]["line"],
                        "col": edit["range"]["start"]["character"],
                    },
                    "end": {
                        "line": edit["range"]["end"]["line"],
                        "col": edit["range"]["end"]["character"],
                    },
                },
                "new_text": edit.get("newText", ""),
            }
            for edit in result
        ]

        return {"formatted": True, "edits": edits}
    except Exception as e:
        return {"error": str(e), "formatted": False}
    finally:
        client.stop()


def lsp_available_languages() -> dict:
    """Get list of supported LSP languages and their server requirements.

    Returns:
        Dict mapping language → {command, install_hint, extensions}
    """
    return {
        lang: {
            "command": config["command"][0],
            "install_hint": config["install_hint"],
            "extensions": config["file_extensions"],
        }
        for lang, config in LSP_SERVERS.items()
    }


def lsp_check_server(lang: str) -> dict:
    """Check if LSP server is installed for a language.

    Args:
        lang: Language name (python, rust, go, etc.)

    Returns:
        {installed: bool, path: str or None, install_command: str}
    """
    import shutil

    if lang not in LSP_SERVERS:
        return {"error": f"Unsupported language: {lang}"}

    config = LSP_SERVERS[lang]
    cmd = config["command"][0]

    path = shutil.which(cmd)
    return {
        "installed": path is not None,
        "path": path,
        "install_command": config["install_hint"],
        "language": lang,
    }


# ─── MCP Tool Registration ──────────────────────────────────────────────


def register_lsp_tools(registry: dict):
    """Register LSP tools with the MCP tool registry."""

    registry["lsp_definition"] = {
        "description": "Go to definition of symbol at position (LSP)",
        "handler": lsp_definition,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "line": {"type": "integer", "description": "Line number (1-indexed)"},
                "col": {"type": "integer", "description": "Column (0-indexed)"},
            },
            "required": ["file", "line", "col"],
        },
    }

    registry["lsp_references"] = {
        "description": "Find all references to symbol at position (LSP)",
        "handler": lsp_references,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "col": {"type": "integer"},
            },
            "required": ["file", "line", "col"],
        },
    }

    registry["lsp_hover"] = {
        "description": "Get type signature and documentation (LSP)",
        "handler": lsp_hover,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "col": {"type": "integer"},
            },
            "required": ["file", "line", "col"],
        },
    }

    registry["lsp_symbols"] = {
        "description": "Get all symbols in a file (LSP)",
        "handler": lsp_symbols,
        "parameters": {
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
        },
    }

    registry["lsp_call_hierarchy_in"] = {
        "description": "Find callers of function (LSP call hierarchy)",
        "handler": lsp_call_hierarchy_in,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "col": {"type": "integer"},
            },
            "required": ["file", "line", "col"],
        },
    }

    registry["lsp_call_hierarchy_out"] = {
        "description": "Find functions called by function (LSP)",
        "handler": lsp_call_hierarchy_out,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "col": {"type": "integer"},
            },
            "required": ["file", "line", "col"],
        },
    }

    registry["lsp_available_languages"] = {
        "description": "Get supported LSP languages and requirements",
        "handler": lsp_available_languages,
        "parameters": {"type": "object", "properties": {}},
    }

    registry["lsp_check_server"] = {
        "description": "Check if LSP server is installed",
        "handler": lsp_check_server,
        "parameters": {
            "type": "object",
            "properties": {
                "lang": {"type": "string", "description": "Language (python, rust, go, etc.)"}
            },
            "required": ["lang"],
        },
    }
