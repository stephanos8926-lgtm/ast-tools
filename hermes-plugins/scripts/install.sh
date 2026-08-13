#!/bin/bash
set -euo pipefail

echo "🚀 AST-Tools Hermes Plugin Installer"
echo "====================================="

PLUGIN_NAME="${1:-}"

if [ -z "$PLUGIN_NAME" ]; then
    echo "Usage: ./install.sh <plugin-name>"
    echo ""
    echo "Available plugins:"
    ls -1 | grep -E '^ast-tools-'
    exit 1
fi

if [ ! -d "$PLUGIN_NAME" ]; then
    echo "❌ Plugin '$PLUGIN_NAME' not found"
    exit 1
fi

echo "Installing plugin: $PLUGIN_NAME"

# Create plugins directory if it doesn't exist
mkdir -p ~/.hermes/plugins

# Copy plugin
cp -r "$PLUGIN_NAME" ~/.hermes/plugins/

echo "✅ Plugin installed to ~/.hermes/plugins/$PLUGIN_NAME"

# Verify installation
if [ -f "~/.hermes/plugins/$PLUGIN_NAME/__init__.py" ]; then
    echo "✅ Plugin files verified"
else
    echo "❌ Plugin file verification failed"
    exit 1
fi

echo ""
echo "Next steps:"
echo "  1. Restart Hermes: hermes restart"
echo "  2. Verify plugin: hermes plugins list"