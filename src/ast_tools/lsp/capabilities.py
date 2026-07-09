"""LSP server capabilities for ast-tools."""

from lsprotocol import types as lsp_types

def get_server_capabilities() -> lsp_types.ServerCapabilities:
    """Return the server's capabilities to the client."""
    return lsp_types.ServerCapabilities(
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
                "ast-tools.llmFix", # Custom LLM-assisted fix
            ],
            resolve_provider=True, # For lazy computation of edits
        ),
        diagnostic_provider=lsp_types.DiagnosticOptions(
            identifier="ast-tools",
            inter_file_dependencies=True, # Diagnostics can depend on other files
            workspace_diagnostics=True, # Can provide diagnostics for entire workspace
            # We are using push diagnostics, so no need for DocumentDiagnosticReport.full / inter_file_dependencies
            # Workaround for pygls typing issue where DiagnosticOptions requires full/workspace_diagnostics
            # This is effectively push diagnostics
            # full=False, 
            # workspace=False,
        ),
        document_formatting_provider=True,
        document_range_formatting_provider=True,
        workspace=lsp_types.WorkspaceFoldersServerCapabilities(
            supported=True,
            change_notifications=True,
        ),
        # Add more capabilities as needed (e.g., hover, definition, references, etc.)
        # Based on what ast-tools can provide via its MCP tools
    )