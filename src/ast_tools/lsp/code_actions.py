"""Code action handler for LSP server."""

from typing import Any

from lsprotocol import types as lsp_types

from ast_tools.fix.engine import FixEngine, FixContext
from ast_tools.fix.config import FixConfig
from ast_tools.fix.engine import SafetyLevel
from ast_tools.fix.fixers import register_plugin_fixers


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
        """Resolve a lazy code action (compute full edit)."""
        # If action already has edit, return as-is
        if action.edit:
            return action
        
        # If action has data with action_id, we could compute the full edit here
        # For now, return the action as-is (lazy resolution not fully implemented)
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
