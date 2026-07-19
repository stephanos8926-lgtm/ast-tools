"""MCP tool handlers for auto-fix and reranker operations."""

from pathlib import Path
from typing import Any

from ast_tools.fix.config import FixConfig as FixConfigData
from ast_tools.fix.engine import FixContext, FixEngine
from ast_tools.reranker import CrossEncoderReranker, RerankerConfig


def _tool_fix_code(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Apply auto-fix to files.

    Args:
        path: File or directory to fix (default: current directory)
        check_only: If true, only report issues without fixing
        lang: Language to fix (auto-detected by default)
        safety: Safety level: safe, unsafe (default: safe)
        max_iterations: Max convergence iterations (default: 10)

    Returns:
        Fix result with actions applied, errors, and convergence status
    """
    target_path = params.get("path", ".")
    check_only = params.get("check_only", False)
    lang = params.get("lang")
    safety = params.get("safety", "safe")
    max_iterations = params.get("max_iterations", 10)

    project_root = Path.cwd().resolve()
    target = (project_root / target_path).resolve()

    # Determine target paths
    if target.is_file() or target.is_dir():
        target_paths = [target]
    else:
        return {"error": f"Path not found: {target}"}

    # Detect language if not specified
    languages: set[str]
    if lang:
        languages = {lang}
    else:
        # Auto-detect from file extensions in target
        extensions = set()
        if target.is_file():
            extensions.add(target.suffix)
        else:
            for p in target.rglob("*"):
                if p.is_file() and p.suffix:
                    extensions.add(p.suffix)

        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".c": "c",
            ".h": "cpp",
            ".hpp": "cpp",
            ".md": "markdown",
            ".mdx": "markdown",
        }
        languages = {lang_map.get(ext) for ext in extensions if lang_map.get(ext)}
        languages = {l for l in languages if l is not None}  # Filter out None

    if not languages:
        languages = {"python"}  # Default fallback


    config = FixConfigData(
        max_iterations=max_iterations,
        safety_level=safety,
        check_only=check_only,
    )

    context = FixContext(
        project_root=project_root,
        target_paths=target_paths,
        languages=languages,
        config=config,
        check_only=check_only,
        verbose=False,
        max_iterations=max_iterations,
    )

    engine = FixEngine(context)
    result = engine.run()

    return {
        "success": result.success,
        "total_fixes": result.total_fixes,
        "files_changed": result.files_changed,
        "iterations": result.iterations,
        "converged": result.converged,
        "execution_time": result.execution_time,
        "errors": result.errors,
        "actions_applied": [
            {
                "tool": a.tool,
                "description": a.description,
                "file_path": str(a.file_path),
                "safety": a.safety,
            }
            for a in result.actions_applied
        ],
        "actions_skipped": [
            {
                "tool": a.tool,
                "description": a.description,
                "file_path": str(a.file_path),
                "safety": a.safety,
            }
            for a in result.actions_skipped
        ],
    }


def _tool_fix_check(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Check what auto-fixes would be applied without modifying files.

    Args:
        path: File or directory to check (default: current directory)
        lang: Language to check (auto-detected by default)

    Returns:
        List of fixes that would be applied, grouped by file
    """
    params["check_only"] = True
    return _tool_fix_code(name, params)


def _tool_rerank_results(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Rerank search results using cross-encoder.

    Args:
        query: The search query
        candidates: List of candidate dicts with 'content' or 'text' key
        model: Model name (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
        top_k: Number of results to return (default: 15)
        score_key: Key to extract text for scoring (default: content)

    Returns:
        Reranked results with scores and confidence
    """
    query = params.get("query", "")
    candidates = params.get("candidates", [])
    model = params.get("model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    top_k = params.get("top_k", 15)
    score_key = params.get("score_key", "content")

    if not query:
        return {"error": "query is required"}
    if not candidates:
        return {"error": "candidates is required"}
    if not isinstance(candidates, list):
        return {"error": "candidates must be a list"}

    reranker_config = RerankerConfig(
        model_name=model,
        use_reranker=True,
        top_k=top_k,
    )

    reranker = CrossEncoderReranker(reranker_config)

    if not reranker.is_available():
        # Fallback: return candidates in original order with identity scores
        return {
            "reranked": candidates[:top_k],
            "confidence": 0.0,
            "model_used": "none (fallback)",
            "fallback_used": True,
            "error": reranker._load_error or "Model not available",
            "total_candidates": len(candidates),
        }

    result = reranker.rerank(query, candidates, score_key=score_key)

    reranked = [candidates[i] for i in result.indices if i < len(candidates)]

    # Attach scores
    for i, idx in enumerate(result.indices):
        if i < len(reranked) and idx < len(result.scores):
            reranked[i]["rerank_score"] = result.scores[idx]
            reranked[i]["rerank_confidence"] = result.confidence

    return {
        "reranked": reranked,
        "confidence": result.confidence,
        "model_used": result.model_used,
        "fallback_used": result.fallback_used,
        "scores": result.scores,
        "total_candidates": len(candidates),
    }
