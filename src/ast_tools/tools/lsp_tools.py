"""LSP integration tools for ast-tools MCP server.

Provides type-aware code intelligence via Language Server Protocol.
Phase 2: code actions, rename, completion, diagnostics, persistent sessions.

Tools:
  Phase 1: definition, references, hover, symbols, call_hierarchy,
           languages, check_server
  Phase 2: code_actions, rename, signature_help, workspace_symbols,
           completion, apply_format, diagnostics (fixed)
"""

from ..lsp_client import LSP_SERVERS, get_lsp_client, release_lsp_client


# ─── Phase 1 Tools (Refactored with persistent sessions) ──────────────────


def lsp_definition(file: str, line: int, col: int) -> dict:
    """Go to definition of symbol at position."""
    client = get_lsp_client(file)
    try:
        result = client.goto_definition(file, line, col)
        if not result:
            return {"found": False, "message": "No definition found"}
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
        release_lsp_client(client)


def lsp_references(file: str, line: int, col: int) -> dict:
    """Find all references to symbol at position."""
    client = get_lsp_client(file)
    try:
        result = client.find_references(file, line, col)
        return {
            "count": len(result),
            "references": [
                {
                    "file": ref["uri"].replace("file://", ""),
                    "line": ref["range"]["start"]["line"] + 1,
                    "col": ref["range"]["start"]["character"],
                }
                for ref in result
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_hover(file: str, line: int, col: int) -> dict:
    """Get type signature and documentation for symbol at position."""
    client = get_lsp_client(file)
    try:
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
        release_lsp_client(client)


def lsp_symbols(file: str) -> dict:
    """Get all symbols in a file."""
    client = get_lsp_client(file)
    try:
        result = client.document_symbols(file)
        if not result:
            return {"count": 0, "symbols": []}

        symbols = []
        for sym in result:
            if "selectionRange" in sym:
                symbols.append({
                    "name": sym.get("name", ""),
                    "kind": sym.get("kind", 0),
                    "file": file,
                    "line": sym["selectionRange"]["start"]["line"] + 1,
                })
            elif "range" in sym:
                symbols.append({
                    "name": sym.get("name", ""),
                    "kind": sym.get("kind", 0),
                    "file": file,
                    "line": sym["range"]["start"]["line"] + 1,
                })

        return {"count": len(symbols), "symbols": symbols}
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_call_hierarchy_in(file: str, line: int, col: int) -> dict:
    """Find all callers of function/method at position."""
    client = get_lsp_client(file)
    try:
        result = client.call_hierarchy_incoming(file, line, col)
        return {
            "count": len(result),
            "callers": [
                {
                    "from_function": item.get("from", {}).get("name", "unknown"),
                    "from_file": item.get("from", {}).get("uri", "").replace("file://", ""),
                    "from_range": item.get("from", {}).get("range", {}),
                }
                for item in result
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_call_hierarchy_out(file: str, line: int, col: int) -> dict:
    """Find all functions/methods called by function at position."""
    client = get_lsp_client(file)
    try:
        result = client.call_hierarchy_outgoing(file, line, col)
        return {
            "count": len(result),
            "callees": [
                {
                    "to_function": item.get("to", {}).get("name", "unknown"),
                    "to_file": item.get("to", {}).get("uri", "").replace("file://", ""),
                    "from_range": item.get("fromRange", {}),
                }
                for item in result
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


# ─── Phase 2 Tools ────────────────────────────────────────────────────────


def lsp_diagnostics(file: str) -> dict:
    """Get compiler errors and warnings for a file.

    Diagnostics are pushed asynchronously by the LSP server via
    textDocument/publishDiagnostics after the file is opened.
    Opens the file if needed to trigger the push.

    Returns:
        Dict with file path, diagnostics list, and summary counts.
    """
    client = get_lsp_client(file)
    try:
        diags = client.diagnostics(file)
        errors = [d for d in diags if d.get("severity", 0) == 1]
        warnings = [d for d in diags if d.get("severity", 0) == 2]
        infos = [d for d in diags if d.get("severity", 0) == 3]
        hints = [d for d in diags if d.get("severity", 0) == 4]
        return {
            "file": file,
            "count": len(diags),
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "hints": len(hints),
            "diagnostics": [
                {
                    "message": d.get("message", ""),
                    "severity": d.get("severity", 0),
                    "line": d.get("range", {}).get("start", {}).get("line", 0) + 1,
                    "col": d.get("range", {}).get("start", {}).get("character", 0),
                    "source": d.get("source", ""),
                    "code": d.get("code", ""),
                }
                for d in diags
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_format(file: str, apply: bool = False) -> dict:
    """Format a file using the language server's formatter.

    Args:
        file: File path to format.
        apply: If True, write formatted output to file.
               If False (default), return edits for preview.

    Returns:
        When apply=False: dict with edits list for preview.
        When apply=True: dict confirming write with edit count.
    """
    client = get_lsp_client(file)
    try:
        result = client.format_document(file)
        if not result:
            return {"formatted": True, "edits": [], "message": "File already formatted"}

        edits = [
            {
                "range": {
                    "start": {"line": e["range"]["start"]["line"], "col": e["range"]["start"]["character"]},
                    "end": {"line": e["range"]["end"]["line"], "col": e["range"]["end"]["character"]},
                },
                "new_text": e.get("newText", ""),
            }
            for e in result
        ]

        if apply:
            write_result = client.apply_text_edits(file, result)
            return {
                "formatted": write_result["applied"],
                "edits_applied": write_result["count"],
                "message": f"Applied {write_result['count']} formatting edits" if write_result["applied"] else f"Failed: {write_result.get('error', 'unknown')}",
            }

        return {"formatted": True, "edits": edits, "edits_count": len(edits), "note": "Pass apply=true to write changes"}
    except Exception as e:
        return {"error": str(e), "formatted": False}
    finally:
        release_lsp_client(client)


def lsp_code_actions(file: str, line: int, col: int) -> dict:
    """Get code actions (quick fixes, refactorings) at a position.

    Args:
        file: File path.
        line: Line number (1-indexed).
        col: Column (0-indexed).

    Returns:
        Dict with list of available code actions.
    """
    client = get_lsp_client(file)
    try:
        result = client.code_actions(file, line, col)
        actions = []
        for action in result:
            if action.get("disabled"):
                continue
            entry = {
                "title": action.get("title", ""),
                "kind": action.get("kind", ""),
            }
            # Extract diagnostics this action fixes
            if action.get("diagnostics"):
                entry["fixes_diagnostics"] = [
                    d.get("message", "") for d in action["diagnostics"]
                ]
            actions.append(entry)

        return {"count": len(actions), "actions": actions}
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_rename(file: str, line: int, col: int, new_name: str) -> dict:
    """Rename a symbol across the workspace.

    Args:
        file: File path.
        line: Line number (1-indexed).
        col: Column (0-indexed).
        new_name: New name for the symbol.

    Returns:
        Dict with list of affected files and edit count.
    """
    client = get_lsp_client(file)
    try:
        result = client.rename_symbol(file, line, col, new_name)
        if not result:
            return {"success": False, "message": "Rename not supported or no changes"}

        # WorkspaceEdit format: changes dict[uri] -> TextEdit[]
        changes = result.get("changes", {})
        document_changes = result.get("documentChanges", [])

        affected_files = list(changes.keys()) if changes else []
        total_edits = sum(len(edits) for edits in changes.values()) if changes else 0

        # Apply all edits
        applied = 0
        for uri, edits in changes.items():
            file_path = uri.replace("file://", "")
            write_result = client.apply_text_edits(file_path, edits)
            if write_result.get("applied"):
                applied += write_result["count"]

        return {
            "success": True,
            "new_name": new_name,
            "affected_files": len(affected_files),
            "total_edits": total_edits,
            "applied_edits": applied,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_signature_help(file: str, line: int, col: int) -> dict:
    """Get function signature and parameter information at a call site.

    Args:
        file: File path.
        line: Line number (1-indexed).
        col: Column (0-indexed).

    Returns:
        Dict with active signature, parameter info, and documentation.
    """
    client = get_lsp_client(file)
    try:
        result = client.signature_help(file, line, col)
        if not result or not result.get("signatures"):
            return {"available": False, "message": "No signature help available"}

        signatures = result["signatures"]
        active_sig_idx = result.get("activeSignature", 0)
        active_param_idx = result.get("activeParameter", 0)

        sigs = []
        for sig in signatures:
            entry = {
                "label": sig.get("label", ""),
                "parameters": [
                    {
                        "label": p.get("label", ""),
                        "documentation": p.get("documentation", ""),
                    }
                    for p in sig.get("parameters", [])
                ],
            }
            if sig.get("documentation"):
                docs = sig["documentation"]
                entry["documentation"] = docs.get("value", docs) if isinstance(docs, dict) else docs
            sigs.append(entry)

        return {
            "available": True,
            "active_signature": active_sig_idx,
            "active_parameter": active_param_idx,
            "signatures": sigs,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_workspace_symbols(query: str) -> dict:
    """Search for symbols across the entire workspace.

    Args:
        query: Symbol name or partial name to search.

    Returns:
        Dict with matching symbols and locations.
    """
    # Need a file to get a workspace-rooted client
    # Uses first available Python file path as anchor
    client = get_lsp_client(__file__)
    try:
        result = client.workspace_symbols(query)
        symbols = []
        for sym in result or []:
            loc = sym.get("location", {})
            uri = loc.get("uri", "")
            symbols.append({
                "name": sym.get("name", ""),
                "kind": sym.get("kind", 0),
                "file": uri.replace("file://", ""),
                "line": loc.get("range", {}).get("start", {}).get("line", 0) + 1 if loc.get("range") else 0,
                "container": sym.get("containerName", ""),
            })

        return {"count": len(symbols), "symbols": symbols}
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


def lsp_completion(file: str, line: int, col: int) -> dict:
    """Get code completions at a position.

    Args:
        file: File path.
        line: Line number (1-indexed).
        col: Column (0-indexed).

    Returns:
        Dict with completion items (label, kind, detail, insertText).
    """
    client = get_lsp_client(file)
    try:
        result = client.completion(file, line, col)
        items = [
            {
                "label": item.get("label", ""),
                "kind": item.get("kind", 0),
                "detail": item.get("detail", ""),
                "documentation": item.get("documentation", ""),
                "insert_text": item.get("insertText", item.get("label", "")),
            }
            for item in result
        ]
        return {"count": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}
    finally:
        release_lsp_client(client)


# ─── Utility Tools ────────────────────────────────────────────────────────


def lsp_available_languages() -> dict:
    """Get list of supported LSP languages and their server requirements."""
    return {
        lang: {
            "command": config["command"][0],
            "install_hint": config["install_hint"],
            "extensions": config["file_extensions"],
        }
        for lang, config in LSP_SERVERS.items()
    }


def lsp_check_server(lang: str) -> dict:
    """Check if LSP server is installed for a language."""
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

    # ── Phase 1 Tools ────────────────────────────────────────────────────
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

    # ── Phase 2 Tools ────────────────────────────────────────────────────
    registry["lsp_diagnostics"] = {
        "description": "Get compiler errors and warnings (LSP, push-based)",
        "handler": lsp_diagnostics,
        "parameters": {
            "type": "object",
            "properties": {"file": {"type": "string", "description": "File path"}},
            "required": ["file"],
        },
    }
    registry["lsp_format"] = {
        "description": "Format file using LSP (preview or apply)",
        "handler": lsp_format,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "apply": {"type": "boolean", "description": "If true, write edits to file", "default": False},
            },
            "required": ["file"],
        },
    }
    registry["lsp_code_actions"] = {
        "description": "Get quick fixes, refactorings, and source actions (LSP)",
        "handler": lsp_code_actions,
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
    registry["lsp_rename"] = {
        "description": "Rename symbol across workspace (LSP)",
        "handler": lsp_rename,
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File containing the symbol"},
                "line": {"type": "integer", "description": "Line number (1-indexed)"},
                "col": {"type": "integer", "description": "Column (0-indexed)"},
                "new_name": {"type": "string", "description": "New name for the symbol"},
            },
            "required": ["file", "line", "col", "new_name"],
        },
    }
    registry["lsp_signature_help"] = {
        "description": "Get function signature and parameter info at call site (LSP)",
        "handler": lsp_signature_help,
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
    registry["lsp_workspace_symbols"] = {
        "description": "Search symbols across workspace (LSP)",
        "handler": lsp_workspace_symbols,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Symbol name or partial name"},
            },
            "required": ["query"],
        },
    }
    registry["lsp_completion"] = {
        "description": "Get code completions at a position (LSP)",
        "handler": lsp_completion,
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

    # ── Utility Tools ────────────────────────────────────────────────────
    registry["lsp_available_languages"] = {
        "description": "Get supported LSP languages and requirements",
        "handler": lsp_available_languages,
        "parameters": {"type": "object", "properties": {}},
    }
    registry["lsp_check_server"] = {
        "description": "Check if LSP server is installed for a language",
        "handler": lsp_check_server,
        "parameters": {
            "type": "object",
            "properties": {
                "lang": {"type": "string", "description": "Language (python, rust, go, etc.)"}
            },
            "required": ["lang"],
        },
    }
