"""Symbol and edge extraction from Python AST.

Extracts:
- Functions, classes, methods, variables, imports, constants
- Edges: calls, imports, inherits, instantiates

Handles errors gracefully:
- Skips nodes that can't be analyzed
- Continues extraction even if some nodes fail
- Logs warnings for edge cases
"""

import ast
from pathlib import Path
from typing import List, Tuple, Optional, Set
import logging

from ..types import Symbol, Edge, SymbolKind, EdgeKind

logger = logging.getLogger(__name__)


class SymbolExtractor(ast.NodeVisitor):
    """Extract symbols and edges from a Python AST.
    
    Walks the AST and collects:
        - Symbol definitions (functions, classes, methods, etc.)
        - Edges (calls, imports, inherits, instantiates)
    
    Usage:
        extractor = SymbolExtractor("module.py")
        extractor.visit(tree)
        symbols = extractor.symbols
        edges = extractor.edges
    """
    
    def __init__(self, file_path: str):
        """Initialize extractor.
        
        Args:
            file_path: Path to the source file (for symbol IDs)
        """
        self.file_path = file_path
        self.symbols: List[Symbol] = []
        self.edges: List[Edge] = []
        self._scope_stack: List[str] = []  # For building qualified names
        self._imports: Set[str] = set()  # Imported names for resolution
    
    def _make_id(self, name: str) -> str:
        """Create unique symbol ID.
        
        Args:
            name: Qualified symbol name
        
        Returns:
            ID in format "file_path:qualified_name"
        """
        return f"{self.file_path}:{name}"
    
    def _add_to_scope(self, name: str) -> str:
        """Push a scope and return the full qualified name.
        
        Args:
            name: Local name (e.g., "method")
        
        Returns:
            Qualified name (e.g., "Class.method")
        """
        self._scope_stack.append(name)
        return ".".join(self._scope_stack)
    
    def _exit_scope(self) -> None:
        """Pop the current scope."""
        if self._scope_stack:
            self._scope_stack.pop()
    
    def _get_qualified_name(self) -> str:
        """Get the current qualified name from scope stack."""
        return ".".join(self._scope_stack) if self._scope_stack else ""
    
    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Extract function signature as a string.
        
        Args:
            node: Function or async function node
        
        Returns:
            Signature like "def foo(arg1, arg2=None) -> str"
        """
        try:
            args = []
            for arg in node.args.args:
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += ": ..."
                args.append(arg_str)
            
            # Add varargs/kwonly
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")
            
            # Add returns
            returns = ""
            if node.returns:
                returns = " -> ..."
            
            return f"def {node.name}({', '.join(args)}){returns}"
        except Exception:
            # Signature extraction is non-critical
            return f"def {node.name}(...)"
    
    def _get_docstring(self, node: ast.AST) -> Optional[str]:
        """Extract docstring from a node.
        
        Args:
            node: AST node (FunctionDef, ClassDef, Module)
        
        Returns:
            Docstring content or None
        """
        if not node.body:
            return None
        
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                doc = first.value.value
                # Truncate long docstrings
                if len(doc) > 1000:
                    doc = doc[:1000] + "..."
                return doc
        return None
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        try:
            qualified_name = self._add_to_scope(node.name)
            symbol = Symbol(
                id=self._make_id(qualified_name),
                name=node.name,
                qualified_name=qualified_name,
                kind=SymbolKind.METHOD if len(self._scope_stack) > 1 else SymbolKind.FUNCTION,
                file_path=self.file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                signature=self._get_signature(node),
                docstring=self._get_docstring(node),
            )
            self.symbols.append(symbol)
            
            # Extract edges (calls, imports)
            self._extract_edges_from_body(node.body)
            
            # Visit body (nested functions, classes)
            self.generic_visit(node)
            
            self._exit_scope()
        except Exception as e:
            logger.warning(f"Error extracting function {node.name}: {e}")
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        # Same as regular function
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        try:
            qualified_name = self._add_to_scope(node.name)
            symbol = Symbol(
                id=self._make_id(qualified_name),
                name=node.name,
                qualified_name=qualified_name,
                kind=SymbolKind.CLASS,
                file_path=self.file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=self._get_docstring(node),
            )
            self.symbols.append(symbol)
            
            # Extract inheritance edges
            for base in node.bases:
                try:
                    if isinstance(base, ast.Name):
                        self.edges.append(Edge(
                            source_id=symbol.id,
                            target_name=base.id,
                            edge_type=EdgeKind.INHERITS,
                        ))
                    elif isinstance(base, ast.Attribute):
                        # e.g., module.BaseClass
                        self.edges.append(Edge(
                            source_id=symbol.id,
                            target_name=base.attr,
                            edge_type=EdgeKind.INHERITS,
                        ))
                except Exception:
                    pass
            
            # Visit methods and nested classes
            self.generic_visit(node)
            
            self._exit_scope()
        except Exception as e:
            logger.warning(f"Error extracting class {node.name}: {e}")
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        try:
            for alias in node.names:
                # Track import for edge resolution
                name = alias.asname or alias.name.split('.')[0]
                self._imports.add(name)
                
                # Create import symbol
                symbol = Symbol(
                    id=self._make_id(f"import_{name}"),
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.IMPORT,
                    file_path=self.file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
                self.symbols.append(symbol)
                
                # Track as edge (if importing module.Class)
                if '.' in alias.name:
                    self.edges.append(Edge(
                        source_id=self._make_id(self._get_qualified_name()),
                        target_name=alias.name.split('.')[0],
                        edge_type=EdgeKind.IMPORTS,
                    ))
        except Exception as e:
            logger.warning(f"Error extracting import: {e}")
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from ... import ... statement."""
        try:
            module = node.module or ''
            for alias in node.names:
                name = alias.asname or alias.name
                self._imports.add(name)
                
                symbol = Symbol(
                    id=self._make_id(f"import_{name}"),
                    name=name,
                    qualified_name=f"{module}.{name}" if module else name,
                    kind=SymbolKind.IMPORT,
                    file_path=self.file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
                self.symbols.append(symbol)
                
                self.edges.append(Edge(
                    source_id=self._make_id(self._get_qualified_name()),
                    target_name=name,
                    edge_type=EdgeKind.IMPORTS,
                ))
        except Exception as e:
            logger.warning(f"Error extracting import from {module}: {e}")
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment to detect constants/variables."""
        try:
            # Check if it's a constant (UPPER_CASE)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    kind = SymbolKind.CONSTANT if name.isupper() else SymbolKind.VARIABLE
                    
                    symbol = Symbol(
                        id=self._make_id(name),
                        name=name,
                        qualified_name=name,
                        kind=kind,
                        file_path=self.file_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                    )
                    self.symbols.append(symbol)
        except Exception as e:
            logger.warning(f"Error extracting assignment: {e}")
    
    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call to track edges."""
        try:
            # Only track calls within a function/class scope
            if not self._scope_stack:
                # Module-level calls - skip (no enclosing symbol to attribute to)
                pass
            else:
                # Track direct calls
                if isinstance(node.func, ast.Name):
                    self.edges.append(Edge(
                        source_id=self._make_id(self._get_qualified_name()),
                        target_name=node.func.id,
                        edge_type=EdgeKind.CALLS,
                    ))
                elif isinstance(node.func, ast.Attribute):
                    # Method calls like obj.method()
                    self.edges.append(Edge(
                        source_id=self._make_id(self._get_qualified_name()),
                        target_name=node.func.attr,
                        edge_type=EdgeKind.CALLS,
                    ))
        except Exception:
            pass  # Non-critical
        
        # Continue visiting children
        self.generic_visit(node)
    
    def _extract_edges_from_body(self, body: List[ast.AST]) -> None:
        """Extract edges from a function/class body.
        
        Args:
            body: List of AST nodes
        """
        for node in body:
            if isinstance(node, ast.Call):
                # Already handled in visit_Call
                pass
    
    def get_symbols(self) -> List[Symbol]:
        """Get all extracted symbols.
        
        Returns:
            List of Symbol dataclass instances
        """
        return self.symbols
    
    def get_edges(self) -> List[Edge]:
        """Get all extracted edges.
        
        Returns:
            List of Edge dataclass instances
        """
        return self.edges


def extract_symbols(tree: ast.AST, file_path: str) -> Tuple[List[Symbol], List[Edge]]:
    """Convenience function to extract symbols and edges from an AST.
    
    Usage:
        result = parse_file(Path("module.py"))
        if result.success:
            symbols, edges = extract_symbols(result.tree, "module.py")
    
    Args:
        tree: Parsed AST
        file_path: Path to the source file
    
    Returns:
        Tuple of (symbols, edges)
    """
    extractor = SymbolExtractor(file_path)
    extractor.visit(tree)
    return extractor.get_symbols(), extractor.get_edges()