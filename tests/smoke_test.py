"""Smoke test to verify the installed package works."""
import sys


def main() -> int:
    """Run smoke tests."""
    errors = []

    # 1. Core import
    try:
        from ast_tools.tools import TOOL_REGISTRY
        assert len(TOOL_REGISTRY) > 0, "TOOL_REGISTRY is empty"
        print(f"✅ Core import OK — {len(TOOL_REGISTRY)} tools registered")
    except Exception as e:
        errors.append(f"Core import failed: {e}")

    # 2. Server import
    try:
        from ast_tools._server import server
        assert server is not None
        print("✅ Server import OK")
    except Exception as e:
        errors.append(f"Server import failed: {e}")

    # 3. Project tools import
    try:
        from ast_tools._project_tools import (
            find_project_root,
            generate_project_json,
            project_info_summary,
        )
        assert callable(find_project_root)
        assert callable(project_info_summary)
        assert callable(generate_project_json)
        print("✅ Project tools import OK")
    except Exception as e:
        errors.append(f"Project tools import failed: {e}")

    # 4. CLI import
    try:
        from ast_tools.cli import main as cli_main
        assert callable(cli_main)
        print("✅ CLI import OK")
    except Exception as e:
        errors.append(f"CLI import failed: {e}")

    # 5. Version check
    try:
        import importlib.metadata
        version = importlib.metadata.version("rw-ast-tools")
        assert version == "0.2.0"
        print(f"✅ Version OK — {version}")
    except Exception as e:
        errors.append(f"Version check failed: {e}")

    if errors:
        print(f"\n❌ {len(errors)} smoke test(s) failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n✅ All smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
