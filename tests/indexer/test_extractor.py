"""Unit tests for symbol extractor."""

import ast

from ast_tools.indexer.extractor import (
    SymbolExtractor,
    extract_symbols,
)
from ast_tools.types import EdgeKind, SymbolKind


class TestSymbolExtractor:
    """Test SymbolExtractor class."""

    def test_extract_function(self):
        """Should extract function definitions."""
        source = """
def foo(x: int) -> int:
    '''A function.'''
    return x + 1
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        assert len(symbols) == 1
        assert symbols[0].name == "foo"
        assert symbols[0].kind == SymbolKind.FUNCTION
        assert "def foo" in symbols[0].signature  # Actual format: 'def foo(x: ...) -> ...'

    def test_extract_class(self):
        """Should extract class definitions."""
        source = """
class MyClass:
    '''A class.'''
    def method(self):
        pass
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        # Should extract class AND method
        assert len(symbols) >= 1
        assert any(s.name == "MyClass" for s in symbols)

    def test_extract_method(self):
        """Should extract methods as METHOD kind."""
        source = """
class MyClass:
    def method(self):
        pass
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        method = next((s for s in symbols if s.name == "method"), None)
        assert method is not None
        assert method.kind == SymbolKind.METHOD

    def test_extract_imports(self):
        """Should extract import statements."""
        source = """
import os
from pathlib import Path
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        import_symbols = [s for s in symbols if s.kind == SymbolKind.IMPORT]
        assert len(import_symbols) >= 2

    def test_extract_variables(self):
        """Should extract variable assignments."""
        source = """
x = 1
CONSTANT = "value"
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        var_symbols = [s for s in symbols if s.kind in (SymbolKind.VARIABLE, SymbolKind.CONSTANT)]
        assert len(var_symbols) >= 1

    def test_extract_constant(self):
        """Should recognize UPPER_CASE as constants."""
        source = "MY_CONSTANT = 42"
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        const = next((s for s in symbols if s.name == "MY_CONSTANT"), None)
        assert const is not None
        assert const.kind == SymbolKind.CONSTANT

    def test_extract_function_docstring(self):
        """Should extract docstrings."""
        source = '''
def foo():
    """This is a docstring."""
    pass
'''
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        assert symbols[0].docstring == "This is a docstring."

    def test_qualified_name_nested(self):
        """Should build qualified names for nested classes and methods."""
        source = """
class Outer:
    class Inner:
        def method(self):
            pass
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        method = next((s for s in symbols if s.name == "method"), None)
        assert method is not None
        # Qualified names include full path
        assert method.qualified_name == "Outer.Inner.method"


class TestExtractEdges:
    """Test edge extraction."""

    def test_extract_imports_edges(self):
        """Should create IMPORTS edges."""
        source = "from os import path"
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        edges = extractor.get_edges()
        import_edges = [e for e in edges if e.edge_type == EdgeKind.IMPORTS]
        assert len(import_edges) >= 1

    def test_extract_inheritance_edges(self):
        """Should create INHERITS edges."""
        source = """
class Base:
    pass

class Child(Base):
    pass
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        edges = extractor.get_edges()
        inherits = [e for e in edges if e.edge_type == EdgeKind.INHERITS]
        assert len(inherits) >= 1

    def test_extract_call_edges(self):
        """Should create CALLS edges."""
        source = """
def foo():
    bar()
"""
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        edges = extractor.get_edges()
        calls = [e for e in edges if e.edge_type == EdgeKind.CALLS]
        assert len(calls) >= 1

    def test_symbol_id_format(self):
        """Symbol IDs should be file_path:qualified_name."""
        source = "def foo(): pass"
        tree = ast.parse(source)
        extractor = SymbolExtractor("test.py")
        extractor.visit(tree)

        symbols = extractor.get_symbols()
        assert symbols[0].id == "test.py:foo"


class TestExtractSymbolsFunction:
    """Test convenience function."""

    def test_extract_symbols_returns_tuple(self):
        """Should return (symbols, edges) tuple."""
        source = "def foo(): bar()"
        tree = ast.parse(source)

        symbols, edges = extract_symbols(tree, "test.py")

        assert isinstance(symbols, list)
        assert isinstance(edges, list)
        assert len(symbols) >= 1
