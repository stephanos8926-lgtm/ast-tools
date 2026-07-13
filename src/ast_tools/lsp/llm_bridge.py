"""LSP bridge connecting LLMClient to IDE code actions.

Thin adapter that wraps LLMClient for LSP's codeAction/resolve flow.
Used by CodeActionHandler to resolve lazy LLM fix actions.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ast_tools.config.unified import UnifiedConfig
from ast_tools.llm.client import LLMClient, LLMFixContext

logger = logging.getLogger(__name__)


class LLMBridge:
    """Connects LSP code action resolve to LLMClient.

    Args:
        server: The ASTToolsLanguageServer instance
    """

    def __init__(self, server):
        self.server = server
        self._client: LLMClient | None = None

    @property
    def client(self) -> LLMClient:
        """Get or create the LLMClient (lazy init)."""
        if self._client is None:
            self._client = LLMClient(self.server.config.lsp.llm)
        return self._client

    async def resolve_llm_fix(self, action, action_data: dict) -> dict | None:
        """Resolve an LLM fix action by calling the LLM.

        Args:
            action: The CodeAction to resolve
            action_data: Parsed data from action.data dict

        Returns:
            dict with edits and diff, or None if resolution fails
        """
        uri = action_data.get("uri", "")
        diagnostic_code = action_data.get("diagnostic_code", "")
        language = action_data.get("language", "python")

        # Get document content from the store
        text = self.server.document_store.get_text(uri)
        if not text:
            logger.warning("No document found for %s", uri)
            return None

        # Build diagnostic message from code and language
        diagnostic_message = f"{diagnostic_code} in {language} file"

        context = LLMFixContext(
            code=text,
            diagnostic_message=diagnostic_message,
            diagnostic_code=diagnostic_code,
            file_path=uri,
            language=language,
        )

        if not self.client.config.enabled:
            logger.info("LLM disabled, skipping fix resolution")
            return None

        result = await self.client.suggest_fix(context)
        if not result.success:
            logger.warning("LLM fix resolution failed: %s", result.error)
            return None

        return {
            "diff": result.diff,
            "confidence": result.confidence,
            "model_used": result.model_used,
            "provider": result.provider,
        }

    async def close(self):
        """Clean up the LLM client."""
        if self._client:
            await self._client.close()
            self._client = None