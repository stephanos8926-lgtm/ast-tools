#!/bin/bash

set -e

# publish.sh — Build and publish the ast-tools-mcp package to PyPI.
#
# Usage: PYPI_TOKEN=pypi-... ./scripts/publish.sh
#
# The CLI entry point remains "ast" regardless of the PyPI package name.
# Only the package name in pyproject.toml changes for distribution.

if [ -z "$PYPI_TOKEN" ]; then
  echo "Error: PYPI_TOKEN environment variable is not set."
  echo "Usage: PYPI_TOKEN=pypi-... $0"
  exit 1
fi

cd "$(dirname "$0")/.."

echo "==> Step 1: Building package with uv..."
uv build

echo ""
echo "==> Step 2: Publishing to PyPI..."
uv publish --token "$PYPI_TOKEN"

echo ""
echo "==> Done! Package published successfully."
echo "    CLI entry points remain: ast-tools, ast-tools-server, ast-tools-project"
echo "    PyPI package name:       ast-tools-mcp"
