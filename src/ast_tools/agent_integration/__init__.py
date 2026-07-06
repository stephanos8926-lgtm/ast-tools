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
    build_ast_tools_context,
    detect_ast_query,
    KEYWORDS as AST_KEYWORDS,
)
from ast_tools.agent_integration.token_tracker import (
    TokenTracker,
    ContextPressureMonitor,
    DEFAULT_BUDGETS,
    DEFAULT_CONTEXT_WINDOW,
)
from ast_tools.agent_integration.error_correction import (
    correct_tool_error,
    get_error_correction,
    ERROR_PATTERNS,
)
from ast_tools.agent_integration.session_intel import (
    call_codebase_summary,
    extract_modified_files,
    write_session_intel,
)

__all__ = [
    "build_ast_tools_context",
    "detect_ast_query",
    "AST_KEYWORDS",
    "TokenTracker",
    "ContextPressureMonitor",
    "DEFAULT_BUDGETS",
    "DEFAULT_CONTEXT_WINDOW",
    "correct_tool_error",
    "get_error_correction",
    "ERROR_PATTERNS",
    "call_codebase_summary",
    "extract_modified_files",
    "write_session_intel",
]
