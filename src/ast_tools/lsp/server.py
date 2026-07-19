"""Main LSP server implementation for ast-tools."""

import logging
from pathlib import Path

from lsprotocol import types as lsp_types
from pygls.lsp.server import LanguageServer

from ast_tools.config.unified import FixConfig, UnifiedConfig, load_unified_config
from ast_tools.fix.engine import FixContext, FixEngine

logger = logging.getLogger(__name__)


class ASTToolsLanguageServer(LanguageServer):
    """Main LSP server for ast-tools."""

    def __init__(self, *args, **kwargs):
        super().__init__("ast-tools", "0.2.0", *args, **kwargs)

        # Core components
        self.config: UnifiedConfig = None
        self.fix_engine: FixEngine = None
        self.language_router = None
        self.diagnostic_publisher = None
        self.config_watcher = None
        self.document_store = None

        # State
        self._initialized = False
        self._workspace_folders: list[lsp_types.WorkspaceFolder] = []

    async def initialize(self, params: lsp_types.InitializeParams) -> lsp_types.InitializeResult:
        """Initialize server, load config, setup components."""
        logger.info("Initializing ast-tools LSP server...")

        # Store workspace folders
        if params.workspace_folders:
            self._workspace_folders = params.workspace_folders

        # 1. Load UnifiedConfig from workspace
        await self._load_configuration()

        # 2. Create LanguageRouter
        from .language_router import LanguageRouter
        self.language_router = LanguageRouter(self.config)

        # 3. Create FixEngine with plugin fixers
        plugin_fixers = self.config.plugins.custom_fixers if self.config.plugins else {}
        self.fix_engine = self._create_fix_engine(plugin_fixers)

        # 4. Create DocumentStore
        from .document_store import DocumentStore
        self.document_store = DocumentStore()

        # 5. Create DiagnosticPublisher
        from .diagnostic_publisher import DiagnosticPublisher
        self.diagnostic_publisher = DiagnosticPublisher(self)

        # 6. Create ConfigWatcher
        from .config_watcher import ConfigWatcher
        self.config_watcher = ConfigWatcher(self)
        await self.config_watcher.start()

        # 7. Register LSP handlers
        self._register_handlers()

        self._initialized = True
        logger.info("ast-tools LSP server initialized successfully")

        # Return capabilities
        return lsp_types.InitializeResult(
            capabilities=lsp_types.ServerCapabilities(
                text_document_sync=lsp_types.TextDocumentSyncOptions(
                    open_close=True,
                    change=lsp_types.TextDocumentSyncKind.Incremental,
                    save=lsp_types.SaveOptions(include_text=True),
                ),
                code_action_provider=lsp_types.CodeActionOptions(
                    code_action_kinds=[
                        lsp_types.CodeActionKind.QuickFix,
                        lsp_types.CodeActionKind.SourceFixAll,
                        lsp_types.CodeActionKind.SourceOrganizeImports,
                        lsp_types.CodeActionKind.Refactor,
                        lsp_types.CodeActionKind.RefactorExtract,
                        lsp_types.CodeActionKind.RefactorInline,
                    ],
                    resolve_provider=True,
                ),
                diagnostic_provider=lsp_types.DiagnosticOptions(
                    identifier="ast-tools",
                    inter_file_dependencies=True,
                    workspace_diagnostics=True,
                ),
                document_formatting_provider=True,
                document_range_formatting_provider=True,
                workspace=lsp_types.WorkspaceFoldersServerCapabilities(
                    supported=True,
                    change_notifications=True,
                ),
            ),
            server_info=lsp_types.ServerInfo(
                name="ast-tools",
                version="0.2.0",
            ),
        )

    async def _load_configuration(self):
        """Load UnifiedConfig from workspace."""
        workspace_root = None
        if self._workspace_folders:
            # Use first workspace folder as root
            workspace_root = Path(self._workspace_folders[0].uri.replace("file://", ""))

        # Try to find config files
        pyproject_path = None
        yaml_path = None

        if workspace_root:
            pyproject_path = workspace_root / "pyproject.toml"
            yaml_path = workspace_root / "ast-tools.yaml"

        # Load config with LSP enabled
        cli_overrides = {"lsp": {"enabled": True}}
        self.config = load_unified_config(
            pyproject_path=pyproject_path if pyproject_path and pyproject_path.exists() else None,
            yaml_path=yaml_path if yaml_path and yaml_path.exists() else None,
            cli_overrides=cli_overrides,
        )

    def _create_fix_engine(self, plugin_fixers: dict[str, str]) -> FixEngine:
        """Create FixEngine with appropriate context."""
        # Create a default FixContext - will be updated per request
        context = FixContext(
            project_root=Path(".").resolve(),
            target_paths=[Path(".").resolve()],
            languages=set(self.language_router.get_all_languages()),
            config=FixConfig(),
            safety_level=self._get_safety_level(),
            check_only=False,
            diff_only=False,
            verbose=False,
            max_iterations=self.config.fix.max_iterations,
        )
        return FixEngine(context, plugin_fixers=plugin_fixers)

    def _get_safety_level(self):
        from ast_tools.fix.engine import SafetyLevel
        level_map = {
            "safe": SafetyLevel.SAFE,
            "unsafe": SafetyLevel.UNSAFE,
            "display_only": SafetyLevel.DISPLAY_ONLY,
        }
        return level_map.get(self.config.fix.safety_level, SafetyLevel.SAFE)

    def _register_handlers(self):
        """Register LSP request/notification handlers."""

        # Document sync
        @self.feature(lsp_types.TEXT_DOCUMENT_DID_OPEN)
        async def did_open(params: lsp_types.DidOpenTextDocumentParams):
            await self._on_did_open(params)

        @self.feature(lsp_types.TEXT_DOCUMENT_DID_CHANGE)
        async def did_change(params: lsp_types.DidChangeTextDocumentParams):
            await self._on_did_change(params)

        @self.feature(lsp_types.TEXT_DOCUMENT_DID_CLOSE)
        async def did_close(params: lsp_types.DidCloseTextDocumentParams):
            await self._on_did_close(params)

        @self.feature(lsp_types.TEXT_DOCUMENT_DID_SAVE)
        async def did_save(params: lsp_types.DidSaveTextDocumentParams):
            await self._on_did_save(params)

        # Code actions
        @self.feature(lsp_types.TEXT_DOCUMENT_CODE_ACTION)
        async def code_action(params: lsp_types.CodeActionParams) -> list[lsp_types.CodeAction]:
            return await self._on_code_action(params)

        @self.feature(lsp_types.CODE_ACTION_RESOLVE)
        async def code_action_resolve(action: lsp_types.CodeAction) -> lsp_types.CodeAction:
            return await self._on_code_action_resolve(action)

        # Formatting
        @self.feature(lsp_types.TEXT_DOCUMENT_FORMATTING)
        async def formatting(params: lsp_types.DocumentFormattingParams) -> list[lsp_types.TextEdit] | None:
            return await self._on_formatting(params)

        @self.feature(lsp_types.TEXT_DOCUMENT_RANGE_FORMATTING)
        async def range_formatting(params: lsp_types.DocumentRangeFormattingParams) -> list[lsp_types.TextEdit] | None:
            return await self._on_range_formatting(params)

        # Diagnostics (pull model)
        @self.feature(lsp_types.TEXT_DOCUMENT_DIAGNOSTIC)
        async def diagnostic(params: lsp_types.DocumentDiagnosticParams) -> lsp_types.DocumentDiagnosticReport:
            return await self._on_diagnostic(params)

        # Configuration changes
        @self.feature(lsp_types.WORKSPACE_DID_CHANGE_CONFIGURATION)
        async def did_change_configuration(params: lsp_types.DidChangeConfigurationParams):
            await self._on_config_change(params)

        # Watched files (config files)
        @self.feature(lsp_types.WORKSPACE_DID_CHANGE_WATCHED_FILES)
        async def did_change_watched_files(params: lsp_types.DidChangeWatchedFilesParams):
            await self._on_watched_files_change(params)

        # Shutdown
        @self.feature(lsp_types.SHUTDOWN)
        async def shutdown():
            await self._shutdown()

        @self.feature(lsp_types.EXIT)
        async def exit():
            await self._exit()

    # Handler implementations
    async def _on_did_open(self, params: lsp_types.DidOpenTextDocumentParams):
        """Handle document open."""
        uri = params.text_document.uri
        text = params.text_document.text
        language = params.text_document.language_id

        self.document_store.did_open(uri, text, language)

        # Trigger diagnostics
        if self.config.lsp.diagnostics.enabled and self.config.lsp.diagnostics.push_diagnostics:
            await self.diagnostic_publisher.publish_diagnostics(uri, text, language)

    async def _on_did_change(self, params: lsp_types.DidChangeTextDocumentParams):
        """Handle document change."""
        uri = params.text_document.uri
        for change in params.content_changes:
            self.document_store.did_change(uri, change)

        # Debounced diagnostics
        if self.config.lsp.diagnostics.enabled and self.config.lsp.diagnostics.push_diagnostics:
            text = self.document_store.get_text(uri)
            if text:
                language = self.language_router.get_language(uri)
                await self.diagnostic_publisher.debounced_publish(uri, text, language)

    async def _on_did_close(self, params: lsp_types.DidCloseTextDocumentParams):
        """Handle document close."""
        uri = params.text_document.uri
        self.document_store.did_close(uri)

    async def _on_did_save(self, params: lsp_types.DidSaveTextDocumentParams):
        """Handle document save - run fix pipeline if configured."""
        uri = params.text_document.uri
        text = params.text if params.text is not None else self.document_store.get_text(uri)

        if not text:
            return

        language = self.language_router.get_language(uri)

        # Run fix pipeline on save if configured
        if self.config.lsp.formatting.fix_on_save:
            await self._run_fix_pipeline(uri, text, language, apply=True)
        elif self.config.lsp.formatting.format_on_save:
            await self._run_fix_pipeline(uri, text, language, apply=False)

    async def _on_code_action(self, params: lsp_types.CodeActionParams) -> list[lsp_types.CodeAction]:
        """Provide code actions for the given range."""
        from .code_actions import CodeActionHandler

        handler = CodeActionHandler(self)
        return await handler.get_code_actions(params)

    async def _on_code_action_resolve(self, action: lsp_types.CodeAction) -> lsp_types.CodeAction:
        """Resolve lazy code action (compute full edit)."""
        from .code_actions import CodeActionHandler

        handler = CodeActionHandler(self)
        return await handler.resolve_code_action(action)

    async def _on_formatting(self, params: lsp_types.DocumentFormattingParams) -> list[lsp_types.TextEdit] | None:
        """Format entire document."""
        uri = params.text_document.uri
        text = self.document_store.get_text(uri)
        if not text:
            return None

        language = self.language_router.get_language(uri)
        return await self._run_formatting(uri, text, language, range_=None)

    async def _on_range_formatting(self, params: lsp_types.DocumentRangeFormattingParams) -> list[lsp_types.TextEdit] | None:
        """Format document range."""
        uri = params.text_document.uri
        text = self.document_store.get_text(uri)
        if not text:
            return None

        language = self.language_router.get_language(uri)
        return await self._run_formatting(uri, text, language, range_=params.range)

    async def _on_diagnostic(self, params: lsp_types.DocumentDiagnosticParams) -> lsp_types.DocumentDiagnosticReport:
        """Pull diagnostics for a document."""
        uri = params.text_document.uri
        text = self.document_store.get_text(uri)
        if not text:
            return lsp_types.DocumentDiagnosticReport(kind="full", items=[])

        language = self.language_router.get_language(uri)
        diagnostics = await self.diagnostic_publisher.compute_diagnostics(uri, text, language)

        return lsp_types.DocumentDiagnosticReport(
            kind="full",
            items=diagnostics,
        )

    async def _on_config_change(self, params: lsp_types.DidChangeConfigurationParams):
        """Handle configuration change from client."""
        # Reload config with client overrides
        # This is a simplified implementation
        logger.info("Configuration changed, reloading...")
        await self._load_configuration()

    async def _on_watched_files_change(self, params: lsp_types.DidChangeWatchedFilesParams):
        """Handle watched file changes (config files)."""
        for change in params.changes:
            if change.uri.endswith("ast-tools.yaml") or change.uri.endswith("pyproject.toml"):
                logger.info(f"Config file changed: {change.uri}")
                await self._load_configuration()
                # Reinitialize components
                if self.fix_engine:
                    plugin_fixers = self.config.plugins.custom_fixers if self.config.plugins else {}
                    self.fix_engine = self._create_fix_engine(plugin_fixers)

    async def _run_fix_pipeline(self, uri: str, text: str, language: str, apply: bool = True):
        """Run the fix pipeline on a document."""
        # Create temporary file for fix engine
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=f".{language}", delete=False) as f:
            f.write(text)
            temp_path = Path(f.name)

        try:
            # Update fix engine context
            self.fix_engine.context.target_paths = [temp_path]
            self.fix_engine.context.languages = {language}
            self.fix_engine.context.check_only = not apply

            # Run fix engine
            result = self.fix_engine.run()

            if apply and result.actions_applied:
                # Read fixed content
                fixed_text = temp_path.read_text()
                # Compute diff and apply as TextEdits
                edits = self._compute_text_edits(text, fixed_text)
                # Apply edits via workspace edit
                await self.apply_edit(lsp_types.WorkspaceEdit(
                    changes={uri: edits}
                ))
        finally:
            temp_path.unlink(missing_ok=True)

    async def _run_formatting(self, uri: str, text: str, language: str, range_: lsp_types.Range | None) -> list[lsp_types.TextEdit] | None:
        """Run formatter on document or range."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=f".{language}", delete=False) as f:
            f.write(text)
            temp_path = Path(f.name)

        try:
            self.fix_engine.context.target_paths = [temp_path]
            self.fix_engine.context.languages = {language}
            self.fix_engine.context.check_only = True

            result = self.fix_engine.run()

            if result.actions_applied:
                fixed_text = temp_path.read_text()
                return self._compute_text_edits(text, fixed_text, range_)
        finally:
            temp_path.unlink(missing_ok=True)

        return None

    def _compute_text_edits(self, original: str, fixed: str, range_: lsp_types.Range | None = None) -> list[lsp_types.TextEdit]:
        """Compute TextEdits from original and fixed content."""
        import difflib

        if range_:
            # Only compute edits for the range
            lines = original.splitlines(keepends=True)
            start_line = range_.start.line
            end_line = range_.end.line + 1
            original_range = "".join(lines[start_line:end_line])

            fixed_lines = fixed.splitlines(keepends=True)
            fixed_range = "".join(fixed_lines[start_line:end_line])

            diff = list(difflib.unified_diff(
                original_range.splitlines(keepends=True),
                fixed_range.splitlines(keepends=True),
                n=0,
            ))
        else:
            diff = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                n=0,
            ))

        # Parse unified diff into TextEdits
        edits = []
        # Simplified: if we have changes, replace the whole range
        if diff and range_:
            edits.append(lsp_types.TextEdit(
                range=range_,
                new_text=fixed if not range_ else "".join(fixed.splitlines(keepends=True)[start_line:end_line])
            ))
        elif diff and not range_:
            edits.append(lsp_types.TextEdit(
                range=lsp_types.Range(
                    start=lsp_types.Position(line=0, character=0),
                    end=lsp_types.Position(line=len(original.splitlines()), character=0),
                ),
                new_text=fixed,
            ))

        return edits

    async def _shutdown(self):
        """Shutdown server."""
        if self.config_watcher:
            await self.config_watcher.stop()
        logger.info("Server shutdown complete")

    async def _exit(self):
        """Exit handler."""
        pass


# Entry point for CLI
def main():
    """Start LSP server via stdio."""
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    server = ASTToolsLanguageServer()
    server.start_io()
