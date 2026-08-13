#!/bin/bash
set -euo pipefail

echo "🚀 AST-Tools All Plugins Installer"
echo "==================================="

# Create plugins directory if it doesn't exist
mkdir -p ~/.hermes/plugins

# Install all plugins
for plugin_dir in ast-tools-*/; do
    if [ -d "$plugin_dir" ]; then
        echo "Installing: $plugin_dir"
        cp -r "$plugin_dir" ~/.hermes/plugins/
        echo "✅ $plugin_dir installed"
    fi
done

echo ""
echo "✅ All plugins installed successfully!"
echo ""
echo "Installed plugins:"
ls -1 ~/.hermes/plugins/ | grep ast-tools || true

echo ""
echo "Next steps:"
echo "  1. Restart Hermes: hermes restart"
echo "  2. Verify plugins: hermes plugins list"
echo "  3. Test functionality: Ask about code analysis"