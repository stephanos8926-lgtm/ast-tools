"""ast_edit tool — surgical AST-based code modification using libcst."""

from typing import Any, Sequence

import libcst as cst
from libcst.metadata import PositionProvider

from ast_tools.utils.file_utils import validate_file_path


def _extract_method_python(
    tree: cst.Module,
    start_line: int,
    end_line: int,
    new_method_name: str,
    new_method_params: Sequence[str] | None = None,
    indentation: str = "    ",
    is_method: bool = False,
) -> cst.Module:
    """Extracts a block of code into a new Python method."""
    if new_method_params is None:
        new_method_params = []

    # If extracting as a method, ensure 'self' is the first parameter
    if is_method and "self" not in new_method_params:
        new_method_params = ["self"] + list(new_method_params)

    # Use a visitor to collect statement positions via correct libcst metadata API
    class PosCollector(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

        def __init__(self):
            self.positions: dict[int, tuple[int, int]] = {}

        def on_leave(self, original_node, updated_node):
            if isinstance(original_node, (cst.SimpleStatementLine, cst.BaseCompoundStatement)):
                try:
                    pos = self.get_metadata(cst.metadata.PositionProvider, original_node)
                    self.positions[id(original_node)] = (pos.start.line, pos.end.line)
                except Exception:
                    pass
            return updated_node

    wrapper = cst.MetadataWrapper(tree)
    collector = PosCollector()
    wrapper.visit(collector)

    extracted_statements: list[cst.BaseStatement] = []
    new_body: list[cst.BaseStatement] = []

    for stmt in wrapper.module.body:
        sid = id(stmt)
        if sid in collector.positions:
            stmt_start, stmt_end = collector.positions[sid]
            if stmt_start <= end_line and stmt_end >= start_line:
                extracted_statements.append(stmt)
            else:
                new_body.append(stmt)
        else:
            new_body.append(stmt)

    if not extracted_statements:
        raise ValueError("No statements found in the specified range for extraction.")

    # Calculate indent level — default to 1 (one level)
    indent_level = 1

    # Re-indent extracted statements for the new function body
    re_indented_statements: list[cst.BaseStatement] = []
    for stmt in extracted_statements:
        re_indented_statements.append(stmt)

    # Create new function definition
    new_function_def = cst.FunctionDef(
        name=cst.Name(new_method_name),
        params=cst.Parameters(
            params=[
                cst.Param(name=cst.Name(p))
                for p in new_method_params
            ]
        ),
        body=cst.IndentedBlock(body=re_indented_statements),
    )

    # Create a call to the new function to replace the extracted block
    call_args = [
        cst.Arg(value=cst.Name(p))
        for p in new_method_params
        if p != "self"  # Don't pass self explicitly in the call
    ]
    if is_method:
        call_func = cst.Attribute(value=cst.Name("self"), attr=cst.Name(new_method_name))
    else:
        call_func = cst.Name(new_method_name)
    new_call = cst.Expr(
        value=cst.Call(
            func=call_func,
            args=call_args,
        )
    )

    # Insert the new function and the call back into the module
    call_insert_index = -1

    # Find where to insert call: right before the first statement that was AFTER the extracted range
    for i, stmt in enumerate(new_body):
        sid = id(stmt)
        if sid in collector.positions:
            stmt_start, _ = collector.positions[sid]
            if stmt_start > end_line:
                call_insert_index = i
                break

    if call_insert_index >= 0:
        new_body.insert(call_insert_index, new_call)
    else:
        new_body.append(new_call) # If no statements after, append to end of existing body

    # Insert new function before the first class/func def, or at beginning
    func_insert_index = -1
    for i, stmt in enumerate(new_body):
        if isinstance(stmt, (cst.ClassDef, cst.FunctionDef)):
            func_insert_index = i
            break
    if func_insert_index >= 0:
        new_body.insert(func_insert_index, new_function_def)
    else:
        new_body.insert(0, new_function_def)

    return tree.with_changes(body=tuple(new_body))


def _build_transformer(operation: str, params: dict):
    """Build a libcst transformer for the given operation."""

    if operation == "rename_function":
        old_name = params["old_name"]
        new_name = params["new_name"]

        class RenameTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):
                if updated_node.name.value == old_name:
                    return updated_node.with_changes(name=cst.Name(new_name))
                return updated_node

            def leave_Call(self, original_node, updated_node):
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
            def leave_FunctionDef(self, original_node, updated_node):
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

            def leave_Module(self, original_node, updated_node):
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

            def leave_Module(self, original_node, updated_node):
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

    elif operation == "inline_variable":
        var_name = params["variable_name"]
        assign_line = params.get("assign_line")

        class InlineVarTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

            def __init__(self):
                self._assigned_expr = None
                self._assign_line = assign_line

            def leave_Assign(self, orig, upd):
                if self._assign_line is None:
                    return upd
                try:
                    pos = self.get_metadata(cst.metadata.PositionProvider, orig)
                    if pos.start.line == self._assign_line:
                        for target in upd.targets:
                            if isinstance(target.target, cst.Name) and target.target.value == var_name:
                                self._assigned_expr = upd.value
                                break
                except Exception:
                    pass
                return upd

            def leave_Name(self, orig, upd):
                if self._assigned_expr is None or upd.value != var_name:
                    return upd
                # Don't replace names at the assignment line (LHS target or RHS expression)
                try:
                    pos = self.get_metadata(cst.metadata.PositionProvider, orig)
                    if pos.start.line == self._assign_line:
                        return upd
                except Exception:
                    pass
                return cst.ensure_type(self._assigned_expr.deep_clone(), cst.BaseExpression)

            def on_leave(self, orig, upd):
                """Filter out the assignment statement from module body."""
                # Let specific leave_* methods fire first via super
                result = super().on_leave(orig, upd)
                if self._assigned_expr is not None and isinstance(orig, cst.SimpleStatementLine):
                    try:
                        pos = self.get_metadata(cst.metadata.PositionProvider, orig)
                        if pos.start.line == self._assign_line:
                            return cst.RemovalSentinel.REMOVE
                    except Exception:
                        pass
                return result

        return InlineVarTransformer()

    return None


def _tool_ast_edit(args: dict[str, Any]) -> dict[str, Any]:
    """Perform surgical AST-based code modification."""
    file_path = args["file"]
    project_path_arg = args.get("project_path")
    operation = args["operation"]
    params = args.get("params", {})
    dry_run = args.get("dry_run", False)

    # Validate file path with security checks
    try:
        file_path = validate_file_path(
            file_path,
            project_path=project_path_arg,
            allow_nonexistent=False,
        )
    except ValueError as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "exists" in error_str.lower():
            error_code = "NOT_FOUND"
        elif "traversal" in error_str.lower() or "outside" in error_str.lower():
            error_code = "PATH_TRAVERSAL"
        else:
            error_code = "INVALID_PATH"
        return {
            "error": str(e),
            "error_code": error_code,
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

    # Handle extract_method specially — direct tree manipulation
    if operation == "extract_method":
        start_line = params.get("start_line", 1)
        end_line = params.get("end_line", start_line)
        new_method_name = params.get("new_method_name", "extracted")
        new_method_params = params.get("new_method_params", [])
        is_method = params.get("is_method", False)
        try:
            new_tree = _extract_method_python(
                tree, start_line, end_line, new_method_name, new_method_params,
                is_method=is_method,
            )
        except ValueError as e:
            return {"error": str(e), "error_code": "NO_EXTRACTABLE", "tool": "ast_edit"}
        new_source = new_tree.code
        if dry_run:
            return {"file": str(file_path), "operation": operation, "modified_source": new_source}
        file_path.write_text(new_source)
        return {"file": str(file_path), "operation": operation, "status": "written"}

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
