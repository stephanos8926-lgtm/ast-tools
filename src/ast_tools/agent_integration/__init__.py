"""Agent integration modules for rw-ast-tools.

Standalone, importable modules with zero Hermes dependency.
Can be used by any agent framework (Hermes, FORGE, Claude Code, etc.).

Modules:
    context_builder — Build context blocks for LLM prompts about AST tools
    token_tracker — Token budget tracking and context pressure warnings
    error_correction — Common tool usage error detection and guidance
    session_intel — Codebase intelligence and session mutation tracking
"""

from ast_tools.agent_integration.context_builder import (
    KEYWORDS as AST_KEYWORDS,
)
from ast_tools.agent_integration.context_builder import (
    build_ast_tools_context,
    detect_ast_query,
)
from ast_tools.agent_integration.error_correction import (
    ERROR_PATTERNS,
    correct_tool_error,
    get_error_correction,
)
from ast_tools.agent_integration.session_intel import (
    call_codebase_summary,
    extract_modified_files,
    write_session_intel,
)
from ast_tools.agent_integration.token_tracker import (
    DEFAULT_BUDGETS,
    DEFAULT_CONTEXT_WINDOW,
    ContextPressureMonitor,
    TokenTracker,
)

__all__ = [
    "AST_KEYWORDS",
    "DEFAULT_BUDGETS",
    "DEFAULT_CONTEXT_WINDOW",
    "ERROR_PATTERNS",
    "ContextPressureMonitor",
    "TokenTracker",
    "build_ast_tools_context",
    "call_codebase_summary",
    "correct_tool_error",
    "detect_ast_query",
    "extract_modified_files",
    "get_error_correction",
    "write_session_intel",
]
