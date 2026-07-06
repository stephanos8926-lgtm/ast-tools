"""MCP tool: Class hierarchy analysis — AST-based inheritance analysis.

Provides C3 linearization (MRO), method categorization, interface detection,
and subclass discovery, all purely from static AST analysis without runtime
imports.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from ast_tools.utils.file_utils import find_python_files

# ── helpers ──────────────────────────────────────────────────────────────


def _get_base_names(class_node: ast.ClassDef) -> list[str]:
    """Extract base-class *names* from a ClassDef AST node.

    Only handles simple ``Name`` nodes (``class Foo(Bar):``).  Call-based
    bases (``class Foo(Bar()):``) or attribute-style (``class Foo(module.Bar):``)
    are returned as their AST dump for transparency.
    """
    names: list[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(f"{_attr_chain(base)}")
        else:
            names.append(ast.dump(base))
    return names


def _attr_chain(node: ast.AST) -> str:
    """Rebuild a dotted name from ``ast.Attribute`` / ``ast.Name`` nodes."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_attr_chain(node.value)}.{node.attr}"
    return ast.dump(node)


def _find_methods(class_node: ast.ClassDef) -> list[str]:
    """Return names of all methods (including async) defined in a class body."""
    methods: list[str] = []
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(child.name)
    return methods


def _find_decorator_names(class_node: ast.ClassDef) -> list[str]:
    """Return the names of decorators on a class node."""
    names: list[str] = []
    for dec in class_node.decorator_list:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.append(_attr_chain(dec))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                names.append(_attr_chain(dec.func))
        else:
            names.append(ast.dump(dec))
    return names


# ── C3 linearisation (MRO) ──────────────────────────────────────────────


def _compute_mro(
    class_name: str,
    all_classes: dict[str, ast.ClassDef],
    _memo: dict[str, list[str]] | None = None,
) -> list[str]:
    """Compute the C3 linearization (MRO) for *class_name*.

    Returns the MRO as a list of class names (``[class_name, ..., 'object']``).

    If the C3 merge fails (inconsistent hierarchy) the function returns the
    best-effort MRO obtained up to the point of failure and sets
    ``_merge_error`` on the returned list so callers can detect the problem.
    """
    if _memo is None:
        _memo = {}

    if class_name in _memo:
        return list(_memo[class_name])

    node = all_classes.get(class_name)
    if node is None:
        # Unknown class — trivial MRO
        result = [class_name]
        _memo[class_name] = result
        return result

    base_names = _get_base_names(node)
    if not base_names:
        result = [class_name, "object"]
        _memo[class_name] = result
        return result

    # Recursively compute parent MROs
    parent_mros: list[list[str]] = []
    for bn in base_names:
        parent_mros.append(_compute_mro(bn, all_classes, _memo))

    # C3 merge
    result = [class_name]
    # merge: [list(bases)] + parent_mros + [list(object)]
    merge_lists: list[list[str]] = [list(base_names), *parent_mros, ["object"]]

    while any(merge_lists):
        # Find a head that is not in the tail of any other list
        candidate: str | None = None
        for lst in merge_lists:
            if not lst:
                continue
            head = lst[0]
            # Check if head appears in the *tail* of any list
            in_tail = False
            for other in merge_lists:
                if head in other[1:]:
                    in_tail = True
                    break
            if not in_tail:
                candidate = head
                break

        if candidate is None:
            # Merge conflict — we still return what we have
            remaining = {lst[0] for lst in merge_lists if lst}
            result.append(f"<MERGE_CONFLICT: {','.join(sorted(remaining))}>")
            # Mark the result as having an error by appending a sentinel
            # that consumers can check
            _memo[class_name] = result
            # Attach an attribute so callers can detect the conflict
            result.append("<MRO_ERROR>")
            return result

        result.append(candidate)
        for lst in merge_lists:
            if lst and lst[0] == candidate:
                lst.pop(0)

    _memo[class_name] = result
    return result


# ── class definition extraction ──────────────────────────────────────────


def _extract_class_definitions(file_path: str) -> dict[str, ast.ClassDef]:
    """Parse *file_path* and return ``{class_name: ClassDef}``.

    Only top-level classes are returned (nested classes are ignored for
    the purposes of hierarchy analysis).
    """
    source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=file_path)
    classes: dict[str, ast.ClassDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Only collect top-level classes (direct children of the module)
            # Skip nested classes
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef) and parent != node:
                    # Check if node is inside parent by seeing if parent
                    # contains node in its body tree
                    for child in ast.walk(parent):
                        if child is node:
                            break
                    else:
                        continue
                    break
            else:
                classes[node.name] = node
    # Simpler: just walk top-level statements
    classes = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes[node.name] = node
    return classes


# ── method categorisation ────────────────────────────────────────────────


def _get_method_categories(
    class_name: str,
    all_classes: dict[str, ast.ClassDef],
) -> dict[str, Any]:
    """Categorise methods of *class_name* into *own*, *inherited*, *overrides*.

    Returns a dict with keys:
        own         — methods defined directly on this class
        inherited   — methods defined only in ancestors (name + source)
        overrides   — methods defined here that also appear in an ancestor
    """
    mro = _compute_mro(class_name, all_classes)
    class_node = all_classes.get(class_name)
    if class_node is None:
        return {"own": [], "inherited": [], "overrides": []}

    own_methods = set(_find_methods(class_node))
    inherited_map: dict[str, str] = {}  # method_name -> from_class
    overrides: list[dict[str, str]] = []

    # Walk MRO after the class itself (skip index 0 which is the class itself)
    for ancestor in mro[1:]:
        if ancestor == "object":
            break
        anc_node = all_classes.get(ancestor)
        if anc_node is None:
            continue
        for method in _find_methods(anc_node):
            if method in own_methods:
                overrides.append({"name": method, "from": ancestor})
            elif method not in inherited_map:
                inherited_map[method] = ancestor

    # Remove overridden methods from own list? No — own methods that
    # happen to also exist in a base are overrides.  Keep them as
    # "own" *and* note them as overrides.
    return {
        "own": sorted(own_methods),
        "inherited": sorted(
            [{"name": n, "from": s} for n, s in inherited_map.items()],
            key=lambda x: x["name"],
        ),
        "overrides": sorted(overrides, key=lambda x: x["name"]),
    }


# ── interface detection ──────────────────────────────────────────────────


def _detect_interface(
    class_node: ast.ClassDef,
    bases: list[str],
) -> bool:
    """Return ``True`` if *class_node* looks like an interface / ABC / Protocol.

    Heuristics:
    - Inherits from ``ABC``, ``ABCMeta``, or ``Protocol``
    - Has an ``@abstractmethod``-decorated method
    """
    interface_markers: set[str] = {"ABC", "ABCMeta", "Protocol"}
    if any(b in interface_markers for b in bases):
        return True

    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in child.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                    return True
                if isinstance(dec, ast.Attribute) and _attr_chain(dec) in (
                    "abc.abstractmethod",
                    "abstractmethod",
                ):
                    return True
    return False


def _has_abstract_methods(class_node: ast.ClassDef) -> bool:
    """Return ``True`` if the class has any ``@abstractmethod``-decorated methods."""
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in child.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                    return True
                if isinstance(dec, ast.Attribute) and _attr_chain(dec) in (
                    "abc.abstractmethod",
                    "abstractmethod",
                ):
                    return True
    return False


def _is_final(class_node: ast.ClassDef) -> bool:
    """Return ``True`` if the class is decorated with ``@final``."""
    for dec in class_node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "final":
            return True
        if isinstance(dec, ast.Attribute) and _attr_chain(dec).endswith("final"):
            return True
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == "final":
                return True
            if isinstance(func, ast.Attribute) and _attr_chain(func).endswith("final"):
                return True
    return False


# ── subclass discovery ───────────────────────────────────────────────────


def _find_subclasses(
    class_name: str,
    workspace: str,
    all_classes: dict[str, ast.ClassDef] | None = None,
) -> list[str]:
    """Scan *workspace* for classes that list *class_name* as a base.

    If *all_classes* is provided (from a prior parse), use it as a cache.

    Returns a sorted list of subclass names.
    """
    subclasses: list[str] = []

    if all_classes is not None:
        for name, node in all_classes.items():
            bases = _get_base_names(node)
            if class_name in bases:
                subclasses.append(name)
        return sorted(subclasses)

    # Scan workspace files
    for py_file in find_python_files(workspace):
        try:
            classes = _extract_class_definitions(str(py_file))
            for name, node in classes.items():
                bases = _get_base_names(node)
                if class_name in bases:
                    subclasses.append(name)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

    return sorted(set(subclasses))


# ── target resolution ────────────────────────────────────────────────────


def _resolve_target(
    target: str,
    file_path: str | None,
    workspace: str | None,
) -> tuple[str | None, str | None, dict[str, ast.ClassDef] | None]:
    """Resolve *target* to ``(class_name, file_path, all_classes_in_file_or_workspace)``.

    *target* can be:
        - ``ClassName``  → search workspace if no *file_path* given
        - ``file.py:ClassName``  → parse *file.py*, return that class
    """
    class_name: str = target
    resolved_file: str | None = file_path
    all_classes: dict[str, ast.ClassDef] | None = None

    # Check for "file:ClassName" format
    if ":" in target:
        parts = target.rsplit(":", 1)
        resolved_file = parts[0]
        class_name = parts[1]

    # If we have a file, parse it
    if resolved_file:
        path = Path(resolved_file)
        if not path.is_absolute():
            if workspace:
                path = Path(workspace) / path
            path = path.resolve()
        if not path.exists():
            return None, None, None
        try:
            all_classes = _extract_class_definitions(str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            return None, None, None
        if class_name not in all_classes:
            return None, str(path), all_classes
        return class_name, str(path), all_classes

    # No file given — search workspace
    if workspace is None:
        return None, None, None

    all_classes = {}
    for py_file in find_python_files(workspace):
        try:
            cls_dict = _extract_class_definitions(str(py_file))
            if class_name in cls_dict:
                all_classes.update(cls_dict)
                return class_name, str(py_file), cls_dict
            all_classes.update(cls_dict)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

    return None, None, all_classes


# ── metrics ──────────────────────────────────────────────────────────────


def _compute_metrics(
    class_name: str,
    class_node: ast.ClassDef,
    all_classes: dict[str, ast.ClassDef],
    mro: list[str],
    method_categories: dict[str, Any],
    is_interface: bool,
    is_class_final: bool,
) -> dict[str, Any]:
    """Compute structural metrics for a class."""
    own_methods = method_categories.get("own", [])
    overrides = method_categories.get("overrides", [])

    # Depth = number of ancestor levels (len(mro) - 1 for self)
    depth = max(0, len(mro) - 1)

    base_names = _get_base_names(class_node)
    has_concrete = (
        not is_interface
        and not _has_abstract_methods(class_node)
        and len(own_methods) > 0
    )

    return {
        "depth": depth,
        "num_methods": len(own_methods),
        "num_overrides": len(overrides),
        "is_abstract": _has_abstract_methods(class_node),
        "is_final": is_class_final,
        "is_interface": is_interface,
        "has_concrete_methods": has_concrete,
        "num_bases": len(base_names),
    }


# ── main tool entry point ────────────────────────────────────────────────


def _tool_class_hierarchy(params: dict[str, Any]) -> dict[str, Any]:
    """Analyze a class's inheritance hierarchy (AST-based, no runtime imports).

    **Input:**

    .. code-block:: python

        {
            "target": str,        # Required — class name, optionally "file.py:ClassName"
            "file": str,          # Optional — file containing the class
            "workspace": str,     # Optional — project root (auto-detect from file)
            "max_depth": int,     # Default 10
        }

    **Output:**

    .. code-block:: python

        {
            "class": "ClassName",
            "file": "/abs/path/to/file.py",
            "bases": ["Base1", "Base2"],
            "mro": ["ClassName", "Base1", ..., "object"],
            "subclasses": ["SubClass1"],
            "interfaces": [...],
            "methods": {
                "own": ["method_a"],
                "inherited": [{"name": "method_c", "from": "Base1"}],
                "overrides": [{"name": "method_d", "from": "Base1"}],
            },
            "metrics": {
                "depth": 2,
                "num_methods": 5,
                "num_overrides": 1,
                "is_abstract": False,
                "is_final": False,
                "is_interface": False,
                "has_concrete_methods": True,
            },
        }
    """
    target = params.get("target", "")
    if not target:
        return {"error": "target is required", "error_code": "MISSING_PARAM"}

    file_path = params.get("file")
    workspace = params.get("workspace")

    # Auto-detect workspace from file if not given
    if not workspace and file_path:
        fp = Path(file_path)
        resolved = fp.resolve() if not fp.is_absolute() else fp
        for parent in reversed(resolved.parents):
            if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
                workspace = str(parent)
                break
        if not workspace:
            workspace = str(resolved.parent)

    int(params.get("max_depth", 10))

    # ── Resolve target ──────────────────────────────────────────────
    class_name, resolved_file, all_classes = _resolve_target(
        target, file_path, workspace
    )

    if class_name is None and all_classes is None:
        return {
            "error": f"Could not find class '{target}'",
            "error_code": "CLASS_NOT_FOUND",
        }

    if class_name is None and resolved_file:
        return {
            "error": f"Class '{target.split(':')[-1] if ':' in target else target}' "
            f"not found in {resolved_file}",
            "error_code": "CLASS_NOT_FOUND_IN_FILE",
            "available_classes": sorted(all_classes.keys()) if all_classes else [],
        }

    if class_name is None:
        return {
            "error": f"Class '{target}' not found in workspace",
            "error_code": "CLASS_NOT_FOUND",
        }

    class_node = all_classes.get(class_name) if all_classes else None
    if class_node is None:
        # Should not happen if _resolve_target worked correctly, but guard
        return {
            "error": f"Internal: class node for '{class_name}' not in parsed classes",
            "error_code": "INTERNAL_ERROR",
        }

    # ── Collect all classes from workspace if we only parsed one file ─
    # We need the full workspace's class map for MRO and subclass detection
    if all_classes and workspace and resolved_file:
        # all_classes already has at least the file-level classes
        pass

    # If we only parsed one file but need subclass detection across workspace
    workspace_classes: dict[str, ast.ClassDef] = {}
    if all_classes:
        workspace_classes.update(all_classes)

    if workspace:
        # Merge any additional classes from other workspace files
        # (don't re-parse, but do expand if we haven't already scanned)
        # For now, only use what we have — subclass detection will scan
        additional_classes: dict[str, ast.ClassDef] = {}
        for py_file in find_python_files(workspace):
            if str(py_file) == resolved_file:
                continue  # already parsed
            try:
                extra = _extract_class_definitions(str(py_file))
                additional_classes.update(extra)
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue
        workspace_classes.update(additional_classes)

    # ── Build full workspace-class map (if workspace given) ──────────
    # For MRO we need ancestors that may live in other files
    full_classes: dict[str, ast.ClassDef] = {}
    full_classes.update(workspace_classes)

    # ── Compute MRO ─────────────────────────────────────────────────
    mro = _compute_mro(class_name, full_classes)

    # Check for merge error sentinel
    has_mro_error = "<MRO_ERROR>" in mro
    if has_mro_error:
        mro = [c for c in mro if c != "<MRO_ERROR>"]

    # ── Bases ────────────────────────────────────────────────────────
    bases = _get_base_names(class_node)

    # ── Methods ──────────────────────────────────────────────────────
    method_categories = _get_method_categories(class_name, full_classes)

    # ── Interface detection ──────────────────────────────────────────
    is_interface = _detect_interface(class_node, bases)

    # ── Final check ──────────────────────────────────────────────────
    is_class_final = _is_final(class_node)

    # ── Metrics ──────────────────────────────────────────────────────
    metrics = _compute_metrics(
        class_name,
        class_node,
        full_classes,
        mro,
        method_categories,
        is_interface,
        is_class_final,
    )

    # ── Subclasses ───────────────────────────────────────────────────
    subclasses = _find_subclasses(class_name, workspace or ".", full_classes)

    # ── Interfaces (detected from bases) ───────────────────────────────
    interface_markers: set[str] = {"ABC", "ABCMeta", "Protocol"}
    interfaces: list[str] = []
    for b in bases:
        if b in interface_markers:
            interfaces.append(b)
        else:
            b_node = full_classes.get(b)
            if b_node:
                b_bases = _get_base_names(b_node)
                if _detect_interface(b_node, b_bases):
                    interfaces.append(b)

    # ── Build response ───────────────────────────────────────────────
    result: dict[str, Any] = {
        "class": class_name,
        "file": resolved_file or "",
        "bases": bases,
        "mro": mro,
        "subclasses": subclasses,
        "interfaces": interfaces,
        "methods": method_categories,
        "metrics": metrics,
    }

    if has_mro_error:
        result["warning"] = "C3 linearization encountered a merge conflict; MRO may be incomplete"

    return result
