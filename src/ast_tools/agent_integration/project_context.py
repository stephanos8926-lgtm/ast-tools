"""Project-aware context injection for AST-tools agent integration.

Detects natural-language codebase queries and injects real project symbols
from the semantic index (via semantic_search). Zero Hermes dependency —
pure functions usable by any agent framework (same design as sibling modules
in this package).

Design notes (2026-08-13, plan-and-audit MEDIUM mode):
- db_path is NEVER hardcoded here: when None, the canonical default
  (~/.ast-tools/cache/codebase.db) is resolved by the DB layer, NOT by this
  module. The old ast-tools-project-context reference hardcoded a nonexistent
  path and silently never injected (reverse-audit finding).
- Event-loop safe: _tool_semantic_search is a sync function (query embeddings
  via provider_generate_embedding_sync; reranker via thread-local loop), so it
  is safe to call from within a running asyncio loop (Hermes hook context).
- Index pre-check: _tool_semantic_search AUTO-REFRESHES an empty index (scans
  the parent dir) — a cost hazard from a hot plugin hook. _index_ready() bails
  fast to None when the DB is missing or has zero symbols.
"""

from __future__ import annotations

import json
import logging
import re as _re
import sqlite3
from pathlib import Path
from typing import Any

from ast_tools.agent_integration.context_builder import detect_ast_query

logger = logging.getLogger(__name__)

# ── Triggers ──────────────────────────────────────────────────────────────

# Unambiguous code-intent interrogatives (no extra code vocab needed).
CODE_INTENT_PHRASES = (
    "what calls",
    "what uses",
    "what imports",
    "who calls",
    "who uses",
    "callers of",
    "callees of",
    "references to",
    "referenced by",
    "imported by",
)

# Project-referential phrasing that indicates "this codebase".
PROJECT_PHRASES = (
    "our codebase",
    "this codebase",
    "my codebase",
    "this project",
    "my project",
    "our project",
    "in this repo",
    "in our repo",
    "in the codebase",
    "across the codebase",
)

# General code-question cues ("where is …", "how does …").
INTERROGATIVE_CUES = (
    "where is",
    "where are",
    "where's",
    "how does",
    "how do",
    "how is",
    "show me",
    "find",
    "search",
    "locate",
    "list",
    "explain",
    "what is",
    "what are",
    "give me",
    "get the",
)

# Domain vocabulary that strongly implies a code/codebase topic.
# Uses word-boundary-aware matching to avoid substring false positives
# (e.g., "api" inside "capital").
_CODE_TERMS_RAW = (
    "function", "class", "method", "handler", "middleware", "pool", "cache",
    "retry", "callback", "service", "module", "import", "dependency",
    "symbol", "api", "endpoint", "route", "database", "db", "websocket",
    "socket", "config", "configuration", "error", "exception", "parser",
    "serializer", "queue", "worker", "task", "controller", "repository",
    "model", "schema", "auth", "login", "token", "session", "policy",
    "provider", "registry", "client", "server", "storage", "index", "cursor",
    "pipeline", "event", "listener", "emitter", "helper", "util", "utility",
    "widget", "component", "extension", "plugin", "hook", "gateway",
    "broker", "producer", "consumer", "connection", "query", "migration",
    "fixture", "test", "decorator", "generator", "iterator", "async",
    "transaction", "lock", "mutex", "thread", "process", "signal",
    "middleware", "router", "view", "template", "factory",
    "adapter", "proxy", "strategy", "observer", "state",
    "machine", "engine", "manager", "loader", "builder", "scheduler",
    "validator", "filter", "transform", "serialize", "deserialize",
    "encryption", "password", "permission", "tenant", "workspace", "org",
)

# Pre-compile word-boundary regexes for each term.
_CODE_TERM_PATTERNS = tuple(
    _re.compile(rf"(?:^|\W){_re.escape(term)}(?:\W|$)") for term in _CODE_TERMS_RAW
)


def _has_code_term(text: str) -> bool:
    """Word-boundary check for code domain vocabulary."""
    return any(p.search(text) for p in _CODE_TERM_PATTERNS)

# ── Detection ─────────────────────────────────────────────────────────────


def detect_project_query(message: str) -> bool:
    """Broad trigger: AST keywords OR natural-language codebase queries.

    Unlike detect_ast_query (substring keyword match for tool names), this
    also fires on natural-language code queries ("where is the database pool",
    "how does retry work") while NOT over-firing on generic questions
    ("what is the weather today").
    """
    if not message or not message.strip():
        return False
    lower = message.lower().strip()

    # AST-tool keywords still trigger (reuse existing detector).
    if detect_ast_query(lower):
        return True

    # Unambiguous code-intent phrasing.
    if any(p in lower for p in CODE_INTENT_PHRASES):
        return True

    # Project-referential phrasing.
    if any(p in lower for p in PROJECT_PHRASES):
        return True

    # Interrogative cue + code-domain vocabulary = plausibly a code query.
    has_cue = any(cue in lower for cue in INTERROGATIVE_CUES)
    return has_cue and _has_code_term(lower)


# ── Context building ──────────────────────────────────────────────────────


def _index_ready(db_path: str | None) -> bool:
    """Cheap check that the semantic index exists and has symbols.

    Guards against _tool_semantic_search's empty-index AUTO-REFRESH, which
    scans a parent dir from a hot plugin hook. Returns False fast when the DB
    is missing or empty.
    """
    try:
        from ast_tools.database.connection import DEFAULT_DB_PATH

        p = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not p.exists() or p.stat().st_size == 0:
            return False
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
            return bool(row and row[0] > 0)
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Index readiness check failed: %s", e)
        return False


def _run_semantic_search(args: dict[str, Any]) -> str:
    """Thin wrapper so tests can monkeypatch the semantic-search call."""
    from ast_tools.tools.semantic_search import _tool_semantic_search

    return _tool_semantic_search(args)


def build_project_context(
    query: str,
    k: int = 8,
    token_budget: int = 4096,
    diversity_limit: int = 3,
    db_path: str | None = None,
) -> dict | None:
    """Inject project-specific semantic context for a codebase query.

    Args:
        query: The user's query (natural language).
        k: Number of symbols to retrieve.
        token_budget: Context token budget for injection.
        diversity_limit: Max symbols per file.
        db_path: Optional explicit DB path. When None, the canonical default
            (~/.ast-tools/cache/codebase.db) is used — never hardcoded here.

    Returns:
        {"context": <markdown>} if meaningful results found, else None.
        Never raises — graceful degradation by contract.
    """
    if not query or not query.strip():
        return None

    # Guard: no index / empty index → skip (avoids auto-refresh cost hazard).
    if not _index_ready(db_path):
        logger.debug("Project index not ready; skipping context injection")
        return None

    try:
        args: dict[str, Any] = {
            "query": query,
            "k": k,
            "inject_context": True,
            "token_budget": token_budget,
            "diversity_limit": diversity_limit,
        }
        if db_path:
            args["db_path"] = db_path

        result = _run_semantic_search(args)
        data = json.loads(result)
        context_info = data.get("context_injection") or {}
        tokens_used = context_info.get("tokens_used", 0)
        markdown = context_info.get("context_markdown", "")

        if tokens_used == 0 or not markdown:
            logger.debug("No relevant project symbols for query")
            return None

        context_parts = [
            "## Project Semantic Context (Injected)",
            "",
            "*Auto-injected from ast-tools project database*",
            f"*Tokens used: {tokens_used}/{token_budget}*",
            f"*Diversity applied: {context_info.get('diversity_applied', False)}*",
            "",
            markdown,
        ]
        return {"context": "\n".join(context_parts)}
    except Exception as e:
        logger.warning("Project context injection failed: %s", e)
        return None
