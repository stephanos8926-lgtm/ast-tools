#!/usr/bin/env python3
"""Tree-sitter based editing for TypeScript/TSX.

Since there's no libcst equivalent for TypeScript, this module provides
string-based transformations guided by tree-sitter AST analysis.

Supported Operations:
- rename_identifier: Rename a variable/function/class
- add_parameter: Add parameter to function
- replace_node: Replace entire node
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def ts_parse_ts(source: str, lang: str = "typescript"):
    """Parse TypeScript/TSX source code."""
    from ts_backend import ts_parse
    return ts_parse(source, lang)


def find_node_by_name(tree, name: str, node_types=None):
    """Find nodes with a specific identifier name."""
    matches = []
    
    def _walk(node):
        if node.type == 'identifier' and node.text.decode('utf-8') == name:
            parent = node.parent
            if parent and (node_types is None or parent.type in node_types):
                matches.append((parent, parent.type))
        for child in node.children:
            _walk(child)
    
    if tree and tree.root_node:
        _walk(tree.root_node)
    
    return matches


def find_function_node(tree, func_name: str):
    """Find function declaration by name."""
    node_types = ['function_declaration', 'arrow_function', 'method_definition']
    return find_node_by_name(tree, func_name, node_types)


def find_class_node(tree, class_name: str):
    """Find class declaration by name."""
    return find_node_by_name(tree, class_name, ['class_declaration'])


def get_node_range(node):
    """Get byte range for a node."""
    return (node.start_byte, node.end_byte)


def calculate_line_col(source: str, byte_offset: int):
    """Calculate line and column from byte offset."""
    text = source.decode('utf-8') if isinstance(source, bytes) else source
    lines = text[:byte_offset].split('\n')
    return len(lines), len(lines[-1]) + 1 if lines else 1


def _rename_identifier(source: str, old_name: str, new_name: str, lang: str) -> dict:
    """Rename an identifier."""
    tree = ts_parse_ts(source, lang)
    if not tree:
        return {'error': 'Failed to parse source'}
    
    matches = find_node_by_name(tree, old_name)
    if not matches:
        return {'error': f"Identifier '{old_name}' not found"}
    
    # Rename from last to first to preserve byte offsets
    modified = source
    matches.sort(key=lambda x: x[0].start_byte, reverse=True)
    
    for node, _ in matches:
        start, end = get_node_range(node)
        # Extract current text and replace identifier
        before = modified[:start]
        target_text = modified[start:end]
        after = modified[end:]
        # Replace the identifier within this node
        new_target = target_text.replace(old_name, new_name, 1)
        modified = before + new_target + after
    
    # Validate
    new_tree = ts_parse_ts(modified, lang)
    if not new_tree:
        return {'error': 'Modified code does not parse'}
    
    return {
        'success': True,
        'changes': len(matches),
        'modified_source': modified
    }


def _add_parameter(source: str, func_name: str, param_name: str, 
                   default_value: str = None, lang: str = "typescript") -> dict:
    """Add a parameter to a function."""
    tree = ts_parse_ts(source, lang)
    if not tree:
        return {'error': 'Failed to parse source'}
    
    func_matches = find_function_node(tree, func_name)
    if not func_matches:
        return {'error': f"Function '{func_name}' not found"}
    
    func_node, _ = func_matches[0]
    
    # Find formal_parameters node
    params_node = None
    for child in func_node.children:
        if child.type == 'formal_parameters':
            params_node = child
            break
    
    if not params_node:
        return {'error': 'Could not find parameters'}
    
    # Find closing paren position
    close_paren = None
    for child in params_node.children:
        if child.type == ')':
            close_paren = child.start_byte
            break
    
    if close_paren is None:
        func_text = source[func_node.start_byte:func_node.end_byte]
        if ')' in func_text:
            close_paren = func_node.start_byte + func_text.rfind(')')
        else:
            return {'error': 'Could not find closing paren'}
    
    # Build new param
    new_param = f"{param_name} = {default_value}" if default_value else param_name
    
    # Check if params exist
    has_params = params_node.start_byte < close_paren - 1
    insert = f", {new_param}" if has_params else new_param
    
    # Insert
    modified = source[:close_paren] + insert + source[close_paren:]
    
    # Validate
    if not ts_parse_ts(modified, lang):
        return {'error': 'Modified code does not parse'}
    
    return {
        'success': True,
        'function': func_name,
        'added': new_param,
        'modified_source': modified
    }


def _replace_node(source: str, query: str, replacement: str, lang: str) -> dict:
    """Replace a node matched by tree-sitter query."""
    try:
        ts_lib = __import__('tree_sitter')
        from ts_backend import _get_language
        language = _get_language(lang)
    except Exception as e:
        return {'error': f'Failed to load parser: {e}'}
    
    tree = ts_parse_ts(source, lang)
    if not tree:
        return {'error': 'Failed to parse'}
    
    try:
        query_obj = ts_lib.Query(language, query)
    except Exception as e:
        return {'error': f'Invalid query: {e}'}
    
    cursor = ts_lib.QueryCursor(query_obj)
    matches = list(cursor.captures(tree.root_node))
    
    nodes = []
    for _, node_list in matches:
        nodes.extend(node_list)
    
    if not nodes:
        return {'error': f'No matches for: {query}'}
    
    target = nodes[0]
    start, end = get_node_range(target)
    
    modified = source[:start] + replacement + source[end:]
    
    if not ts_parse_ts(modified, lang):
        return {'error': 'Modified code does not parse'}
    
    return {
        'success': True,
        'replaced': True,
        'modified_source': modified
    }


def ts_edit(file: str, operation: str, params: dict[str, Any], 
            lang: str = "typescript", dry_run: bool = True) -> dict[str, Any]:
    """Edit TypeScript/TSX code.
    
    Args:
        file: File path
        operation: 'rename_identifier', 'add_parameter', or 'replace_node'
        params: Operation parameters
        lang: Language (typescript, tsx, javascript, jsx)
        dry_run: If True, don't write to file
    
    Returns:
        Result dict
    """
    file_path = Path(file)
    if not file_path.exists():
        return {'error': f'File not found: {file}'}
    
    try:
        source = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {'error': f'Read failed: {e}'}
    
    # Dispatch
    if operation == 'rename_identifier':
        result = _rename_identifier(
            source, 
            params.get('old_name'), 
            params.get('new_name'), 
            lang
        )
    elif operation == 'add_parameter':
        result = _add_parameter(
            source,
            params.get('function'),
            params.get('param_name'),
            params.get('default_value'),
            lang
        )
    elif operation == 'replace_node':
        result = _replace_node(
            source,
            params.get('query'),
            params.get('replacement'),
            lang
        )
    else:
        return {'error': f'Unknown operation: {operation}'}
    
    if 'error' not in result:
        result['file'] = file
        result['dry_run'] = dry_run
        
        if not dry_run:
            try:
                file_path.write_text(result['modified_source'], encoding='utf-8')
                result['written'] = True
            except Exception as e:
                return {'error': f'Write failed: {e}'}
    
    return result


def _tool_ts_edit(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for ts_edit."""
    return ts_edit(
        file=args.get('file'),
        operation=args.get('operation'),
        params=args.get('params', {}),
        lang=args.get('lang', 'typescript'),
        dry_run=args.get('dry_run', True)
    )