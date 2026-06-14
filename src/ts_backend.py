#!/usr/bin/env python3
"""Tree-sitter backend for AST parsing, grep, and read operations.

Provides an alternative AST parsing backend using tree-sitter instead of
Python's built-in `ast` module. Useful for languages beyond Python and
for unified AST handling.

Tree-sitter query syntax differs from our AST pattern syntax:
  - Patterns use S-expressions: (function_definition name: (identifier) @name)
  - Captures use @name suffix
  - Node types follow tree-sitter grammar (e.g., function_definition, class_definition)

For compatibility, we also support simplified patterns:
  - "function_definition" → matches any function_definition node
  - "class_definition" → matches any class_definition node
  - "method_definition" → matches method_definition nodes
  - "import_statement" → matches import_statement / import_from_statement
  - "call_expression" → matches call_expression nodes
"""

import ast as pyast
from pathlib import Path
from typing import Any

# Lazy imports — tree-sitter is optional
_tree_sitter = None
_tree_sitter_python = None


def _ensure_tree_sitter():
    """Lazy-load tree-sitter modules."""
    global _tree_sitter, _tree_sitter_python
    if _tree_sitter is None:
        try:
            import tree_sitter
            import tree_sitter_python
            _tree_sitter = tree_sitter
            _tree_sitter_python = tree_sitter_python
        except ImportError:
            raise ImportError(
                "tree-sitter not installed. Install: pip install tree-sitter tree-sitter-python"
            )
    return _tree_sitter, _tree_sitter_python


# ─── Language support ─────────────────────────────────────────────────────

_LANGUAGE_MAP = {
    "python": None,  # set on first access
}


def _get_language(lang: str):
    """Get a tree-sitter Language object for the given language code."""
    ts, ts_py = _ensure_tree_sitter()
    if lang in _LANGUAGE_MAP:
        if _LANGUAGE_MAP[lang] is None:
            if lang == "python":
                _LANGUAGE_MAP[lang] = ts.Language(ts_py.language())
        return _LANGUAGE_MAP[lang]
    raise ValueError(f"Unsupported language: {lang}")


# ─── Parse ────────────────────────────────────────────────────────────────

def ts_parse(source: str, lang: str = "python"):
    """Parse source code with tree-sitter.

    Args:
        source: Source code string.
        lang: Language code (default: "python").

    Returns:
        tree_sitter.Tree object, or None on parse failure.
    """
    ts, _ = _ensure_tree_sitter()
    language = _get_language(lang)
    parser = ts.Parser(language)
    tree = parser.parse(bytes(source, "utf-8"))
    if tree is None:
        return None
    return tree


# ─── Grep ─────────────────────────────────────────────────────────────────

def ts_grep(tree, pattern: str) -> list[dict[str, Any]]:
    """Search a tree-sitter parse tree for matching nodes.

    Supports both simplified patterns and tree-sitter queries.

    Simplified patterns (convenience):
        "function_definition" → matches all function definitions
        "class_definition"   → matches all class definitions
        "method_definition"   → matches all method definitions
        "import_statement"    → matches import_statement and import_from_statement
        "call_expression"     → matches all call expressions
        "all"                 → matches all node types (returns flattened list)

    Args:
        tree: tree_sitter.Tree from ts_parse().
        pattern: Simplified pattern string.

    Returns:
        List of match dicts with keys: type, text, start_line, start_col, end_line, end_col, captures.
    """
    ts, _ = _ensure_tree_sitter()

    if tree is None:
        return []

    # Map simplified patterns to tree-sitter query strings
    _SIMPLE_PATTERNS = {
        "function_definition": "(function_definition) @match",
        "class_definition": "(class_definition) @match",
        "method_definition": "(method_definition) @match",
        "import_statement": "(import_statement) @match (import_from_statement) @match",
        "call_expression": "(call_expression) @match",
    }

    if pattern in _SIMPLE_PATTERNS:
        query_str = _SIMPLE_PATTERNS[pattern]
    elif pattern == "all":
        # Return all nodes
        return _flatten_nodes(tree.root_node)
    else:
        # Treat as a raw tree-sitter query
        query_str = pattern

    language = tree.language
    query = ts.Query(language, query_str)
    query_cursor = ts.QueryCursor(query)
    captures = query_cursor.captures(tree.root_node)

    results = []
    # captures is a dict of {capture_name: [nodes]}
    for name, nodes in captures.items():
        for node in nodes:
            results.append({
                "type": node.type,
                "text": node.text.decode("utf-8"),
                "start_line": node.start_point[0] + 1,  # 1-indexed
                "start_col": node.start_point[1],
                "end_line": node.end_point[0] + 1,  # 1-indexed
                "end_col": node.end_point[1],
                "captures": [name],
            })

    return results


def _flatten_nodes(node) -> list[dict[str, Any]]:
    """Flatten all nodes into a list of match dicts."""
    results = []
    results.append({
        "type": node.type,
        "text": node.text.decode("utf-8")[:200],
        "start_line": node.start_point[0] + 1,
        "start_col": node.start_point[1],
        "end_line": node.end_point[0] + 1,
        "end_col": node.end_point[1],
        "captures": [],
    })
    for child in node.children:
        results.extend(_flatten_nodes(child))
    return results


# ─── Read (API surface extraction) ────────────────────────────────────────

def ts_read(tree) -> dict[str, Any]:
    """Extract API surface from a tree-sitter parse tree.

    Returns a dict with:
        - functions: list of {name, signature, line, docstring}
        - classes: list of {name, line, methods, docstring}
        - imports: list of {module, names, line}
        - summary: {total_functions, total_classes, total_imports}

    Note: tree-sitter does not provide the same level of detail as Python's `ast`
    for things like parameter names and default values. Signatures are reconstructed
    where possible.
    """
    if tree is None:
        return {"functions": [], "classes": [], "imports": [], "summary": {}}

    root = tree.root_node
    functions = []
    classes = []
    imports = []
    docstring = None

    _walk_ts_node(root, functions, classes, imports)

    return {
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "docstring": docstring,
        "summary": {
            "total_functions": len(functions),
            "total_classes": len(classes),
            "total_imports": len(imports),
        },
    }


def _walk_ts_node(node, functions, classes, imports):
    """Walk a tree-sitter node tree and extract API surface."""
    for child in node.children:
        if child.type == "function_definition":
            _extract_function(child, functions)
        elif child.type == "class_definition":
            _extract_class(child, classes)
        elif child.type in ("import_statement", "import_from_statement"):
            _extract_import(child, imports)
        else:
            # Recurse into compound statements that might contain classes/functions
            if child.type in ("block", "module", "if_statement", "try_statement",
                              "for_statement", "while_statement", "with_statement",
                              "match_statement"):
                _walk_ts_node(child, functions, classes, imports)


def _extract_function(node, functions: list):
    """Extract a function definition from a tree-sitter node."""
    name = ""
    params = []
    line = node.start_point[0] + 1

    for child in node.children:
        if child.type == "identifier":
            name = child.text.decode("utf-8")
        elif child.type == "parameters":
            params = _extract_params(child)
        elif child.type == "type" and not params:
            # Return type annotation
            pass

    signature = f"({', '.join(params)})" if params else "()"

    # Try to get docstring from first string literal in body
    docstring = None
    for child in node.children:
        if child.type == "block":
            for sub in child.children:
                if sub.type == "expression_statement":
                    for expr in sub.children:
                        if expr.type == "string" and len(expr.children) > 0:
                            docstring = expr.text.decode("utf-8").strip("'\"")
                            break

    functions.append({
        "name": name,
        "signature": signature,
        "line": line,
        "docstring": docstring,
    })


def _extract_params(node) -> list[str]:
    """Extract parameter names from a tree-sitter parameters node."""
    params = []
    for child in node.children:
        if child.type == "identifier":
            params.append(child.text.decode("utf-8"))
        elif child.type in ("typed_parameter", "default_parameter"):
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(sub.text.decode("utf-8"))
                    break
    return params


def _extract_class(node, classes: list):
    """Extract a class definition from a tree-sitter node."""
    name = ""
    line = node.start_point[0] + 1
    methods = []
    bases = []

    for child in node.children:
        if child.type == "identifier":
            name = child.text.decode("utf-8")
        elif child.type == "argument_list":
            # Base classes
            for sub in child.children:
                if sub.type == "identifier":
                    bases.append(sub.text.decode("utf-8"))
        elif child.type == "block":
            # Body — find methods
            _extract_methods(child, methods)

    # Try docstring
    docstring = None
    for child in node.children:
        if child.type == "block":
            for sub in child.children:
                if sub.type == "expression_statement":
                    for expr in sub.children:
                        if expr.type == "string":
                            docstring = expr.text.decode("utf-8").strip("'\"")
                            break

    classes.append({
        "name": name,
        "line": line,
        "bases": bases,
        "methods": methods,
        "docstring": docstring,
    })


def _extract_methods(node, methods: list):
    """Extract method definitions from a class body."""
    for child in node.children:
        if child.type == "function_definition":
            name = ""
            params = []
            line = child.start_point[0] + 1
            for sub in child.children:
                if sub.type == "identifier":
                    name = sub.text.decode("utf-8")
                elif sub.type == "parameters":
                    params = _extract_params(sub)
            methods.append({
                "name": name,
                "line": line,
            })
        elif child.type == "block":
            _extract_methods(child, methods)


def _extract_import(node, imports: list):
    """Extract import information from a tree-sitter import node."""
    module = ""
    names = []
    line = node.start_point[0] + 1

    if node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = child.text.decode("utf-8")
                names = [module.split(".")[-1]]
            elif child.type == "aliased_import":
                for sub in child.children:
                    if sub.type == "dotted_name":
                        module = sub.text.decode("utf-8")
                    elif sub.type == "identifier":
                        names.append(f"{module} as {sub.text.decode('utf-8')}")
    elif node.type == "import_from_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = child.text.decode("utf-8")
            elif child.type == "identifier":
                names.append(child.text.decode("utf-8"))

    imports.append({
        "module": module,
        "names": names,
        "line": line,
    })
