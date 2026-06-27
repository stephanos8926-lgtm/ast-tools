"""Markdown formatting and token counting for context injection."""

import tiktoken

# Token cache for efficiency
_TOKEN_CACHE: dict[str, int] = {}


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for

    Returns:
        Token count
    """
    if not text:
        return 0

    if text in _TOKEN_CACHE:
        return _TOKEN_CACHE[text]

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate (4 chars per token)
        tokens = len(text) // 4

    _TOKEN_CACHE[text] = tokens
    return tokens


class MarkdownFormatter:
    """Formats context injection results as markdown for LLM consumption."""

    def __init__(self):
        """Initialize formatter."""
        pass

    def format_symbol(self, symbol: dict) -> str:
        """Format a single symbol as markdown.

        Args:
            symbol: Symbol dict with keys:
                - id, name, kind, file_path, line
                - signature, docstring
                - relevance_score, relevance_breakdown

        Returns:
            Formatted markdown string
        """
        name = symbol.get("name", "Unknown")
        kind = symbol.get("kind", "symbol")
        file_path = symbol.get("file_path", "unknown")
        line = symbol.get("line", 0)
        signature = symbol.get("signature", "")
        docstring = symbol.get("docstring", "")
        relevance_score = symbol.get("relevance_score", 0.0)
        breakdown = symbol.get("relevance_breakdown", {})

        # Build header
        header = f"### `{file_path}:{line}` — `{name}` ({kind})"

        # Build code block
        code_block = f"```python\n{signature}\n"
        if docstring:
            code_block += f'"""{docstring}"""'
        code_block += "```"

        # Build relevance info
        score_line = f"**Relevance:** {relevance_score:.2f}"

        breakdown_parts = []
        if "semantic" in breakdown:
            breakdown_parts.append(f"semantic: {breakdown['semantic']:.2f}")
        if "recency" in breakdown:
            breakdown_parts.append(f"recency: {breakdown['recency']:.2f}")
        if "usage" in breakdown:
            breakdown_parts.append(f"usage: {breakdown['usage']:.2f}")
        if "kind" in breakdown:
            breakdown_parts.append(f"kind: {breakdown['kind']:.2f}")
        if "proximity" in breakdown:
            breakdown_parts.append(f"proximity: {breakdown['proximity']:.2f}")
        if "callgraph" in breakdown:
            breakdown_parts.append(f"callgraph: {breakdown['callgraph']:.2f}")

        breakdown_str = ", ".join(breakdown_parts)
        if breakdown_str:
            score_line += f" ({breakdown_str})"

        # Build why_included (if available)
        why = symbol.get("why_included", "")
        why_line = f"\n**Why included:** {why}" if why else ""

        return f"{header}\n{code_block}\n{score_line}{why_line}"

    def format_header(
        self,
        total_injected: int,
        total_available: int,
        tokens_used: int,
        tokens_budget: int,
        model_context_window: int,
    ) -> str:
        """Format context injection header.

        Args:
            total_injected: Number of symbols injected
            total_available: Max symbols available
            tokens_used: Tokens used by injected context
            tokens_budget: Token budget for context
            model_context_window: Model's total context window

        Returns:
            Formatted header string
        """
        # Format context window size
        if model_context_window >= 1000000:
            window_str = f"{model_context_window / 1000000:.0f}M"
        elif model_context_window >= 1000:
            window_str = f"{model_context_window / 1000:.0f}K"
        else:
            window_str = str(model_context_window)

        header = (
            f"## Context: Relevant Symbols (injected by ast-tools)\n\n"
            f"*Injected {total_injected}/{total_available} symbols • "
            f"{tokens_used}/{tokens_budget} tokens • "
            f"{window_str} context window*\n"
        )

        return header

    def format_empty(self, query: str) -> str:
        """Format empty result message.

        Args:
            query: Original query that yielded no results

        Returns:
            Formatted message
        """
        return f"## Context: Relevant Symbols\n\n*No relevant symbols found for '{query}'.*\n"

    def format_context_injection_result(
        self,
        symbols: list[dict],
        total_available: int,
        tokens_used: int,
        tokens_budget: int,
        model_context_window: int,
        query: str | None = None,
    ) -> str:
        """Format complete context injection result.

        Args:
            symbols: List of symbol dicts to inject
            total_available: Max symbols available
            tokens_used: Tokens used
            tokens_budget: Token budget
            model_context_window: Model context window
            query: Original query (optional)

        Returns:
            Complete formatted markdown
        """
        if not symbols:
            if query:
                return self.format_empty(query)
            return self.format_empty("unknown")

        lines = [
            self.format_header(
                total_injected=len(symbols),
                total_available=total_available,
                tokens_used=tokens_used,
                tokens_budget=tokens_budget,
                model_context_window=model_context_window,
            )
        ]

        for symbol in symbols:
            lines.append("\n")
            lines.append(self.format_symbol(symbol))

        return "\n".join(lines)
