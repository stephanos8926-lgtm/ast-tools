"""Unit tests for parser module."""

import pytest
from pathlib import Path
import tempfile
import ast

from ast_tools.indexer.parser import (
    parse_file,
    parse_source,
    Parser,
    compute_content_hash,
)


class TestComputeContentHash:
    """Test content hash computation."""
    
    def test_hash_is_deterministic(self):
        """Same content should produce same hash."""
        content = "def foo(): pass"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2
    
    def test_hash_differs_on_change(self):
        """Different content should produce different hash."""
        hash1 = compute_content_hash("def foo(): pass")
        hash2 = compute_content_hash("def bar(): pass")
        assert hash1 != hash2
    
    def test_hash_handles_unicode(self):
        """Hash should handle unicode characters."""
        content = "def 你好(): pass"
        hash_val = compute_content_hash(content)
        assert len(hash_val) == 64  # SHA256 hex length


class TestParseSource:
    """Test parsing source code strings."""
    
    def test_parse_valid_function(self):
        """Should parse valid Python function."""
        source = "def foo(x: int) -> int:\n    return x + 1"
        result = parse_source(source)
        
        assert result.success is True
        assert result.tree is not None
        assert isinstance(result.tree, ast.Module)
        assert len(result.tree.body) == 1
    
    def test_parse_empty_source(self):
        """Should handle empty source code."""
        result = parse_source("")
        
        assert result.success is True
        assert result.tree is not None
        assert len(result.tree.body) == 0
    
    def test_parse_whitespace_only(self):
        """Should handle whitespace-only source."""
        result = parse_source("   \n\n   ")
        
        assert result.success is True
        assert result.error is None
    
    def test_parse_syntax_error(self):
        """Should gracefully handle syntax errors."""
        source = "def foo(:  # Missing parameter"
        result = parse_source(source)
        
        assert result.success is False
        assert result.tree is None
        assert "SyntaxError" in result.error
    
    def test_parse_with_content_hash(self):
        """Should compute content hash."""
        source = "x = 1"
        result = parse_source(source)
        
        assert result.content_hash is not None
        assert len(result.content_hash) == 64


class TestParseFile:
    """Test parsing files from disk."""
    
    def test_parse_valid_file(self):
        """Should parse valid Python file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def foo(): pass\n")
            f.flush()
            
            result = parse_file(Path(f.name))
            
            assert result.success is True
            assert result.tree is not None
    
    def test_parse_nonexistent_file(self):
        """Should handle nonexistent files."""
        result = parse_file(Path("/nonexistent/file.py"))
        
        assert result.success is False
        assert result.error is not None
    
    def test_parse_empty_file(self):
        """Should handle empty files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("")
            f.flush()
            
            result = parse_file(Path(f.name))
            
            assert result.success is True
            assert result.tree is not None
    
    def test_parse_syntax_error_file(self):
        """Should handle files with syntax errors."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("if True:\n")  # Incomplete statement
            f.flush()
            
            result = parse_file(Path(f.name))
            
            assert result.success is False
            assert "SyntaxError" in result.error


class TestParserClass:
    """Test Parser convenience class."""
    
    def test_parser_parse_file(self):
        """Parser.parse_file should delegate to parse_file."""
        parser = Parser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("x = 1")
            f.flush()
            
            result = parser.parse_file(Path(f.name))
            assert result.success is True
    
    def test_parser_parse_source(self):
        """Parser.parse_source should delegate to parse_source."""
        parser = Parser()
        result = parser.parse_source("y = 2")
        assert result.success is True