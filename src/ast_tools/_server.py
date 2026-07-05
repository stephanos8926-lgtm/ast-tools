#!/usr/bin/env python3
"""
AST Tools MCP Server — structural code analysis and editing tools.

Exposes 17 tools:
  ast_grep                    — Structural search (via ast-grep CLI)
  ast_edit                    — Surgical AST-based modification (via libcst)
  ast_read                    — Structural context extraction (via ast module)
  ast_generate_stub           — Generate .pyi stubs or interfaces (via ast)
  ast_refactor_extract_interface — Extract interface to ABC/Protocol (via libcst)
  structural_analysis         — Call graphs, type hierarchies, symbol references (via jedi)
  project_info                — Project intelligence (project.json manifest)
  codebase_summary            — High-level architecture overview (<500 tokens)
  find_references             — Cross-file symbol usage search
  impact_analysis             — What breaks if you change a file or symbol
  module_imports              — Module-level import analysis (fan-in / fan-out)
  search_symbols              — FTS5 full-text search of indexed symbols
  find_symbol_definition      — Find symbol by qualified name
  list_symbols                — List symbols in a file
  index_status                — Get index statistics
  refresh_index               — Index a project (incremental, with content hashing)
  semantic_search             — Hybrid vector + FTS5 semantic search
"""

import json
import logging
import sys
from typing import Any

from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions

import anyio
from mcp.server import Server
from mcp.types import TextContent, Tool

from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)

server = Server("ast-tools")


# ─── Tool Definitions ────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Dynamically build Tool definitions from TOOL_SCHEMAS.

    Every registered tool with a schema in TOOL_SCHEMAS is automatically
    exposed as an MCP tool. Add a new tool by registering it in
    ``ast_tools/tools/__init__.py`` — it appears here automatically.
    """
    from ast_tools.tools import TOOL_SCHEMAS, list_tool_names

    tools: list[Tool] = []
    names = list_tool_names()
    for name in sorted(names):
        schema = TOOL_SCHEMAS.get(name)
        if schema is None:
            continue
        tools.append(
            Tool(
                name=name,
                description=schema.get("description", ""),
                inputSchema=schema.get("inputSchema", {"type": "object", "properties": {}}),
            )
        )
    return tools


# ─── Tool Handlers ────────────────────────────────────────────────────────


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to registered handlers."""
    try:
        if name not in TOOL_REGISTRY:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": f"Unknown tool: {name}",
                            "error_code": "NOT_FOUND",
                            "available_tools": list_tool_names(),
                        }
                    ),
                )
            ]

        handler = get_tool_handler(name)
        result = await anyio.to_thread.run_sync(handler, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "error_code": "INTERNAL", "tool": name}),
            )
        ]


async def main():
    """Run the ast-tools MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        import anyio
        anyio.run(main)
    except KeyboardInterrupt:
        pass
