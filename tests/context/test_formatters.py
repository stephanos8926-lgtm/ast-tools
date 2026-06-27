"""Tests for MarkdownFormatter - token counting, output formatting."""

from ast_tools.context.formatters import MarkdownFormatter, count_tokens


class TestTokenCounting:
    """Test token counting accuracy."""

    def test_count_tokens_simple(self):
        """Test basic token counting."""
        tokens = count_tokens("hello world")
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_count_tokens_empty(self):
        """Test empty string."""
        tokens = count_tokens("")
        assert tokens == 0

    def test_count_tokens_consistency(self):
        """Test same text gives same count."""
        text = "def hello_world(): return 'hello'"
        tokens1 = count_tokens(text)
        tokens2 = count_tokens(text)
        assert tokens1 == tokens2

    def test_count_tokens_caching(self):
        """Test caching works."""
        from ast_tools.context.formatters import _TOKEN_CACHE

        cache_size_before = len(_TOKEN_CACHE)

        text = "test caching"
        count_tokens(text)
        count_tokens(text)

        assert len(_TOKEN_CACHE) == cache_size_before + 1


class TestMarkdownFormatter:
    """Test markdown output formatting."""

    def test_formatter_init(self):
        """Test formatter initialization."""
        formatter = MarkdownFormatter()
        assert formatter is not None

    def test_format_symbol_basic(self):
        """Test formatting a basic symbol."""
        formatter = MarkdownFormatter()

        symbol = {
            "id": "sym-1",
            "name": "AuthService",
            "kind": "class",
            "file_path": "src/auth.py",
            "line": 42,
            "signature": "class AuthService:",
            "docstring": "Handles user authentication.",
            "relevance_score": 0.87,
            "relevance_breakdown": {
                "semantic": 0.92,
                "recency": 0.8,
                "usage": 0.9,
                "kind": 1.0,
                "proximity": 0.0,
                "callgraph": 0.0,
            },
        }

        markdown = formatter.format_symbol(symbol)

        assert "AuthService" in markdown
        assert "class" in markdown
        assert "src/auth.py:42" in markdown
        assert "0.87" in markdown
        assert "semantic: 0.92" in markdown
        assert "```python" in markdown

    def test_format_symbol_with_callgraph(self):
        """Test formatting with callgraph info."""
        formatter = MarkdownFormatter()

        symbol = {
            "id": "sym-2",
            "name": "login_handler",
            "kind": "function",
            "file_path": "src/routes.py",
            "line": 15,
            "signature": "async def login_handler(request: Request) -> Response:",
            "docstring": "HTTP handler for login endpoint.",
            "relevance_score": 0.74,
            "relevance_breakdown": {
                "semantic": 0.65,
                "recency": 0.7,
                "usage": 0.6,
                "kind": 0.7,
                "proximity": 1.0,
                "callgraph": 0.9,
            },
        }

        markdown = formatter.format_symbol(symbol)

        assert "login_handler" in markdown
        assert "function" in markdown
        assert "proximity: 1.0" in markdown
        assert "callgraph: 0.9" in markdown

    def test_format_context_header(self):
        """Test context header generation."""
        formatter = MarkdownFormatter()

        header = formatter.format_header(
            total_injected=3,
            total_available=10,
            tokens_used=900,
            tokens_budget=3000,
            model_context_window=32000,
        )

        assert "Injected 3/10" in header
        assert "900/3000" in header
        assert "32K" in header or "32000" in header

    def test_format_empty_result(self):
        """Test empty result message."""
        formatter = MarkdownFormatter()

        markdown = formatter.format_empty("authentication")

        assert "No relevant symbols found" in markdown
        assert "authentication" in markdown
