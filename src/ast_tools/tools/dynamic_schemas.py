"""
Generate dynamic minimal tool schemas for all registered tools.
Used by Hermes plugin for context injection.
"""

import json
from src.ast_tools.tools import TOOL_REGISTRY, get_tool_schema, find_similar_tool, list_tool_names


def generate_minimal_tool_schemas() -> dict[str, dict]:
    """
    Generate minimal schemas for all tools.
    
    Returns dict of {tool_name: {description, required_params, param_names}}.
    Limited to ~100-200 tokens total for LLM context efficiency.
    """
    schemas = {}
    
    for name in sorted(TOOL_REGISTRY.keys()):
        schema = get_tool_schema(name)
        if schema:
            # Minimal: description (truncated), required params, all param names
            input_schema = schema.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            
            schemas[name] = {
                "desc": schema.get("description", "")[:150],
                "required": required,
                "params": list(properties.keys())[:8],  # Limit param names
            }
        else:
            # Fallback for tools without registered schema
            schemas[name] = {
                "desc": "Tool available (schema not registered)",
                "required": [],
                "params": [],
            }
    
    return schemas


def generate_quick_reference() -> str:
    """
    Generate a compact markdown reference table of all tools.
    ~300-500 tokens, suitable for injection into LLM context.
    """
    schemas = generate_minimal_tool_schemas()
    
    lines = [
        "### AST-Tools Quick Reference",
        "",
        "| Tool | Description | Required Params |",
        "|------|-------------|-----------------|",
    ]
    
    for name, info in sorted(schemas.items()):
        desc = info["desc"].replace("|", "\\|")[:100]  # Escape pipes, truncate
        required = ", ".join(info["required"]) or "none"
        lines.append(f"| `{name}` | {desc} | {required} |")
    
    lines.append("")
    lines.append(f"*Total: {len(schemas)} tools available*")
    
    return "\n".join(lines)


def get_tool_count() -> int:
    """Return total number of registered tools."""
    return len(TOOL_REGISTRY)


# Export for plugin use
__all__ = [
    "generate_minimal_tool_schemas",
    "generate_quick_reference",
    "find_similar_tool",
    "get_tool_count",
    "list_tool_names",
]