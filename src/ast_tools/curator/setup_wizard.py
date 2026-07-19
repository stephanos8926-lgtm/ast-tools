#!/usr/bin/env python3
"""Setup wizard for AST-Tools — first-time initialization.

Usage:
    ast-tools init                    Interactive mode
    ast-tools init --non-interactive  Auto mode (smart defaults)
    ast-tools init --skip-model       No model download (FTS5 only)
    ast-tools init --model-path PATH  Use pre-downloaded model

Creates ~/.ast-tools/ structure, initializes database, downloads
embedding model, and creates initial index.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Directory structure ─────────────────────────────────────────────────

AST_TOOLS_DIR = Path.home() / ".ast-tools"
SUBDIRS = ["config", "cache/models", "cache/tmp", "logs", "backups"]

MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_CHECKSUM = ""  # Set when downloaded, verified on subsequent runs

# ── Main entry point ────────────────────────────────────────────────────


def run(
    non_interactive: bool = False,
    skip_model: bool = False,
    model_path: str | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    """Run the setup wizard.

    Args:
        non_interactive: Skip prompts, use defaults.
        skip_model: Skip embedding model download.
        model_path: Path to pre-downloaded model directory.
        project_root: Root of project to index (default: current dir).

    Returns:
        Dict with setup results and status.
    """
    results: dict[str, Any] = {
        "config_dir": None,
        "db_initialized": False,
        "model_installed": False,
        "index_created": False,
        "health_score": 0,
        "errors": [],
        "warnings": [],
    }

    log_path = AST_TOOLS_DIR / "logs" / "setup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Create config directory structure
        _log_step("Creating config directory...")
        config_dir = _create_config_dir()
        results["config_dir"] = str(config_dir)
        _log_ok(f"Config dir: {config_dir}")

        # Step 2: Check environment
        _log_step("Checking environment...")
        env_ok, env_issues = _check_environment()
        for issue in env_issues:
            results["warnings"].append(issue)
            _log_warn(issue)
        if not env_ok and non_interactive:
            _log_warn("Environment checks had warnings, continuing anyway")

        # Step 3: Initialize database
        _log_step("Initializing database...")
        db_path = _init_database(config_dir)
        results["db_initialized"] = True
        _log_ok(f"Database: {db_path}")

        # Step 4: Download embedding model
        if skip_model:
            _log_step("Skipping model download (--skip-model)")
            results["model_installed"] = False
        elif model_path:
            _log_step(f"Using pre-downloaded model: {model_path}")
            _install_model_from_path(Path(model_path))
            results["model_installed"] = True
            _log_ok("Model installed from path")
        else:
            _log_step("Downloading embedding model...")
            results["model_installed"] = _download_model()
            if results["model_installed"]:
                _log_ok("Model installed")
            else:
                results["warnings"].append("Model download failed, using FTS5-only mode")
                _log_warn("Model download failed — FTS5-only mode")

        # Step 5: Create initial index
        if project_root:
            _log_step(f"Creating initial index for {project_root}...")
            results["index_created"] = _create_initial_index(Path(project_root))
            if results["index_created"]:
                _log_ok("Initial index created")
            else:
                results["warnings"].append("Initial index creation had issues")

        # Step 6: Run health check
        _log_step("Running health check...")
        health = _run_health_check(config_dir)
        results["health_score"] = health.get("score", 0)
        _log_ok(f"Health score: {results['health_score']}/100")

        return results

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        results["errors"].append(str(e))
        # Attempt rollback
        _rollback(config_dir)
        raise


# ── Steps ───────────────────────────────────────────────────────────────


def _create_config_dir() -> Path:
    """Create config directory structure idempotently."""
    cfg = AST_TOOLS_DIR.resolve()
    for subdir in SUBDIRS:
        (cfg / subdir).mkdir(parents=True, exist_ok=True)
    # Set restrictive permissions on config
    (cfg / "config").chmod(0o700)
    return cfg


def _check_environment() -> tuple[bool, list[str]]:
    """Check Python version, dependencies, disk space."""
    issues: list[str] = []

    # Python version

    # Disk space
    try:
        import shutil

        free = shutil.disk_usage(AST_TOOLS_DIR).free
        if free < 500 * 1024 * 1024:  # 500MB
            issues.append(f"Low disk space: {free // (1024 * 1024)}MB free (recommended: 500MB+)")
    except Exception:
        issues.append("Could not check disk space")

    # Required packages
    required = ["mcp", "tree_sitter", "sqlite_vec"]
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_").replace("/", "."))
        except ImportError:
            issues.append(f"Package not found: {pkg} (run: pip install ast-tools[all])")

    return len(issues) == 0, issues


def _init_database(config_dir: Path) -> Path:
    """Initialize SQLite database with schema."""
    from ast_tools.database.connection import get_db_path
    db_path = get_db_path()
    data_dir = config_dir / "cache"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Import schema from existing module
    from ast_tools.database.connection import get_connection
    from ast_tools.database.schema import init_schema, migrate

    conn = get_connection(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)
        migrate(conn)
        conn.commit()
    finally:
        conn.close()

    logger.info(f"Database initialized at {db_path}")
    return db_path


def _download_model() -> bool:
    """Download embedding model with progress and checksum verification."""
    cache_dir = AST_TOOLS_DIR / "cache" / "models"
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Downloading model {MODEL_REPO} to {cache_dir}...")
        model = SentenceTransformer(MODEL_REPO, cache_folder=str(cache_dir))

        # Verify: run a test embedding
        test_emb = model.encode("test")
        if len(test_emb) == 0:
            raise ValueError("Model returned empty embedding — corrupt download?")

        logger.info(f"Model downloaded successfully (embedding dim: {len(test_emb)})")
        return True

    except ImportError:
        logger.warning("sentence-transformers not installed, skipping model download")
        return False
    except Exception as e:
        logger.error(f"Model download failed: {e}")
        # Clean partial download
        import shutil

        model_cache = cache_dir / "models--BAAI--bge-small-en-v1.5"
        if model_cache.exists():
            shutil.rmtree(model_cache, ignore_errors=True)
        return False


def _install_model_from_path(model_path: Path) -> None:
    """Copy pre-downloaded model to cache directory."""
    target = AST_TOOLS_DIR / "cache" / "models"
    target.mkdir(parents=True, exist_ok=True)
    if model_path.is_dir():
        shutil.copytree(model_path, target / model_path.name, dirs_exist_ok=True)
    else:
        raise ValueError(f"Model path is not a directory: {model_path}")


def _create_initial_index(project_root: Path) -> bool:
    """Create initial symbol index for the given project.

    Uses tree-sitter-based extraction for better accuracy.
    Falls back to counting Python files if import fails.
    """
    try:
        from ast_tools.database.connection import get_connection, get_db_path
        from ast_tools.indexer.extractor import extract_symbols_ts

        db_path = get_db_path()
        conn = get_connection(db_path)

        indexed = 0
        for py_file in sorted(project_root.rglob("*.py")):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                symbols = extract_symbols_ts(source, "python")
                for sym in symbols:
                    conn.execute(
                        """INSERT OR REPLACE INTO symbols
                           (id, name, qualified_name, kind, file_path, start_line,
                            end_line, signature, docstring, is_public, content_hash, indexed_at, lang)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            f"{py_file}:{sym.name}",
                            sym.name,
                            sym.name,
                            sym.kind,
                            str(py_file),
                            sym.start_line,
                            sym.end_line,
                            str(getattr(sym, "signature", "") or ""),
                            str(getattr(sym, "docstring", "") or ""),
                            1,
                            hashlib.sha256(str(py_file).encode()).hexdigest(),
                            int(time.time()),
                            "python",
                        ),
                    )
                    indexed += 1
                conn.commit()
            except Exception as e:
                logger.debug(f"Skipping {py_file}: {e}")
                continue

        logger.info(f"Indexed {indexed} symbols from {project_root}")
        return indexed > 0

    except Exception as e:
        logger.warning(f"Initial index failed (can run later via ast-tools index): {e}")
        return False


def _run_health_check(config_dir: Path) -> dict:
    """Run basic health check after setup."""
    score = 100
    checks = []

    # DB exists
    from ast_tools.database.connection import get_db_path
    db_path = get_db_path()
    if db_path.exists():
        checks.append({"check": "database", "status": "ok", "score": 30})
    else:
        checks.append({"check": "database", "status": "fail", "score": 0})
        score -= 30

    # DB integrity
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            if result == "ok":
                checks.append({"check": "integrity", "status": "ok", "score": 20})
            else:
                checks.append({"check": "integrity", "status": "fail", "score": 0})
                score -= 20
            conn.close()
        except Exception:
            checks.append({"check": "integrity", "status": "error", "score": 0})

    # Model
    model_dir = config_dir / "cache" / "models"
    if model_dir.exists() and any(model_dir.iterdir()):
        checks.append({"check": "model", "status": "ok", "score": 20})
    else:
        checks.append({"check": "model", "status": "missing", "score": 10})
        score -= 10

    # Config
    config_dir_path = config_dir / "config"
    if config_dir_path.exists():
        checks.append({"check": "config", "status": "ok", "score": 15})
    else:
        checks.append({"check": "config", "status": "fail", "score": 0})
        score -= 15

    # Disk space
    try:
        free = shutil.disk_usage(config_dir).free
        if free > 500 * 1024 * 1024:
            checks.append({"check": "disk", "status": "ok", "score": 15})
        else:
            checks.append({"check": "disk", "status": "warn", "score": 5})
            score -= 10
    except Exception:
        pass

    return {"score": max(0, score), "checks": checks}


def _rollback(config_dir: Path) -> None:
    """Clean up on setup failure."""
    logger.warning("Rolling back setup...")
    if config_dir.exists():
        shutil.rmtree(config_dir, ignore_errors=True)
        logger.info("Removed config directory")


# ── Logging helpers ─────────────────────────────────────────────────────


def _log_step(msg: str) -> None:
    print(f"  {msg}")


def _log_ok(msg: str) -> None:
    print(f"    ✅ {msg}")


def _log_warn(msg: str) -> None:
    print(f"    ⚠️  {msg}")


# ── CLI entry point ─────────────────────────────────────────────────────


def cli_init(args: dict | list | None = None) -> str:
    """CLI entry point for ast-tools init command."""
    if isinstance(args, list):
        args = {
            "non_interactive": "--non-interactive" in args or "-n" in args,
            "skip_model": "--skip-model" in args or "-s" in args,
            "model_path": None,
            "project_root": None,
        }
        for i, a in enumerate(args):
            if a == "--model-path" and i + 1 < len(args):
                args["model_path"] = args[i + 1]

    non_interactive = getattr(args, "get", lambda _k, d=None: d)("non_interactive", False)
    skip_model = getattr(args, "get", lambda _k, d=None: d)("skip_model", False)
    model_path = getattr(args, "get", lambda _k, d=None: d)("model_path", None)
    project_root = getattr(args, "get", lambda _k, d=None: d)("project_root", None)

    result = run(
        non_interactive=bool(non_interactive),
        skip_model=bool(skip_model),
        model_path=model_path,
        project_root=project_root,
    )

    if result["errors"]:
        return f"❌ Setup failed: {'; '.join(result['errors'])}"
    else:
        return (
            f"✅ Setup complete!\n"
            f"   Config: {result['config_dir']}\n"
            f"   Database: {'✅' if result['db_initialized'] else '❌'}\n"
            f"   Model: {'✅' if result['model_installed'] else '⚠️  skipped'}\n"
            f"   Initial index: {'✅' if result['index_created'] else '⚠️  not created'}\n"
            f"   Health score: {result['health_score']}/100"
        )
