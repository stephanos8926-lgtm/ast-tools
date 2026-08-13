#!/bin/bash
set -euo pipefail

echo "🗑️  AST-Tools Plugin Uninstaller"
echo "================================="

PLUGIN_NAME="${1:-}"

if [ -z "$PLUGIN_NAME" ]; then
    echo "Usage: ./uninstall.sh <plugin-name>"
    echo ""
    echo "Installed plugins:"
    ls -1 ~/.hermes/plugins/ | grep ast-tools || echo "  (none found)"
    exit 1
fi

if [ ! -d "~/.hermes/plugins/$PLUGIN_NAME" ]; then
    echo "❌ Plugin '$PLUGIN_NAME' not installed"
    exit 1
fi

# Remove plugin
rm -rf "~/.hermes/plugins/$PLUGIN_NAME"

echo "✅ Plugin '$PLUGIN_NAME' removed"
echo ""
echo "Remaining ast-tools plugins:"
ls -1 ~/.hermes/plugins/ | grep ast-tools || echo "  (none)"