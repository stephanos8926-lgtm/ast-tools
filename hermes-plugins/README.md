# AST-Tools Hermes Plugins

**Version:** 1.0.0  
**License:** MIT  
**Author:** Hermes Agent Team

A production-ready distribution package of Hermes Agent plugins designed to enhance workflows with the AST-Tools MCP server.

## Overview

This package contains plugins that integrate AST-Tools capabilities directly into Hermes Agent's operation, providing:

- **Automatic context injection** when discussing code analysis topics
- **Token usage tracking** to prevent context overflow
- **Smart recommendations** for efficient tool usage
- **Context pressure monitoring** to manage large conversations

## Included Plugins

### 1. `ast-tools-context`

Automatically injects AST-Tools documentation into the LLM context when relevant queries are detected.

**Features:**
- Smart keyword detection for AST/code analysis topics
- Concise tool reference (~1000 tokens)
- Usage patterns and best practices
- Zero configuration required

**Hooks:** `pre_llm_call`

### 2. `ast-tools-tokens`

Tracks token usage for ast-tools operations and provides context pressure warnings.

**Features:**
- Per-tool token budgets
- Automatic budget monitoring
- Context pressure alerts
- Configurable thresholds

**Hooks:** `post_tool_call`, `pre_llm_call`

## Quick Start

### Prerequisites

- **Hermes Agent** (any recent version with plugin support)
- **Python 3.10+**
- **AST-Tools MCP Server** (for full functionality)

### Installation Option 1: Install All Plugins

```bash
# From the hermes-plugins directory
./scripts/install-all.sh
```

This installs all plugins and restarts Hermes.

### Installation Option 2: Install Individual Plugins

```bash
# Install specific plugin
./scripts/install.sh ast-tools-context

# Or manually copy
cp -r ast-tools-context ~/.hermes/plugins/
```

### Installation Option 3: Manual Installation

```bash
# Create plugins directory if it doesn't exist
mkdir -p ~/.hermes/plugins

# Copy plugins
cp -r ast-tools-context ~/.hermes/plugins/
cp -r ast-tools-tokens ~/.hermes/plugins/
cp -r ast-tools-codebase-index ~/.hermes/plugins/

# Restart Hermes
hermes restart
```

## Verification

After installation, verify plugins are loaded:

```bash
hermes plugins list
```

You should see:
- `ast-tools-context`
- `ast-tools-tokens`

## Usage

### Automatic Operation

Both plugins work automatically without configuration:

1. **Context Injection**: When you ask about AST, code structure, or related topics, documentation is automatically provided.

2. **Token Tracking**: All ast-tools operations are monitored for token usage.

3. **Context Pressure**: You'll receive warnings when approaching compression thresholds.

### Example Workflows

#### Code Search Workflow

```
User: Find all function definitions in the codebase

Plugin: [Injects ast_grep documentation]

Assistant: You can use the ast_grep tool with pattern `def $FUNC($$$ARGS)` 
to search for all function definitions. This will match any function 
definition across your codebase.
```

#### Making Changes Safely

```
User: I want to refactor this function, what should I check first?

Plugin: [Injects impact_analysis documentation]

Assistant: Before refactoring, run impact_analysis to understand which 
files will be affected. Then use ast_edit with dry_run=true to preview 
changes before applying them.
```

#### Context Pressure Alert

```
[After extensive conversation]

Plugin: [Injects context pressure warning]

Assistant: ⚠️ Context Pressure Alert detected. Consider using /compress 
or focusing queries on recent context to avoid automatic compression.
```

## Configuration

### Customizing ast-tools-context

Edit `ast-tools-context/__init__.py` to:

1. **Add keywords** to the `ast_keywords` list
2. **Modify injected context** in `build_ast_tools_context()`

### Customizing ast-tools-tokens

Edit `ast-tools-tokens/__init__.py` to:

1. **Adjust token budgets** in `AST_TOOLS_TOKEN_BUDGETS`
2. **Add new models** to `context_lengths` dictionary
3. **Change compression threshold** (currently 50%)

## Hooks Documentation

### `pre_llm_call`

Called before each LLM invocation.

**Purpose:** Inject context or warnings into the conversation.

**Used by:**
- `ast-tools-context`: Injects tool documentation
- `ast-tools-tokens`: Injects context pressure warnings

**Parameters:**
```python
session_id: str
user_message: str
conversation_history: list
is_first_turn: bool
model: str
platform: str
**kwargs
```

**Returns:** `dict` with `"context"` key, or `None`

### `post_tool_call`

Called after each tool invocation.

**Purpose:** Track and monitor tool usage.

**Used by:** `ast-tools-tokens`

**Parameters:**
```python
tool_name: str
params: dict
result: str
**kwargs
```

**Returns:** None (logs warnings as needed)

## Skills and Config Requirements

### Required Skills

No additional skills required. These plugins work with standard Hermes Agent capabilities.

### Required Configuration

#### Hermes Config (`~/.hermes/config.yaml`)

No special configuration required. Plugins use default Hermes plugin system.

Optional, for enhanced logging:

```yaml
logging:
  level: warning  # To see token budget warnings
```

#### Environment Variables

None required.

### MCP Server Requirements

For full functionality:

- **AST-Tools MCP Server** must be configured in your MCP settings
- Server provides the actual AST analysis capabilities
- Plugins only provide documentation and monitoring

**Example MCP Config** (`~/.hermes/mcp.json`):

```json
{
  "mcpServers": {
    "ast-tools": {
      "command": "uvx",
      "args": ["ast-tools-mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

## Troubleshooting

### Plugins Not Loading

1. **Check file structure:**
   ```bash
   ls -la ~/.hermes/plugins/ast-tools-*/
   ```
   Should show `__init__.py` and `plugin.yaml`

2. **Verify YAML syntax:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('~/.hermes/plugins/ast-tools-context/plugin.yaml'))"
   ```

3. **Check Python syntax:**
   ```bash
   python3 -m py_compile ~/.hermes/plugins/ast-tools-context/__init__.py
   ```

4. **Restart Hermes:**
   ```bash
   hermes restart
   ```

### Context Not Injecting

1. **Check keywords:** Your query must contain recognized keywords
2. **Add custom keywords** to `ast_keywords` list
3. **Enable debug logging:** `hermes --log-level debug`

### Token Warnings Not Appearing

1. **Check logging level:** Set to warning or lower
2. **Verify tool name format:** Must start with `mcp_ast_tools_`
3. **Check budget values:** May need adjustment for your use case

### Context Pressure Warnings

If you're getting frequent warnings:

1. **Increase budgets** in ast-tools-tokens plugin
2. **Use `/compress`** command proactively
3. **Focus queries** on specific topics
4. **Start new session** for unrelated topics

## File Structure

```
hermes-plugins/
├── README.md                        # This file
├── INSTALL.md                       # Installation guide
├── USAGE.md                         # Detailed usage documentation
├── MANIFEST.yaml                    # Distribution manifest
├── LICENSE                          # MIT license
├── docs/
│   ├── hooks.md                     # Hooks documentation
│   └── configuration.md             # Configuration guide
├── scripts/
│   ├── install.sh                   # Single plugin installer
│   ├── install-all.sh              # Batch installer
│   ├── uninstall.sh                # Uninstaller
│   └── verify.sh                   # Verification script
├── ast-tools-context/
│   ├── __init__.py                  # Plugin code
│   ├── plugin.yaml                  # Plugin metadata
│   └── README.md                    # Plugin documentation
└── ast-tools-tokens/
    ├── __init__.py                  # Plugin code
    ├── plugin.yaml                  # Plugin metadata
    └── README.md                    # Plugin documentation
```

## Development

### Extending the Package

To add new plugins:

1. Create plugin directory under `hermes-plugins/`
2. Implement `__init__.py` with `register(ctx)` function
3. Create `plugin.yaml` with metadata
4. Write `README.md` for the plugin
5. Update `MANIFEST.yaml`
6. Test with `./scripts/verify.sh`

### Testing

```bash
# Run verification
./scripts/verify.sh

# Test installation
./scripts/install-all.sh --dry-run

# Check plugin syntax
python3 -m py_compile ast-tools-context/__init__.py
python3 -m py_compile ast-tools-tokens/__init__.py
```

### Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Run verification
5. Submit PR

## License

MIT License

See LICENSE file for full text.

## Supporting AST-Tools

These plugins are designed to work with the AST-Tools MCP server. For more information about AST-Tools:

- Documentation: [AST-Tools Docs](https://example.com/ast-tools-docs)
- GitHub: [AST-Tools Repository](https://example.com/ast-tools)
- MCP Server Installation: See INSTALL.md

## Contact

For issues or questions:
- Check troubleshooting section
- Review individual plugin READMEs
- Consult Hermes Agent documentation

---

**Built for Hermes Agent** | **Version 1.0.0** | **MIT License**