#!/usr/bin/env python3
"""MCP tools for project registry management.

Manages a list of indexed projects in the ast-tools database,
allowing multi-project analysis without running multiple servers.
"""

from pathlib import Path
from typing import Any

from ..database.connection import get_connection, get_db_path
from ..server_config import load_server_config


def _get_db(project_root: str | None = None):
    """Get database connection for project or global DB."""
    db_path = get_db_path(project_root=project_root)
    return get_connection(db_path)


def project_add(args: dict) -> dict:
    """Add a project to the registry.

    Args:
        path: Project root path (required)
        name: Optional friendly name (defaults to directory name)
        auto_watch: Whether to add to daemon watch paths (default: true)

    Returns:
        Status dict with project info.
    """
    path = args.get("path", "")
    if not path:
        return {"status": "error", "message": "path is required"}

    path = str(Path(path).resolve())
    if not Path(path).exists():
        return {"status": "error", "message": f"Path does not exist: {path}"}

    db = _get_db()
    try:
        # Check for duplicate
        existing = db.execute(
            "SELECT * FROM projects WHERE root_path = ?", (path,)
        ).fetchone()
        if existing:
            return {"status": "exists", "project": dict(existing), "message": "Project already registered"}

        # Create project entry
        import uuid
        from datetime import datetime

        project_id = str(uuid.uuid4())
        name = args.get("name") or Path(path).name
        now = datetime.now().isoformat()

        db.execute(
            """
            INSERT INTO projects
            (id, name, root_path, added_at, auto_watch, last_indexed_at, symbol_count, file_count, index_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                path,
                now,
                1 if args.get("auto_watch", True) else 0,
                None,
                0,
                0,
                "pending",
            ),
        )
        db.commit()

        project = {
            "id": project_id,
            "name": name,
            "path": path,
            "auto_watch": args.get("auto_watch", True),
            "added_at": now,
        }

        # If daemon running and auto_watch, add to watch paths
        if project["auto_watch"]:
            _add_to_daemon_watch(path)

        return {"status": "added", "project": project}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def project_remove(args: dict) -> dict:
    """Remove a project from the registry.

    Args:
        path: Project root path to remove

    Returns:
        Status dict
    """
    path = args.get("path", "")
    if not path:
        return {"status": "error", "message": "path is required"}

    path = str(Path(path).resolve())

    db = _get_db()
    try:
        cursor = db.execute("DELETE FROM projects WHERE root_path = ?", (path,))
        db.commit()
        if cursor.rowcount > 0:
            return {"status": "removed", "path": path}
        else:
            return {"status": "not_found", "message": f"Project not registered: {path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def project_list(args: dict) -> dict:
    """List all registered projects.

    Returns:
        Dict with list of projects
    """
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT * FROM projects ORDER BY added_at DESC"
        ).fetchall()
        projects = [dict(r) for r in rows]
        return {"projects": projects, "total": len(projects)}
    except Exception as e:
        return {"status": "error", "message": str(e), "projects": [], "total": 0}
    finally:
        db.close()


def project_info(args: dict) -> dict:
    """Get detailed info for a project.

    Args:
        path: Project root path (optional, if omitted returns all projects)

    Returns:
        Project info dict
    """
    path = args.get("path")
    if not path:
        return project_list(args)

    path = str(Path(path).resolve())

    db = _get_db()
    try:
        # Check if registered
        project = db.execute(
            "SELECT * FROM projects WHERE root_path = ?", (path,)
        ).fetchone()

        if not project:
            return {"status": "not_found", "message": f"Project not registered: {path}"}

        project = dict(project)

        # Get index stats from the project's DB
        project_db = _get_db(project_root=path)
        stats = {}
        try:
            # Symbol counts by kind
            for row in project_db.execute(
                "SELECT kind, COUNT(*) as count FROM symbols GROUP BY kind"
            ):
                stats[f"symbols_{row['kind']}"] = row["count"]
            stats["total_symbols"] = sum(stats.values())

            # File count
            stats["files_indexed"] = project_db.execute(
                "SELECT COUNT(DISTINCT file_path) FROM symbols"
            ).fetchone()[0]

            # Embedding count
            stats["embeddings"] = project_db.execute(
                "SELECT COUNT(*) FROM symbols_vec"
            ).fetchone()[0]

            # Edge count
            stats["edges"] = project_db.execute(
                "SELECT COUNT(*) FROM edges"
            ).fetchone()[0]

            project["stats"] = stats
        except Exception:
            project["stats"] = {}
        finally:
            project_db.close()

        return {"status": "found", "project": project}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def _check_indexed(path: str) -> bool:
    """Check if project has an index database."""
    db_path = get_db_path(project_root=path)
    return db_path.exists()


def _get_index_stats(path: str) -> dict | None:
    """Get index statistics for a project."""
    try:
        from ..database.connection import get_connection

        db_path = get_db_path(project_root=path)
        if not db_path.exists():
            return None

        conn = get_connection(str(db_path))
        stats = {}

        # Symbol counts
        for row in conn.execute("SELECT kind, COUNT(*) as count FROM symbols GROUP BY kind"):
            stats[f"symbols_{row['kind']}"] = row["count"]
        stats["total_symbols"] = sum(stats.values())

        # File count
        stats["files_indexed"] = conn.execute(
            "SELECT COUNT(DISTINCT file_path) FROM symbols"
        ).fetchone()[0]

        # Embedding count
        stats["embeddings"] = conn.execute(
            "SELECT COUNT(*) FROM symbols_vec"
        ).fetchone()[0]

        return stats
    except Exception:
        return None


def _add_to_daemon_watch(cfg: dict[str, Any], path: str) -> None:
    """Add path to daemon watch_paths."""
    watch_paths = cfg.setdefault("daemon", {}).setdefault("watch_paths", [])
    if path not in watch_paths:
        watch_paths.append(path)
        _save_config(cfg, path)


def _remove_from_daemon_watch(cfg: dict[str, Any], path: str) -> None:
    """Remove path from daemon watch_paths."""
    watch_paths = cfg.get("daemon", {}).get("watch_paths", [])
    if path in watch_paths:
        watch_paths.remove(path)
        _save_config(cfg, path)


def _get_config() -> dict[str, Any]:
    """Load server config (includes project registry)."""
    return load_server_config()


def _save_config(cfg: dict[str, Any], project_root: str | None = None) -> None:
    """Save config to YAML file."""
    import yaml

    config_path = Path.home() / ".config" / "rw-ast-tools" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))


def register_tools(registry: dict) -> None:
    """Register project registry tools."""
    from ..tools import register_tool

    register_tool("project_add", project_add)
    register_tool("project_remove", project_remove)
    register_tool("project_list", project_list)
    register_tool("project_info", project_info)