#!/bin/bash
set -euo pipefail

echo "🔍 AST-Tools Plugin Verification"
echo "================================="

CHECKS_PASSED=0
CHECKS_FAILED=0

check() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
        ((CHECKS_PASSED++))
    else
        echo "❌ $1"
        ((CHECKS_FAILED++))
    fi
}

# Check installed plugins
echo "Checking installed plugins..."
for plugin_dir in ~/.hermes/plugins/ast-tools-*; do
    if [ -d "$plugin_dir" ]; then
        plugin_name=$(basename "$plugin_dir")
        
        # Check __init__.py exists
        test -f "$plugin_dir/__init__.py"
        check "$plugin_name: __init__.py exists"
        
        # Check plugin.yaml exists
        test -f "$plugin_dir/plugin.yaml"
        check "$plugin_name: plugin.yaml exists"
        
        # Validate YAML syntax
        python3 -c "import yaml; yaml.safe_load(open('$plugin_dir/plugin.yaml'))" 2>/dev/null
        check "$plugin_name: plugin.yaml valid YAML"
        
        # Check Python syntax
        python3 -m py_compile "$plugin_dir/__init__.py" 2>/dev/null
        check "$plugin_name: __init__.py valid Python"
    fi
done

# Check installation state
echo ""
echo "Checking Hermes state..."

# Check if Hermes is running
if pgrep -f "hermes" > /dev/null 2>&1; then
    echo "✅ Hermes is running"
    ((CHECKS_PASSED++))
else
    echo "⚠️  Hermes is not running (restart required after install)"
    ((CHECKS_FAILED++))
fi

echo ""
echo "================================"
echo "Results: $CHECKS_PASSED passed, $CHECKS_FAILED failed"

if [ $CHECKS_FAILED -gt 0 ]; then
    echo ""
    echo "⚠️  Some checks failed."
    echo "Try: ./install-all.sh && hermes restart"
    exit 1
else
    echo ""
    echo "✅ All checks passed! Plugins ready."
    exit 0
fi