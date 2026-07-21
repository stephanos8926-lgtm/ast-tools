"""Symbol and edge extraction from Python AST and tree-sitter ASTs.

Extracts:
- Functions, classes, methods, variables, imports, constants
- Edges: calls, imports, inherits, instantiates

Handles errors gracefully:
- Skips nodes that can't be analyzed
- Continues extraction even if some nodes fail
- Logs warnings for edge cases

Supports both Python's built-in ast module and tree-sitter for multi-language support.
"""

import ast
import logging

from ..embeddings.provider import provider_generate_embedding_sync as generate_embedding
from ..symbols import Edge, EdgeKind, Symbol, SymbolKind

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
        self.symbols: list[Symbol] = []
        self.edges: list[Edge] = []
        self._scope_stack: list[str] = []  # For building qualified names
        self._imports: set[str] = set()  # Imported names for resolution

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

    def _get_docstring(self, node: ast.AST) -> str | None:
        """Extract docstring from a node.

        Args:
            node: AST node (FunctionDef, ClassDef, Module)

        Returns:
            Docstring content or None
        """
        if not node.body:
            return None

        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
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
            signature = self._get_signature(node)
            docstring = self._get_docstring(node)

            # Generate embedding text (signature + docstring)
            embedding_text = f"{signature or ''} {docstring or ''}".strip()
            embedding = generate_embedding(embedding_text) if embedding_text else None

            symbol = Symbol(
                id=self._make_id(qualified_name),
                name=node.name,
                qualified_name=qualified_name,
                kind=SymbolKind.METHOD if len(self._scope_stack) > 1 else SymbolKind.FUNCTION,
                file_path=self.file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                signature=signature,
                docstring=docstring,
                embedding=embedding,
                lang="python",
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
            docstring = self._get_docstring(node)

            # Generate embedding text (class name + docstring)
            embedding_text = f"class {node.name} {docstring or ''}".strip()
            embedding = generate_embedding(embedding_text) if embedding_text else None

            symbol = Symbol(
                id=self._make_id(qualified_name),
                name=node.name,
                qualified_name=qualified_name,
                kind=SymbolKind.CLASS,
                file_path=self.file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=docstring,
                embedding=embedding,
                lang="python",
            )
            self.symbols.append(symbol)

            # Extract inheritance edges
            for base in node.bases:
                try:
                    if isinstance(base, ast.Name):
                        self.edges.append(
                            Edge(
                                source_id=symbol.id,
                                target_name=base.id,
                                edge_type=EdgeKind.INHERITS,
                            )
                        )
                    elif isinstance(base, ast.Attribute):
                        # e.g., module.BaseClass
                        self.edges.append(
                            Edge(
                                source_id=symbol.id,
                                target_name=base.attr,
                                edge_type=EdgeKind.INHERITS,
                            )
                        )
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
                name = alias.asname or alias.name.split(".")[0]
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
                    lang="python",
                )
                self.symbols.append(symbol)

                # Track as edge (if importing module.Class)
                if "." in alias.name:
                    self.edges.append(
                        Edge(
                            source_id=self._make_id(self._get_qualified_name()),
                            target_name=alias.name.split(".")[0],
                            edge_type=EdgeKind.IMPORTS,
                        )
                    )
        except Exception as e:
            logger.warning(f"Error extracting import: {e}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from ... import ... statement."""
        try:
            module = node.module or ""
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
                    lang="python",
                )
                self.symbols.append(symbol)

                self.edges.append(
                    Edge(
                        source_id=self._make_id(self._get_qualified_name()),
                        target_name=name,
                        edge_type=EdgeKind.IMPORTS,
                    )
                )
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
                        lang="python",
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
                    self.edges.append(
                        Edge(
                            source_id=self._make_id(self._get_qualified_name()),
                            target_name=node.func.id,
                            edge_type=EdgeKind.CALLS,
                        )
                    )
                elif isinstance(node.func, ast.Attribute):
                    # Method calls like obj.method()
                    self.edges.append(
                        Edge(
                            source_id=self._make_id(self._get_qualified_name()),
                            target_name=node.func.attr,
                            edge_type=EdgeKind.CALLS,
                        )
                    )
        except Exception:
            pass  # Non-critical

        # Continue visiting children
        self.generic_visit(node)

    def _extract_edges_from_body(self, body: list[ast.AST]) -> None:
        """Extract edges from a function/class body.

        Args:
            body: List of AST nodes
        """
        for node in body:
            if isinstance(node, ast.Call):
                # Already handled in visit_Call
                pass

    def get_symbols(self) -> list[Symbol]:
        """Get all extracted symbols.

        Returns:
            List of Symbol dataclass instances
        """
        return self.symbols

    def get_edges(self) -> list[Edge]:
        """Get all extracted edges.

        Returns:
            List of Edge dataclass instances
        """
        return self.edges


def extract_symbols(tree: ast.AST, file_path: str) -> tuple[list[Symbol], list[Edge]]:
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


# ─── Tree-sitter symbol extraction (multi-language) ─────────────────────────


def extract_symbols_ts(source: str, lang: str) -> list[Symbol]:
    """Extract symbols from any tree-sitter supported language.

    Args:
        source: Source code string
        lang: Language code (python, rust, go, typescript, javascript, cpp, c, etc.)

    Returns:
        List of Symbol objects with .lang field set
    """
    from ast_tools.ts_backend import ts_parse

    tree = ts_parse(source, lang)
    if tree is None:
        return []

    extractor = TreeSitterSymbolExtractor(lang)
    return extractor.extract(tree)


class TreeSitterSymbolExtractor:
    """Language-specific symbol extraction via tree-sitter."""

    def __init__(self, lang: str):
        """Initialize extractor for a specific language.

        Args:
            lang: Language code
        """
        self.lang = lang
        self.queries = self._load_queries(lang)

    def _load_queries(self, lang: str) -> dict[str, str]:
        """Load tree-sitter queries for symbol extraction.

        Args:
            lang: Language code

        Returns:
            Dict of query names to query strings
        """
        return {
            "python": """
                (function_definition name: (identifier) @name) @function
                (class_definition name: (identifier) @name) @class
                (import_statement) @import
                (import_from_statement) @import
            """,
            "rust": """
                (function_item name: (identifier) @name) @function
                (struct_item name: (type_identifier) @name) @struct
                (enum_item name: (type_identifier) @name) @enum
                (impl_item type: (type_identifier) @name) @impl
                (use_declaration) @import
            """,
            "go": """
                (function_declaration name: (identifier) @name) @function
                (method_declaration name: (field_identifier) @name) @method
                (type_spec name: (type_identifier) @name type: (struct_type)) @struct
                (type_spec name: (type_identifier) @name type: (interface_type)) @interface
                (import_spec) @import
            """,
            "typescript": """
                (function_declaration name: (identifier) @name) @function
                (class_declaration name: (type_identifier) @name) @class
                (interface_declaration name: (type_identifier) @name) @interface
                (import_statement) @import
            """,
            "javascript": """
                (function_declaration name: (identifier) @name) @function
                (class_declaration name: (identifier) @name) @class
                (import_statement) @import
            """,
            "cpp": """
                (function_definition declarator: (function_declarator declarator: (identifier) @name)) @function
                (class_specifier name: (type_identifier) @name) @class
                (struct_specifier name: (type_identifier) @name) @struct
                (preproc_include) @import
            """,
            "c": """
                (function_definition declarator: (function_declarator declarator: (identifier) @name)) @function
                (struct_specifier name: (type_identifier) @name) @struct
                (preproc_include) @import
            """,
        }.get(lang, "")

    def extract(self, tree) -> list[Symbol]:
        """Extract symbols from a tree-sitter parse tree.

        Args:
            tree: tree_sitter.Tree object

        Returns:
            List of Symbol objects
        """
        from ast_tools.ts_backend import _ensure_tree_sitter

        ts = _ensure_tree_sitter()
        symbols = []

        query_str = self.queries.get(self.lang, "")
        if not query_str:
            return symbols

        try:
            language = tree.language
            query = ts.Query(language, query_str)
            query_cursor = ts.QueryCursor(query)
            captures = query_cursor.captures(tree.root_node)

            # Organize captures by capture name
            matches = {}
            for name, nodes in captures.items():
                if name not in matches:
                    matches[name] = []
                matches[name].extend(nodes)

            # Process each match
            for node in matches.get("function", []):
                symbols.append(self._extract_function(node))

            for node in matches.get("class", []):
                symbols.append(self._extract_class(node))

            for node in matches.get("struct", []):
                symbols.append(self._extract_struct(node))

            for node in matches.get("enum", []):
                symbols.append(self._extract_enum(node))

            for node in matches.get("import", []):
                symbols.append(self._extract_import(node))

            for node in matches.get("method", []):
                symbols.append(self._extract_method(node))

            for node in matches.get("interface", []):
                symbols.append(self._extract_interface(node))

            for node in matches.get("impl", []):
                symbols.append(self._extract_impl(node))

        except Exception as e:
            logger.warning(f"Error extracting symbols for {self.lang}: {e}")

        return symbols

    def _extract_function(self, node) -> Symbol:
        """Extract a function symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.FUNCTION,
            file_path="",
            start_line=line,
            end_line=end_line,
            signature="()",
            lang=self.lang,
        )

    def _extract_class(self, node) -> Symbol:
        """Extract a class symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.CLASS,
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _extract_struct(self, node) -> Symbol:
        """Extract a struct symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.CLASS,  # Treat struct like class
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _extract_enum(self, node) -> Symbol:
        """Extract an enum symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.CLASS,  # Treat enum like class
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _extract_import(self, node) -> Symbol:
        """Extract an import symbol."""
        name = node.text.decode("utf-8")[:100]
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":import:{line}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.IMPORT,
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _extract_method(self, node) -> Symbol:
        """Extract a method symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.METHOD,
            file_path="",
            start_line=line,
            end_line=end_line,
            signature="()",
            lang=self.lang,
        )

    def _extract_interface(self, node) -> Symbol:
        """Extract an interface symbol."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":{name}",
            name=name,
            qualified_name=name,
            kind=SymbolKind.CLASS,  # Treat interface like class
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _extract_impl(self, node) -> Symbol:
        """Extract an impl symbol (Rust specific)."""
        name = self._find_name(node)
        line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return Symbol(
            id=f":impl:{name}",
            name=f"impl {name}",
            qualified_name=name,
            kind=SymbolKind.CLASS,
            file_path="",
            start_line=line,
            end_line=end_line,
            lang=self.lang,
        )

    def _find_name(self, node) -> str:
        """Find the name identifier in a node tree."""
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "name", "field_identifier"):
                return child.text.decode("utf-8")
            # Recurse
            name = self._find_name(child)
            if name:
                return name
        return "anonymous"
