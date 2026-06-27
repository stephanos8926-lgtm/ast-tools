#!/usr/bin/env python3
"""Tree-sitter backend for AST parsing, grep, and read operations.

Provides an alternative AST parsing backend using tree-sitter instead of
Python's built-in `ast` module. Supports multiple languages:
- Python, Rust, Go, TypeScript, JavaScript, C++, C, JSON, YAML, Bash

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

from typing import Any

# Lazy imports — tree-sitter is optional
_tree_sitter = None
_LANGUAGE_MAP = {
    "python": None,
    "rust": None,
    "go": None,
    "typescript": None,
    "javascript": None,
    "cpp": None,
    "c": None,
    "json": None,
    "yaml": None,
    "bash": None,
}


def _ensure_tree_sitter():
    """Lazy-load tree-sitter modules."""
    global _tree_sitter
    if _tree_sitter is None:
        try:
            import tree_sitter

            _tree_sitter = tree_sitter
        except ImportError:
            raise ImportError(
                "tree-sitter not installed. Install: pip install tree-sitter tree-sitter-python"
            )
    return _tree_sitter


def _get_language(lang: str):
    """Get a tree-sitter Language object for the given language code.

    Args:
        lang: Language code (python, rust, go, typescript, javascript, cpp, c, json, yaml, bash)

    Returns:
        tree_sitter.Language object

    Raises:
        ImportError: If tree-sitter or language parser not installed
        ValueError: If language not supported
    """
    ts = _ensure_tree_sitter()

    if lang not in _LANGUAGE_MAP:
        raise ValueError(
            f"Unsupported language: {lang}. Supported: {', '.join(_LANGUAGE_MAP.keys())}"
        )

    if _LANGUAGE_MAP[lang] is None:
        # Lazy load the parser module
        module_name = f"tree_sitter_{lang.replace('-', '_')}"
        try:
            module = __import__(module_name)

            # Special handling for tree-sitter-typescript which has separate languages
            if lang == "typescript":
                _LANGUAGE_MAP[lang] = ts.Language(module.language_typescript())
            elif lang == "javascript":
                # JavaScript uses standard language()
                _LANGUAGE_MAP[lang] = ts.Language(module.language())
            else:
                _LANGUAGE_MAP[lang] = ts.Language(module.language())
        except ImportError as e:
            raise ImportError(
                f"Parser for {lang} not installed. Try: pip install {module_name}"
            ) from e
        except AttributeError as e:
            # Fallback for modules with different attribute names
            if lang == "typescript" and hasattr(module, "language_typescript"):
                _LANGUAGE_MAP[lang] = ts.Language(module.language_typescript())
            else:
                raise ImportError(
                    f"Parser for {lang} has unexpected API. Module: {module_name}"
                ) from e

    return _LANGUAGE_MAP[lang]


# ─── Parse ────────────────────────────────────────────────────────────────


def ts_parse(source: str, lang: str = "python"):
    """Parse source code with tree-sitter.

    Args:
        source: Source code string.
        lang: Language code (default: "python").
              Supported: python, rust, go, typescript, javascript, cpp, c, json, yaml, bash

    Returns:
        tree_sitter.Tree object, or None on parse failure.
    """
    ts = _ensure_tree_sitter()
    language = _get_language(lang)
    parser = ts.Parser(language)
    tree = parser.parse(bytes(source, "utf-8"))
    if tree is None:
        return None
    return tree


# ─── Grep ─────────────────────────────────────────────────────────────────


def ts_grep(tree, pattern: str) -> list[dict[str, Any]]:
    """Search a tree-sitter parse tree for matching nodes (Python-only for backward compat).

    For multi-language support, use ts_grep_lang() instead.

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
    ts = _ensure_tree_sitter()

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
            results.append(
                {
                    "type": node.type,
                    "text": node.text.decode("utf-8"),
                    "start_line": node.start_point[0] + 1,  # 1-indexed
                    "start_col": node.start_point[1],
                    "end_line": node.end_point[0] + 1,  # 1-indexed
                    "end_col": node.end_point[1],
                    "captures": [name],
                }
            )

    return results


def ts_grep_lang(tree, pattern: str, lang: str) -> list[dict[str, Any]]:
    """Search a tree-sitter parse tree for matching nodes with language-specific queries.

    This function handles language-specific query patterns, since different languages
    have different node types (e.g., 'function_item' in Rust vs 'function_definition' in Python).

    Args:
        tree: tree_sitter.Tree from ts_parse(source, lang).
        pattern: Simplified pattern string (language-agnostic).
        lang: Language code for context.

    Returns:
        List of match dicts with keys: type, text, start_line, start_col, end_line, end_col, captures.
    """
    ts = _ensure_tree_sitter()

    if tree is None:
        return []

    # Language-specific query mappings
    _LANG_PATTERNS = {
        "python": {
            "function": "(function_definition) @match",
            "class": "(class_definition) @match",
            "import": "(import_statement) @match (import_from_statement) @match",
            "call": "(call_expression) @match",
        },
        "rust": {
            "function": "(function_item) @match",
            "struct": "(struct_item) @match",
            "enum": "(enum_item) @match",
            "impl": "(impl_item) @match",
            "import": "(use_declaration) @match",
            "call": "(call_expression) @match",
        },
        "go": {
            "function": "(function_declaration) @match (method_declaration) @match",
            "struct": "(type_spec type: (struct_type)) @match",
            "interface": "(type_spec type: (interface_type)) @match",
            "import": "(import_spec) @match",
            "call": "(call_expression) @match",
        },
        "typescript": {
            "function": "(function_declaration) @match (arrow_function) @match",
            "class": "(class_declaration) @match",
            "interface": "(interface_declaration) @match",
            "import": "(import_statement) @match",
            "call": "(call_expression) @match",
        },
        "javascript": {
            "function": "(function_declaration) @match (arrow_function) @match",
            "class": "(class_declaration) @match",
            "import": "(import_statement) @match",
            "call": "(call_expression) @match",
        },
        "cpp": {
            "function": "(function_definition) @match",
            "class": "(class_specifier) @match",
            "struct": "(struct_specifier) @match",
            "import": "(preproc_include) @match",
            "call": "(call_expression) @match",
        },
        "c": {
            "function": "(function_definition) @match",
            "struct": "(struct_specifier) @match",
            "import": "(preproc_include) @match",
            "call": "(call_expression) @match",
        },
        "json": {
            "object": "(pair) @match",
            "array": "(array) @match",
        },
        "yaml": {
            "mapping": "(block_mapping_pair) @match",
            "sequence": "(block_sequence_item) @match",
        },
        "bash": {
            "function": "(function_definition) @match",
            "command": "(command) @match",
        },
    }

    patterns = _LANG_PATTERNS.get(lang, {})

    if pattern in patterns:
        query_str = patterns[pattern]
    elif pattern in _LANG_PATTERNS.get("python", {}):
        # Fallback: try with Python patterns if lang-specific not found
        query_str = patterns.get("call", f"({pattern}) @match")
    else:
        # Treat as a raw tree-sitter query
        query_str = pattern

    language = tree.language
    query = ts.Query(language, query_str)
    query_cursor = ts.QueryCursor(query)
    captures = query_cursor.captures(tree.root_node)

    results = []
    for name, nodes in captures.items():
        for node in nodes:
            results.append(
                {
                    "type": node.type,
                    "text": node.text.decode("utf-8"),
                    "start_line": node.start_point[0] + 1,
                    "start_col": node.start_point[1],
                    "end_line": node.end_point[0] + 1,
                    "end_col": node.end_point[1],
                    "captures": [name],
                }
            )

    return results


def _flatten_nodes(node) -> list[dict[str, Any]]:
    """Flatten all nodes into a list of match dicts."""
    results = []
    results.append(
        {
            "type": node.type,
            "text": node.text.decode("utf-8")[:200],
            "start_line": node.start_point[0] + 1,
            "start_col": node.start_point[1],
            "end_line": node.end_point[0] + 1,
            "end_col": node.end_point[1],
            "captures": [],
        }
    )
    for child in node.children:
        results.extend(_flatten_nodes(child))
    return results


# ─── Read (API surface extraction) ────────────────────────────────────────


def ts_read(tree, lang: str = "python") -> dict[str, Any]:
    """Extract API surface from a tree-sitter parse tree.

    For multi-language support, use ts_read_lang(file_path, lang) instead.

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

    _walk_ts_node(root, functions, classes, imports, lang)

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


def _walk_ts_node(node, functions, classes, imports, lang: str = "python"):
    """Walk a tree-sitter node tree and extract API surface."""
    # Get language-specific node types
    node_types = _get_node_types(lang)

    for child in node.children:
        if child.type in node_types.get("function", []):
            _extract_function_ts(child, functions, lang)
        elif child.type in node_types.get("class", []):
            _extract_class_ts(child, classes, lang)
        elif child.type in node_types.get("import", []):
            _extract_import_ts(child, imports, lang)
        else:
            # Recurse into compound statements that might contain classes/functions
            if child.type in ("block", "module", "statement_block"):
                _walk_ts_node(child, functions, classes, imports, lang)


def _get_node_types(lang: str) -> dict[str, list[str]]:
    """Get tree-sitter node types for a language."""
    _NODE_TYPES = {
        "python": {
            "function": ["function_definition"],
            "class": ["class_definition"],
            "import": ["import_statement", "import_from_statement"],
        },
        "rust": {
            "function": ["function_item"],
            "class": ["struct_item", "enum_item", "trait_item"],
            "import": ["use_declaration"],
        },
        "go": {
            "function": ["function_declaration", "method_declaration"],
            "class": ["type_spec"],
            "import": ["import_spec"],
        },
        "typescript": {
            "function": ["function_declaration", "arrow_function", "method_definition"],
            "class": ["class_declaration", "interface_declaration", "type_alias_declaration"],
            "import": ["import_statement"],
        },
        "javascript": {
            "function": ["function_declaration", "arrow_function", "method_definition"],
            "class": ["class_declaration"],
            "import": ["import_statement"],
        },
        "cpp": {
            "function": ["function_definition"],
            "class": ["class_specifier", "struct_specifier"],
            "import": ["preproc_include"],
        },
        "c": {
            "function": ["function_definition"],
            "class": ["struct_specifier"],
            "import": ["preproc_include"],
        },
        "json": {
            "function": [],
            "class": [],
            "import": [],
        },
        "yaml": {
            "function": [],
            "class": [],
            "import": [],
        },
        "bash": {
            "function": ["function_definition"],
            "class": [],
            "import": [],
        },
    }
    return _NODE_TYPES.get(lang, _NODE_TYPES["python"])


def ts_read_lang(file_path: str, lang: str) -> dict[str, Any]:
    """Extract API surface from a file for any supported language.

    Args:
        file_path: Path to source file
        lang: Language code

    Returns:
        Dict with functions, classes, imports, summary (same as ts_read)
    """
    from pathlib import Path

    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ts_parse(source, lang)
        return ts_read(tree, lang)
    except Exception as e:
        return {"functions": [], "classes": [], "imports": [], "summary": {}, "error": str(e)}


def _extract_function_ts(node, functions: list, lang: str = "python"):
    """Extract a function definition from a tree-sitter node."""
    name = ""
    params = []
    line = node.start_point[0] + 1

    for child in node.children:
        if child.type == "identifier":
            name = child.text.decode("utf-8")
        elif child.type == "name":
            # Rust uses 'name' instead of 'identifier'
            name = child.text.decode("utf-8")
        elif child.type in ("parameters", "parameter_list", "formal_parameters"):
            params = _extract_params_ts(child, lang)

    signature = f"({', '.join(params)})" if params else "()"

    functions.append(
        {
            "name": name,
            "signature": signature,
            "line": line,
            "docstring": None,  # tree-sitter doesn't reliably extract docstrings
        }
    )


def _extract_params_ts(node, lang: str = "python") -> list[str]:
    """Extract parameter names from a tree-sitter parameters node."""
    params = []
    for child in node.children:
        if child.type == "identifier":
            params.append(child.text.decode("utf-8"))
        elif child.type in ("typed_parameter", "default_parameter", "parameter"):
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(sub.text.decode("utf-8"))
                    break
        elif child.type == "type_identifier":
            # Skip type annotations
            pass
    return params


def _extract_class_ts(node, classes: list, lang: str = "python"):
    """Extract a class definition from a tree-sitter node."""
    name = ""
    line = node.start_point[0] + 1
    methods = []
    bases = []

    for child in node.children:
        if child.type in ("identifier", "type_identifier", "name"):
            name = child.text.decode("utf-8")
        elif child.type in ("argument_list", "type_arguments"):
            # Base classes / type parameters
            for sub in child.children:
                if sub.type in ("identifier", "type_identifier"):
                    bases.append(sub.text.decode("utf-8"))
        elif child.type in ("block", "field_declaration_list", "body"):
            # Body — find methods
            _extract_methods_ts(child, methods, lang)

    classes.append(
        {
            "name": name,
            "line": line,
            "bases": bases,
            "methods": methods,
            "docstring": None,
        }
    )


def _extract_methods_ts(node, methods: list, lang: str = "python"):
    """Extract method definitions from a class body."""
    node_types = _get_node_types(lang)
    function_types = node_types.get("function", ["function_definition"])

    for child in node.children:
        if child.type in function_types:
            name = ""
            line = child.start_point[0] + 1
            for sub in child.children:
                if sub.type in ("identifier", "name"):
                    name = sub.text.decode("utf-8")
            methods.append(
                {
                    "name": name,
                    "line": line,
                }
            )


def _extract_import_ts(node, imports: list, lang: str = "python"):
    """Extract import information from a tree-sitter import node."""
    module = ""
    names = []
    line = node.start_point[0] + 1

    if node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = child.text.decode("utf-8")
                names = [module.split(".")[-1]]
    elif node.type == "import_from_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = child.text.decode("utf-8")
            elif child.type == "identifier":
                names.append(child.text.decode("utf-8"))
    elif node.type == "use_declaration":
        # Rust use statements
        for child in node.children:
            if child.type == "scoped_identifier":
                module = child.text.decode("utf-8")
                names = [module.split("::")[-1]]
    elif node.type == "import_spec":
        # Go imports
        for child in node.children:
            if child.type == "interpreted_string_literal":
                module = child.text.decode("utf-8").strip('"')
                names = [module.split("/")[-1]]

    imports.append(
        {
            "module": module,
            "names": names,
            "line": line,
        }
    )


__all__ = [
    "ts_grep",
    "ts_grep_lang",
    "ts_parse",
    "ts_read",
    "ts_read_lang",
]
