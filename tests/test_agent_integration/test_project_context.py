"""Tests for ast_tools.agent_integration project_context module.

Verifies:
- detect_project_query broadens the trigger to natural-language code queries
  without over-firing on generic/non-code queries.
- build_project_context degrades gracefully (returns None, never raises) when
  there is no index / no meaningful results, and is event-loop-safe.
"""

from ast_tools.agent_integration import (
    build_project_context,
    detect_project_query,
)


class TestDetectProjectQuery:
    """Natural-language code queries should trigger; generic should not."""

    def test_detects_ast_tool_keywords(self):
        # AST keywords still trigger via project detection
        assert detect_project_query("ast_grep functions")
        assert detect_project_query("semantic search the codebase")

    def test_detects_natural_language_code_query(self):
        # This is the KEY improvement — NLP code queries the old keyword
        # detect_ast_query() missed:
        assert detect_project_query("where is the database pool")
        assert detect_project_query("show me the auth middleware")
        assert detect_project_query("how does retry logic work")
        assert detect_project_query("find the websocket handler")
        assert detect_project_query("what calls process_payment")
        assert detect_project_query("find all function definitions")

    def test_does_not_detect_generic_non_code_query(self):
        # Broad trigger must NOT over-fire on unrelated questions
        assert not detect_project_query("what is the weather today")
        assert not detect_project_query("tell me about your hobbies")
        assert not detect_project_query("hello there")
        assert not detect_project_query("")

    def test_detects_project_referential_phrasing(self):
        assert detect_project_query("in our codebase, how are errors handled")
        assert detect_project_query("find in this project the retry helper")


class TestBuildProjectContext:
    """Graceful degradation — must never raise, returns None when no results."""

    def test_returns_none_on_absent_or_empty_index(self, monkeypatch):
        # Force an empty/no-op semantic result path by pointing at a temp DB
        # that doesn't exist; _tool_semantic_search short-circuits on 0 symbols.
        import tempfile
        from pathlib import Path

        empty_db = Path(tempfile.mkdtemp()) / "missing.db"
        result = build_project_context(
            "database pool", k=3, token_budget=1024, db_path=str(empty_db)
        )
        assert result is None

    def test_returns_none_for_no_match_query(self):
        import tempfile
        from pathlib import Path

        empty_db = Path(tempfile.mkdtemp()) / "missing.db"
        result = build_project_context(
            "zzzz_nonexistent_xyzzy", k=3, token_budget=1024, db_path=str(empty_db)
        )
        assert result is None

    def test_event_loop_safe(self):
        # Calling build_project_context must not interfere with an active loop.
        import asyncio
        import tempfile
        from pathlib import Path

        async def inner():
            empty_db = Path(tempfile.mkdtemp()) / "missing.db"
            return build_project_context(
                "anything", k=2, token_budget=512, db_path=str(empty_db)
            )

        result = asyncio.run(inner())
        # Graceful — no exception, no "event loop already running"
        assert result is None

    def test_returns_dict_shape_when_context_produced(self, monkeypatch):
        # When semantic search yields context, return {"context": markdown}.
        # Stub _tool_semantic_search to simulate a populated index; stub the
        # readiness guard so the test stays hermetic (no real DB dependency).
        import json

        fake = json.dumps({
            "results": [{"name": "x", "file_path": "/a.py", "kind": "function"}],
            "context_injection": {
                "tokens_used": 120,
                "context_markdown": "## Context\n\n### /a.py — x (function)",
                "diversity_applied": True,
            },
        })

        def fake_tool(args):
            return fake

        monkeypatch.setattr(
            "ast_tools.agent_integration.project_context._run_semantic_search",
            fake_tool,
        )
        monkeypatch.setattr(
            "ast_tools.agent_integration.project_context._index_ready",
            lambda db_path: True,
        )
        result = build_project_context("something", k=5)
        assert result is not None
        assert "context" in result
        assert "120" in result["context"]  # tokens_used surfaced