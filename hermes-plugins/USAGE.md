# AST-Tools Hermes Plugins - Usage Documentation

Comprehensive guide for using AST-Tools plugins with Hermes Agent.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Plugin Capabilities](#plugin-capabilities)
3. [Common Workflows](#common-workflows)
4. [AST-Tools Integration](#ast-tools-integration)
5. [Advanced Configuration](#advanced-configuration)
6. [Best Practices](#best-practices)
7. [Examples](#examples)

## Quick Start

### Basic Usage

Once installed, the plugins work automatically:

1. **Start a conversation** with Hermes Agent
2. **Ask about code analysis** topics
3. **Receive enhanced responses** with tool documentation

### What You Get

- Automatic tool documentation when relevant
- Token usage monitoring
- Context pressure warnings
- Smart recommendations

## Plugin Capabilities

### ast-tools-context

**Purpose:** Provide tool documentation automatically

**When it activates:**
- User mentions AST, code structure, or analysis topics
- Queries about code search or dependencies
- Discussions about structural editing

**What it provides:**
- Overview of 26 AST-Tools MCP capabilities
- Usage patterns for common workflows
- Tool-specific guidance
- Best practices

**Example:**
```
User: "How can I find all references to this function?"

Injected Context: Documentation about find_references tool
Response: "You can use the find_references tool to locate all usages..."
```

### ast-tools-tokens

**Purpose:** Monitor and manage token usage

**When it activates:**
- After any ast-tools operation (silent monitoring)
- When context approaches compression threshold (50%)
- When tool results exceed token budgets

**What it provides:**
- Token budget tracking
- Usage warnings in logs
- Context pressure alerts
- Recommendations for optimization

**Example:**
```
[After extensive conversation]

Injected Alert: "⚠️ Context Pressure Alert - Current usage: ~100k tokens..."
Recommendations: Use /compress, focus queries, etc.
```

## Common Workflows

### Workflow 1: Structural Code Search

**Goal:** Find code patterns across the codebase

**Steps:**
1. Start with semantic search for conceptual queries
2. Refine with ast_grep for structural patterns
3. Verify with ast_read for full context

**Example Conversation:**
```
User: "Find all API endpoints in the codebase"

Plugin: [Injects semantic_search and ast_grep documentation]

Assistant: "Let's search for API endpoints. I'll use semantic_search first 
to find relevant patterns, then use ast_grep with a pattern like:
`@app.route($PATH)` or `router.$METHOD($PATH)`."

[After search]
User: "Show me the actual code"

Assistant: "Using ast_read to get the full context of each match..."
```

### Workflow 2: Safe Code Modification

**Goal:** Make changes without breaking dependencies

**Steps:**
1. Analyze with structural_analysis
2. Check impact with impact_analysis
3. Preview edit with ast_edit (dry_run=true)
4. Apply edit (dry_run=false)
5. Verify with ast_read

**Example Conversation:**
```
User: "I need to rename this function"

Plugin: [Injects impact_analysis and ast_edit documentation]

Assistant: "Before renaming, let's check what will be affected:
1. Running impact_analysis to find all usages
2. Then I'll preview the rename with ast_edit (dry_run=true)
3. You can review, then I'll apply it"

[After analysis]
Assistant: "Found 5 references across 3 files. Here's the planned change..."
```

### Workflow 3: Understanding Dependencies

**Goal:** Map module relationships

**Steps:**
1. Get overview with codebase_summary
2. Extract structure with ast_read
3. Find dependencies with module_imports
4. Locate usages with find_references

**Example Conversation:**
```
User: "What does this module do and what depends on it?"

Plugin: [Injects ast_read and module_imports documentation]

Assistant: "Let me analyze the module structure:
1. ast_read to get exports and structure
2. module_imports for fan-in (who imports this)
3. module_imports for fan-out (what this imports)"
```

### Workflow 4: Managing Large Projects

**Goal:** Work efficiently with large codebases

**Steps:**
1. Monitor context usage continuously
2. Use focused queries instead of full context dumps
3. Compress proactively when needed
4. Start new sessions for unrelated topics

**Example:**
```
[Context pressure warning appears]

Plugin: "⚠️ Context Pressure Alert - 40% used, compression at 50%"

Assistant: "We're approaching context limits. Options:
1. Use /compress with focus on 'code structure'
2. Start new session for this new topic
3. I'll focus on most recent context only"
```

## AST-Tools Integration

### Required Setup

To fully utilize the plugins, you need:

1. **AST-Tools MCP Server** installed
2. **MCP Configuration** in Hermes
3. **Project indexing** completed (for search features)

### MCP Configuration

Add to `~/.hermes/mcp.json`:

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

### Indexing Your Project

```bash
# From Hermes, trigger index refresh
/use mcp_ast_tools_refresh_index
```

Or ask:
```
"Index my current project for structural search"
```

### Available Tools

The plugins document these 26 tools:

**Core Tools:**
- ast_grep
- ast_read
- ast_edit
- ast_generate_stub

**Analysis Tools:**
- structural_analysis
- impact_analysis
- module_imports
- find_references

**Search Tools:**
- semantic_search
- search_symbols
- find_symbol_definition
- list_symbols

**Index Tools:**
- refresh_index
- index_status

And more specialized tools for code generation, validation, etc.

## Advanced Configuration

### Customizing Context Injection

Edit `ast-tools-context/__init__.py`:

```python
# Add your domain-specific keywords
ast_keywords = [
    # ... existing keywords
    "graphql", "resolver", "mutation",  # For GraphQL projects
    "react component", "hooks",  # For React projects
    # Add your own
]

# Modify injected context
def build_ast_tools_context(query: str) -> str:
    # Start with base context
    context = """..."""
    
    # Add domain-specific tips
    if "graphql" in query.lower():
        context += "\n\n### GraphQL Tips\nUse ast_grep with pattern: `type Query { ... }`\n"
    
    return context
```

### Customizing Token Budgets

Edit `ast-tools-tokens/__init__.py`:

```python
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": 5000,  # Increase for large projects
    "structural_analysis": 8000,
    "semantic_search": 4000,
    # Add custom tool types
    "my_custom_tool": 3000,
}
```

### Model-Specific Settings

Add support for new models:

```python
context_lengths = {
    "qwen/qwen3.5-397b-a17b": 262144,
    "claude-3-opus": 200000,
    "gpt-4-turbo": 128000,
    "your-model": 65536,
    "default": 262144
}
```

### Compression Threshold

Adjust when warnings appear:

```python
# In check_context_pressure()
compression_threshold = int(context_length * 0.40)  # 40% instead of 50%
warning_threshold = compression_threshold * 0.80  # Warn at 80% of threshold
```

## Best Practices

### 1. Use Focused Queries

**Good:**
- "Find all REST API route definitions"
- "Show impact of changing this function signature"

**Avoid:**
- "Analyze my entire codebase"
- "Tell me everything about this file"

### 2. Preview Before Applying

Always use dry_run first:

```
"Preview this change with ast_edit dry_run=true"
"Show me what will change before applying"
```

### 3. Monitor Context Usage

Watch for warnings and:
- Use `/compress` proactively
- Start new sessions for unrelated work
- Focus on recent context

### 4. Layer Your Searches

Start broad, then narrow:

```
1. semantic_search: "API endpoints"
2. ast_grep: "@route" patterns
3. ast_read: Full context of matches
```

### 5. Understand Before Changing

Always analyze first:

```
1. structural_analysis: Understand code structure
2. impact_analysis: See what's affected
3. Then make changes
```

### 6. Use Context7 for Libraries

For external API documentation:

```
"Use context7 to get pymongo documentation"
```

### 7. Manage Large Results

When working with large codebases:

```
"Limit results to 10 matches"
"Focus on src/ directory only"
"Search only in Python files"
```

## Examples

### Example 1: Finding Unused Code

```
User: "Find unused functions in the codebase"

Plugin: [Injects find_references documentation]

Assistant: "I'll search for function definitions, then check 
which ones have no references:

1. Use ast_read to list all functions
2. Use find_references for each function
3. Functions with no references (except definition) are likely unused

Note: This is conservative - functions might be called dynamically."
```

### Example 2: Refactoring Preparation

```
User: "I want to extract this into a utility module"

Plugin: [Injects impact_analysis and module_imports documentation]

Assistant: "Great plan. Let's prepare:

1. impact_analysis: See all current usages
2. module_imports: Understand dependency structure
3. Plan new module location
4. ast_edit: Preview the extraction
5. Update imports in affected files

Shall we start with impact analysis?"
```

### Example 3: Understanding Legacy Code

```
User: "This codebase is confusing. Where do I start?"

Plugin: [Injects codebase_summary and structural_analysis documentation]

Assistant: "Let's build understanding systematically:

1. codebase_summary: High-level overview
2. structural_analysis: Find main entry points
3. module_imports: Identify core modules (high fan-in)
4. ast_read: Examine key modules in detail

I'll start with a summary of the codebase structure."
```

### Example 4: Type Safety Improvements

```
User: "Add type hints to this module"

Plugin: [Injects ast_generate_stub and ast_edit documentation]

Assistant: "For adding type hints:

1. ast_read: Understand current signatures
2. ast_generate_stub: Create .pyi stub file
3. Review suggested types
4. ast_edit: Apply hints to source (preserving formatting)

Would you like me to generate stubs first for review?"
```

### Example 5: Cross-Language Search

```
User: "Find similar patterns in Python and JavaScript"

Plugin: [Injects ast_grep documentation with multi-language support]

Assistant: "ast_grep supports 20+ languages. I'll run:

1. ast_grep with pattern in Python files
2. ast_grep with same pattern in JS files
3. Compare results

ast_grep patterns are language-aware, so the same pattern 
works across languages."
```

### Example 6: Managing Context Pressure

```
[After 2 hours of conversation]

Plugin: ⚠️ Context Pressure Alert
- Current usage: ~100,000 tokens (38% of window)
- Compression threshold: 131,072 tokens (50%)
- Compression will fire soon

Assistant: "We're getting close to context limits. 

Options:
1. /compress with focus='refactoring work'
2. I'll summarize key findings so far
3. Start new session for next phase

Which do you prefer?"
```

### Example 7: Debugging Plugin Issues

```
User: "The plugins don't seem to be working"

Assistant: "Let's troubleshoot:

1. Check installation:
   ls -la ~/.hermes/plugins/ast-tools-*/

2. Verify plugins loaded:
   hermes plugins list

3. Test with clear trigger:
   Ask: 'What is ast_grep?'
   (Should inject documentation)

4. Check logs:
   hermes --log-level debug
   Look for plugin registration"
```

## Troubleshooting

### Plugin-Related Issues

See [INSTALL.md](INSTALL.md#troubleshooting-installation) for installation issues.

### Usage-Related Issues

**Problem:** Context injecting when it shouldn't

**Solution:** 
- Check if query contains trigger keywords
- Remove or modify keywords in config

**Problem:** Token warnings too frequent

**Solution:**
- Increase budgets in ast-tools-tokens plugin
- Check if using limit parameters

**Problem:** Not getting expected documentation

**Solution:**
- Verify AST-Tools MCP server is connected
- Check that query matches trigger keywords
- Enable debug logging

### Performance Issues

**Problem:** High memory usage

**Solution:**
- Use /compress proactively
- Avoid loading entire codebases at once
- Use focused queries

**Problem:** Slow responses

**Solution:**
- Limit search scope
- Use dry_run for large edits
- Check MCP server performance

## Additional Resources

- [Main README](README.md) - Overview and quick start
- [INSTALL.md](INSTALL.md) - Installation guide
- [../docs/hooks.md](docs/hooks.md) - Detailed hooks documentation
- [../docs/configuration.md](docs/configuration.md) - Configuration guide

## Getting Help

1. Check this documentation first
2. Review individual plugin READMEs
3. Enable debug logging for troubleshooting
4. Consult Hermes Agent documentation

---

**Next:** [Hooks Documentation](docs/hooks.md) | [Configuration Guide](docs/configuration.md)