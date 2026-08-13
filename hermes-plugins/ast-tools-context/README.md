# AST-Tools Context Plugin

**Version:** 1.0.0  
**License:** MIT  
**Author:** Hermes Agent Team

## Overview

The `ast-tools-context` plugin automatically injects AST-Tools MCP server documentation into the LLM context when the user's query relates to code structure analysis, AST manipulation, or structural code search.

This plugin helps the LLM understand what tools are available and how to use them effectively, without requiring manual reminders in every session.

## Features

- **Automatic Context Injection**: Detects relevant queries and provides tool documentation
- **Smart Keyword Detection**: Recognizes 20+ AST and code analysis related terms
- **Concise Documentation**: Limited to ~1000 tokens to avoid context bloat
- **Usage Patterns**: Provides best practices for common workflows

## Detected Topics

The plugin activates when user queries mention:

- AST manipulation (`ast`, `ast-grep`, `abstract syntax tree`, `parse tree`)
- Code structure analysis (`code structure`, `structural`)
- Symbol analysis (`symbol`, `reference`, `dependency`, `import analysis`)
- Search operations (`code search`, `grep`, `structural grep`)
- Parsing libraries (`libcst`, `concrete syntax tree`, `cst`)
- Impact analysis (`impact analysis`, `call graph`, `type hierarchy`)
- Module dependencies (`module imports`, `fan-in`, `fan-out`)
- Semantic search (`semantic search`, `codebase summary`)

## Provided Documentation

When activated, the plugin provides:

1. **Core Tools Reference**
   - `ast_grep`: Structural code search with AST patterns
   - `ast_read`: Structural context extraction
   - `ast_edit`: Surgical AST-based modifications
   - `ast_generate_stub`: Type stub generation

2. **Analysis Tools**
   - `structural_analysis`: Call graphs, type hierarchies, symbol references
   - `impact_analysis`: Change impact assessment
   - `module_imports`: Import dependency analysis
   - `find_references`: Cross-file symbol search

3. **Search & Discovery**
   - `semantic_search`: Vector + FTS5 hybrid search
   - `search_symbols`: Full-text symbol search
   - `find_symbol_definition`: Find by qualified name
   - `list_symbols`: List all symbols in file

4. **Index Management**
   - `refresh_index`: Incremental indexing
   - `index_status`: Statistics

5. **Usage Patterns**
   - Code search workflow
   - Making changes safely
   - Understanding code workflows

## Installation

### Manual Installation

```bash
# Copy plugin to your Hermes plugins directory
cp -r ast-tools-context ~/.hermes/plugins/

# Restart Hermes session or reload plugins
hermes restart
```

### Using Install Script

```bash
# From the hermes-plugins directory
./scripts/install.sh ast-tools-context
```

## Requirements

- Hermes Agent (any recent version with plugin support)
- Python 3.10+
- `hermes_cli.plugins.PluginContext` module

## Hooks

This plugin registers the following hooks:

### `pre_llm_call`

Called before each LLM invocation to inject context when relevant.

**Parameters:**
- `session_id`: Current session identifier
- `user_message`: User's current query
- `conversation_history`: Previous messages
- `is_first_turn`: First turn in session flag
- `model`: LLM model name
- `platform`: Platform (cli, telegram, discord, etc.)

**Returns:**
- `dict` with `"context"` key if injection needed
- `None` if query not relevant

## Configuration

No configuration required. The plugin works out of the box.

To customize keyword detection, edit the `ast_keywords` list in `__init__.py`.

To modify the injected context, edit the `build_ast_tools_context()` function.

## Usage Examples

### Example 1: Structural Code Search

**User:** "Find all function definitions in the codebase"

**Plugin Action:** Injects AST-Tools documentation, highlighting `ast_grep` tool.

**LLM Response:** Can now reference `ast_grep` with pattern `def $FUNC($$$ARGS)`.

### Example 2: Impact Analysis

**User:** "I want to refactor this function, what will be affected?"

**Plugin Action:** Injects documentation about `impact_analysis` tool.

**LLM Response:** Suggests using `impact_analysis` before making changes.

### Example 3: Understanding Dependencies

**User:** "Which modules import this file?"

**Plugin Action:** Injects documentation about `module_imports` tool.

**LLM Response:** Explains how to use `module_imports` for fan-in analysis.

## Development

### File Structure

```
ast-tools-context/
├── __init__.py          # Main plugin code
└── plugin.yaml          # Plugin metadata
```

### Testing

To test the plugin:

1. Install it in your Hermes plugins directory
2. Start a new Hermes session
3. Ask questions related to AST or code analysis
4. Verify that documentation is injected

### Debugging

Enable debug logging in Hermes:

```bash
hermes --log-level debug
```

Look for plugin registration messages in the logs.

## Troubleshooting

### Plugin Not Loading

1. Verify file structure matches expected layout
2. Check `plugin.yaml` syntax (must be valid YAML)
3. Ensure `__init__.py` has no syntax errors
4. Restart Hermes session

### Context Not Injecting

1. Check if your query contains recognized keywords
2. Add your terms to `ast_keywords` list
3. Verify hook registration in `register()` function
4. Check Hermes logs for errors

## License

MIT License - see LICENSE file in the main distribution package.

## Support

For issues or questions, refer to the main AST-Tools Hermes Plugins documentation.