"""Structured prompt templates for LLM fix generation."""

from __future__ import annotations


class Prompts:
    """Prompt templates for LLM fix generation.

    Provides static methods for building structured prompts used by
    LLMClient. Handles code truncation to prevent token overflow.
    """

    MAX_CODE_CHARS = 6000  # Truncate code to avoid context overflow

    @staticmethod
    def fix_suggestion(
        code: str,
        diagnostic_message: str,
        diagnostic_code: str,
        file_path: str,
        language: str,
    ) -> str:
        """Build the fix suggestion prompt for an LLM.

        Args:
            code: Source code snippet containing the issue
            diagnostic_message: Human-readable diagnostic (e.g. "Unused import os")
            diagnostic_code: Rule code (e.g. "F401")
            file_path: File path for context
            language: Language ID (python, typescript, etc.)

        Returns:
            Formatted prompt string ready for LLM consumption
        """
        # Truncate code if too long to avoid token overflow
        if len(code) > Prompts.MAX_CODE_CHARS:
            code = code[:Prompts.MAX_CODE_CHARS] + "\n# ... [truncated]\n"

        return (
            "You are an expert code reviewer and fixer. Given a diagnostic and "
            "the surrounding code context, suggest the minimal, correct fix.\n\n"
            f"Diagnostic: {diagnostic_message}\n"
            f"Rule: {diagnostic_code}\n"
            f"File: {file_path}\n"
            f"Language: {language}\n\n"
            "Code context:\n"
            f"```{language}\n{code}```\n\n"
            "Return ONLY the unified diff that fixes the issue. "
            "Use standard unified diff format with lines starting with + and -. "
            "Be minimal — only change what's needed to fix the diagnostic."
        )
