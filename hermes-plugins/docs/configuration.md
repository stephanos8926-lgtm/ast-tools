# Configuration Guide

Complete guide for configuring AST-Tools Hermes Plugins.

## Table of Contents

1. [Quick Configuration](#quick-configuration)
2. [Hermes Configuration](#hermes-configuration)
3. [Plugin Configuration](#plugin-configuration)
4. [MCP Server Configuration](#mcp-server-configuration)
5. [Advanced Configuration](#advanced-configuration)
6. [Troubleshooting](#troubleshooting)

## Quick Configuration

### Minimal Setup

The plugins work out of the box with no configuration needed.

**Required:**
- Hermes Agent installed
- Plugins copied to `~/.hermes/plugins/`
- Hermes restarted

**Verify:**
```bash
hermes plugins list
```

### Recommended Setup

Add to `~/.hermes/config.yaml`:

```yaml
logging:
  level: warning  # To see token budget warnings
```

## Hermes Configuration

### Config File Location

`~/.hermes/config.yaml`

### Basic Configuration

```yaml
# Hermes Agent Configuration

# Logging
logging:
  level: warning  # info, debug, warning, error
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Plugins
plugins:
  enabled: true
  directory: ~/.hermes/plugins
  auto_load: true

# Session settings
session:
  memory_enabled: true
  compression_threshold: 0.50  # 50% of context window
  auto_compress: true

# Model settings
model:
  default: "qwen/qwen3.5-397b-a17b"
  context_length: 262144

# MCP servers
mcp:
  enabled: true
  config_file: ~/.hermes/mcp.json
```

### Plugin-Specific Settings

Currently, plugins don't require separate configuration sections. All settings are in the plugin code itself.

### Enabling/Disabling Plugins

To temporarily disable a plugin:

```yaml
plugins:
  disabled:
    - ast-tools-context
    - ast-tools-tokens
```

Or rename the plugin directory:

```bash
mv ~/.hermes/plugins/ast-tools-context ~/.hermes/plugins/ast-tools-context.disabled
```

## Plugin Configuration

### ast-tools-context Configuration

**File:** `~/.hermes/plugins/ast-tools-context/__init__.py`

#### Keywords Configuration

Edit the `ast_keywords` list to customize trigger detection:

```python
ast_keywords = [
    # Core AST keywords
    "ast ", "ast-grep", "astedit", "ast edit", "ast read", "ast_read",
    "abstract syntax tree", "parse tree", "code structure",
    
    # Analysis keywords
    "symbol", "reference", "dependency", "import analysis",
    "structural", "code search", "grep", "structural grep",
    
    # Parser keywords
    "libcst", "concrete syntax tree", "cst",
    
    # Impact analysis
    "impact analysis", "call graph", "type hierarchy",
    
    # Module dependencies
    "module imports", "fan-in", "fan-out",
    
    # Search
    "semantic search", "codebase summary",
    
    # ADD YOUR CUSTOM KEYWORDS HERE
    "your-keyword",  # Add your domain-specific triggers
]
```

#### Injected Context Configuration

Edit `build_ast_tools_context()` to customize the injected documentation:

```python
def build_ast_tools_context(query: str) -> str:
    """Build context string for ast-tools capabilities."""
    
    # Base context
    context = """
## AST-Tools MCP Server Capabilities

... (existing content) ...
"""
    
    # Add domain-specific context
    if "graphql" in query.lower():
        context += """

### GraphQL-Specific Tips

For GraphQL schemas, use these patterns:
- `type Query { $FIELD }` - Query type
- `type Mutation { $FIELD }` - Mutation type
- `type $TYPE { $FIELD }` - Any type definition
"""
    
    if "react" in query.lower():
        context += """

### React-Specific Tips

For React components:
- `function $COMPONENT($$$PROPS)` - Function components
- `const $COMPONENT = ($$$PROPS)` - Arrow function components
- `<$COMPONENT $$$PROPS>` - JSX usage
"""
    
    return context
```

### ast-tools-tokens Configuration

**File:** `~/.hermes/plugins/ast-tools-tokens/__init__.py`

#### Token Budgets Configuration

Edit `AST_TOOLS_TOKEN_BUDGETS` to customize budgets:

```python
AST_TOOLS_TOKEN_BUDGETS = {
    # Core tools
    "ast_grep": 2000,  # Adjust based on typical result sizes
    "structural_analysis": 4000,
    "impact_analysis": 3000,
    "semantic_search": 2500,
    "ast_read": 1500,
    "ast_edit": 1000,
    
    # Add custom tool budgets
    "your_custom_tool": 3000,
    
    # Default fallback
    "default": 1000,
}
```

**Tips:**
- Increase budgets if you're getting frequent warnings
- Decrease budgets to encourage more focused queries
- Monitor actual usage in logs to find appropriate values

#### Context Length Configuration

Edit `context_lengths` to add support for your models:

```python
context_lengths = {
    # Known models
    "qwen/qwen3.5-397b-a17b": 262144,
    
    # Add your model
    "claude-3-opus": 200000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "llama-3-70b": 8192,
    "your-model-here": 65536,  # Add your model
    "default": 262144,  # Fallback
}
```

#### Compression Threshold Configuration

Edit `compression_threshold` to change when warnings appear:

```python
# In check_context_pressure()

# Current: 50% of context window
compression_threshold = int(context_length * 0.50)

# More aggressive warning (warn earlier):
compression_threshold = int(context_length * 0.40)  # 40%

# Less aggressive warning (warn later):
compression_threshold = int(context_length * 0.60)  # 60%

# Warning trigger (currently 80% of threshold)
warning_trigger = 0.80  # Warn at 80% of threshold

# More sensitive warning:
warning_trigger = 0.70  # Warn at 70% of threshold

# Less sensitive warning:
warning_trigger = 0.90  # Warn at 90% of threshold
```

## MCP Server Configuration

### Config File Location

`~/.hermes/mcp.json`

### Basic AST-Tools MCP Setup

```json
{
  "mcpServers": {
    "ast-tools": {
      "command": "uvx",
      "args": ["rw-ast-tools"],
      "cwd": "/home/sysop/Workspaces",
      "env": {}
    }
  }
}
```

### Advanced MCP Configuration

```json
{
  "mcpServers": {
    "ast-tools": {
      "command": "uvx",
      "args": [
        "rw-ast-tools",
        "--verbose",
        "--log-level", "info"
      ],
      "cwd": "/home/sysop/Workspaces",
      "env": {
        "PYTHONPATH": "/home/sysop/Workspaces",
        "AST_TOOLS_CONFIG": "/home/sysop/.ast-tools/config.yaml"
      },
      "timeout": 300
    }
  }
}
```

### Multi-Project Configuration

```json
{
  "mcpServers": {
    "ast-tools-project1": {
      "command": "uvx",
      "args": ["rw-ast-tools"],
      "cwd": "/home/sysop/Workspaces/project1"
    },
    "ast-tools-project2": {
      "command": "uvx",
      "args": ["rw-ast-tools"],
      "cwd": "/home/sysop/Workspaces/project2"
    }
  }
}
```

### MCP Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `command` | `str` | Command to run the MCP server |
| `args` | `list` | Command-line arguments |
| `cwd` | `str` | Working directory |
| `env` | `dict` | Environment variables |
| `timeout` | `int` | Timeout in seconds (optional) |

## Advanced Configuration

### Custom Warning Messages

Edit the `check_context_pressure()` function to customize warnings:

```python
def check_context_pressure(...) -> dict | None:
    # ... existing calculation code ...
    
    if estimated_tokens >= compression_threshold * 0.80:
        return {
            "context": f"""

⚠️ **Custom Context Warning**

You're using a lot of context.

- Tokens used: ~{estimated_tokens:,}
- Threshold: {compression_threshold:,}

**What to do:**
1. Be more specific
2. Use /compress
3. Start new session

"""
        }
    
    return None
```

### Environment-Specific Configuration

Use environment variables to configure behavior:

```python
import os

# Get budget from environment, fallback to default
CUSTOM_BUDGET = os.getenv("AST_TOOLS_BUDGET", "2000")
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": int(CUSTOM_BUDGET),
    # ...
}

# Get threshold from environment
CUSTOM_THRESHOLD = float(os.getenv("AST_TOOLS_COMPRESSION_THRESHOLD", "0.50"))
compression_threshold = int(context_length * CUSTOM_THRESHOLD)
```

### Session Memory Integration

Store truncated results in session memory (advanced):

```python
def track_ast_tools_usage(tool_name, params, result, **kwargs):
    # ... existing code ...
    
    if estimated_tokens > budget:
        # Store truncated version in session memory
        session_id = kwargs.get('session_id')
        if session_id:
            session = get_session(session_id)
            session.store_truncated_result(
                tool_name=tool_name,
                full_result=result,
                truncate_to=budget
            )
```

### Custom Logging Configuration

Set up dedicated logging for plugins:

```python
import logging

# Create logger
logger = logging.getLogger("ast-tools-plugins")
logger.setLevel(logging.WARNING)

# Create handler
handler = logging.FileHandler("/tmp/ast-tools-plugins.log")
handler.setLevel(logging.WARNING)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add handler
logger.addHandler(handler)

# Use in hooks
def track_ast_tools_usage(...):
    if estimated_tokens > budget:
        logger.warning(f"Budget exceeded: {tool_name}")
```

## Troubleshooting

### Configuration Issues

#### Plugin Not Respecting Changes

**Problem:** Changes to config files have no effect.

**Solutions:**
1. Restart Hermes after changes: `hermes restart`
2. Verify file permissions: `ls -la ~/.hermes/plugins/`
3. Check YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"`
4. Clear Python cache: `find ~/.hermes/plugins -name "*.pyc" -delete`

#### Wrong Keywords Triggering

**Problem:** Context injects when it shouldn't.

**Solution:**
- Remove overly broad keywords from `ast_keywords` list
- Add more specific phrases instead of single words
- Use context checking: require multiple keywords

Example:
```python
# Bad: Triggers on "read" alone
ast_keywords = ["read", "ast", ...]

# Good: More specific
ast_keywords = ["ast read", "ast_read", "read the ast", ...]
```

#### Budget Warnings Too Frequent

**Problem:** Getting warnings on normal usage.

**Solution:**
- Increase budgets in `AST_TOOLS_TOKEN_BUDGETS`
- Check character-to-token ratio (currently 4:1)
- Monitor actual usage in logs to set realistic budgets

```python
# Increase budget
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": 5000,  # Was 2000
    # ...
}
```

#### No Warnings When Expected

**Problem:** Context pressure warnings not appearing.

**Solution:**
1. Check logging level: `hermes --log-level warning`
2. Verify model is in `context_lengths` dict
3. Check compression threshold calculation
4. Start a longer conversation to trigger threshold

### MCP Configuration Issues

#### MCP Server Not Connecting

**Problem:** AST-Tools MCP server not available.

**Solution:**
1. Verify MCP config syntax: `python3 -m json.tool ~/.hermes/mcp.json`
2. Check command path: `which uvx`
3. Test MCP server manually: `uvx rw-ast-tools`
4. Check Hermes MCP status: `hermes mcp status`

#### Wrong Project Indexed

**Problem:** MCP server indexing wrong project.

**Solution:**
- Update `cwd` in MCP config to correct project path
- Restart MCP server: `hermes mcp restart`
- Refresh index: `/use mcp_ast_tools_refresh_index`

### Performance Issues

#### High Memory Usage

**Problem:** Hermes using excessive memory.

**Solution:**
- Lower compression threshold: `0.40` instead of `0.50`
- Use `/compress` more frequently
- Reduce token budgets to limit result sizes
- Start new sessions for unrelated topics

#### Slow Response Times

**Problem:** Hermes responding slowly.

**Solution:**
- Reduce hook logic complexity
- Check MCP server performance
- Limit search scope (use file filters)
- Use dry_run for large operations

### Debugging Configuration

#### Enable Debug Mode

```bash
hermes --log-level debug
```

#### Check Plugin Loading

```bash
hermes --log-level debug | grep "Plugin.*registered"
```

#### Check Hook Execution

```bash
hermes --log-level debug | grep "hook"
```

#### Check MCP Status

```bash
hermes mcp status
hermes mcp list-servers
```

## Configuration Examples

### Example 1: Production Configuration

Minimal configuration for production use:

```yaml
# ~/.hermes/config.yaml
logging:
  level: warning

plugins:
  enabled: true
  auto_load: true
```

```json
// ~/.hermes/mcp.json
{
  "mcpServers": {
    "ast-tools": {
      "command": "uvx",
      "args": ["rw-ast-tools"],
      "cwd": "/home/sysop/Workspaces/production-project"
    }
  }
}
```

### Example 2: Development Configuration

Verbose configuration for development:

```yaml
# ~/.hermes/config.yaml
logging:
  level: debug
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

plugins:
  enabled: true
  auto_load: true
  
session:
  memory_enabled: true
  compression_threshold: 0.40
  auto_compress: false

model:
  default: "qwen/qwen3.5-397b-a17b"
  context_length: 262144
```

```python
# ~/.hermes/plugins/ast-tools-tokens/__init__.py (excerpts)
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": 5000,  # Higher for development
    "structural_analysis": 8000,
    "default": 3000,
}

context_lengths = {
    "qwen/qwen3.5-397b-a17b": 262144,
    "default": 262144
}

compression_threshold = int(context_length * 0.40)  # More aggressive
```

### Example 3: Custom Domain Configuration

Configuration for GraphQL development:

```python
# ~/.hermes/plugins/ast-tools-context/__init__.py (excerpts)
ast_keywords = [
    # ... standard keywords ...
    "graphql", "schema", "type def",
    "query", "mutation", "resolver",
    "fragment", "directive"
]

def build_ast_tools_context(query: str) -> str:
    context = """..."""
    
    if "graphql" in query.lower():
        context += """

### GraphQL Patterns

- `type Query { $FIELD }`
- `type Mutation { $FIELD }`
- `type $TYPE { $FIELD }`
- `extend type $TYPE`
"""
    
    return context
```

## Configuration Reference

### File Locations

| File | Path | Purpose |
|------|------|---------|
| Hermes Config | `~/.hermes/config.yaml` | Main Hermes configuration |
| MCP Config | `~/.hermes/mcp.json` | MCP server configuration |
| Plugin Config | `~/.hermes/plugins/<plugin>/__init__.py` | Plugin code and settings |
| Plugin Metadata | `~/.hermes/plugins/<plugin>/plugin.yaml` | Plugin metadata |

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `HERMES_LOG_LEVEL` | Override logging level | `info` |
| `HERMES_CONFIG` | Override config path | `~/.hermes/config.yaml` |
| `AST_TOOLS_BUDGET` | Set default token budget | `1000` |
| `AST_TOOLS_COMPRESSION_THRESHOLD` | Set compression threshold | `0.50` |

### Configuration Files

- [Hermes Config Example](#hermes-configuration)
- [MCP Config Example](#mcp-server-configuration)
- [Plugin Config Examples](#advanced-configuration)

## Resources

- [Hermes Configuration Documentation](https://hermes-agent.nousresearch.com/docs/configuration)
- [MCP Configuration Guide](https://hermes-agent.nousresearch.com/docs/mcp)
- [Plugin Development Guide](https://hermes-agent.nousresearch.com/docs/plugin-dev)
- [Hooks Documentation](hooks.md)

---

**Previous:** [Hooks Documentation](hooks.md) | **Next:** [Installation Guide](../INSTALL.md)