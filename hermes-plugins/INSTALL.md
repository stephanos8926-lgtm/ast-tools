# Installation Guide

This guide covers all methods to install AST-Tools Hermes Plugins.

## Prerequisites

Before installing, ensure you have:

1. **Hermes Agent** installed and configured
   - Version: Any recent version with plugin support
   - Check: `hermes --version`

2. **Python 3.10+** available
   - Check: `python3 --version`

3. **Plugins directory** exists
   - Path: `~/.hermes/plugins/`
   - Create if needed: `mkdir -p ~/.hermes/plugins`

## Quick Install Methods

### Method 1: Install All Plugins (Recommended)

```bash
# Navigate to hermes-plugins directory
cd /path/to/hermes-plugins

# Run the all-in-one installer
./scripts/install-all.sh
```

This will:
- Install all plugins
- Verify each installation
- Restart Hermes (with confirmation)

### Method 2: Install Individual Plugin

```bash
# Install specific plugin
./scripts/install.sh ast-tools-context

# Or
./scripts/install.sh ast-tools-tokens
```

### Method 3: Manual Copy

```bash
# Copy plugin directory
cp -r ast-tools-context ~/.hermes/plugins/
cp -r ast-tools-tokens ~/.hermes/plugins/

# Verify installation
ls -la ~/.hermes/plugins/

# Restart Hermes
hermes restart
```

## Detailed Installation Steps

### Step 1: Prepare Your System

```bash
# Ensure plugins directory exists
mkdir -p ~/.hermes/plugins

# Backup existing plugins (optional but recommended)
cp -r ~/.hermes/plugins ~/.hermes/plugins.backup.$(date +%Y%m%d)
```

### Step 2: Choose Installation Method

Select one of the methods above based on your needs.

### Step 3: Verify Installation

```bash
# List installed plugins
hermes plugins list

# Or check manually
ls -la ~/.hermes/plugins/ast-tools-*/
```

Expected output:
```
ast-tools-context/
  __init__.py
  plugin.yaml
  README.md

ast-tools-tokens/
  __init__.py
  plugin.yaml
  README.md
```

### Step 4: Test Plugins

Start a new Hermes session and test:

```bash
# Start Hermes
hermes

# Test ast-tools-context
Ask: "What is ast_grep?"

# You should see AST-Tools documentation injected in the response
```

### Step 5: Enable Logging (Optional)

To see plugin activity in logs:

```bash
# Edit Hermes config
nano ~/.hermes/config.yaml

# Add or modify:
logging:
  level: warning  # or debug for more detail

# Restart Hermes
hermes restart
```

## Installation Scripts Reference

### `install.sh`

Installs a single plugin.

**Usage:**
```bash
./scripts/install.sh <plugin-name>
```

**Example:**
```bash
./scripts/install.sh ast-tools-context
```

**Options:**
- No options required
- Interactive confirmation before installation
- Automatic verification after install

### `install-all.sh`

Installs all plugins in the package.

**Usage:**
```bash
./scripts/install-all.sh
```

**Options:**
- `--dry-run`: Show what would be installed without making changes
- `--no-restart`: Skip Hermes restart prompt
- `--verbose`: Show detailed output

**Example:**
```bash
./scripts/install-all.sh --dry-run
```

### `uninstall.sh`

Removes plugins from Hermes.

**Usage:**
```bash
./scripts/uninstall.sh <plugin-name>
# or
./scripts/uninstall.sh --all
```

**Options:**
- `--keep-config`: Don't remove configuration files
- `--verbose`: Show detailed output

### `verify.sh`

Verifies plugin integrity and syntax.

**Usage:**
```bash
./scripts/verify.sh
```

**Checks:**
- File structure
- YAML syntax
- Python syntax
- Plugin metadata

## Troubleshooting Installation

### Common Issues

#### "Plugin not found after installation"

**Solution:**
1. Verify file structure:
   ```bash
   ls -la ~/.hermes/plugins/ast-tools-context/
   ```
2. Check that `__init__.py` and `plugin.yaml` exist
3. Restart Hermes: `hermes restart`

#### "Syntax error in plugin"

**Solution:**
1. Check Python syntax:
   ```bash
   python3 -m py_compile ~/.hermes/plugins/ast-tools-context/__init__.py
   ```
2. Check YAML syntax:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('~/.hermes/plugins/ast-tools-context/plugin.yaml'))"
   ```
3. Reinstall if needed

#### "Permission denied"

**Solution:**
```bash
# Fix permissions
chmod -R 755 ~/.hermes/plugins/ast-tools-*/
chown -R $USER:$USER ~/.hermes/plugins/ast-tools-*/
```

#### "Plugin loads but doesn't work"

**Solution:**
1. Enable debug logging: `hermes --log-level debug`
2. Check logs for error messages
3. Verify MCP server is configured (for ast-tools functionality)
4. Test with relevant queries

### Getting Help

If installation fails:

1. Check individual plugin READMEs
2. Review troubleshooting section in main README
3. Enable debug logging and check for errors
4. Verify prerequisites are met

## Post-Installation

### Verify All Plugins

```bash
./scripts/verify.sh
```

### Test Context Injection

```
User: "How do I search for function definitions?"

Expected: Response includes ast_grep documentation
```

### Test Token Tracking

```
User: "Run ast_grep on my entire codebase"

Expected: [Later] Warning if result exceeds budget
```

### Test Context Pressure

Start a very long conversation to trigger context pressure monitoring.

## Uninstallation

To remove plugins:

```bash
# Remove specific plugin
./scripts/uninstall.sh ast-tools-context

# Remove all
./scripts/uninstall.sh --all

# Or manually
rm -rf ~/.hermes/plugins/ast-tools-context
rm -rf ~/.hermes/plugins/ast-tools-tokens

# Restart Hermes
hermes restart
```

## Updates

Currently, plugins are version 1.0.0. To update:

1. Download new version
2. Run `./scripts/uninstall.sh --all`
3. Run `./scripts/install-all.sh`
4. Verify with `./scripts/verify.sh`

## Next Steps

After installation:
1. Read USAGE.md for detailed usage guide
2. Review individual plugin READMEs
3. Configure settings if needed
4. Start using AST-Tools with enhanced Hermes integration

---

**Installation Complete** → Proceed to [USAGE.md](USAGE.md)