---
name: ast-tools
description: "Structural code analysis and editing via MCP — AST search, refactoring, dependency analysis, semantic search."
version: 1.0.0
author: RapidWebs Enterprise
tags: [mcp, code-analysis, ast, refactoring, python]
platforms: [claude-code]
---

# Ast-Tools — Claude Code Integration

## Installation

```bash
pip install rw-ast-tools
```

## Quick Start

Start the MCP server:

```bash
ast-tools-server
```

## Tool Reference

### Code Search
Use `ast_grep` to find code by structure:
- `ast_grep(pattern="def $FUNC($$$ARGS)")` — find all function definitions
- `ast_grep(pattern="class $NAME($$$BASES)")` — find all class definitions

### Code Reading
Use `ast_read` to get a structured overview of any file before editing.

### Code Editing
Use `ast_edit` with `dry_run: true` first, then apply:
- `replace_node` — substitute one AST node for another
- `rename_function` — rename a function and its references
- `add_parameter` — add a parameter to a function signature

### Analysis
- `impact_analysis(target="src/module.py")` — what breaks if I change this?
- `module_imports(module="mypackage.core")` — import dependency analysis
- `structural_analysis(analysis_type="callers", symbol="my_function", file="src/lib.py", line=42)` — who calls this?

### Semantic Search
- `semantic_search(query="error handling pattern", k=10)` — find code by meaning

## Workflow

1. **Discover**: `semantic_search` → `ast_grep` → `ast_read`
2. **Analyze**: `impact_analysis` → `structural_analysis`
3. **Edit**: `ast_edit(dry_run=true)` → `ast_edit(dry_run=false)` → `ast_read` (verify)
4. **Index**: `refresh_index`