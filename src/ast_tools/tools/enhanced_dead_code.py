#!/usr/bin/env python3
"""Enhanced dead code detection with reduced false positives.

Enhancements over basic dead code detection:
1. Polymorphism tracking - marks implemented interface methods as 'alive'
2. Framework decorator detection - Flask, FastAPI, Celery, Click, Django routes
3. Entry point detection - __main__.py, Click groups, Celery tasks
4. Orphan cluster detection - SCC algorithm for circular dead code
5. __all__ exports check - don't flag exported symbols
6. Confidence scoring - High/Medium/Low per finding

Usage:
    from ast_tools.tools.enhanced_dead_code import find_dead_code_enhanced
    result = find_dead_code_enhanced("/path/to/project")
"""

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ast_tools.tools.dependency import _iter_project_python_files

logger = logging.getLogger(__name__)


@dataclass
class DeadCodeFinding:
    """Represents a single dead code finding with metadata."""

    name: str
    file: str
    line: int
    symbol_type: str  # 'function', 'class', 'method'
    confidence: str  # 'high', 'medium', 'low'
    reason: str  # Why it's considered dead
    alive_signals: list[str] = field(default_factory=list)  # Signals that suggest it's alive


class EnhancedDeadCodeDetector:
    """Enhanced dead code detector with multiple false-positive reduction strategies."""

    # Framework decorators that indicate entry points or routes
    FRAMEWORK_DECORATORS = {
        # Flask
        "route",
        "app.route",
        "blueprint.route",
        "Flask.route",
        # FastAPI
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "options",
        "fastapi.get",
        "fastapi.post",
        # Celery
        "task",
        "celery.task",
        "shared_task",
        # Click
        "command",
        "group",
        "click.command",
        "click.group",
        # Django
        "admin.register",
        "admin.site.register",
        "receiver",
        "signal",
        # Pytest
        "fixture",
        "pytest.fixture",
        # General
        "abstractmethod",
        "abc.abstractmethod",
    }

    # Decorators that mark methods as implemented (polymorphism)
    POLYMORPHISM_DECORATORS = {"override", "overrides", "impl", "implements"}

    def __init__(self, project_root: str, entry_points: list[str] | None = None):
        """Initialize detector.

        Args:
            project_root: Root directory of the project
            entry_points: List of known entry point files
        """
        self.project_root = Path(project_root)
        self.entry_points = entry_points or self._detect_default_entry_points()

        # Symbol tracking
        self.definitions: dict[str, list[dict]] = defaultdict(list)
        self.references: dict[str, list[str]] = defaultdict(list)
        self.implements_map: dict[str, set[str]] = defaultdict(set)  # class -> interface methods
        self.decorated_symbols: set[str] = set()  # Symbols with framework decorators
        self.exported_symbols: set[str] = set()  # Symbols in __all__
        self.entry_point_symbols: set[str] = set()  # Symbols reachable from entry points

        # Call graph for SCC
        self.call_graph: dict[str, set[str]] = defaultdict(set)

    def _detect_default_entry_points(self) -> list[str]:
        """Detect common entry point files."""
        candidates = []

        # Common entry point patterns
        patterns = [
            "main.py",
            "__main__.py",
            "cli.py",
            "app.py",
            "wsgi.py",
            "asgi.py",
            "manage.py",  # Django
            "celery.py",
        ]

        for pattern in patterns:
            for match in self.project_root.rglob(pattern):
                if "test" not in str(match) and "__pycache__" not in str(match):
                    candidates.append(str(match.relative_to(self.project_root)))

        return candidates

    def _make_symbol_key(self, file: str, name: str, symbol_type: str) -> str:
        """Create unique symbol key."""
        return f"{file}:{name}:{symbol_type}"

    def _is_framework_decorator(self, decorator_node: ast.expr) -> tuple[bool, str]:
        """Check if decorator is a framework decorator.

        Returns:
            Tuple of (is_framework_decorator, decorator_name)
        """
        if isinstance(decorator_node, ast.Name):
            name = decorator_node.id
            if name in self.FRAMEWORK_DECORATORS:
                return True, name
        elif isinstance(decorator_node, ast.Attribute):
            # Handle e.g., @app.route, @Flask.get
            parts = []
            current = decorator_node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            full_name = ".".join(reversed(parts))
            if any(dec in full_name for dec in self.FRAMEWORK_DECORATORS):
                return True, full_name
        elif isinstance(decorator_node, ast.Call):
            # Handle e.g., @app.route('/path')
            return self._is_framework_decorator(decorator_node.func)

        return False, ""

    def _is_polymorphism_decorator(self, decorator_node: ast.expr) -> bool:
        """Check if decorator indicates polymorphism (override)."""
        if isinstance(decorator_node, ast.Name):
            return decorator_node.id in self.POLYMORPHISM_DECORATORS
        elif isinstance(decorator_node, ast.Attribute):
            return decorator_node.attr in self.POLYMORPHISM_DECORATORS
        return False

    def _collect_from_file(self, py_file: Path) -> None:
        """Collect definitions, references, and metadata from a single file."""
        rel_path = str(py_file.relative_to(self.project_root))

        try:
            with open(py_file, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)

            # Check for __all__ exports
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__all__"
                            and isinstance(node.value, (ast.List, ast.Tuple))
                        ):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str
                                ):
                                    self.exported_symbols.add(elt.value)
                                    logger.debug(f"Exported symbol: {elt.value}")

            # Walk tree for definitions and references
            current_class: str | None = None

            for node in ast.walk(tree):
                # Track current class context
                if isinstance(node, ast.ClassDef):
                    current_class = node.name

                # Collect function/method definitions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_name = node.name
                    symbol_key = self._make_symbol_key(rel_path, func_name, "function")

                    # Check decorators
                    is_framework = False
                    is_polymorphism = False

                    for dec in node.decorator_list:
                        is_framework, dec_name = self._is_framework_decorator(dec)
                        if is_framework:
                            self.decorated_symbols.add(symbol_key)
                            logger.debug(f"Framework decorator: {symbol_key} @{dec_name}")

                        if self._is_polymorphism_decorator(dec):
                            is_polymorphism = True
                            logger.debug(f"Polymorphism marker: {symbol_key}")

                    # Check if this is likely an interface method (abstract)
                    is_abstract = any(
                        (isinstance(dec, ast.Name) and dec.id == "abstractmethod")
                        or (isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod")
                        for dec in node.decorator_list
                    )

                    if is_abstract and current_class:
                        self.implements_map[current_class].add(func_name)

                    # Don't skip - we still track it, but mark as potentially alive
                    self.definitions[func_name].append(
                        {
                            "file": rel_path,
                            "line": node.lineno,
                            "type": "method" if current_class else "function",
                            "class": current_class,
                            "is_framework": is_framework,
                            "is_polymorphism": is_polymorphism,
                            "is_abstract": is_abstract,
                        }
                    )

                    # Track call graph edges (calls within function body)
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                            callee = child.func.id
                            self.call_graph[symbol_key].add(
                                self._make_symbol_key(rel_path, callee, "function")
                            )

                # Collect class definitions
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    class_name = node.name
                    symbol_key = self._make_symbol_key(rel_path, class_name, "class")

                    # Check for framework inheritance (e.g., Flask views)
                    for base in node.bases:
                        if isinstance(base, ast.Attribute):
                            full_name = ""
                            current = base
                            while isinstance(current, ast.Attribute):
                                full_name = current.attr + "." + full_name
                                current = current.value
                            if isinstance(current, ast.Name):
                                full_name += current.id

                            if any(fw in full_name for fw in ["View", "Resource", "Handler"]):
                                self.decorated_symbols.add(symbol_key)

                    self.definitions[class_name].append(
                        {
                            "file": rel_path,
                            "line": node.lineno,
                            "type": "class",
                            "bases": [
                                b.id if isinstance(b, ast.Name) else str(b) for b in node.bases
                            ],
                        }
                    )

                # Collect references (Name nodes with Load context)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    self.references[node.id].append(rel_path)

        except (SyntaxError, UnicodeDecodeError) as e:
            logger.debug(f"Skipping unparseable file {py_file}: {e}")

    def _mark_entry_point_reachable(self) -> None:
        """Mark symbols reachable from entry points."""
        if not self.entry_points:
            return

        visited = set()
        to_visit = list(self.entry_points)

        while to_visit:
            entry = to_visit.pop(0)
            if entry in visited:
                continue
            visited.add(entry)

            # Find all symbols defined in this entry point file
            for symbol_name, defs in self.definitions.items():
                for defn in defs:
                    if defn["file"] == entry:
                        self.entry_point_symbols.add(symbol_name)

                        # Add called symbols to visit next
                        symbol_key = self._make_symbol_key(
                            defn["file"], symbol_name, defn["type"]
                        )
                        for called in self.call_graph.get(symbol_key, []):
                            # Extract just the symbol name from the key
                            called_name = called.split(":")[1]
                            if called_name not in visited:
                                to_visit.append(called_name)

    def _detect_scc_clusters(self) -> list[set[str]]:
        """Detect strongly connected components (circular reference clusters).

        Uses Tarjan's algorithm for SCC detection.
        Returns clusters of symbols that reference each other.
        """

        class TarjanSCC:
            def __init__(self, graph: dict[str, set[str]]):
                self.graph = graph
                self.index_counter = [0]
                self.stack = []
                self.lowlinks = {}
                self.index = {}
                self.on_stack = {}
                self.sccs = []

            def strongconnect(self, node: str) -> None:
                self.index[node] = self.index_counter[0]
                self.lowlinks[node] = self.index_counter[0]
                self.index_counter[0] += 1
                self.stack.append(node)
                self.on_stack[node] = True

                for successor in self.graph.get(node, []):
                    if successor not in self.index:
                        self.strongconnect(successor)
                        self.lowlinks[node] = min(self.lowlinks[node], self.lowlinks[successor])
                    elif self.on_stack.get(successor, False):
                        self.lowlinks[node] = min(self.lowlinks[node], self.index[successor])

                if self.lowlinks[node] == self.index[node]:
                    scc = []
                    while True:
                        w = self.stack.pop()
                        self.on_stack[w] = False
                        scc.append(w)
                        if w == node:
                            break
                    if len(scc) > 1:  # Only clusters with >1 node
                        self.sccs.append(set(scc))

            def run(self) -> list[set[str]]:
                for node in self.graph:
                    if node not in self.index:
                        self.strongconnect(node)
                return self.sccs

        tarjan = TarjanSCC(self.call_graph)
        return tarjan.run()

    def _calculate_confidence(
        self, symbol: str, defs: list[dict], is_referenced: bool
    ) -> tuple[str, str, list[str]]:
        """Calculate confidence score and reason for dead code finding.

        Returns:
            Tuple of (confidence, reason, alive_signals)
        """
        alive_signals = []

        # Check if referenced
        if is_referenced:
            return "low", "Symbol is referenced but may still be dead", ["referenced_in_code"]

        defn = defs[0] if defs else {}

        # Check framework decorators
        symbol_key = self._make_symbol_key(
            defn.get("file", ""), symbol, defn.get("type", "function")
        )
        if symbol_key in self.decorated_symbols:
            alive_signals.append("framework_decorator")
            return "low", "Has framework decorator (route/task/command)", alive_signals

        # Check polymorphism
        if defn.get("is_polymorphism"):
            alive_signals.append("polymorphism_marker")
            return "low", "Marked as polymorphism override", alive_signals

        # Check abstract methods
        if defn.get("is_abstract"):
            alive_signals.append("abstract_method")
            return "medium", "Abstract method (may be implemented elsewhere)", alive_signals

        # Check if in __all__
        if symbol in self.exported_symbols:
            alive_signals.append("exported_in_all")
            return "medium", "Exported in __all__", alive_signals

        # Check if reachable from entry point
        if symbol in self.entry_point_symbols:
            alive_signals.append("entry_point_reachable")
            return "low", "Reachable from entry point", alive_signals

        # Check if class implements interface
        if defn.get("class") and defn["class"] in self.implements_map and symbol in self.implements_map[defn["class"]]:
            alive_signals.append("interface_implementation")
            return "low", "Implements interface method", alive_signals

        # Default: high confidence dead code
        return "high", "No references or alive signals detected", []

    def analyze(self) -> dict[str, Any]:
        """Run full dead code analysis.

        Returns:
            Dict with dead functions, classes, methods, and metadata
        """
        # Phase 1: Collect from all files
        logger.info(f"Analyzing project: {self.project_root}")
        for py_file in _iter_project_python_files(self.project_root):
            if py_file.name.startswith("test_"):
                continue
            self._collect_from_file(py_file)

        # Phase 2: Mark entry point reachable symbols
        self._mark_entry_point_reachable()

        # Phase 3: Detect SCC clusters
        scc_clusters = self._detect_scc_clusters()
        scc_members: set[str] = set()
        for cluster in scc_clusters:
            for member in cluster:
                # Extract symbol name from key
                symbol_name = member.split(":")[1]
                scc_members.add(symbol_name)

        # Phase 4: Find dead code
        dead_functions = []
        dead_classes = []
        dead_methods = []

        for symbol, defs in self.definitions.items():
            is_referenced = symbol in self.references and len(self.references[symbol]) > 0
            is_in_scc = symbol in scc_members

            for defn in defs:
                confidence, reason, alive_signals = self._calculate_confidence(
                    symbol, defs, is_referenced or is_in_scc
                )

                finding = {
                    "name": symbol,
                    "file": f"{defn['file']}:{defn['line']}",
                    "confidence": confidence,
                    "reason": reason,
                    "alive_signals": alive_signals,
                    "symbol_type": defn.get("type", "function"),
                }

                if defn.get("type") == "class":
                    dead_classes.append(finding)
                elif defn.get("type") == "method":
                    dead_methods.append(finding)
                else:
                    dead_functions.append(finding)

        # Sort by confidence (high first)
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        dead_functions.sort(key=lambda x: confidence_order.get(x["confidence"], 3))
        dead_classes.sort(key=lambda x: confidence_order.get(x["confidence"], 3))
        dead_methods.sort(key=lambda x: confidence_order.get(x["confidence"], 3))

        return {
            "dead_functions": dead_functions[:100],
            "dead_classes": dead_classes[:100],
            "dead_methods": dead_methods[:100],
            "summary": {
                "total_dead_functions": len(dead_functions),
                "total_dead_classes": len(dead_classes),
                "total_dead_methods": len(dead_methods),
                "false_positive_mitigations": {
                    "framework_decorators": len(self.decorated_symbols),
                    "exported_symbols": len(self.exported_symbols),
                    "entry_point_symbols": len(self.entry_point_symbols),
                    "scc_cluster_members": len(scc_members),
                    "interface_implementations": sum(
                        len(methods) for methods in self.implements_map.values()
                    ),
                },
                "entry_points_analyzed": self.entry_points,
            },
        }


def find_dead_code_enhanced(
    project_root: str, entry_points: list[str] | None = None
) -> dict[str, Any]:
    """Enhanced dead code detection with reduced false positives.

    Args:
        project_root: Root directory of the project
        entry_points: List of known entry point files (auto-detected if None)

    Returns:
        Dict with dead code findings and metadata
    """
    detector = EnhancedDeadCodeDetector(project_root, entry_points)
    return detector.analyze()


def _tool_dead_code_enhanced(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for enhanced dead code detection."""
    project_root = args.get("project_root", ".")
    entry_points = args.get("entry_points")
    return find_dead_code_enhanced(project_root, entry_points)
