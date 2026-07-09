"""In-memory document store for LSP synchronization."""

from typing import Any
from lsprotocol import types as lsp_types


class TextDocument:
    """Represents a text document in the LSP."""
    
    def __init__(self, uri: str, text: str, language_id: str, version: int = 0):
        self.uri = uri
        self.text = text
        self.language_id = language_id
        self.version = version
    
    def apply_change(self, change):
        """Apply a content change to the document.
        
        Supports both full document replacement (TextDocumentContentChangeWholeDocument)
        and range-based incremental updates (TextDocumentContentChangePartial).
        """
        from lsprotocol.types import TextDocumentContentChangeWholeDocument
        
        if isinstance(change, TextDocumentContentChangeWholeDocument):
            # Full document replacement
            self.text = change.text
        elif hasattr(change, 'range') and change.range is not None:
            # Range-based change
            range_ = change.range
            start_offset = self._position_to_offset(range_.start)
            end_offset = self._position_to_offset(range_.end)
            self.text = self.text[:start_offset] + change.text + self.text[end_offset:]
        else:
            # Simple text change (whole document)
            self.text = change.text
        
        self.version += 1
    
    def _position_to_offset(self, position: lsp_types.Position) -> int:
        """Convert LSP position to text offset."""
        lines = self.text.splitlines(keepends=True)
        offset = sum(len(lines[i]) for i in range(position.line))
        offset += position.character
        return min(offset, len(self.text))


class DocumentStore:
    """In-memory document synchronization store."""
    
    def __init__(self):
        self._documents: dict[str, TextDocument] = {}
    
    def did_open(self, params: lsp_types.DidOpenTextDocumentParams):
        """Handle textDocument/didOpen notification."""
        doc = params.text_document
        self._documents[doc.uri] = TextDocument(
            uri=doc.uri,
            text=doc.text,
            language_id=doc.language_id,
            version=doc.version,
        )
    
    def did_change(self, params: lsp_types.DidChangeTextDocumentParams):
        """Handle textDocument/didChange notification."""
        uri = params.text_document.uri
        if uri not in self._documents:
            return
        
        doc = self._documents[uri]
        for change in params.content_changes:
            doc.apply_change(change)
    
    def did_close(self, params: lsp_types.DidCloseTextDocumentParams):
        """Handle textDocument/didClose notification."""
        uri = params.text_document.uri
        self._documents.pop(uri, None)
    
    def get_document(self, uri: str) -> TextDocument | None:
        """Get document by URI."""
        return self._documents.get(uri)
    
    def get_text(self, uri: str) -> str | None:
        """Get document text by URI."""
        doc = self._documents.get(uri)
        return doc.text if doc else None
    
    def get_language(self, uri: str) -> str | None:
        """Get document language by URI."""
        doc = self._documents.get(uri)
        return doc.language_id if doc else None
    
    def get_version(self, uri: str) -> int | None:
        """Get document version by URI."""
        doc = self._documents.get(uri)
        return doc.version if doc else None