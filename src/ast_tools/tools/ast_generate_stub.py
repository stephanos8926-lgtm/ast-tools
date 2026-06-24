"""ast_generate_stub tool — generate .pyi stub files or interface summaries."""

import ast
from pathlib import Path
from typing import Any

from ast_tools.utils import _annotation_to_str, _extract_all_names


def _tool_ast_generate_stub(args: dict[str, Any]) -> dict[str, Any]:
    """Generate a .pyi stub file or interface summary from a Python source file."""
    file_path = Path(args["file"]).resolve()
    include_private = args.get("include_private", False)
    include_docstrings = args.get("include_docstrings", True)
    output_format = args.get("output_format", "stub")
    
    if not file_path.exists():
        return {"error": f"File not found: {file_path}", "error_code": "NOT_FOUND", "tool": "ast_generate_stub"}
    
    source = file_path.read_text()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}", "error_code": "PARSE_ERROR", "tool": "ast_generate_stub"}
    
    # Extract __all__ if present
    all_names = _extract_all_names(tree)
    filtered_by_all = all_names is not None
    if filtered_by_all:
        all_set = set(all_names)
    else:
        all_set = set()
    
    lines = []
    
    def add_line(line: str = ""):
        lines.append(line)
    
    # Add module docstring if present and requested
    if include_docstrings:
        module_doc = ast.get_docstring(tree)
        if module_doc:
            add_line(f'"""{module_doc}"""')
            add_line("")
    
    # Collect imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    imports.append(f"import {alias.name} as {alias.asname}")
                else:
                    imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
            if node.level > 0:
                imports.append(f"from {'.' * node.level}{module} import {names}")
            else:
                imports.append(f"from {module} import {names}")
    
    # Filter imports if needed
    if filtered_by_all:
        # Keep all imports for stubs (they may be needed for type references)
        pass
    
    for imp in imports:
        add_line(imp)
    if imports:
        add_line("")
    
    # Process top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if not include_private and node.name.startswith("_"):
                continue
            if filtered_by_all and node.name not in all_set:
                continue
            _generate_class_stub(node, add_line, include_private, include_docstrings, filtered_by_all, all_set)
            add_line("")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_private and node.name.startswith("_"):
                continue
            if filtered_by_all and node.name not in all_set:
                continue
            _generate_function_stub(node, add_line, include_docstrings)
            add_line("")
        elif isinstance(node, ast.Assign):
            # Only include if it's a type annotation or __all__
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        continue
                    if not include_private and target.id.startswith("_"):
                        continue
                    if filtered_by_all and target.id not in all_set:
                        continue
                    if node.annotation:
                        add_line(f"{target.id}: {_annotation_to_str(node.annotation)}")
                    add_line("")
    
    stub_content = "\n".join(lines).rstrip() + "\n"
    
    if output_format == "interface":
        # For interface mode, just return the extracted symbols without full stub formatting
        return {
            "file": str(file_path),
            "format": "interface",
            "stub": stub_content,
        }
    
    return {
        "file": str(file_path),
        "format": "stub",
        "stub": stub_content,
    }


def _generate_class_stub(
    node: ast.ClassDef,
    add_line: callable,
    include_private: bool,
    include_docstrings: bool,
    filtered_by_all: bool,
    all_set: set,
    indent: int = 0,
):
    """Generate stub for a class definition."""
    prefix = "    " * indent
    bases = ", ".join(_annotation_to_str(b) for b in node.bases)
    if bases:
        add_line(f"{prefix}class {node.name}({bases}):")
    else:
        add_line(f"{prefix}class {node.name}:")
    
    if include_docstrings:
        doc = ast.get_docstring(node)
        if doc:
            add_line(f'{prefix}    """{doc}"""')
    
    has_body = False
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_private and item.name.startswith("_"):
                continue
            if filtered_by_all and item.name not in all_set:
                continue
            _generate_function_stub(item, lambda line: add_line(prefix + "    " + line), include_docstrings)
            has_body = True
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            # Type annotated attribute
            if not include_private and item.target.id.startswith("_"):
                continue
            if filtered_by_all and item.target.id not in all_set:
                continue
            ann = _annotation_to_str(item.annotation)
            add_line(f"{prefix}    {item.target.id}: {ann}")
            has_body = True
    
    if not has_body and not (include_docstrings and ast.get_docstring(node)):
        add_line(f"{prefix}    pass")


def _generate_function_stub(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    add_line: callable,
    include_docstrings: bool,
):
    """Generate stub for a function definition."""
    # Build signature
    args_str = _build_args(node.args)
    returns = ""
    if node.returns:
        returns = f" -> {_annotation_to_str(node.returns)}"
    
    keyword = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    add_line(f"{keyword} {node.name}({args_str}){returns}:")
    
    if include_docstrings:
        doc = ast.get_docstring(node)
        if doc:
            add_line(f'    """{doc}"""')
    add_line("    ...")


def _build_args(args: ast.arguments) -> str:
    """Build function argument string for stub."""
    parts = []
    
    # posonlyargs (Python 3.8+)
    if args.posonlyargs:
        for arg in args.posonlyargs:
            ann = f": {_annotation_to_str(arg.annotation)}" if arg.annotation else ""
            parts.append(f"{arg.arg}{ann}")
        parts.append("/")
    
    # args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        ann = f": {_annotation_to_str(arg.annotation)}" if arg.annotation else ""
        default_idx = i - defaults_offset
        if default_idx >= 0 and args.defaults[default_idx]:
            default = _get_default_value(args.defaults[default_idx])
            parts.append(f"{arg.arg}{ann}={default}")
        else:
            parts.append(f"{arg.arg}{ann}")
    
    # *args
    if args.vararg:
        ann = f": {_annotation_to_str(args.vararg.annotation)}" if args.vararg.annotation else ""
        parts.append(f"*{args.vararg.arg}{ann}")
    
    # kwonlyargs
    for i, arg in enumerate(args.kwonlyargs):
        ann = f": {_annotation_to_str(arg.annotation)}" if arg.annotation else ""
        if args.kw_defaults[i]:
            default = _get_default_value(args.kw_defaults[i])
            parts.append(f"{arg.arg}{ann}={default}")
        else:
            parts.append(f"{arg.arg}{ann}")
    
    # **kwargs
    if args.kwarg:
        ann = f": {_annotation_to_str(args.kwarg.annotation)}" if args.kwarg.annotation else ""
        parts.append(f"**{args.kwarg.arg}{ann}")
    
    return ", ".join(parts)


def _get_default_value(node: ast.AST) -> str:
    """Get string representation of default value."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return repr(node.value)
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.List):
        return "[]"
    if isinstance(node, ast.Dict):
        return "{}"
    if isinstance(node, ast.Tuple):
        return "()"
    return "..."