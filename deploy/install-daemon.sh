#!/bin/bash
# install-daemon.sh — Automated rw-ast-tools systemd daemon installer
# Run from ast-tools project root or deploy/ directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_FILE="$SCRIPT_DIR/rw-ast-tools.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"
TARGET_SERVICE="$USER_SERVICE_DIR/rw-ast-tools.service"
CACHE_DIR="$HOME/.cache/rw-ast-tools"
CONFIG_DIR="$HOME/.config/rw-ast-tools"

AST_TOOLS_SERVER="/home/sysop/Workspaces/ast-tools/.venv/bin/ast-tools-server"

echo "🔧 rw-ast-tools daemon installer"
echo "=================================="

# Check prerequisites
echo "Checking prerequisites..."

if ! test -x "$AST_TOOLS_SERVER"; then
    echo "❌ ast-tools-server not found at $AST_TOOLS_SERVER"
    echo "   Ensure the .venv is set up in $PROJECT_ROOT"
    exit 1
fi

if ! systemctl --user --version &> /dev/null; then
    echo "❌ systemd user mode not available"
    exit 1
fi

echo "✅ ast-tools-server found: $AST_TOOLS_SERVER"
echo "✅ systemd user mode available"

# Create directories
echo ""
echo "Creating directories..."
mkdir -p "$USER_SERVICE_DIR"
mkdir -p "$CACHE_DIR"
mkdir -p "$CONFIG_DIR"

# Copy service file
echo "Installing systemd service..."
cp "$SERVICE_FILE" "$TARGET_SERVICE"
echo "✅ Service installed to $TARGET_SERVICE"

# Create default config if not exists
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Creating default config..."
    cat > "$CONFIG_FILE" << EOF
server:
  mode: "daemon"
  timeout_seconds: 900

daemon:
  socket_path: "$HOME/.cache/rw-ast-tools/server.sock"
  watchdogs: true
  max_codebases: 10

watchdog:
  enabled: true
  debounce_ms: 100
  auto_index: true
  metrics_ttl_hours: 168
EOF
    echo "✅ Default config created at $CONFIG_FILE"
else
    echo "⚠️ Config already exists at $CONFIG_FILE — skipping"
fi

# Reload systemd
echo ""
echo "Reloading systemd daemon..."
systemctl --user daemon-reload
echo "✅ systemd reloaded"

# Enable and start
echo ""
echo "Enabling and starting service..."
systemctl --user enable --now rw-ast-tools

# Wait a moment for startup
sleep 2

# Check status
echo ""
echo "Checking service status..."
if systemctl --user is-active --quiet rw-ast-tools; then
    echo "✅ Service is RUNNING"
    systemctl --user status rw-ast-tools --no-pager -l
else
    echo "❌ Service failed to start"
    echo "Check logs: journalctl --user -u rw-ast-tools -n 50"
    exit 1
fi

# Verify socket
echo ""
echo "Verifying Unix socket..."
SOCKET_PATH="${HOME}/.cache/rw-ast-tools/server.sock"
if [[ -S "$SOCKET_PATH" ]]; then
    echo "✅ Socket exists at $SOCKET_PATH"
else
    echo "⚠️ Socket not found at $SOCKET_PATH (may need more time)"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Usage:"
echo "  - As MCP server: configure socat to connect to $SOCKET_PATH"
echo "  - Via CLI: ast search \"query\" --project-root /path/to/project"
echo "  - Logs: journalctl --user -u rw-ast-tools -f"
echo "  - Config: $CONFIG_FILE"