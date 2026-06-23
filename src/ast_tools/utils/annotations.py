#!/usr/bin/env python3
"""AST annotation helpers and function signature extraction."""

import ast
from typing import Any


def _annotation_to_str(node: ast.expr | None) -> str:
    """Convert an AST annotation node to a human-readable type string.
    
    Handles:
      ast.Name(id='str')                    -> "str"
      ast.Name(id='int')                    -> "int"
      ast.Constant(value=None)             -> "None"
      ast.Subscript(value=Name('list'), slice=Name('str')) -> "list[str]"
      ast.BinOp(left, op=BitOr(), right)   -> "X | Y"
      ast.Attribute(value=Name('pathlib'), attr='Path') -> "pathlib.Path"
    Fallback: ast.dump truncated to 80 chars.
    """
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        value_str = _annotation_to_str(node.value)
        return f"{value_str}.{node.attr}" if value_str else node.attr
    if isinstance(node, ast.Subscript):
        value_str = _annotation_to_str(node.value)
        slice_str = _annotation_to_str(node.slice)
        return f"{value_str}[{slice_str}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left_str = _annotation_to_str(node.left)
        right_str = _annotation_to_str(node.right)
        return f"{left_str} | {right_str}"
    if isinstance(node, ast.Tuple):
        # Handle multi-element subscripts like Dict[str, int]
        elements = [_annotation_to_str(e) for e in node.elts]
        return ", ".join(elements)
    # Fallback: truncated ast.dump
    dumped = ast.dump(node)
    return dumped if len(dumped) <= 80 else dumped[:77] + "..."


def _get_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract a human-readable function signature."""
    args = node.args
    parts = []

    # Positional args
    for arg in args.args:
        name = arg.arg
        if arg.annotation:
            name += f": {_annotation_to_str(arg.annotation)}"
        parts.append(name)

    # *args
    if args.vararg:
        vname = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            vname += f": {_annotation_to_str(args.vararg.annotation)}"
        parts.append(vname)

    # Keyword-only
    for arg in args.kwonlyargs:
        name = arg.arg
        if arg.annotation:
            name += f": {_annotation_to_str(arg.annotation)}"
        parts.append(name)

    # **kwargs
    if args.kwarg:
        kname = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            kname += f": {_annotation_to_str(args.kwarg.annotation)}"
        parts.append(kname)

    sig = f"({', '.join(parts)})"
    if node.returns:
        sig += f" -> {_annotation_to_str(node.returns)}"
    return sig


def _extract_all_names(tree: ast.Module) -> list[str] | None:
    """Extract all top-level names (imports, functions, classes, assignments)."""
    try:
        names = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                names.append(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                names.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    names.append(f"{base}=module")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base = node.module.split(".")[0]
                    names.append(f"{base}=module")
                for alias in node.names:
                    names.append(alias.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.append(f"{target.id}=var")
                    elif isinstance(target, ast.Tuple | ast.List):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name):
                                names.append(f"{elt.id}=var")
        return names
    except Exception:
        return None