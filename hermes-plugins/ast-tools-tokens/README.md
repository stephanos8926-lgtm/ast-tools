# AST-Tools Tokens Plugin

**Version:** 1.0.0  
**License:** MIT  
**Author:** Hermes Agent Team

## Overview

The `ast-tools-tokens` plugin provides token usage tracking and context pressure management specifically for AST-Tools MCP server operations.

This plugin helps prevent context overflow by monitoring token usage and providing warnings when approaching compression thresholds.

## Features

- **Token Budget Tracking**: Monitors token consumption per ast-tools operation
- **Configurable Budgets**: Different budgets for different tool types
- **Context Pressure Warnings**: Alerts when approaching compression threshold
- **Automatic Logging**: Logs warnings for verbose results
- **Smart Recommendations**: Provides actionable advice when limits approached

## Token Budgets

The plugin uses these default token budgets (approximately 4 characters = 1 token):

| Tool Type | Budget (tokens) |
|-----------|-----------------|
| `ast_grep` | 2,000 |
| `structural_analysis` | 4,000 |
| `impact_analysis` | 3,000 |
| `semantic_search` | 2,500 |
| `ast_read` | 1,500 |
| `ast_edit` | 1,000 |
| Default | 1,000 |

These budgets can be customized in the `AST_TOOLS_TOKEN_BUDGETS` dictionary.

## Context Pressure Monitoring

The plugin continuously monitors context usage and triggers warnings when:

- Usage exceeds 80% of the compression threshold
- Compression threshold is set to 50% of total context window

### Example Warning

```
⚠️ **Context Pressure Alert**

- Current usage: ~52,000 tokens (19.8% of window)
- Compression threshold: 131,072 tokens (50%)
- Compression will fire soon if usage continues

**Recommendations:**
- Use `/compress` for manual compression with focus topic
- Focus queries on recent context
- For large codebases, use semantic_search with focused queries instead of full context injection
```

## Installation

### Manual Installation

```bash
# Copy plugin to your Hermes plugins directory
cp -r ast-tools-tokens ~/.hermes/plugins/

# Restart Hermes session or reload plugins
hermes restart
```

### Using Install Script

```bash
# From the hermes-plugins directory
./scripts/install.sh ast-tools-tokens
```

## Requirements

- Hermes Agent (any recent version with plugin support)
- Python 3.10+
- `hermes_cli.plugins.PluginContext` module
- `logging` module (standard library)

## Hooks

This plugin registers two hooks:

### `post_tool_call`

Called after each tool invocation to track token usage.

**Parameters:**
- `tool_name`: Name of the tool that was called
- `params`: Parameters passed to the tool
- `result`: Tool result string
- `**kwargs`: Additional context

**Action:**
- Checks if tool is ast-tools related
- Estimates token count from result length
- Logs warning if exceeds budget

### `pre_llm_call`

Called before each LLM invocation to check context pressure.

**Parameters:**
- `session_id`: Current session identifier
- `user_message`: User's current query
- `conversation_history`: Previous messages
- `is_first_turn`: First turn in session flag
- `model`: LLM model name
- `**kwargs`: Additional context

**Returns:**
- `dict` with `"context"` key if pressure warning needed
- `None` if context usage is normal

## Configuration

### Customizing Token Budgets

Edit the `AST_TOOLS_TOKEN_BUDGETS` dictionary in `__init__.py`:

```python
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": 3000,  # Increase budget for ast_grep
    "structural_analysis": 5000,
    # ... add more as needed
}
```

### Model-Specific Context Lengths

To add support for a new model, update the `context_lengths` dictionary in `check_context_pressure()`:

```python
context_lengths = {
    "qwen/qwen3.5-397b-a17b": 262144,
    "your-model-name": 128000,  # Add your model
    "default": 262144
}
```

### Compression Threshold

The compression threshold is set to 50% of total context window. To change:

```python
# In check_context_pressure()
compression_threshold = int(context_length * 0.40)  # Change to 40%
```

## Usage Examples

### Example 1: Large ast_grep Result

**Tool Call:** `mcp_ast_tools_ast_grep` returns 10,000 characters

**Plugin Action:** Logs warning:
```
ast-tools result exceeded budget: mcp_ast_tools_ast_grep used ~2500 tokens (budget: 2000). Consider using limit parameters or result filtering.
```

### Example 2: High Context Usage

**Scenario:** Session has accumulated 100,000 tokens of conversation

**Plugin Action:** Injects context pressure alert into next LLM call with recommendations.

### Example 3: Normal Operation

**Scenario:** Tool result within budget, context usage low

**Plugin Action:** No warnings, silent operation.

## Development

### File Structure

```
ast-tools-tokens/
├── __init__.py          # Main plugin code
└── plugin.yaml          # Plugin metadata
```

### Adding New Tool Budgets

When the AST-Tools MCP server adds new tools, add corresponding budgets:

1. Identify the tool type from the name (e.g., `mcp_ast_tools_new_feature`)
2. Add entry to `AST_TOOLS_TOKEN_BUDGETS` with appropriate budget
3. Test with typical result sizes

### Extending Context Pressure Logic

You can extend the plugin to:

- Store truncated results in session memory
- Automatically suggest focused follow-up queries
- Track token usage statistics across sessions

## Logging

The plugin uses Python's standard logging module. Warnings are logged at WARNING level.

To see warnings:

```bash
# Set logging level
hermes --log-level warning
```

## Troubleshooting

### Warnings Not Appearing

1. Check if logging level is set appropriately
2. Verify tool names start with `mcp_ast_tools_`
3. Check token budget configuration

### False Positives

If warnings appear too frequently:

1. Increase token budgets
2. Check character-to-token ratio (currently 4:1)
3. Adjust compression threshold

### Performance Impact

The plugin has minimal performance impact:
- Token estimation: O(n) string length check
- Context pressure: O(n) conversation history scan
- Both operations are fast for typical conversation sizes

## Future Enhancements

Potential improvements:

- Store truncated results in session memory for reference
- Automatic suggestion of limit parameters for large queries
- Integration with Hermes compression system
- Per-session token usage statistics
- Configurable budgets via plugin config file

## License

MIT License - see LICENSE file in the main distribution package.

## Support

For issues or questions, refer to the main AST-Tools Hermes Plugins documentation.