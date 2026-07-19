"""Code action handler for LSP server."""


from lsprotocol import types as lsp_types

from ast_tools.fix.config import FixConfig
from ast_tools.fix.engine import FixContext, FixEngine, SafetyLevel


class CodeActionHandler:
    """Handles textDocument/codeAction and codeAction/resolve requests."""

    def __init__(self, server):
        self.server = server

    async def get_code_actions(self, params: lsp_types.CodeActionParams) -> list[lsp_types.CodeAction]:
        """Provide code actions for the given range."""
        uri = params.text_document.uri
        text = self.server.document_store.get_text(uri)
        if not text:
            return []

        language = self.server.language_router.get_language(uri)
        if not language:
            return []

        # Get the range from the request
        range_ = params.range

        # Get diagnostics in the range
        diagnostics = params.context.diagnostics if params.context else []

        # Create fix engine context for this document
        import tempfile
        from pathlib import Path

        ext = self._get_extension(language)
        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
            f.write(text)
            temp_path = Path(f.name)

        try:
            # Get fixers for this language
            fixers = self.server.language_router.get_fixers_for_language(language)
            if not fixers:
                return []

            # Create fix context in check-only mode
            fix_config = FixConfig(
                check_only=True,
                max_iterations=1,
                safety_level=self._get_safety_level(),
            )

            context = FixContext(
                project_root=temp_path.parent,
                target_paths=[temp_path],
                languages={language},
                config=fix_config,
                safety_level=self._get_safety_level(),
                check_only=True,
                diff_only=False,
                verbose=False,
                max_iterations=1,
            )

            # Create fix engine with plugin fixers
            plugin_fixers = self.server.config.plugins.custom_fixers if self.server.config.plugins else {}
            engine = FixEngine(context, plugin_fixers=plugin_fixers)

            # Run fix engine to get available actions
            result = engine.run()

            # Convert FixActions to CodeActions
            code_actions = []
            for action in result.actions_applied:
                code_action = self._fix_action_to_code_action(action, range_, uri)
                if code_action:
                    code_actions.append(code_action)

            return code_actions

        finally:
            temp_path.unlink(missing_ok=True)

    async def resolve_code_action(self, action: lsp_types.CodeAction) -> lsp_types.CodeAction:
        """Resolve a lazy code action (compute full edit).

        Supports LLM fix resolution via LLMBridge when action.data
        indicates an llm_fix action type.
        """
        # If action already has edit, return as-is
        if action.edit:
            return action

        # Check if this is an LLM fix action needing lazy resolution
        if action.data and isinstance(action.data, dict):
            action_type = action.data.get("action_type")
            if action_type == "llm_fix":
                return await self._resolve_llm_fix(action)

        # Return as-is for other cases
        return action

    async def _resolve_llm_fix(self, action: lsp_types.CodeAction) -> lsp_types.CodeAction:
        """Resolve an LLM fix action by calling the LLM bridge."""
        from .llm_bridge import LLMBridge

        bridge = LLMBridge(self.server)
        try:
            result = await bridge.resolve_llm_fix(action, dict(action.data))
            if result and result.get("diff"):
                # Apply the diff as a workspace edit
                uri = action.data.get("uri", "")
                diff = result["diff"]
                # Parse the diff into TextEdits
                from ast_tools.llm.diff_parser import parse_and_validate_diff

                text = self.server.document_store.get_text(uri)
                if text:
                    parsed = parse_and_validate_diff(diff, text)
                    if parsed.success and parsed.edits:
                        edits = [
                            lsp_types.TextEdit(
                                range=lsp_types.Range(
                                    start=lsp_types.Position(line=e["start_line"], character=0),
                                    end=lsp_types.Position(line=e["end_line"], character=0),
                                ),
                                new_text=e["new_text"],
                            )
                            for e in parsed.edits
                        ]
                        action.edit = lsp_types.WorkspaceEdit(
                            changes={uri: edits}
                        )
                        action.title = f"🤖 {action.title} (via {result.get('model_used', 'LLM')})"
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("Failed to resolve LLM fix: %s", e)
        finally:
            await bridge.close()

        return action

    def _fix_action_to_code_action(self, action, range_: lsp_types.Range, uri: str) -> lsp_types.CodeAction | None:
        """Convert a FixAction to an LSP CodeAction."""
        from ast_tools.fix.fixers import FixAction

        if not isinstance(action, FixAction):
            return None

        # Create workspace edit
        edit = lsp_types.WorkspaceEdit(changes={uri: [lsp_types.TextEdit(
            range=range_,
            new_text=action.fixed_content or "",
        )]})

        kind = self._safety_to_code_action_kind(action.safety)

        return lsp_types.CodeAction(
            title=action.description,
            kind=kind,
            diagnostics=None,
            edit=edit,
            data={
                "fixer": action.tool,
                "safety": action.safety,
                "action_id": f"{action.tool}:{action.description}",
            },
        )

    def _safety_to_code_action_kind(self, safety: str) -> lsp_types.CodeActionKind:
        """Map safety level to code action kind."""
        if safety == "safe":
            return lsp_types.CodeActionKind.QuickFix
        elif safety == "unsafe":
            return lsp_types.CodeActionKind.Refactor
        else:  # display_only
            return lsp_types.CodeActionKind.RefactorInline

    def _get_safety_level(self) -> SafetyLevel:
        level_map = {
            "safe": SafetyLevel.SAFE,
            "unsafe": SafetyLevel.UNSAFE,
            "display_only": SafetyLevel.DISPLAY_ONLY,
        }
        return level_map.get(self.server.config.fix.safety_level, SafetyLevel.SAFE)

    def _get_extension(self, language: str) -> str:
        ext_map = {
            "python": ".py",
            "typescript": ".ts",
            "javascript": ".js",
            "go": ".go",
            "rust": ".rs",
            "cpp": ".cpp",
            "c": ".c",
            "markdown": ".md",
        }
        return ext_map.get(language, ".txt")
