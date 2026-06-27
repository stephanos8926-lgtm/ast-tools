"""ast_edit tool — surgical AST-based code modification using libcst."""

from pathlib import Path
from typing import Any

import libcst as cst


def _build_transformer(operation: str, params: dict):
    """Build a libcst transformer for the given operation."""

    if operation == "rename_function":
        old_name = params["old_name"]
        new_name = params["new_name"]

        class RenameTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):  # noqa: ARG002
                if updated_node.name.value == old_name:
                    return updated_node.with_changes(name=cst.Name(new_name))
                return updated_node

            def leave_Call(self, original_node, updated_node):  # noqa: ARG002
                if isinstance(updated_node.func, cst.Name) and updated_node.func.value == old_name:
                    return updated_node.with_changes(func=cst.Name(new_name))
                return updated_node

        return RenameTransformer()

    elif operation == "add_parameter":
        func_name = params["function_name"]
        param_name = params["parameter_name"]
        default_value = params.get("default_value")

        class AddParamTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):
                if updated_node.name.value == func_name:
                    default = cst.parse_expression(default_value) if default_value else None
                    new_param = cst.Param(
                        name=cst.Name(param_name),
                        default=default,
                    )
                    params_list = list(updated_node.params.params)
                    params_list.append(new_param)
                    return updated_node.with_changes(
                        params=updated_node.params.with_changes(params=params_list)
                    )
                return updated_node

        return AddParamTransformer()

    elif operation == "change_signature":
        func_name = params["function_name"]
        new_params = params["parameters"]  # list of {"name": str, "default": str|None}

        class ChangeSigTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):  # noqa: ARG002
                if updated_node.name.value == func_name:
                    new_params_list = []
                    for p in new_params:
                        default = cst.parse_expression(p["default"]) if p.get("default") else None
                        new_params_list.append(cst.Param(name=cst.Name(p["name"]), default=default))
                    return updated_node.with_changes(
                        params=updated_node.params.with_changes(params=new_params_list)
                    )
                return updated_node

        return ChangeSigTransformer()

    elif operation == "replace_node":
        # Replace a specific AST node identified by line range
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        replacement = params["replacement"]

        class ReplaceTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

            def __init__(self):
                self._replacement_nodes = list(cst.parse_module(replacement).body)

            def leave_Module(self, original_node, updated_node):  # noqa: ARG002
                if start_line is None:
                    return updated_node
                new_body = []
                for stmt in updated_node.body:
                    try:
                        pos = self.get_metadata(cst.metadata.PositionProvider, stmt)
                        stmt_line = pos.start.line
                    except (KeyError, AttributeError):
                        stmt_line = 0
                    if start_line <= stmt_line <= end_line:
                        if not hasattr(self, "_replaced"):
                            new_body.extend(self._replacement_nodes)
                            self._replaced = True
                    else:
                        new_body.append(stmt)
                return updated_node.with_changes(body=new_body)

        return ReplaceTransformer()

    elif operation == "remove_node":
        start_line = params.get("start_line")
        end_line = params.get("end_line")

        class RemoveTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

            def leave_Module(self, original_node, updated_node):  # noqa: ARG002
                if start_line is None:
                    return updated_node
                new_body = []
                for stmt in updated_node.body:
                    try:
                        pos = self.get_metadata(cst.metadata.PositionProvider, stmt)
                        stmt_line = pos.start.line
                    except (KeyError, AttributeError):
                        stmt_line = 0
                    if start_line <= stmt_line <= end_line:
                        continue
                    new_body.append(stmt)
                return updated_node.with_changes(body=new_body)

        return RemoveTransformer()

    return None


def _tool_ast_edit(args: dict[str, Any]) -> dict[str, Any]:
    """Perform surgical AST-based code modification."""
    file_path = Path(args["file"]).resolve()
    operation = args["operation"]
    params = args.get("params", {})
    dry_run = args.get("dry_run", False)

    if not file_path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_code": "NOT_FOUND",
            "tool": "ast_edit",
        }

    source = file_path.read_text()
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        return {
            "error": f"Syntax error in {file_path}: {e}",
            "error_code": "PARSE_ERROR",
            "tool": "ast_edit",
        }

    transformer = _build_transformer(operation, params)
    if transformer is None:
        return {
            "error": f"Unknown operation: {operation}",
            "error_code": "INVALID_INPUT",
            "tool": "ast_edit",
        }

    wrapper = cst.MetadataWrapper(tree)
    try:
        new_tree = wrapper.visit(transformer)
    except Exception as e:
        return {
            "error": f"Transformation failed: {e}",
            "error_code": "INTERNAL",
            "tool": "ast_edit",
        }

    new_source = new_tree.code

    if dry_run:
        return {"file": str(file_path), "operation": operation, "modified_source": new_source}

    file_path.write_text(new_source)
    return {"file": str(file_path), "operation": operation, "status": "written"}
