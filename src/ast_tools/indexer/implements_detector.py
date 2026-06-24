"""Detects interface/protocol implementation relationships in Python code.

Identifies when a class implements:
- ABC (Abstract Base Class) methods
- Protocol (typing.Protocol) methods
- Interface-like base classes (naming conventions: *Interface, *Protocol)

Usage:
    detector = ImplementsDetector()
    detector.visit(tree)
    implements_edges = detector.edges  # List of Edge with type IMPLEMENTS
"""

import ast
from typing import List, Set
import logging

from ast_tools.types import Edge, EdgeKind

logger = logging.getLogger(__name__)


class ImplementsDetector(ast.NodeVisitor):
    """Detect interface/protocol implementation relationships.
    
    Walks a Python AST and identifies classes that implement interfaces by:
    1. Inheriting from ABC or Protocol base classes
    2. Overriding abstract methods defined in parent interfaces
    3. Following naming conventions (*Interface, *Protocol)
    
    Generates IMPLEMENTS edges from implementing classes to interface methods.
    """
    
    def __init__(self, file_path: str):
        """Initialize detector.
        
        Args:
            file_path: Path to source file (for edge source IDs)
        """
        self.file_path = file_path
        self.edges: List[Edge] = []
        self._interface_methods: dict[str, Set[str]] = {}  # interface_name -> method_names
        self._class_bases: dict[str, List[str]] = {}  # class_name -> base_class_names
        self._current_class: str | None = None
        
    def _make_id(self, name: str) -> str:
        """Create unique symbol ID.
        
        Args:
            name: Qualified symbol name
        
        Returns:
            ID in format "file_path:qualified_name"
        """
        return f"{self.file_path}:{name}"
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to detect interface implementation.
        
        Args:
            node: ClassDef AST node
        """
        class_name = node.name
        self._current_class = class_name
        
        # Collect base classes
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle typing.Protocol, abc.ABC, etc.
                base_names.append(self._get_full_name(base))
        
        self._class_bases[class_name] = base_names
        
        # Check if this class inherits from interface-like bases
        is_interface_subclass = any(
            self._is_interface_base(base_name)
            for base_name in base_names
        )
        
        if is_interface_subclass:
            # This class implements one or more interfaces
            for base_name in base_names:
                if self._is_interface_base(base_name):
                    # Will add edges after we collect interface methods
                    pass
        
        # Continue visiting children to collect method definitions
        self.generic_visit(node)
        
        self._current_class = None
    
    def _is_interface_base(self, base_name: str) -> bool:
        """Check if a base class name suggests an interface.
        
        Args:
            base_name: Base class name (e.g., 'ABC', 'Protocol', 'IMyInterface')
        
        Returns:
            True if base appears to be an interface
        """
        # Standard library interfaces
        if base_name in ('ABC', 'Protocol'):
            return True
        
        # Check for interface naming conventions
        if base_name.startswith('I') and len(base_name) > 1:
            # IMyInterface, IService, etc.
            return True
        if base_name.endswith('Interface'):
            # MyInterface, IServiceInterface, etc.
            return True
        if base_name.endswith('Protocol'):
            # MyProtocol, etc.
            return True
        
        # Check registered interfaces
        if base_name in self._interface_methods:
            return True
        
        return False
    
    def _get_full_name(self, node: ast.Attribute) -> str:
        """Get full dotted name from an Attribute node.
        
        Args:
            node: Attribute AST node (e.g., typing.Protocol)
        
        Returns:
            Full name as string (e.g., "typing.Protocol")
        """
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition to track interface methods.
        
        Args:
            node: FunctionDef AST node
        """
        if self._current_class:
            func_name = node.name
            
            # Check if this is an abstract method (decorated with @abstractmethod)
            is_abstract = any(
                (isinstance(dec, ast.Name) and dec.id == 'abstractmethod') or
                (isinstance(dec, ast.Attribute) and dec.attr == 'abstractmethod')
                for dec in node.decorator_list  # Fixed: decorator_list not decorators
            )
            
            if is_abstract:
                # Register this as an interface method
                if self._current_class not in self._interface_methods:
                    self._interface_methods[self._current_class] = set()
                self._interface_methods[self._current_class].add(func_name)
                
                logger.debug(
                    f"Registered abstract method: {self._current_class}.{func_name}"
                )
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition (same as FunctionDef).
        
        Args:
            node: AsyncFunctionDef AST node
        """
        self.visit_FunctionDef(node)
    
    def detect_implements_edges(self) -> List[Edge]:
        """Generate IMPLEMENTS edges after visiting the AST.
        
        Returns:
            List of Edge objects with type IMPLEMENTS
        """
        edges = []
        
        for class_name, bases in self._class_bases.items():
            for base_name in bases:
                if base_name in self._interface_methods:
                    # This class implements methods from the interface
                    interface_methods = self._interface_methods[base_name]
                    source_id = self._make_id(class_name)
                    
                    for method_name in interface_methods:
                        target_name = f"{base_name}.{method_name}"
                        edge = Edge(
                            source_id=source_id,
                            target_name=target_name,
                            edge_type=EdgeKind.IMPLEMENTS,
                            metadata={
                                "interface": base_name,
                                "implemented_method": method_name,
                                "implementing_class": class_name
                            }
                        )
                        edges.append(edge)
                        logger.debug(
                            f"DETECTED: {class_name} implements {target_name}"
                        )
        
        return edges


def find_implements_relationships(
    tree: ast.AST,
    file_path: str
) -> List[Edge]:
    """Convenience function to detect all IMPLEMENTS relationships in a file.
    
    Usage:
        tree = ast.parse(source_code)
        edges = find_implements_relationships(tree, "/path/to/file.py")
    
    Args:
        tree: Parsed Python AST
        file_path: Path to source file
    
    Returns:
        List of IMPLEMENTS edges
    """
    detector = ImplementsDetector(file_path)
    detector.visit(tree)
    return detector.detect_implements_edges()