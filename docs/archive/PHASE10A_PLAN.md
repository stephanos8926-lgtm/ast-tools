# Phase 10A Implementation Plan

**Generated:** 2026-06-25  
**Mode:** MEDIUM (TDD required, forward+reverse audits complete, user sign-off needed)  
**Status:** Pending sign-off  

---

## Overview

**Goal:** Implement three new MCP tools for ast-tools structural code intelligence enhancement.

**Timeline:** 6-9 days total
- Day 1-2: `code_validate_syntax`
- Day 3-5: `repo_skeleton`
- Day 6-7: `file_related_suggest`
- Day 8: Integration testing + docs + ship v0.2.0

**Files:** 7 new files (~950 lines), 1 modified file

---

## Kanban Board Setup

**Board:** `ast-tools-phase-10a` (create if not exists)

**Tasks to Create** (in dependency order):

### Phase 1: code_validate_syntax (Days 1-2)

```
Task 1.1: Create code_validate.py skeleton with Python validation
Task 1.2: Write test_code_validate.py — Python valid/invalid cases
Task 1.3: TDD cycle — Red (test fails) → Green (implement) → Refactor
Task 1.4: Add SQL validation (sqlparse library)
Task 1.5: Add Shell validation (bash -n subprocess)
Task 1.6: Add JavaScript validation (node --check fallback)
Task 1.7: Add TypeScript validation (tsc --noEmit)
Task 1.8: Add Rust validation (rustc --emit=metadata)
Task 1.9: Add Go validation (go build -o /dev/null)
Task 1.10: Register tool in __init__.py, update docstrings
Task 1.11: Run full test suite, verify coverage >90%
Task 1.12: Commit phase 1
```

### Phase 2: repo_skeleton (Days 3-5)

```
Task 2.1: Create repo_skeleton.py skeleton with project type detection
Task 2.2: Write test_repo_skeleton.py — Python project detection
Task 2.3: TDD cycle — Python detection (pyproject.toml, src/ layout)
Task 2.4: Add Node.js detection (package.json, *.js/ts)
Task 2.5: Add Go detection (go.mod, *.go)
Task 2.6: Add Rust detection (Cargo.toml, *.rs)
Task 2.7: Implement confidence scoring algorithm
Task 2.8: Implement key file identification
Task 2.9: Implement entry point detection (reuse project_info logic)
Task 2.10: Implement dependency graph (parse pyproject.toml, package.json, go.mod, Cargo.toml)
Task 2.11: Implement ASCII tree generation
Task 2.12: Register tool in __init__.py, update docstrings
Task 2.13: Test on ast-tools, NexusAgent, FORGE repos
Task 2.14: Run full test suite, verify coverage >90%
Task 2.15: Commit phase 2
```

### Phase 3: file_related_suggest (Days 6-7)

```
Task 3.1: Create file_related.py skeleton with test file detection
Task 3.2: Write test_file_related.py — test file pattern matching
Task 3.3: TDD cycle — Test file detection (test_*.py, */tests/*.py)
Task 3.4: Implement import relationship detection (reuse module_imports)
Task 3.5: Implement sibling detection (same-directory scan)
Task 3.6: Implement name matching across project (**/{stem}.py)
Task 3.7: Implement call graph integration (reuse structural_analysis)
Task 3.8: Implement confidence scoring + ranking
Task 3.9: Register tool in __init__.py, update docstrings
Task 3.10: Test on ast-tools codebase (verify semantic_search → test file)
Task 3.11: Run full test suite, verify coverage >90%
Task 3.12: Commit phase 3
```

### Phase 4: Integration + Release (Day 8)

```
Task 4.1: Integration test — Call all 3 tools via Hermes
Task 4.2: Update README.md with new tools
Task 4.3: Update ast-tools-usage skill with new tools
Task 4.4: Write PHASE10A_COMPLETE.md summary
Task 4.5: Bump version to 0.2.0 in pyproject.toml
Task 4.6: git commit, tag v0.2.0, push to GitHub
Task 4.7: Verify MCP discovery in Hermes (hermes tools list)
Task 4.8: Ship! 🚀
```

---

## Detailed Task Breakdown

### Task 1.1: Create code_validate.py skeleton

**Objective:** Create new tool file with Python validation working.

**Files:**
- Create: `src/ast_tools/tools/code_validate.py`
- Test: `tests/tools/test_code_validate.py`

**Step 1: Write skeleton code**

```python
# src/ast_tools/tools/code_validate.py
"""Code syntax validation for multiple languages."""

import ast
import time
from typing import Any

def _tool_code_validate(params: dict[str, Any]) -> dict[str, Any]:
    """
    Validate code syntax for multiple languages.
    
    Parameters:
        content: str — Code to validate
        language: str — Language (python, javascript, typescript, rust, go, sql, shell)
        file_path: Optional[str] — For context (tsconfig.json location, etc.)
    
    Returns:
        {
            "valid": bool,
            "errors": [{"line": int, "column": int, "message": str}],
            "warnings": [],
            "parser_used": str,
            "duration_ms": float
        }
    """
    start_time = time.time()
    
    content = params.get("content", "")
    language = params.get("language", "python").lower()
    file_path = params.get("file_path")
    
    if not content:
        return {
            "valid": False,
            "errors": [{"line": 0, "column": 0, "message": "Empty content"}],
            "parser_used": "none",
            "duration_ms": 0
        }
    
    VALIDATORS = {
        "python": _validate_python,
        "sql": _validate_sql,
        "shell": _validate_shell,
        "javascript": _validate_javascript,
        "typescript": _validate_typescript,
        "rust": _validate_rust,
        "go": _validate_go,
    }
    
    if language not in VALIDATORS:
        return {
            "valid": False,
            "errors": [{"line": 0, "column": 0, "message": f"Unsupported language: {language}"}],
            "parser_used": "none",
            "duration_ms": 0
        }
    
    try:
        result = VALIDATORS[language](content, file_path)
        result["duration_ms"] = (time.time() - start_time) * 1000
        return result
    except Exception as e:
        return {
            "valid": False,
            "errors": [{"line": 0, "column": 0, "message": str(e)}],
            "parser_used": language,
            "duration_ms": (time.time() - start_time) * 1000
        }


def _validate_python(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate Python syntax using ast.parse()."""
    try:
        ast.parse(content)
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "ast.parse"}
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [{
                "line": e.lineno or 0,
                "column": e.offset or 0,
                "message": f"SyntaxError: {e.msg}"
            }],
            "warnings": [],
            "parser_used": "ast.parse"
        }


def _validate_sql(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate SQL syntax using sqlparse."""
    try:
        import sqlparse
        parsed = sqlparse.parse(content)
        if not parsed:
            return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Failed to parse SQL"}], "warnings": [], "parser_used": "sqlparse"}
        # Basic validation: check for balanced parentheses
        if content.count('(') != content.count(')'):
            return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Unbalanced parentheses"}], "warnings": [], "parser_used": "sqlparse"}
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "sqlparse"}
    except ImportError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "sqlparse not installed. Run: pip install sqlparse"}], "warnings": [], "parser_used": "none"}
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": str(e)}], "warnings": [], "parser_used": "sqlparse"}


def _validate_shell(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate shell syntax using bash -n."""
    import subprocess
    try:
        result = subprocess.run(
            ["bash", "-n", "-c", content],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            # Parse bash error output
            error_lines = result.stderr.strip().split('\n')
            errors = []
            for line in error_lines:
                if line:
                    # Expected format: bash: line N: message
                    parts = line.split(':')
                    line_num = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                    errors.append({
                        "line": line_num,
                        "column": 0,
                        "message": ':'.join(parts[2:]).strip() if len(parts) > 2 else line
                    })
            return {"valid": False, "errors": errors, "warnings": [], "parser_used": "bash"}
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "bash"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Timeout after 5s"}], "warnings": [], "parser_used": "bash"}
    except FileNotFoundError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "bash not found"}], "warnings": [], "parser_used": "none"}


def _validate_javascript(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate JavaScript syntax using node --check (fallback to babel if available)."""
    import subprocess
    import tempfile
    import os
    
    # Try babel parser first (if available)
    try:
        import babel  # noqa: F401
        # Would use babel.parse() here if we add the dependency
        # For now, fall through to node --check
    except ImportError:
        pass
    
    # Use node --check
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        result = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        os.unlink(temp_path)
        
        if result.returncode != 0:
            # Parse node error (format: /path/file.js:line:column message)
            error_lines = result.stderr.strip().split('\n')
            errors = []
            for line in error_lines:
                if ':' in line:
                    parts = line.split(':')
                    try:
                        line_num = int(parts[1]) if len(parts) > 1 else 0
                        col_num = int(parts[2]) if len(parts) > 2 else 0
                        message = ':'.join(parts[3:]).strip() if len(parts) > 3 else line
                    except ValueError:
                        line_num, col_num = 0, 0
                        message = line
                    errors.append({"line": line_num, "column": col_num, "message": message})
            return {"valid": False, "errors": errors, "warnings": [], "parser_used": "node"}
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "node"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Timeout after 5s"}], "warnings": [], "parser_used": "node"}
    except FileNotFoundError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "node not found"}], "warnings": [], "parser_used": "none"}
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": str(e)}], "warnings": [], "parser_used": "node"}


def _validate_typescript(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate TypeScript syntax using tsc --noEmit."""
    import subprocess
    import tempfile
    import os
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        # Look for tsconfig.json in file_path directory if provided
        cmd = ["tsc", "--noEmit", "--skipLibCheck"]
        if file_path:
            import os
            config_dir = os.path.dirname(file_path)
            if os.path.exists(os.path.join(config_dir, "tsconfig.json")):
                cmd.extend(["-p", config_dir])
        
        result = subprocess.run(
            cmd + [temp_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(file_path) if file_path else None
        )
        os.unlink(temp_path)
        
        if result.returncode != 0:
            # Parse tsc error (format: file.ts(line,col): error TSXXXX: message)
            error_lines = result.stderr.strip().split('\n')
            errors = []
            for line in error_lines:
                if '(' in line and ')' in line:
                    try:
                        # Extract line,col from file.ts(line,col)
                        start = line.index('(') + 1
                        end = line.index(')')
                        line_col = line[start:end].split(',')
                        line_num = int(line_col[0]) if line_col[0].isdigit() else 0
                        col_num = int(line_col[1]) if len(line_col) > 1 and line_col[1].isdigit() else 0
                        message = line.split(':', 2)[2].strip() if ':' in line else line
                    except (ValueError, IndexError):
                        line_num, col_num = 0, 0
                        message = line
                    errors.append({"line": line_num, "column": col_num, "message": message})
                else:
                    errors.append({"line": 0, "column": 0, "message": line})
            return {"valid": False, "errors": errors, "warnings": [], "parser_used": "tsc"}
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "tsc"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Timeout after 10s"}], "warnings": [], "parser_used": "tsc"}
    except FileNotFoundError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "tsc not found. Install TypeScript: npm install -g typescript"}], "warnings": [], "parser_used": "none"}
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": str(e)}], "warnings": [], "parser_used": "tsc"}


def _validate_rust(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate Rust syntax using rustc --emit=metadata -Z no-codegen."""
    import subprocess
    import tempfile
    import os
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        # rustc requires edition flag
        result = subprocess.run(
            ["rustc", "--emit=metadata", "-Z", "no-codegen", "--edition=2021", temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        os.unlink(temp_path)
        # Clean up generated .rmeta file
        meta_file = temp_path.replace('.rs', '.rmeta')
        if os.path.exists(meta_file):
            os.unlink(meta_file)
        
        if result.returncode != 0:
            # Parse rustc error (format: error[E###]: file.rs:line:col message)
            error_lines = result.stderr.strip().split('\n')
            errors = []
            for line in error_lines:
                if ':' in line:
                    parts = line.split(':')
                    try:
                        line_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                        col_num = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                        message = ':'.join(parts[3:]).strip() if len(parts) > 3 else line
                    except ValueError:
                        line_num, col_num = 0, 0
                        message = line
                    errors.append({"line": line_num, "column": col_num, "message": message})
                else:
                    errors.append({"line": 0, "column": 0, "message": line})
            return {"valid": False, "errors": errors, "warnings": [], "parser_used": "rustc"}
        return {"valid": True, "errors": [], "warnings": [], "parser_used": "rustc"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Timeout after 10s"}], "warnings": [], "parser_used": "rustc"}
    except FileNotFoundError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "rustc not found"}], "warnings": [], "parser_used": "none"}
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": str(e)}], "warnings": [], "parser_used": "rustc"}


def _validate_go(content: str, file_path: str | None = None) -> dict[str, Any]:
    """Validate Go syntax using go build -o /dev/null."""
    import subprocess
    import tempfile
    import os
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "main.go")
            with open(temp_path, 'w') as f:
                f.write(content)
            
            # go build requires a module
            # Create minimal go.mod
            with open(os.path.join(tmpdir, "go.mod"), 'w') as f:
                f.write("module temp\n\ngo 1.21\n")
            
            result = subprocess.run(
                ["go", "build", "-o", "/dev/null", "."],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir
            )
            
            if result.returncode != 0:
                # Parse go build error (format: ./file.go:line:col: message)
                error_lines = result.stderr.strip().split('\n')
                errors = []
                for line in error_lines:
                    if ':' in line:
                        parts = line.split(':')
                        try:
                            line_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                            col_num = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
                            message = ':'.join(parts[3:]).strip() if len(parts) > 3 else line
                        except ValueError:
                            line_num, col_num = 0, 0
                            message = line
                        errors.append({"line": line_num, "column": col_num, "message": message})
                    else:
                        errors.append({"line": 0, "column": 0, "message": line})
                return {"valid": False, "errors": errors, "warnings": [], "parser_used": "go"}
            return {"valid": True, "errors": [], "warnings": [], "parser_used": "go"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "Timeout after 10s"}], "warnings": [], "parser_used": "go"}
    except FileNotFoundError:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": "go not found"}], "warnings": [], "parser_used": "none"}
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "column": 0, "message": str(e)}], "warnings": [], "parser_used": "go"}
```

**Step 2: Register tool in __init__.py**

```python
# src/ast_tools/tools/__init__.py
# Add import
from .code_validate import _tool_code_validate

# Register
register_tool("code_validate_syntax", _tool_code_validate)
```

**Step 3: Write initial test (Python only)**

```python
# tests/tools/test_code_validate.py
"""Tests for code_validate syntax validation tool."""

import pytest
from src.ast_tools.tools.code_validate import _tool_code_validate


class TestPythonValidation:
    def test_valid_function(self):
        result = _tool_code_validate({
            "content": "def foo():\n    return 42",
            "language": "python"
        })
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["parser_used"] == "ast.parse"
    
    def test_valid_class(self):
        result = _tool_code_validate({
            "content": "class Foo:\n    def __init__(self):\n        pass",
            "language": "python"
        })
        assert result["valid"] is True
    
    def test_invalid_syntax_missing_colon(self):
        result = _tool_code_validate({
            "content": "def foo()\n    pass",
            "language": "python"
        })
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["line"] == 1
        assert "SyntaxError" in result["errors"][0]["message"]
    
    def test_invalid_syntax_unclosed_paren(self):
        result = _tool_code_validate({
            "content": "print('hello'",
            "language": "python"
        })
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
    
    def test_empty_content(self):
        result = _tool_code_validate({
            "content": "",
            "language": "python"
        })
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert "Empty" in result["errors"][0]["message"]
    
    def test_unsupported_language(self):
        result = _tool_code_validate({
            "content": "print 42",
            "language": "cobol"
        })
        assert result["valid"] is False
        assert "Unsupported" in result["errors"][0]["message"]
    
    def test_duration_included(self):
        result = _tool_code_validate({
            "content": "x = 1",
            "language": "python"
        })
        assert "duration_ms" in result
        assert result["duration_ms"] >= 0
```

**Step 4: Run test (should fail — TDD red)**

```bash
cd /home/sysop/Workspaces/ast-tools
python3 -m pytest tests/tools/test_code_validate.py::TestPythonValidation::test_valid_function -xvs
# Expected: FAIL (tool doesn't exist yet)
```

**Step 5: Implement minimal code to pass (TDD green)**

[Code from Step 1]

**Step 6: Run test (should pass)**

```bash
python3 -m pytest tests/tools/test_code_validate.py::TestPythonValidation -v
# Expected: 7 passed
```

**Step 7: Commit**

```bash
git add src/ast_tools/tools/code_validate.py tests/tools/test_code_validate.py src/ast_tools/tools/__init__.py
git commit -m "feat: add code_validate_syntax tool with Python validation (phase 10a)"
```

---

[Continue with remaining tasks in same TDD format...]

---

## Completion Checklist

- [ ] All 3 tools implemented and tested
- [ ] Test coverage >90% for new code
- [ ] Integration test passes (call all tools via Hermes)
- [ ] README.md updated with new tools
- [ ] ast-tools-usage skill updated
- [ ] PHASE10A_COMPLETE.md written
- [ ] Version bumped to 0.2.0
- [ ] Git tag v0.2.0 created
- [ ] Pushed to GitHub
- [ ] Verified in Hermes (hermes tools list)

---

**Ready for sign-off.** Review with plan-and-audit skill (medium mode) before user approval.