# rw-ast-tools Hermes Plugin

**Version:** 2.0.0  
**License:** MIT  
**Author:** RapidWebs Enterprise

---

A unified Hermes Agent plugin that provides AST-Tools integration: automatic context injection, token usage tracking, session intelligence, and context pressure monitoring.

## Overview

This plugin replaces the three legacy plugins (`ast-tools-context`, `ast-tools-tokens`, `ast-tools-codebase-index`) with a single, streamlined plugin that imports from the `ast_tools.agent_integration` package — zero Hermes dependency in the core logic.

## Features

- **Automatic context injection** — When discussing code analysis topics, relevant AST-Tools documentation is injected
- **Token usage tracking** — Monitors token budgets per tool, prevents context overflow
- **Session intelligence** — Tracks file mutations, MCP call patterns, codebase metrics
- **Context pressure monitoring** — Warns when approaching compression thresholds
- **Smart recommendations** — Suggests focused queries, compression, or new sessions

## Quick Start

### Prerequisites

- **Hermes Agent** (recent version with plugin support)
- **Python 3.10+**
- **rw-ast-tools MCP Server** (`ast-tools-server`)

### Installation

```bash
# From the hermes-plugins directory
cp -r rw-ast-tools ~/.hermes/plugins/

# Or use the installer script
./scripts/install.sh rw-ast-tools

# Restart Hermes to load the plugin
hermes restart
```

### Verification

```bash
hermes plugins list
```

You should see: `rw-ast-tools`

## Usage

The plugin works automatically:

1. **Context Injection**: When you ask about AST, code structure, or related topics, documentation is provided
2. **Token Tracking**: All ast-tools operations are monitored for token usage
3. **Context Pressure**: Warnings appear when approaching compression thresholds

### Example Workflows

#### Code Search
```
User: Find all function definitions in the codebase
Plugin: [Injects ast_grep documentation]
Assistant: Use ast_grep with pattern `def $FUNC($$$ARGS)` to search for all function definitions.
```

#### Safe Refactoring
```
User: I want to refactor this function, what should I check first?
Plugin: [Injects impact_analysis documentation]
Assistant: Run impact_analysis to understand affected files. Use ast_edit with dry_run=true to preview.
```

#### Context Pressure
```
[After extensive conversation]
Plugin: [Injects context pressure warning]
Assistant: ⚠️ Context Pressure Alert. Consider /compress or focusing on recent context.
```

## Configuration

### Customizing Context Injection

Edit `~/.hermes/plugins/rw-ast-tools/__init__.py`:

```python
# Add keywords to trigger context
AST_KEYWORDS = [
    "ast", "ast-grep", "structural", "code search",
    # Add your domain-specific keywords
]

# Modify injected context
def build_context(query: str) -> str:
    context = "..."
    if "graphql" in query.lower():
        context += "\n### GraphQL Tips\nUse pattern: `type Query { ... }`\n"
    return context
```

### Token Budgets

```python
# In the same file
TOKEN_BUDGETS = {
    "ast_grep": 2000,
    "structural_analysis": 4000,
    "semantic_search": 2500,
    # Adjust for your project size
}
```

### Model Context Lengths

```python
CONTEXT_LENGTHS = {
    "qwen/qwen3.5-397b-a17b": 262144,
    "claude-3-opus": 200000,
    "default": 262144,
}
```

## Hooks Documentation

| Hook | Purpose | Trigger |
|------|---------|---------|
| `on_session_start` | Inject session intelligence | Session begins |
| `pre_llm_call` | Inject context / pressure warnings | Before LLM processes message |
| `post_tool_call` | Track token usage, update session intel | After tool execution |

## Troubleshooting

### Plugin Not Loading
```bash
# Check syntax
python3 -m py_compile ~/.hermes/plugins/rw-ast-tools/__init__.py

# Verify plugin.yaml
python3 -c "import yaml; yaml.safe_load(open('~/.hermes/plugins/rw-ast-tools/plugin.yaml'))"

# Check Hermes logs
journalctl --user -u hermes-gateway -n 50
```

### Context Not Injecting
- Your query must contain recognized keywords
- Add custom keywords to `AST_KEYWORDS` list
- Enable debug: `hermes --log-level debug`

## Development

### Testing
```bash
# Verify syntax
python3 -m py_compile rw-ast-tools/__init__.py

# Test install
./scripts/install.sh rw-ast-tools --dry-run

# Run verification
./scripts/verify.sh
```

## License

MIT License — RapidWebs Enterprise