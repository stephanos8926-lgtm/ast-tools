"""Unit tests for the LSP document store."""

from lsprotocol import types as lsp_types

from ast_tools.lsp.document_store import DocumentStore, TextDocument


class TestTextDocument:
    """Test the TextDocument class."""

    def test_init(self):
        doc = TextDocument("file:///test.py", "x = 1", "python")
        assert doc.uri == "file:///test.py"
        assert doc.text == "x = 1"
        assert doc.language_id == "python"
        assert doc.version == 0

    def test_apply_change_full(self):
        doc = TextDocument("file:///test.py", "x = 1", "python")
        change = lsp_types.TextDocumentContentChangeWholeDocument(text="y = 2")
        doc.apply_change(change)
        assert doc.text == "y = 2"
        assert doc.version == 1

    def test_apply_change_range(self):
        doc = TextDocument("file:///test.py", "x = 1\ny = 2\n", "python")
        # Replace "x = 1" with "x = 42"
        change = lsp_types.TextDocumentContentChangePartial(
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=1, character=0),
            ),
            text="x = 42\n",
        )
        doc.apply_change(change)
        assert doc.text == "x = 42\ny = 2\n"
        assert doc.version == 1

    def test_apply_change_simple(self):
        doc = TextDocument("file:///test.py", "x = 1", "python")
        # Simple dict-based change (some LSP clients use this)
        class SimpleChange:
            def __init__(self, text):
                self.text = text
        change = SimpleChange("x = 42")
        doc.apply_change(change)
        assert doc.text == "x = 42"

    def test_position_to_offset(self):
        doc = TextDocument("file:///test.py", "line1\nline2\nline3\n", "python")
        offset = doc._position_to_offset(lsp_types.Position(line=1, character=0))
        assert offset == 6  # "line1\n" = 6 chars


class TestDocumentStore:
    """Test the DocumentStore class."""

    def test_did_open(self):
        store = DocumentStore()
        params = lsp_types.DidOpenTextDocumentParams(
            text_document=lsp_types.TextDocumentItem(
                uri="file:///test.py",
                language_id="python",
                version=1,
                text="x = 1",
            )
        )
        store.did_open(params)
        assert store.get_text("file:///test.py") == "x = 1"
        assert store.get_language("file:///test.py") == "python"
        assert store.get_version("file:///test.py") == 1

    def test_did_change(self):
        store = DocumentStore()
        store.did_open(lsp_types.DidOpenTextDocumentParams(
            text_document=lsp_types.TextDocumentItem(
                uri="file:///test.py", language_id="python", version=1, text="x = 1"
            )
        ))
        change_params = lsp_types.DidChangeTextDocumentParams(
            text_document=lsp_types.VersionedTextDocumentIdentifier(
                uri="file:///test.py", version=2
            ),
            content_changes=[
                lsp_types.TextDocumentContentChangeWholeDocument(text="y = 2")
            ],
        )
        store.did_change(change_params)
        assert store.get_text("file:///test.py") == "y = 2"
        assert store.get_version("file:///test.py") == 2

    def test_did_change_nonexistent(self):
        store = DocumentStore()
        change_params = lsp_types.DidChangeTextDocumentParams(
            text_document=lsp_types.VersionedTextDocumentIdentifier(
                uri="file:///nonexistent.py", version=1
            ),
            content_changes=[lsp_types.TextDocumentContentChangeWholeDocument(text="y")],
        )
        # Should not raise
        store.did_change(change_params)

    def test_did_close(self):
        store = DocumentStore()
        store.did_open(lsp_types.DidOpenTextDocumentParams(
            text_document=lsp_types.TextDocumentItem(
                uri="file:///test.py", language_id="python", version=1, text="x = 1"
            )
        ))
        store.did_close(lsp_types.DidCloseTextDocumentParams(
            text_document=lsp_types.TextDocumentIdentifier(uri="file:///test.py")
        ))
        assert store.get_text("file:///test.py") is None
        assert store.get_version("file:///test.py") is None

    def test_get_document(self):
        store = DocumentStore()
        store.did_open(lsp_types.DidOpenTextDocumentParams(
            text_document=lsp_types.TextDocumentItem(
                uri="file:///test.py", language_id="python", version=1, text="x = 1"
            )
        ))
        doc = store.get_document("file:///test.py")
        assert doc is not None
        assert doc.text == "x = 1"

    def test_get_nonexistent(self):
        store = DocumentStore()
        assert store.get_text("file:///missing.py") is None
        assert store.get_language("file:///missing.py") is None
        assert store.get_document("file:///missing.py") is None