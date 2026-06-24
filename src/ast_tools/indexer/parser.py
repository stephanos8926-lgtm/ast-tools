"""Python AST parser with comprehensive error handling.

Wraps ast.parse() with graceful handling of:
- SyntaxError (malformed Python)
- Empty files
- Encoding errors
- Very large files

Does NOT use tree-sitter (deferred to Phase 2+).
"""

import ast
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Maximum file size to parse (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class ParseResult:
    """Result of parsing a Python file.
    
    Attributes:
        success: True if parsing succeeded
        tree: AST tree (None if failed)
        error: Error message (None if succeeded)
        content_hash: SHA256 hash of file content
    """
    __slots__ = ('success', 'tree', 'error', 'content_hash')
    
    def __init__(
        self,
        success: bool,
        tree: Optional[ast.AST] = None,
        error: Optional[str] = None,
        content_hash: str = ""
    ):
        self.success = success
        self.tree = tree
        self.error = error
        self.content_hash = content_hash


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of file content.
    
    Args:
        content: File content as string
    
    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(content.encode('utf-8', errors='surrogateescape')).hexdigest()


def parse_file(file_path: Path) -> ParseResult:
    """Parse a Python file with comprehensive error handling.
    
    Handles:
        - Empty files (returns empty module, not error)
        - Syntax errors (logs and returns failure)
        - Encoding errors (uses surrogateescape)
        - Permission errors (logs and returns failure)
        - Oversized files (rejects >10MB)
    
    Args:
        file_path: Path to Python file
    
    Returns:
        ParseResult with success flag, AST tree (or None), and error message
    
    Example:
        >>> result = parse_file(Path("module.py"))
        >>> if result.success:
        ...     symbols = extract_symbols(result.tree)
        >>> else:
        ...     logger.warning(f"Parse failed: {result.error}")
    """
    try:
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"File too large (>10MB): {file_path}")
            return ParseResult(
                success=False,
                error=f"File too large: {file_size} bytes"
            )
        
        # Read file content
        try:
            content = file_path.read_text(encoding='utf-8', errors='surrogateescape')
        except PermissionError:
            logger.warning(f"Permission denied: {file_path}")
            return ParseResult(
                success=False,
                error="Permission denied"
            )
        except Exception as e:
            logger.warning(f"Read error for {file_path}: {e}")
            return ParseResult(
                success=False,
                error=f"Read error: {e}"
            )
        
        # Compute hash
        content_hash = compute_content_hash(content)
        
        # Handle empty files (valid Python, 0 symbols)
        if not content.strip():
            empty_module = ast.Module(body=[], type_ignores=[])
            return ParseResult(
                success=True,
                tree=empty_module,
                content_hash=content_hash
            )
        
        # Parse AST
        tree = ast.parse(content, filename=str(file_path))
        return ParseResult(
            success=True,
            tree=tree,
            content_hash=content_hash
        )
    
    except SyntaxError as e:
        logger.debug(f"Syntax error in {file_path}: {e}")
        return ParseResult(
            success=False,
            error=f"SyntaxError: {e.msg} at line {e.lineno}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error parsing {file_path}")
        return ParseResult(
            success=False,
            error=f"Unexpected error: {e}"
        )


def parse_source(source: str, filename: str = "<unknown>") -> ParseResult:
    """Parse Python source code from a string.
    
    Args:
        source: Python source code
        filename: Filename for error messages
    
    Returns:
        ParseResult with success flag and AST tree
    
    Example:
        >>> result = parse_source("def foo(): pass")
        >>> if result.success:
        ...     tree = result.tree
    """
    try:
        content_hash = compute_content_hash(source)
        
        # Handle empty source
        if not source.strip():
            empty_module = ast.Module(body=[], type_ignores=[])
            return ParseResult(
                success=True,
                tree=empty_module,
                content_hash=content_hash
            )
        
        tree = ast.parse(source, filename=filename)
        return ParseResult(
            success=True,
            tree=tree,
            content_hash=content_hash
        )
    
    except SyntaxError as e:
        return ParseResult(
            success=False,
            error=f"SyntaxError: {e.msg} at line {e.lineno}"
        )


class Parser:
    """Stateless parser for Python files.
    
    Convenience wrapper around parse_file() and parse_source().
    
    Usage:
        parser = Parser()
        result = parser.parse_file(Path("module.py"))
        if result.success:
            symbols = extractor.extract(result.tree)
    """
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a Python file."""
        return parse_file(file_path)
    
    def parse_source(self, source: str, filename: str = "<unknown>") -> ParseResult:
        """Parse Python source code from a string."""
        return parse_source(source, filename)