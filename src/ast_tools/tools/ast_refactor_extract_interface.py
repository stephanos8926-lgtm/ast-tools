#!/usr/bin/env python3
"""Extract interface from a class using libcst."""

from pathlib import Path
from typing import Any

import libcst as cst


def _tool_ast_refactor_extract_interface(args: dict[str, Any]) -> dict[str, Any]:
    """Extract a public interface from a class and create an ABC or Protocol."""
    file_path = Path(args["file"]).resolve()
    class_name = args["class_name"]
    interface_name = args.get("interface_name", f"I{class_name}")
    interface_type = args.get("interface_type", "abc")
    output_file = args.get("output_file")
    include_properties = args.get("include_properties", True)
    include_classmethods = args.get("include_classmethods", True)
    include_staticmethods = args.get("include_staticmethods", True)
    dry_run = args.get("dry_run", False)

    if not file_path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_code": "NOT_FOUND",
            "tool": "ast_refactor_extract_interface",
        }

    source = file_path.read_text()
    try:
        tree = cst.parse_module(source)
    except Exception as e:
        return {
            "error": f"Parse error: {e}",
            "error_code": "PARSE_ERROR",
            "tool": "ast_refactor_extract_interface",
        }

    # Find the target class
    target_class = None
    for node in tree.body:
        if isinstance(node, cst.ClassDef) and node.name.value == class_name:
            target_class = node
            break

    if not target_class:
        return {
            "error": f"Class '{class_name}' not found in {file_path}",
            "error_code": "NOT_FOUND",
            "tool": "ast_refactor_extract_interface",
        }

    # Extract public methods
    interface_methods = []
    for item in target_class.body:
        if isinstance(item, cst.FunctionDef):
            # Skip private methods
            if item.name.value.startswith("_"):
                continue
            # Check decorators
            is_property = False
            is_classmethod = False
            is_staticmethod = False
            for dec in item.decorators:
                dec_name = ""
                if isinstance(dec.decorator, cst.Name):
                    dec_name = dec.decorator.value
                elif isinstance(dec.decorator, cst.Attribute):
                    dec_name = dec.decorator.attr.value
                if dec_name == "property":
                    is_property = True
                elif dec_name == "classmethod":
                    is_classmethod = True
                elif dec_name == "staticmethod":
                    is_staticmethod = True

            # Apply filters
            if is_property and not include_properties:
                continue
            if is_classmethod and not include_classmethods:
                continue
            if is_staticmethod and not include_staticmethods:
                continue

            # Create abstract method signature
            method_stub = _create_method_stub(
                item, is_property, is_classmethod, is_staticmethod, interface_type
            )
            interface_methods.append(method_stub)

    if not interface_methods:
        return {
            "error": f"No public methods found in class '{class_name}'",
            "error_code": "NO_METHODS",
            "tool": "ast_refactor_extract_interface",
        }

    # Generate interface file content
    if interface_type == "abc":
        interface_code = _generate_abc_interface(interface_name, target_class, interface_methods)
    else:
        interface_code = _generate_protocol_interface(
            interface_name, target_class, interface_methods
        )

    # Determine output file path
    if not output_file:
        output_file = str(file_path.parent / f"{interface_name.lower()}.py")

    result = {
        "source_file": str(file_path),
        "class_name": class_name,
        "interface_name": interface_name,
        "interface_type": interface_type,
        "interface_file": output_file,
        "interface_content": interface_code,
        "methods_extracted": len(interface_methods),
    }

    if not dry_run:
        # Write interface file
        Path(output_file).write_text(interface_code)
        result["interface_written"] = True

        # Modify source file to add interface inheritance
        modified_source = _add_interface_inheritance(
            source, class_name, interface_name, file_path.parent
        )
        Path(file_path).write_text(modified_source)
        result["source_modified"] = True

    return result


def _create_method_stub(
    method: cst.FunctionDef,
    is_property: bool,
    is_classmethod: bool,
    is_staticmethod: bool,
    interface_type: str,
) -> cst.FunctionDef:
    """Create an abstract method stub from a method definition."""
    # Build decorator list
    decorators = []
    if interface_type == "abc":
        if is_property:
            decorators.append(cst.Decorator(decorator=cst.Name("property")))
        elif is_classmethod:
            decorators.append(cst.Decorator(decorator=cst.Name("classmethod")))
            decorators.append(cst.Decorator(decorator=cst.Name("abstractmethod")))
        elif is_staticmethod:
            decorators.append(cst.Decorator(decorator=cst.Name("staticmethod")))
            decorators.append(cst.Decorator(decorator=cst.Name("abstractmethod")))
        else:
            decorators.append(cst.Decorator(decorator=cst.Name("abstractmethod")))
    else:
        # Protocol - no decorators needed, just the signature
        if is_property:
            decorators.append(cst.Decorator(decorator=cst.Name("property")))
        elif is_classmethod:
            decorators.append(cst.Decorator(decorator=cst.Name("classmethod")))
        elif is_staticmethod:
            decorators.append(cst.Decorator(decorator=cst.Name("staticmethod")))

    # Create ellipsis body
    body = cst.SimpleStatementSuite(body=[cst.Expr(value=cst.Ellipsis())])

    return cst.FunctionDef(
        name=method.name,
        params=method.params,
        body=body,
        decorators=decorators,
        returns=method.returns,
    )


def _generate_abc_interface(
    interface_name: str, target_class: cst.ClassDef, methods: list[cst.FunctionDef]
) -> str:
    """Generate an Abstract Base Class interface."""
    lines = [
        '"""Auto-generated interface for backward compatibility."""',
        "from abc import ABC, abstractmethod",
        "",
        "",
        f"class {interface_name}(ABC):",
    ]

    # Add docstring if present
    docstring = target_class.docstring
    if docstring:
        lines.append(f'    """{docstring.value}"""')

    if not methods:
        lines.append("    pass")
    else:
        for method in methods:
            method_code = cst.Module(body=[method]).code
            # Indent method body
            for line in method_code.split("\n"):
                lines.append(f"    {line}")

    lines.append("")
    return "\n".join(lines)


def _generate_protocol_interface(
    interface_name: str, target_class: cst.ClassDef, methods: list[cst.FunctionDef]
) -> str:
    """Generate a typing.Protocol interface."""
    lines = [
        '"""Auto-generated protocol interface for backward compatibility."""',
        "from typing import Protocol",
        "",
        "",
        f"class {interface_name}(Protocol):",
    ]

    docstring = target_class.docstring
    if docstring:
        lines.append(f'    """{docstring.value}"""')

    if not methods:
        lines.append("    pass")
    else:
        for method in methods:
            method_code = cst.Module(body=[method]).code
            for line in method_code.split("\n"):
                lines.append(f"    {line}")

    lines.append("")
    return "\n".join(lines)


def _add_interface_inheritance(
    source: str, class_name: str, interface_name: str, module_dir: Path
) -> str:
    """Add interface to class inheritance list."""
    tree = cst.parse_module(source)

    class InterfaceAdder(cst.CSTTransformer):
        def leave_ClassDef(
            self, original_node: cst.ClassDef, updated_node: cst.ClassDef
        ) -> cst.ClassDef:
            if original_node.name.value == class_name:
                # Create base class reference
                new_base = cst.Arg(value=cst.Name(interface_name))
                if updated_node.bases:
                    new_bases = [*list(updated_node.bases), new_base]
                else:
                    new_bases = [new_base]
                return updated_node.with_changes(bases=new_bases)
            return updated_node

    modified_tree = tree.visit(InterfaceAdder())
    return modified_tree.code
