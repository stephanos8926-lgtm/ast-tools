# Hooks Documentation

Detailed documentation of Hermes plugin hooks used by AST-Tools plugins.

## Overview

Hermes Agent plugins use hooks to intercept and modify agent behavior at specific points in the execution lifecycle.

The AST-Tools plugins use two hooks:
- `pre_llm_call`: Inject context before LLM invocation
- `post_tool_call`: Track tool usage after execution

## Hook: pre_llm_call

### Purpose

Called before every LLM invocation, allowing plugins to inject context, modify prompts, or add warnings.

### Registration

```python
def register(ctx: PluginContext):
    ctx.register_hook("pre_llm_call", my_hook_function)
```

### Signature

```python
def my_hook_function(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs
) -> dict | None:
    ...
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | `str` | Unique identifier for current session |
| `user_message` | `str` | User's current message/query |
| `conversation_history` | `list` | List of previous messages: `[{"role": "user/assistant", "content": "..."}]` |
| `is_first_turn` | `bool` | `True` if this is the first turn in the session |
| `model` | `str` | Current LLM model name (e.g., `"qwen/qwen3.5-397b-a17b"`) |
| `platform` | `str` | Platform identifier: `"cli"`, `"telegram"`, `"discord"`, etc. |
| `**kwargs` | `dict` | Additional context (future-proofing) |

### Returns

- **`dict`**: Return `{"context": "your injected text"}` to inject context
- **`None`**: Return `None` to make no changes

Multiple plugins can inject context; Hermes combines them in registration order.

### Example Implementation

```python
def inject_ast_tools_context(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs
) -> dict | None:
    # Check if relevant
    if "ast" not in user_message.lower():
        return None
    
    # Build context
    context = build_context()
    
    # Inject
    return {"context": context}
```

### Usage in ast-tools-context

The `ast-tools-context` plugin uses this hook to:

1. Check if `user_message` contains AST-related keywords
2. Build documentation context
3. Return context for injection

```python
def inject_ast_tools_context(...):
    ast_keywords = ["ast ", "ast-grep", "code structure", ...]
    
    if not any(kw in user_message.lower() for kw in ast_keywords):
        return None
    
    context = build_ast_tools_context(user_message)
    return {"context": context}
```

### Usage in ast-tools-tokens

The `ast-tools-tokens` plugin uses this hook to:

1. Calculate total context usage
2. Estimate tokens in conversation history
3. Compare to compression threshold
4. Inject warning if approaching limit

```python
def check_context_pressure(...):
    # Calculate usage
    estimated_tokens = sum(len(msg["content"]) for msg in conversation_history) // 4
    
    # Check threshold
    if estimated_tokens >= compression_threshold * 0.80:
        return {"context": build_warning(estimated_tokens)}
    
    return None
```

### Best Practices

1. **Be specific**: Only inject when truly relevant
2. **Be concise**: Keep context under 1000 tokens
3. **Be helpful**: Provide actionable information
4. **Check relevance**: Analyze `user_message` before injecting
5. **Don't overuse**: Return `None` when not needed

### Common Use Cases

- Injecting tool documentation
- Adding warnings or alerts
- Modifying system prompts
- Adding retrieval context
- Injecting memory summaries

## Hook: post_tool_call

### Purpose

Called after every tool invocation, allowing plugins to monitor, log, or modify tool results.

### Registration

```python
def register(ctx: PluginContext):
    ctx.register_hook("post_tool_call", my_hook_function)
```

### Signature

```python
def my_hook_function(
    tool_name: str,
    params: dict,
    result: str,
    session_id: str | None = None,
    **kwargs
) -> dict | None:
    ...
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_name` | `str` | Name of the tool that was called (e.g., `"mcp_ast_tools_ast_grep"`) |
| `params` | `dict` | Parameters passed to the tool |
| `result` | `str` | Tool result string |
| `session_id` | `str \| None` | Session identifier (may be None) |
| `**kwargs` | `dict` | Additional context |

### Returns

- **`dict`**: Return `{"modified_result": "new result"}` to modify the result
- **`None`**: Return `None` to leave result unchanged

Most plugins use this hook for monitoring only (return `None`).

### Example Implementation

```python
def track_ast_tools_usage(
    tool_name: str,
    params: dict,
    result: str,
    **kwargs
):
    # Only track ast-tools
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    
    # Estimate tokens
    tokens = len(result) // 4
    
    # Log if exceeds budget
    if tokens > BUDGET:
        logger.warning(f"Tool exceeded budget: {tokens} tokens")
    
    # No modification
    return None
```

### Usage in ast-tools-tokens

The `ast-tools-tokens` plugin uses this hook to:

1. Check if tool is ast-tools related
2. Extract tool type from name
3. Look up budget for tool type
4. Estimate token count
5. Log warning if exceeds budget

```python
def track_ast_tools_usage(tool_name, params, result, **kwargs):
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    
    tool_key = tool_name.replace("mcp_ast_tools_", "").split("_")[0]
    budget = AST_TOOLS_TOKEN_BUDGETS.get(tool_key, 1000)
    
    estimated_tokens = len(result) // 4
    
    if estimated_tokens > budget:
        logger.warning(f"Exceeded budget: {tool_name}")
    
    return None
```

### Best Practices

1. **Minimize latency**: Keep hook logic fast
2. **Don't block**: Avoid long operations
3. **Log appropriately**: Use logging, not prints
4. **Check tool names**: Filter for relevant tools
5. **Preserve results**: Only modify when necessary

### Common Use Cases

- Token usage tracking
- Result caching
- Result filtering or redaction
- Usage logging/analytics
- Automatic retries
- Result transformation

## Hook Lifecycle

### Execution Order

When Hermes processes a conversation turn:

1. User sends message
2. **`pre_llm_call` hooks** run (in registration order)
3. Contexts are combined
4. LLM is called with injected context
5. LLM generates response (may include tool calls)
6. Tools are executed
7. **`post_tool_call` hooks** run (in registration order)
8. Response is finalized
9. Response sent to user

### Multiple Hooks

Multiple plugins can register the same hook:

```python
# Plugin A
ctx.register_hook("pre_llm_call", inject_tool_docs)

# Plugin B
ctx.register_hook("pre_llm_call", inject_memory)

# Both run, contexts combined
```

Order: Hooks run in registration order (plugin load order).

## Hook Context Injection

### Format

Injected context should be formatted as:

```python
return {
    "context": """
## Section Header

Your documentation or message here.

Use Markdown formatting for clarity.
"""
}
```

### Multiple Injections

If multiple plugins inject context:

```python
# Plugin A returns:
{"context": "Context A"}

# Plugin B returns:
{"context": "Context B"}

# LLM receives:
"""
Context A

Context B
"""
```

Hermes handles concatenation automatically.

### Context Placement

Injected context typically appears:

1. After system prompt
2. Before conversation history
3. Before current user message

This ensures the LLM sees it before responding.

## Error Handling

### Hook Errors

If a hook raises an exception:

1. Hermes logs the error
2. Hook execution stops
3. Other hooks continue
4. Conversation proceeds without injection

### Best Practices

```python
def my_hook(...):
    try:
        # Your logic here
        result = process()
        return {"context": result}
    except Exception as e:
        logger.error(f"Hook error: {e}")
        return None  # Fail gracefully
```

## Testing Hooks

### Unit Testing

```python
def test_inject_ast_tools_context():
    result = inject_ast_tools_context(
        session_id="test-123",
        user_message="How does ast_grep work?",
        conversation_history=[],
        is_first_turn=True,
        model="qwen/qwen3.5-397b-a17b",
        platform="cli"
    )
    
    assert result is not None
    assert "ast_grep" in result["context"]
```

### Integration Testing

1. Install plugin
2. Start Hermes session
3. Send test messages
4. Verify context injection
5. Check logs for errors

## Advanced Hooks

### Other Available Hooks

Hermes supports additional hooks:

- `pre_session_start`: Before session initialization
- `post_session_end`: After session ends
- `pre_tool_call`: Before tool execution (not implemented yet)
- `on_user_message`: When user sends message
- Custom hooks (plugin-specific)

### Creating Custom Hooks

Plugins can define custom hooks for other plugins:

```python
# Define custom hook
def register(ctx: PluginContext):
    ctx.register_hook("ast_tools_custom", my_custom_hook)

# Use in another plugin
ctx.invoke_hook("ast_tools_custom", ...)
```

## Debugging Hooks

### Enable Debug Logging

```bash
hermes --log-level debug
```

### Check Hook Registration

Look for log messages:

```
[DEBUG] Plugin ast-tools-context registered hook: pre_llm_call
[DEBUG] Plugin ast-tools-tokens registered hook: post_tool_call
```

### Monitor Hook Execution

```bash
hermes --log-level debug | grep "hook"
```

See hook invocations and results.

### Common Issues

**Hook not running:**
- Check registration in `register()` function
- Verify hook name matches exactly
- Check plugin loaded successfully

**Hook running but not injecting:**
- Check return value (must return `dict` with `"context"`)
- Check condition logic (may be returning `None`)
- Check logs for errors

**Hook causing errors:**
- Enable debug logging
- Check exception stack trace
- Test hook logic in isolation

## Performance Considerations

### Optimizing pre_llm_call

```python
# Bad: Expensive operation every call
def inject_context(...):
    huge_data = load_massive_file()  # Slow!
    return {"context": huge_data}

# Good: Check relevance first
def inject_context(...):
    if not is_relevant(user_message):
        return None  # Fast path
    
    context = load_context()
    return {"context": context}
```

### Optimizing post_tool_call

```python
# Bad: Process every tool call
def track_usage(...):
    process_tool_call(tool_name, params, result)  # For ALL tools

# Good: Filter first
def track_usage(...):
    if not tool_name.startswith("mcp_ast_tools_"):
        return  # Early return
    
    # Only process relevant tools
    process_tool_call(tool_name, params, result)
```

## Reference Implementation

Complete example of both hooks:

```python
"""
Complete hook implementation example
"""

from hermes_cli.plugins import PluginContext
import logging

logger = logging.getLogger(__name__)

def register(ctx: PluginContext):
    """Register all hooks."""
    ctx.register_hook("pre_llm_call", inject_context)
    ctx.register_hook("post_tool_call", track_usage)

def inject_context(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs
) -> dict | None:
    """
    Inject context when relevant.
    
    Returns dict with 'context' key or None.
    """
    # Check relevance
    if not is_relevant(user_message):
        return None
    
    # Build context
    context = build_context()
    
    logger.debug(f"Injecting context for: {user_message[:50]}...")
    return {"context": context}

def track_usage(
    tool_name: str,
    params: dict,
    result: str,
    **kwargs
):
    """
    Track tool usage.
    
    Returns None (no result modification).
    """
    # Filter for relevant tools
    if not tool_name.startswith("mcp_my_tools_"):
        return
    
    # Track usage
    tokens = len(result) // 4
    logger.info(f"Tool {tool_name} used {tokens} tokens")
    
    # No modification
    return None

def is_relevant(message: str) -> bool:
    """Check if message is relevant."""
    keywords = ["keyword1", "keyword2"]
    message_lower = message.lower()
    return any(kw in message_lower for kw in keywords)

def build_context() -> str:
    """Build context string."""
    return "## Documentation\n\nYour context here."
```

## Resources

- [Hermes Plugin System Documentation](https://hermes-agent.nousresearch.com/docs/plugins)
- [Plugin Development Guide](https://hermes-agent.nousresearch.com/docs/plugin-dev)
- [AST-Tools Context Plugin](../ast-tools-context/__init__.py)
- [AST-Tools Tokens Plugin](../ast-tools-tokens/__init__.py)

---

**Next:** [Configuration Guide](configuration.md)