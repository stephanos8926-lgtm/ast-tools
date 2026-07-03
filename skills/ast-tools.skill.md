---
name: ast-tools
description: "Structural code analysis and editing via MCP — AST search, refactoring, dependency analysis, semantic search."
version: 1.0.0
author: RapidWebs Enterprise
tags: [mcp, code-analysis, ast, refactoring, python]
platforms: [generic]
---

# Ast-Tools — Cross-Platform Skill

## Installation

```bash
pip install rw-ast-tools
```

## Quick Start

Run the MCP server:

```bash
ast-tools-server
```

## Tools

| Tool | Description |
|------|-------------|
| `ast_grep` | Structural code search using AST patterns |
| `ast_read` | Structural context extraction from source files |
| `ast_edit` | Surgical AST-based code modification |
| `ast_generate_stub` | Generate .pyi stub files |
| `ast_refactor_extract_interface` | Extract ABC/Protocol interfaces |
| `structural_analysis` | Call graphs, type hierarchies, symbol references |
| `impact_analysis` | Change impact assessment |
| `module_imports` | Import dependency analysis (fan-in/fan-out) |
| `find_references` | Cross-file symbol usage search |
| `semantic_search` | Hybrid vector + FTS5 semantic search |
| `codebase_summary` | Compact project overview |
| `project_info` | Full project manifest |
| `refresh_index` | Incremental project indexing |
| `search_symbols` | Full-text symbol search |
| `find_symbol_definition` | Find symbol by qualified name |
| `list_symbols` | List all symbols in a file |
| `index_status` | Index statistics |

## Config Management

```bash
# Create default config
ast-tools config init

# View config path
ast-tools config path

# Show active configuration
ast-tools config show

# Validate configuration
ast-tools config validate
```

## Troubleshooting

1. Ensure the project is indexed (`refresh_index`)
2. Check `ast config validate` for configuration issues
3. Verify the MCP server is running (`ast-tools-server`)