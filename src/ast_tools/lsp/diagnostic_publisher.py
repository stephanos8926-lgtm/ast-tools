"""Diagnostic publisher for LSP server."""

import asyncio
import hashlib

from lsprotocol import types as lsp_types

from ast_tools.config.unified import DiagnosticConfig
from ast_tools.fix.config import FixConfig
from ast_tools.fix.engine import FixContext, FixEngine


class DiagnosticPublisher:
    """Runs fixers in check-only mode, converts to LSP diagnostics."""

    def __init__(self, server, config: DiagnosticConfig):
        self.server = server
        self.config = config
        self._debounce_timers: dict[str, asyncio.Task] = {}
        self._last_diagnostics: dict[str, str] = {}  # uri -> hash

    async def publish_diagnostics(self, uri: str, text: str, language: str):
        """Run check-only fix pipeline, publish results immediately."""
        # Cancel any pending debounced publish
        if uri in self._debounce_timers:
            self._debounce_timers[uri].cancel()

        diagnostics = await self.compute_diagnostics(uri, text, language)

        # Deduplicate: only publish if changed
        diag_hash = self._hash_diagnostics(diagnostics)
        if self._last_diagnostics.get(uri) != diag_hash:
            self._last_diagnostics[uri] = diag_hash
            self.server.publish_diagnostics(uri, diagnostics)

    async def debounced_publish(self, uri: str, text: str, language: str):
        """Publish diagnostics with debounce."""
        # Cancel existing timer
        if uri in self._debounce_timers:
            self._debounce_timers[uri].cancel()

        async def _delayed_publish():
            try:
                await asyncio.sleep(self.config.debounce_ms / 1000.0)
                await self.publish_diagnostics(uri, text, language)
            except asyncio.CancelledError:
                pass

        self._debounce_timers[uri] = asyncio.create_task(_delayed_publish())

    async def compute_diagnostics(self, uri: str, text: str, language: str) -> list[lsp_types.Diagnostic]:
        """Run fixers in check-only mode and convert to LSP diagnostics."""
        if not self.config.enabled:
            return []

        # Create a fix engine for this document
        import tempfile
        from pathlib import Path

        # Write text to temp file
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
                safety_level=self.server.config.fix.safety_level,
            )

            context = FixContext(
                project_root=temp_path.parent,
                target_paths=[temp_path],
                languages={language},
                config=fix_config,
                safety_level=self.server._get_safety_level(),
                check_only=True,
                verbose=False,
                max_iterations=1,
            )

            # Create fix engine with plugin fixers
            plugin_fixers = self.server.config.plugins.custom_fixers if self.server.config.plugins else {}

            engine = FixEngine(context, plugin_fixers=plugin_fixers)
            result = engine.run()

            # Convert FixActions to Diagnostics
            diagnostics = self._fix_actions_to_diagnostics(result.actions_applied, language, text)

            # Limit diagnostics per file
            if len(diagnostics) > self.config.max_diagnostics_per_file:
                diagnostics = diagnostics[:self.config.max_diagnostics_per_file]

            return diagnostics

        finally:
            temp_path.unlink(missing_ok=True)

    def _fix_actions_to_diagnostics(self, actions: list, language: str, source_text: str) -> list[lsp_types.Diagnostic]:
        """Convert FixAction list to LSP Diagnostic objects."""
        from ast_tools.fix.fixers import FixAction

        diagnostics = []

        for action in actions:
            if not isinstance(action, FixAction):
                continue

            # Determine range from action metadata
            start_pos = action.metadata.get("start_pos", (0, 0))
            end_pos = action.metadata.get("end_pos", (0, 0))

            # If no position metadata, try to find the change in source
            if start_pos == (0, 0) and end_pos == (0, 0):
                # Try to locate the change
                start_pos, end_pos = self._locate_change(source_text, action.original_content, action.fixed_content)

            diagnostic = lsp_types.Diagnostic(
                range=lsp_types.Range(
                    start=lsp_types.Position(line=start_pos[0], character=start_pos[1]),
                    end=lsp_types.Position(line=end_pos[0], character=end_pos[1]),
                ),
                severity=self._safety_to_severity(action.safety),
                code=action.metadata.get("rule_code", action.tool),
                code_description=lsp_types.CodeDescription(
                    href=f"https://github.com/astral-sh/ruff/blob/main/docs/rules/{action.metadata.get('rule_code', '').lower()}.md"
                ) if action.metadata.get("rule_code") else None,
                source=f"ast-tools.{action.tool}",
                message=action.description,
                tags=[lsp_types.DiagnosticTag.Unnecessary] if "unused" in action.description.lower() else None,
                related_information=None,
                data={
                    "fixer": action.tool,
                    "safety": action.safety,
                    "fixable": True,
                    "action_id": f"{action.tool}:{action.description}",
                },
            )
            diagnostics.append(diagnostic)

        return diagnostics

    def _locate_change(self, source: str, original: str, fixed: str) -> tuple[tuple[int, int], tuple[int, int]]:
        """Find the position of a change in source text."""
        # Find the first differing line
        source_lines = source.splitlines(keepends=True)
        original_lines = original.splitlines(keepends=True)

        # Simple heuristic: find the line that changed
        for i, (src_line, orig_line) in enumerate(zip(source_lines, original_lines)):
            if src_line != orig_line:
                # Found the changed line
                start_char = 0
                end_char = len(src_line.rstrip("\n"))
                return (i, start_char), (i, end_char)

        # Fallback: return first line
        return (0, 0), (0, len(source_lines[0]) if source_lines else 0)

    def _safety_to_severity(self, safety: str) -> lsp_types.DiagnosticSeverity:
        """Map safety level to diagnostic severity."""
        if safety == "unsafe":
            return lsp_types.DiagnosticSeverity.Warning
        elif safety == "display_only":
            return lsp_types.DiagnosticSeverity.Hint
        else:  # safe
            return lsp_types.DiagnosticSeverity.Information

    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
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

    def _hash_diagnostics(self, diagnostics: list[lsp_types.Diagnostic]) -> str:
        """Create hash of diagnostics for change detection."""
        # Create a deterministic string representation
        parts = []
        for d in diagnostics:
            parts.append(f"{d.range.start.line}:{d.range.start.character}-{d.range.end.line}:{d.range.end.character}:{d.message}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()
