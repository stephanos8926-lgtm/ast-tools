---
name: ast-tools
description: "Structural code analysis and editing via MCP — AST search, refactoring, dependency analysis, semantic search."
version: 1.0.0
author: RapidWebs Enterprise
tags: [mcp, code-analysis, ast, refactoring, python]
platforms: [hermes]
---

# Ast-Tools — Hermes Agent Skill

## Installation

```bash
pip install rw-ast-tools
# Or via uv:
uv tool install rw-ast-tools
```

## Quick Start

Start the MCP server:

```bash
ast-tools-server
```

Configure in `~/.hermes/config.yaml`:

```yaml
mcpServers:
  ast-tools:
    command: ast-tools-server
```

## Hermes Plugins

The following plugins enhance the ast-tools experience:

- **ast-tools-context** — Auto-injects code context into LLM prompts based on your current file
- **ast-tools-tokens** — Token budget management (configure via `ast config init` + edit `~/.ast-tools/config/tokens.yaml`)
- **ast-tools-codebase-index** — Fast symbol indexing and caching

## Tool Catalog

### Core Tools
- `ast_grep` — Structural code search via AST patterns
- `ast_read` — Structural context extraction from source files
- `ast_edit` — Surgical AST-based code modification (libcst)
- `ast_generate_stub` — Generate .pyi stubs or interfaces
- `ast_refactor_extract_interface` — Extract ABC/Protocol interfaces

### Analysis Tools
- `structural_analysis` — Call graphs, type hierarchies, symbol references
- `impact_analysis` — Change impact assessment (what breaks?)
- `module_imports` — Fan-in/fan-out import analysis
- `find_references` — Cross-file symbol usage search
- `semantic_search` — Hybrid vector + FTS5 semantic search (6-factor RRF)

### Index Management
- `refresh_index` — Incremental project indexing
- `index_status` — Database and index statistics
- `search_symbols` — FTS5 full-text symbol search
- `find_symbol_definition` — Find by qualified name
- `list_symbols` — List symbols in a file

### Utility
- `codebase_summary` — Compact project overview (<500 tokens)
- `project_info` — Full project manifest
- `kg_query` / `kg_shortest_path` / `kg_neighborhood` — Knowledge graph traversal

## Usage

```bash
# Index a project
ast-tools refresh_index /path/to/project

# Search structurally
ast-tools grep "def $FUNC($$$ARGS)" /path/to/project

# Semantic search
ast-tools semantic_search "authentication logic" --k 10
```

## Troubleshooting

- **Server won't start**: Check `ast config path` for config directory
- **No results**: Run `refresh_index` first to build the index
- **Slow queries**: Check `~/.ast-tools/config/tokens.yaml` for budget settings