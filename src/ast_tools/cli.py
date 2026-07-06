#!/usr/bin/env python3
"""AST Tools CLI — Terminal workflows for structural code analysis.

Commands:
    ast search <query>        — Semantic search across codebase
    ast navigate <symbol>     — Jump to symbol definition
    ast blast-radius <target> — Unified blast radius: imports + hierarchy + call graph
    ast find-dead             — Enhanced dead code detection
    ast summary               — Codebase overview
    ast symbols <file>        — List symbols in file
    ast refs <symbol>         — Find all references

Usage:
    ast search "authentication"
    ast navigate GraphEngine
    ast blast-radius src/ast_tools/kg/graph_engine.py
    ast blast-radius GraphEngine --format json
    ast find-dead --format table
    ast summary --format markdown"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ast_tools.tools.blast_radius_v2 import _tool_blast_radius_v2


def _cli_init_cmd(args) -> str:
    """Wrapper for ast-tools init."""
    from ast_tools.curator.setup_wizard import cli_init
    return cli_init(vars(args))

def _cli_doctor_cmd(args) -> str:
    """Wrapper for ast-tools doctor."""
    from ast_tools.curator.doctor import cli_doctor
    return cli_doctor(vars(args))

def _cli_vacuum_cmd(args) -> str:
    """Wrapper for ast-tools vacuum."""
    from ast_tools.curator.vacuum import cli_vacuum
    return cli_vacuum(vars(args))

def _cli_curator_cmd(args) -> str:
    """Wrapper for ast-tools curator."""
    from ast_tools.curator.daemon import run_daily_audit
    if vars(args).get("dry_run"):
        return "[DRY RUN] Curator operations previewed"
    result = run_daily_audit()
    return json.dumps(result, indent=2)

def _cli_cleanup_cmd(args) -> str:
    """Wrapper for ast-tools cleanup."""
    from ast_tools.curator.cleanup import cli_cleanup
    return cli_cleanup(vars(args))

# Import tool functions
from ast_tools.tools.dependency_tools import dead_code_detection
from ast_tools.tools.enhanced_dead_code import find_dead_code_enhanced
from ast_tools.tools.find_references import _tool_find_references
from ast_tools.tools.find_symbol_definition import _tool_find_symbol_definition
from ast_tools.tools.list_symbols import _tool_list_symbols
from ast_tools.tools.module_imports import _tool_module_imports
from ast_tools.tools.project_info import _tool_project_info
from ast_tools.tools.semantic_search import _tool_semantic_search
from ast_tools.tools.structural_analysis import _ast_find_callees, _ast_find_callers


def cmd_search(args: argparse.Namespace) -> int:
    """Semantic search command."""
    query = args.query
    limit = args.limit or 10

    # Run async function
    result = asyncio.run(_tool_semantic_search(
        query=query,
        k=limit,
        inject_context=False,  # CLI wants raw results
    ))

    if not isinstance(result, dict):
        import json
        try:
            result = json.loads(result)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in result: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: Unexpected result type: {type(result)}, error: {e}", file=sys.stderr)
            return 1

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    # Format based on output format
    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_search_markdown(result)
    else:  # table
        _print_search_table(result)

    return 0


def cmd_navigate(args: argparse.Namespace) -> int:
    """Navigate to symbol definition command."""
    project_root = args.project_root or "."
    symbol = args.symbol

    result = _tool_find_symbol_definition({
        "symbol": symbol,
        "project_root": project_root,
    })

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    # Find the best match
    matches = result.get("matches", [])
    if not matches:
        print(f"Symbol '{symbol}' not found", file=sys.stderr)
        return 1

    best = matches[0]
    file_path = best.get("file", "")
    line = best.get("line", 0)
    kind = best.get("kind", "symbol")

    if args.format == "json":
        print(json.dumps(best, indent=2, default=str))
    elif args.format == "markdown":
        print(f"**{symbol}** ({kind})\n")
        print(f"📍 `{file_path}:{line}`")
    else:  # concise
        print(f"{file_path}:{line} — {kind}")

    return 0


def cmd_blast_radius(args: argparse.Namespace) -> int:
    """Unified blast radius analysis command (import graph + class hierarchy + call graph)."""
    project_root = args.project_root or "."
    file_path = args.file_path

    # Parse file:line format if provided as single arg — convert to target
    target = file_path
    if ":" in file_path:
        parts = file_path.split(":")
        if len(parts) == 2:
            target = parts[0]

    result = _tool_blast_radius_v2({
        "target": target,
        "cwd": project_root,
        "max_depth": args.max_depth or 5,
        "include_imports": True,
        "include_hierarchy": True,
        "include_callers": not (args.no_callers or False),
    })

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_blast_radius_markdown(result)
    else:  # table
        _print_blast_radius_table(result)

    return 0


def cmd_find_dead(args: argparse.Namespace) -> int:
    """Enhanced dead code detection command."""
    project_root = args.project_root or "."
    use_enhanced = not args.basic
    entry_points = args.entry_points.split(",") if args.entry_points else None

    if use_enhanced:
        result = find_dead_code_enhanced(project_root, entry_points)
    else:
        result = dead_code_detection(project_root, entry_points)

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_dead_code_markdown(result)
    else:  # table
        _print_dead_code_table(result)

    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Codebase summary command."""
    project_root = args.project_root or "."

    result = _tool_project_info({
        "cwd": project_root,
        "full": False,  # Summary mode
    })

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_summary_markdown(result)
    else:  # concise
        _print_summary_concise(result)

    return 0


def cmd_symbols(args: argparse.Namespace) -> int:
    """List symbols in file command."""
    project_root = args.project_root or "."
    file_path = args.file_path
    kind = args.kind

    result = _tool_list_symbols({
        "file_path": file_path,
        "project_root": project_root,
        "kind": kind,
    })

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    symbols = result.get("symbols", [])

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_symbols_markdown(symbols)
    else:  # table
        _print_symbols_table(symbols)

    return 0


def cmd_refs(args: argparse.Namespace) -> int:
    """Find references command."""
    project_root = args.project_root or "."
    symbol = args.symbol
    file_path = args.file_path or None

    result = _tool_find_references({
        "symbol": symbol,
        "file_path": file_path,
        "project_root": project_root,
    })

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    refs = result.get("references", [])

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        _print_refs_markdown(refs)
    else:  # table
        _print_refs_table(refs)

    return 0


def cmd_callers(args: argparse.Namespace) -> int:
    """Find callers of a symbol command."""
    project_root = args.project_root or "."
    symbol = args.symbol
    max_files = args.max_files or 100

    callers = _ast_find_callers(symbol, project_root, max_files)

    if not callers:
        print(f"No callers found for '{symbol}'", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps({"symbol": symbol, "callers": callers}, indent=2, default=str))
    elif args.format == "markdown":
        print(f"## Callers of `{symbol}`\n")
        for call in callers[:20]:
            file_path = call.get("file", "")
            line = call.get("line", "")
            caller = call.get("caller", "")
            ctx = call.get("context", "")
            print(f"- `{file_path}:{line}` in `{caller}()` — `{ctx}`")
        if len(callers) > 20:
            print(f"\n_... and {len(callers) - 20} more_")
    else:  # table
        print(f"Callers of `{symbol}` ({len(callers)} found)\n")
        print(f"{'File':<50} {'Line':<8} {'Caller':<20}")
        print("-" * 80)
        for call in callers[:20]:
            file_path = call.get("file", "")[:48]
            line = str(call.get("line", ""))[:6]
            caller = call.get("caller", "")[:18]
            print(f"{file_path:<50} {line:<8} {caller:<20}")
        if len(callers) > 20:
            print(f"\n... and {len(callers) - 20} more")

    return 0


def cmd_callees(args: argparse.Namespace) -> int:
    """Find callees (what a symbol calls) command."""
    project_root = args.project_root or "."
    symbol = args.symbol
    file_path = args.file_path

    if not file_path:
        print("Error: --file-path is required for callees analysis", file=sys.stderr)
        return 1

    callees = _ast_find_callees(symbol, file_path, project_root)

    if not callees:
        print(f"No callees found for '{symbol}' in {file_path}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps({"symbol": symbol, "file": file_path, "callees": callees}, indent=2, default=str))
    elif args.format == "markdown":
        print(f"## Callees of `{symbol}` ({file_path})\n")
        for callee in callees:
            name = callee.get("name", "")
            line = callee.get("line", "")
            ctx = callee.get("context", "")
            print(f"- `{name}` at line {line} — `{ctx}`")
    else:  # table
        print(f"Callees of `{symbol}` in {file_path} ({len(callees)} found)\n")
        print(f"{'Name':<30} {'Line':<8} {'Context':<40}")
        print("-" * 80)
        for callee in callees:
            name = callee.get("name", "")[:28]
            line = str(callee.get("line", ""))[:6]
            ctx = callee.get("context", "")[:38]
            print(f"{name:<30} {line:<8} {ctx:<40}")

    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    """Show import dependencies of a file command."""
    project_root = args.project_root or "."
    file_path = args.file_path

    result = _tool_module_imports({
        "module": file_path,
        "cwd": project_root,
    })

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    fan_in = result.get("fan_in", [])
    fan_out = result.get("fan_out", [])

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        print(f"## Dependencies of `{file_path}`\n")
        if fan_out:
            print("### Imports (fan-out)\n")
            for imp in fan_out:
                mod = imp.get("module", "")
                file_path_imp = imp.get("file", "")
                line = imp.get("line", "")
                print(f"- `{mod}` — `{file_path_imp}:{line}`")
        if fan_in:
            print(f"\n### Imported by (fan-in) — {len(fan_in)} files\n")
            for imp in fan_in[:15]:
                file_path_imp = imp.get("file", "")
                line = imp.get("line", "")
                print(f"- `{file_path_imp}:{line}`")
            if len(fan_in) > 15:
                print(f"\n_... and {len(fan_in) - 15} more_")
    else:  # table
        print(f"Dependencies of `{file_path}`\n")
        print(f"Fan-out (imports): {len(fan_out)}")
        print(f"Fan-in (imported by): {len(fan_in)}\n")

        if fan_out:
            print("Imports:")
            print(f"  {'Module':<40} {'File':<40}")
            print("  " + "-" * 82)
            for imp in fan_out[:10]:
                mod = imp.get("module", "")[:38]
                file_path_imp = imp.get("file", "")[:38]
                print(f"  {mod:<40} {file_path_imp:<40}")
            if len(fan_out) > 10:
                print(f"  ... and {len(fan_out) - 10} more")

        if fan_in:
            print(f"\nImported by ({len(fan_in)}):")
            print(f"  {'File':<60} {'Line':<8}")
            print("  " + "-" * 70)
            for imp in fan_in[:10]:
                file_path_imp = imp.get("file", "")[:58]
                line = str(imp.get("line", ""))[:6]
                print(f"  {file_path_imp:<60} {line:<8}")
            if len(fan_in) > 10:
                print(f"  ... and {len(fan_in) - 10} more")

    return 0


def _browse_fallback(project_root: str, kind: str, limit: int) -> list[dict]:
    """Fallback browse using filesystem scanning when no DB index exists."""
    import ast as ast_mod

    symbols = []
    py_files = list(Path(project_root).rglob("*.py"))[:200]  # Cap at 200 files

    for py_file in py_files:
        if any(p in py_file.parts for p in (".venv", "__pycache__", ".git", ".eggs", "node_modules")):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast_mod.parse(source, filename=str(py_file))
            for node in ast_mod.walk(tree):
                if isinstance(node, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef)):
                    sym_kind = "function"
                elif isinstance(node, ast_mod.ClassDef):
                    sym_kind = "class"
                else:
                    continue
                if kind != "all" and sym_kind != kind:
                    continue
                rel_path = str(py_file.relative_to(project_root))
                symbols.append({
                    "name": node.name,
                    "kind": sym_kind,
                    "file": rel_path,
                    "line": node.lineno,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                })
                if len(symbols) >= limit:
                    return symbols
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
    return symbols


def cmd_browse(args: argparse.Namespace) -> int:
    """Browse all symbols in project with filters command."""
    project_root = args.project_root or "."
    kind = args.kind or "all"
    lang = args.lang or "all"
    limit = args.limit or 50

    # If project_root is explicitly set (not default), use filesystem fallback
    # to avoid polluting/reading from global cache
    use_fallback = project_root != "."

    if not use_fallback:
        # Try DB-backed list first
        result = _tool_list_symbols({
            "file_path": None,  # All files
            "project_root": project_root,
            "kind": kind if kind != "all" else None,
            "lang": lang if lang != "all" else None,
            "limit": limit,
        })

        # Fall back to filesystem scanning if no DB/index
        if result.get("error_code") == "INDEX_NOT_FOUND":
            symbols = _browse_fallback(project_root, kind, limit)
            result = {"project_root": project_root, "symbols": symbols, "count": len(symbols)}
        elif "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            return 1
        else:
            symbols = result.get("symbols", [])
    else:
        # Explicit project root: use filesystem scanning
        symbols = _browse_fallback(project_root, kind, limit)
        result = {"project_root": project_root, "symbols": symbols, "count": len(symbols)}

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    elif args.format == "markdown":
        print(f"## Symbols in {project_root}")
        if kind != "all":
            print(f"*(kind={kind})*")
        if lang != "all":
            print(f"*(lang={lang})*")
        print(f"\n**Found {len(symbols)} symbols**\n")

        for sym in symbols:
            name = sym.get("name", "")
            kind_sym = sym.get("kind", "")
            file_path = sym.get("file", "")
            line = sym.get("line", "")
            sig = sym.get("signature", "")
            print(f"- **{name}** (`{kind_sym}`) — `{file_path}:{line}`")
            if sig:
                print(f"  ```python\n  {sig}\n  ```")
    else:  # table
        print(f"Symbols in {project_root}")
        if kind != "all":
            print(f"Kind: {kind}")
        if lang != "all":
            print(f"Lang: {lang}")
        print(f"\nFound {len(symbols)} symbols\n")
        print(f"{'Name':<30} {'Kind':<12} {'File':<40} {'Line':<6}")
        print("-" * 90)
        for sym in symbols:
            name = sym.get("name", "")[:28]
            kind_sym = sym.get("kind", "")[:10]
            file_path = sym.get("file", "")[:38]
            line = str(sym.get("line", ""))
            print(f"{name:<30} {kind_sym:<12} {file_path:<40} {line:<6}")

    return 0


# ——————————————————————————————
# Formatters
# ——————————————————————————————

def _print_search_table(result: dict) -> None:
    """Print search results in table format."""
    symbols = result.get("symbols", [])

    if not symbols:
        print("No results found")
        return

    from ast_tools.context.formatters import count_tokens

    print(f"Found {len(symbols)} symbol(s) [~{count_tokens(str(symbols))} tokens]\n")
    print(f"{'Symbol':<30} {'Kind':<12} {'File':<40} {'Line':<6}")
    print("-" * 90)

    for sym in symbols[:20]:
        name = sym.get("name", "")[:28]
        kind = sym.get("kind", "")[:10]
        file_path = sym.get("file", "")[:38]
        line = str(sym.get("line", ""))
        print(f"{name:<30} {kind:<12} {file_path:<40} {line:<6}")

    if len(symbols) > 20:
        print(f"\n... and {len(symbols) - 20} more")


def _print_search_markdown(result: dict) -> None:
    """Print search results in markdown format."""
    symbols = result.get("symbols", [])

    if not symbols:
        print("No results found")
        return

    print(f"## Found {len(symbols)} symbol(s)\n")

    for sym in symbols[:20]:
        name = sym.get("name", "")
        kind = sym.get("kind", "")
        file_path = sym.get("file", "")
        line = sym.get("line", "")
        print(f"- **{name}** (`{kind}`) — `{file_path}:{line}`")

    if len(symbols) > 20:
        print(f"\n_... and {len(symbols) - 20} more_")


def _print_blast_radius_table(result: dict) -> None:
    """Print blast radius v2 analysis in table format."""
    summary = result.get("summary", {})
    axes = result.get("axes", {})
    recommendations = result.get("recommendations", [])

    target = result.get("target", "?")
    target_kind = result.get("target_kind", "?")
    risk = summary.get("risk", "none").upper()
    confidence = summary.get("confidence", 0.0)
    total = summary.get("total_affected", 0)
    files = summary.get("distinct_files", 0)

    print(f"\n🎯 Blast Radius: {target} [{target_kind}]\n")
    print(f"  Risk:       {risk}")
    print(f"  Confidence: {confidence:.0%}")
    print(f"  Affected:   {total} items across {files} files\n")

    print("  Axes breakdown:")
    for ax_name, ax_result in axes.items():
        if ax_result is None:
            continue
        a = ax_result.get("affected", 0)
        r = ax_result.get("risk", "none").upper()
        c = ax_result.get("confidence", 0.0)
        label = ax_name.replace("_", " ").title()
        print(f"    {label:<20} {a:>3} affected  [{r:<8}]  {c:.0%} confidence")

    if recommendations:
        print("\n  Recommendations:")
        for rec in recommendations:
            print(f"    💡 {rec}")

    by_file = result.get("combined", {}).get("by_file", [])
    if by_file:
        print(f"\n  Files ({len(by_file)}):")
        for entry in by_file[:10]:
            reasons = ", ".join(entry.get("reasons", []))
            print(f"    {entry['file']:<55} [{reasons}]")
        if len(by_file) > 10:
            print(f"    ... and {len(by_file) - 10} more")
    print()


def _print_blast_radius_markdown(result: dict) -> None:
    """Print blast radius v2 analysis in markdown format."""
    summary = result.get("summary", {})
    axes = result.get("axes", {})
    recommendations = result.get("recommendations", [])

    target = result.get("target", "?")
    target_kind = result.get("target_kind", "?")
    risk = summary.get("risk", "none")
    confidence = summary.get("confidence", 0.0)
    total = summary.get("total_affected", 0)
    files = summary.get("distinct_files", 0)

    print(f"## 🎯 Blast Radius: `{target}` ({target_kind})\n")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Risk | **{risk}** |")
    print(f"| Confidence | {confidence:.0%} |")
    print(f"| Affected | {total} items across {files} files |")
    print()

    if axes:
        print("### Axes Breakdown\n")
        print("| Axis | Affected | Risk | Confidence |")
        print("|------|----------|------|------------|")
        for axis_name, axis_result in axes.items():
            if axis_result is None:
                continue
            a = axis_result.get("affected", 0)
            r = axis_result.get("risk", "none")
            c = axis_result.get("confidence", 0.0)
            label = axis_name.replace("_", " ").title()
            print(f"| {label} | {a} | {r} | {c:.0%} |")

    if recommendations:
        print("\n### Recommendations\n")
        for rec in recommendations:
            print(f"- 💡 {rec}")

    by_file = result.get("combined", {}).get("by_file", [])
    if by_file:
        print("\n### Affected Files\n")
        for entry in by_file:
            reasons = ", ".join(entry.get("reasons", []))
            print(f"- `{entry['file']}` — [{reasons}]")

    print()


def _print_dead_code_table(result: dict) -> None:
    """Print dead code findings in table format."""
    funcs = result.get("dead_functions", [])
    classes = result.get("dead_classes", [])
    methods = result.get("dead_methods", [])

    total = len(funcs) + len(classes) + len(methods)
    print(f"🔍 Dead Code Detection — {total} findings\n")

    if result.get("summary", {}).get("false_positive_mitigations"):
        mits = result["summary"]["false_positive_mitigations"]
        print("Excluded via:")
        print(f"  • Framework decorators: {mits.get('framework_decorators', 0)}")
        print(f"  • Entry point reachable: {mits.get('entry_point_symbols', 0)}")
        print(f"  • Exported in __all__: {mits.get('exported_symbols', 0)}")
        print(f"  • SCC clusters: {mits.get('scc_cluster_members', 0)}")
        print(f"  • Interface impls: {mits.get('interface_implementations', 0)}\n")

    # High confidence first
    high_conf = [f for f in funcs if f.get("confidence") == "high"][:15]
    if high_conf:
        print("HIGH CONFIDENCE:")
        print(f"  {'Name':<30} {'File':<40} {'Type':<10}")
        print("  " + "-" * 82)
        for item in high_conf:
            name = item.get("name", "")[:28]
            file_path = item.get("file", "")[:38]
            sym_type = item.get("symbol_type", "")[:8]
            print(f"  {name:<30} {file_path:<40} {sym_type:<10}")
        print()

    # Summary stats
    summary = result.get("summary", {})
    print(f"Total: {summary.get('total_dead_functions', 0)} functions, "
          f"{summary.get('total_dead_classes', 0)} classes, "
          f"{summary.get('total_dead_methods', 0)} methods")


def _print_dead_code_markdown(result: dict) -> None:
    """Print dead code findings in markdown format."""
    funcs = result.get("dead_functions", [])
    classes = result.get("dead_classes", [])
    methods = result.get("dead_methods", [])

    total = len(funcs) + len(classes) + len(methods)
    print(f"## 🔍 Dead Code Detection — {total} findings\n")

    # High confidence first
    high_conf = [f for f in funcs if f.get("confidence") == "high"][:15]
    if high_conf:
        print("### HIGH CONFIDENCE\n")
        for item in high_conf:
            name = item.get("name", "")
            file_path = item.get("file", "")
            print(f"- `{name}` — `{file_path}`")
        print()


def _print_summary_markdown(result: dict) -> None:
    """Print project summary in markdown format."""
    print(f"# 📦 {result.get('name', 'Project')}\n")

    print(f"**Version:** {result.get('version', 'N/A')}")
    print(f"**Test framework:** {result.get('test_framework', 'N/A')}\n")

    # Languages
    langs = result.get("languages", {})
    if langs:
        print("## Languages\n")
        for lang, stats in langs.items():
            files = stats.get("files", 0)
            lines = stats.get("lines", 0)
            print(f"- **{lang}:** {files} files, {lines:,} lines")
        print()

    # Modules
    modules = result.get("modules", [])
    if modules:
        print("## Top Modules\n")
        # modules may be a list of dicts (full info) or strings (names only)
        if modules and isinstance(modules[0], str):
            for mod in modules[:10]:
                print(f"- `{mod}`")
        else:
            for mod in modules[:10]:
                path = mod.get("path", "")
                lines = mod.get("lines", 0)
                funcs = len(mod.get("functions", []))
                classes = len(mod.get("classes", []))
                print(f"- `{path}` — {lines:,} lines, {funcs} funcs, {classes} classes")


def _print_summary_concise(result: dict) -> None:
    """Print project summary in concise format."""
    name = result.get("name", "Project")
    version = result.get("version", "")

    # Count files and lines
    total_files = 0
    total_lines = 0
    for _lang, stats in result.get("languages", {}).items():
        total_files += stats.get("files", 0)
        total_lines += stats.get("lines", 0)

    modules = result.get("modules", [])

    print(f"{name} v{version} — {total_files:,} files, {total_lines:,} lines, {len(modules):,} modules")


def _print_symbols_table(symbols: list) -> None:
    """Print symbols in table format."""
    if not symbols:
        print("No symbols found")
        return

    print(f"{'Name':<30} {'Kind':<12} {'Line':<8} {'Signature':<50}")
    print("-" * 102)

    for sym in symbols[:30]:
        name = sym.get("name", "")[:28]
        kind = sym.get("kind", "")[:10]
        line = str(sym.get("line", ""))[:6]
        sig = sym.get("signature", "")[:48]
        print(f"{name:<30} {kind:<12} {line:<8} {sig:<50}")

    if len(symbols) > 30:
        print(f"\n... and {len(symbols) - 30} more")


def _print_symbols_markdown(symbols: list) -> None:
    """Print symbols in markdown format."""
    if not symbols:
        print("No symbols found")
        return

    print(f"## Found {len(symbols)} symbol(s)\n")

    for sym in symbols[:30]:
        name = sym.get("name", "")
        kind = sym.get("kind", "")
        line = sym.get("line", "")
        sig = sym.get("signature", "")
        print(f"- **{name}** (`{kind}`) line {line}: `{sig}`")

    if len(symbols) > 30:
        print(f"\n_... and {len(symbols) - 30} more_")


def _print_refs_table(refs: list) -> None:
    """Print references in table format."""
    if not refs:
        print("No references found")
        return

    print(f"{'File':<50} {'Line':<8} {'Context':<40}")
    print("-" * 100)

    for ref in refs[:20]:
        file_path = ref.get("file", "")[:48]
        line = str(ref.get("line", ""))[:6]
        ctx = ref.get("context", "")[:38]
        print(f"{file_path:<50} {line:<8} {ctx:<40}")

    if len(refs) > 20:
        print(f"\n... and {len(refs) - 20} more")


def _print_refs_markdown(refs: list) -> None:
    """Print references in markdown format."""
    if not refs:
        print("No references found")
        return

    print(f"## Found {len(refs)} reference(s)\n")

    for ref in refs[:20]:
        file_path = ref.get("file", "")
        line = ref.get("line", "")
        ctx = ref.get("context", "")
        print(f"- `{file_path}:{line}` — `{ctx}`")

    if len(refs) > 20:
        print(f"\n_... and {len(refs) - 20} more_")


# ─── Config Commands ─────────────────────────────────────────────────


def cmd_config_path(args: argparse.Namespace) -> int:
    """Print config directory path."""
    from ast_tools.config.loader import ensure_config_dir, get_config_dir

    cfg = get_config_dir()
    ensure_config_dir()
    print(str(cfg))
    return 0


def cmd_config_init(args: argparse.Namespace) -> int:
    """Create default config files."""
    import yaml

    from ast_tools.config.loader import ensure_config_dir
    from ast_tools.config.tokens_schema import DEFAULT_TOKENS

    cfg = ensure_config_dir()
    tokens_path = cfg / "config" / "tokens.yaml"
    if not tokens_path.exists():
        tokens_path.write_text(yaml.dump(DEFAULT_TOKENS, default_flow_style=False))
        tokens_path.chmod(0o600)
        print(f"✅ Created {tokens_path}")
    else:
        print(f"ℹ️  Already exists: {tokens_path}")
    print(f"📁 Config directory: {cfg}")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show current configuration."""
    from ast_tools.config.loader import get_config_dir, load_tokens_config

    cfg = get_config_dir()
    print(f"Config directory: {cfg}")
    print()
    tokens = load_tokens_config()
    if tokens:
        print("Token budgets:")
        for tool, budgets in sorted(tokens.items()):
            inp = budgets.get("max_input_tokens", "?")
            out = budgets.get("max_output_tokens", "?")
            print(f"  {tool}: in={inp}, out={out}")
    return 0


def cmd_config_validate(args: argparse.Namespace) -> int:
    """Validate all config files."""
    from ast_tools.config.validate import validate_config

    result = validate_config()
    if result["valid"]:
        print("✅ Config valid")
        return 0
    for err in result["errors"]:
        file = err.get("file", "")
        warning = err.get("warning", "")
        error = err.get("error", "")
        if warning:
            print(f"⚠️  {file}: {warning}")
        if error:
            print(f"❌ {file}: {error}")
    return 0 if result["valid"] else 1


# ─── Governance Commands ──────────────────────────────────────────────


def cmd_governance_init(args: argparse.Namespace) -> int:
    """Create default governance.yaml."""
    from ast_tools.governance.schema import init_governance_file

    path = init_governance_file()
    print(f"✅ Created {path}")
    return 0


def cmd_governance_check(args: argparse.Namespace) -> int:
    """Scan project for governance violations."""
    from ast_tools.governance.reporter import format_violations
    from ast_tools.governance.scanner import scan_project
    from ast_tools.governance.schema import load_governance

    config = load_governance()
    if config is None:
        print("❌ No governance.yaml found. Run 'ast governance init' first.")
        return 1

    violations = scan_project(args.project_root, config)
    report = format_violations(violations, format=args.format, fail_on=args.fail_on)
    print(report)
    return 1 if violations else 0


def cmd_governance_diff(args: argparse.Namespace) -> int:
    """Compare governance between branches."""
    from ast_tools.governance.differ import diff_branches

    result = diff_branches(base_branch=args.base, cwd=args.project_root)
    if "error" in result:
        print(f"❌ {result['error']}")
        return 1
    if "warning" in result:
        print(f"⚠️  {result['warning']}")

    delta = result.get("delta", {})
    if delta.get("total_new", 0) > 0:
        print(f"🆕 {delta['total_new']} new violation(s) in current branch:")
        for v in delta.get("new", []):
            print(f"  ❌ {v['message']}")

    if delta.get("total_fixed", 0) > 0:
        print(f"✅ {delta['total_fixed']} violation(s) fixed in current branch")

    if delta.get("total_new", 0) == 0 and delta.get("total_fixed", 0) == 0:
        print("ℹ️  No governance changes between branches")
    return 0


def cmd_governance_report(args: argparse.Namespace) -> int:
    """Generate HTML governance report."""
    from pathlib import Path

    from ast_tools.governance.reporter import generate_report_html
    from ast_tools.governance.scanner import scan_project
    from ast_tools.governance.schema import load_governance

    config = load_governance()
    if config is None:
        print("❌ No governance.yaml found")
        return 1

    violations = scan_project(args.project_root, config)
    html = generate_report_html(violations)
    output_path = Path(args.output)
    output_path.write_text(html)
    print(f"✅ Report saved to {output_path}")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ast",
        description="AST Tools CLI — Structural code analysis workflows",
        epilog="Run 'ast <command> --help' for more info on a specific command.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="ast-tools 0.1.0",
    )

    parser.add_argument(
        "--project-root", "-p",
        default=".",
        help="Project root directory (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ——————————————————
    # Command: search
    # ——————————————————
    search_p = subparsers.add_parser(
        "search",
        help="Semantic search across codebase",
        description="Search for symbols by meaning using hybrid FTS5 + vector search",
    )
    search_p.add_argument("query", help="Search query (natural language)")
    search_p.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    search_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    search_p.set_defaults(func=cmd_search)

    # ——————————————————
    # Command: navigate
    # ——————————————————
    nav_p = subparsers.add_parser(
        "navigate",
        help="Jump to symbol definition",
        description="Find where a symbol is defined",
    )
    nav_p.add_argument("symbol", help="Symbol name to find")
    nav_p.add_argument(
        "--format", "-f",
        choices=["concise", "json", "markdown"],
        default="concise",
        help="Output format",
    )
    nav_p.set_defaults(func=cmd_navigate)

    # ——————————————————
    # Command: blast-radius
    # ——————————————————
    blast_p = subparsers.add_parser(
        "blast-radius",
        help="Impact analysis",
        description="Find all code affected by a change",
    )
    blast_p.add_argument(
        "file_path",
        help="File path (or file:line format)",
    )
    blast_p.add_argument(
        "--line", "-l",
        type=int,
        help="Specific line number (if not in file_path)",
    )
    blast_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    blast_p.add_argument(
        "--max-depth", "-d",
        type=int,
        default=5,
        help="BFS traversal depth (default: 5)",
    )
    blast_p.add_argument(
        "--no-callers",
        action="store_true",
        help="Skip call graph analysis (faster)",
    )
    blast_p.set_defaults(func=cmd_blast_radius)

    # ——————————————————
    # Command: find-dead
    # ——————————————————
    dead_p = subparsers.add_parser(
        "find-dead",
        help="Enhanced dead code detection",
        description="Find unused code with false-positive reduction",
    )
    dead_p.add_argument(
        "--basic",
        action="store_true",
        help="Use basic dead code detection (no FP reduction)",
    )
    dead_p.add_argument(
        "--entry-points",
        help="Comma-separated entry point files (auto-detected if omitted)",
    )
    dead_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    dead_p.set_defaults(func=cmd_find_dead)

    # ——————————————————
    # Command: summary
    # ——————————————————
    sum_p = subparsers.add_parser(
        "summary",
        help="Codebase overview",
        description="Print project summary",
    )
    sum_p.add_argument(
        "--format", "-f",
        choices=["concise", "json", "markdown"],
        default="concise",
        help="Output format",
    )
    sum_p.set_defaults(func=cmd_summary)

    # ——————————————————
    # Command: symbols
    # ——————————————————
    sym_p = subparsers.add_parser(
        "symbols",
        help="List symbols in file",
        description="Show all symbols defined in a file",
    )
    sym_p.add_argument("file_path", help="File path")
    sym_p.add_argument(
        "--kind",
        choices=["function", "class", "method", "all"],
        default="all",
        help="Filter by symbol kind",
    )
    sym_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    sym_p.set_defaults(func=cmd_symbols)

    # ——————————————————
    # Command: refs
    # ——————————————————
    refs_p = subparsers.add_parser(
        "refs",
        help="Find references",
        description="Find all references to a symbol",
    )
    refs_p.add_argument("symbol", help="Symbol name")
    refs_p.add_argument(
        "--file-path",
        help="Limit to specific file",
    )
    refs_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    refs_p.set_defaults(func=cmd_refs)

    # ——————————————————
    # Command: callers
    # ——————————————————
    callers_p = subparsers.add_parser(
        "callers",
        help="Find callers of a symbol",
        description="Find all functions/methods that call this symbol",
    )
    callers_p.add_argument("symbol", help="Symbol name to find callers for")
    callers_p.add_argument("--max-files", "-n", type=int, default=100, help="Max files to search")
    callers_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    callers_p.set_defaults(func=cmd_callers)

    # ——————————————————
    # Command: callees
    # ——————————————————
    callees_p = subparsers.add_parser(
        "callees",
        help="Find what a symbol calls",
        description="Find all functions called by this symbol",
    )
    callees_p.add_argument("symbol", help="Symbol name")
    callees_p.add_argument("--file-path", required=True, help="File containing the symbol")
    callees_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    callees_p.set_defaults(func=cmd_callees)

    # ——————————————————
    # Command: deps
    # ——————————————————
    deps_p = subparsers.add_parser(
        "deps",
        help="Show import dependencies",
        description="Show fan-in/fan-out import dependencies for a file",
    )
    deps_p.add_argument("file_path", help="File path to analyze")
    deps_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    deps_p.set_defaults(func=cmd_deps)

    # ——————————————————
    # Command: browse
    # ——————————————————
    browse_p = subparsers.add_parser(
        "browse",
        help="Browse all symbols",
        description="Browse symbols in the project with filters",
    )
    browse_p.add_argument(
        "--kind",
        choices=["function", "class", "method", "variable", "all"],
        default="all",
        help="Filter by symbol kind",
    )
    browse_p.add_argument(
        "--lang",
        choices=["python", "javascript", "typescript", "rust", "go", "all"],
        default="all",
        help="Filter by language",
    )
    browse_p.add_argument("-n", "--limit", type=int, default=50, help="Max results")
    browse_p.add_argument(
        "--format", "-f",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    browse_p.set_defaults(func=cmd_browse)

    # ——————————————————
    # Command: init
    # ——————————————————
    init_p = subparsers.add_parser(
        "init",
        help="Initialize AST-Tools (setup wizard)",
        description="First-time setup: create config dir, init DB, download model",
    )
    init_p.add_argument("--non-interactive", "-n", action="store_true", help="Skip prompts, use defaults")
    init_p.add_argument("--skip-model", "-s", action="store_true", help="Skip model download (FTS5 only)")
    init_p.add_argument("--model-path", help="Path to pre-downloaded model")
    init_p.set_defaults(func=lambda a: print(_cli_init_cmd(a)))

    # ——————————————————
    # Command: doctor
    # ——————————————————
    doctor_p = subparsers.add_parser(
        "doctor",
        help="Run health checks",
        description="Comprehensive health check with score 0-100",
    )
    doctor_p.add_argument("--verbose", "-v", action="store_true", help="Detailed per-check output")
    doctor_p.add_argument("--fix", "-f", action="store_true", help="Auto-fix discovered issues")
    doctor_p.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    doctor_p.set_defaults(func=lambda a: print(_cli_doctor_cmd(a)))

    # ——————————————————
    # Command: vacuum
    # ——————————————————
    vacuum_p = subparsers.add_parser(
        "vacuum",
        help="Reclaim disk space",
        description="SQLite VACUUM, temp cleanup, log rotation",
    )
    vacuum_p.add_argument("--aggressive", "-a", action="store_true", help="Also clear model cache")
    vacuum_p.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    vacuum_p.set_defaults(func=lambda a: print(_cli_vacuum_cmd(a)))

    # ——————————————————
    # Command: curator
    # ——————————————————
    curator_p = subparsers.add_parser(
        "curator",
        help="Run index curator",
        description="Prune stale symbols, deduplicate, scan PII",
    )
    curator_p.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    curator_p.add_argument("--pii-action", choices=["flag", "redact", "remove"], default="flag",
                          help="PII action (default: flag)")
    curator_p.set_defaults(func=lambda a: print(_cli_curator_cmd(a)))

    # ——————————————————
    # Command: cleanup
    # ——————————————————
    cleanup_p = subparsers.add_parser(
        "cleanup",
        help="Remove temp and stale files",
        description="Delete cache/tmp, expired caches, stale logs",
    )
    cleanup_p.add_argument("--aggressive", "-a", action="store_true", help="Also clear model cache")
    cleanup_p.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    cleanup_p.set_defaults(func=lambda a: print(_cli_cleanup_cmd(a)))

    # ——————————————————
    # Command: config
    # ——————————————————
    config_p = subparsers.add_parser(
        "config",
        help="Manage configuration",
        description="View and validate AST-Tools configuration",
    )
    config_sub = config_p.add_subparsers(dest="config_cmd")
    config_show_p = config_sub.add_parser("show", help="Show current configuration")
    config_show_p.set_defaults(func=cmd_config_show)

    config_validate_p = config_sub.add_parser("validate", help="Validate configuration")
    config_validate_p.set_defaults(func=cmd_config_validate)

    config_init_p = config_sub.add_parser("init", help="Create default config files")
    config_init_p.set_defaults(func=cmd_config_init)

    config_path_p = config_sub.add_parser("path", help="Print config directory path")
    config_path_p.set_defaults(func=cmd_config_path)

    # ——————————————————
    # Command: governance
    # ——————————————————
    gov_p = subparsers.add_parser(
        "governance",
        help="Architecture governance rules and checking",
        description="Enforce architectural boundaries via governance.yaml",
    )
    gov_sub = gov_p.add_subparsers(dest="gov_cmd")

    gov_init_p = gov_sub.add_parser("init", help="Create default governance.yaml")
    gov_init_p.set_defaults(func=cmd_governance_init)

    gov_check_p = gov_sub.add_parser("check", help="Scan project for violations")
    gov_check_p.add_argument("--format", choices=["text", "json"], default="text")
    gov_check_p.add_argument("--fail-on", choices=["error", "warn"], default="error")
    gov_check_p.add_argument("--project-root", default=".")
    gov_check_p.set_defaults(func=cmd_governance_check)

    gov_diff_p = gov_sub.add_parser("diff", help="Compare governance between branches")
    gov_diff_p.add_argument("--base", default="main", help="Base branch")
    gov_diff_p.add_argument("--project-root", default=".")
    gov_diff_p.set_defaults(func=cmd_governance_diff)

    gov_report_p = gov_sub.add_parser("report", help="Generate HTML governance report")
    gov_report_p.add_argument("--output", "-o", default="governance-report.html")
    gov_report_p.add_argument("--project-root", default=".")
    gov_report_p.set_defaults(func=cmd_governance_report)
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
