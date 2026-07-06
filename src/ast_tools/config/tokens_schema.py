"""Token budget defaults and JSON Schema for tokens.yaml validation."""

DEFAULT_TOKENS: dict[str, dict[str, int]] = {
    "ast_grep": {"max_input_tokens": 4096, "max_output_tokens": 16384},
    "ast_edit": {"max_input_tokens": 8192, "max_output_tokens": 4096},
    "ast_read": {"max_input_tokens": 2048, "max_output_tokens": 32768},
    "ast_generate_stub": {"max_input_tokens": 4096, "max_output_tokens": 8192},
    "ast_refactor_extract_interface": {"max_input_tokens": 8192, "max_output_tokens": 8192},
    "structural_analysis": {"max_input_tokens": 4096, "max_output_tokens": 16384},
    "project_info": {"max_input_tokens": 2048, "max_output_tokens": 4096},
    "codebase_summary": {"max_input_tokens": 2048, "max_output_tokens": 2048},
    "find_references": {"max_input_tokens": 2048, "max_output_tokens": 8192},
    "impact_analysis": {"max_input_tokens": 2048, "max_output_tokens": 8192},
    "module_imports": {"max_input_tokens": 2048, "max_output_tokens": 8192},
    "search_symbols": {"max_input_tokens": 1024, "max_output_tokens": 8192},
    "semantic_search": {"max_input_tokens": 512, "max_output_tokens": 8192},
    "index_status": {"max_input_tokens": 512, "max_output_tokens": 2048},
    "refresh_index": {"max_input_tokens": 1024, "max_output_tokens": 4096},
}

TOKENS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        tool: {
            "type": "object",
            "properties": {
                "max_input_tokens": {"type": "integer", "minimum": 128},
                "max_output_tokens": {"type": "integer", "minimum": 128},
            },
            "required": ["max_input_tokens", "max_output_tokens"],
            "additionalProperties": False,
        }
        for tool in DEFAULT_TOKENS
    },
    "additionalProperties": False,
}
