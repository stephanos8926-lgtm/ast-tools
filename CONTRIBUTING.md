# Contributing to ast-tools

Thank you for your interest in contributing to ast-tools! We welcome
contributions of all kinds — bug fixes, new features, documentation
improvements, and performance optimizations.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Adding a New Tool](#adding-a-new-tool)

## Code of Conduct

This project adheres to the [Contributor Covenant](CODE_OF_CONDUCT.md).
By participating, you agree to uphold this code. Report unacceptable
behavior to <steven@rapidwebs.io>.

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/ast-tools.git`
3. **Set up** a development environment (see below).
4. **Create a branch** for your changes: `git checkout -b feat/my-feature`
5. **Make changes** following the coding standards.
6. **Run tests** before committing.
7. **Push** and open a pull request.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
# Using uv (recommended)
uv sync --all-extras

# Using pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files  # Verify everything passes
```

## Coding Standards

### Python

- **Line length**: 100 characters maximum
- **Formatting**: Ruff formatter (matching `ruff format`)
- **Linting**: All code must pass `ruff check` with no errors
- **Type hints**: Required for all public functions and methods
- **Docstrings**: Google-style docstrings for all public APIs

### Tool Implementation Pattern

Every tool follows a consistent pattern:

```python
def _tool_my_new_tool(params: dict[str, Any]) -> dict[str, Any]:
    \"\"\"Brief description of what the tool does.

    Args:
        param_name: Description (required)
        optional_param: Description (default: value)

    Returns:
        Dict with result keys.
    \"\"\"
    # 1. Extract and validate params
    input_val = params.get("input_param", default)
    
    # 2. Process
    result = do_something(input_val)
    
    # 3. Return structured response
    return {"status": "ok", "result": result}
```

### Directory Structure

```
src/ast_tools/tools/         # Tool implementations (one file per tool or group)
src/ast_tools/database/       # Database layer
src/ast_tools/indexer/        # Code indexing
src/ast_tools/embeddings/     # Embedding models
tests/                        # Test files mirror src structure
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/tools/test_file_related.py -v

# Run with coverage
pytest tests/ --cov=src/ast_tools
```

### Test Requirements

- **All new code must have tests.** No exceptions.
- Tests should use `tmp_path` fixture for filesystem operations.
- Integration tests against real ast-tools files are encouraged.
- Test behavior, not implementation — use the public API.

### TDD Process

For complex changes, follow TDD:

1. Write a **failing test** that describes the desired behavior
2. Confirm it fails (`pytest tests/test_foo.py -v`)
3. Implement the minimal code to make it pass
4. Confirm it passes
5. Refactor with confidence

## Pull Request Process

1. **One change per PR** — keep pull requests focused.
2. **Write a clear title** using conventional commits:
   - `feat: add new tool for X`
   - `fix: correct crash when Y is missing`
   - `perf: reduce index time by 40%`
   - `docs: update README with new tool list`
   - `refactor: extract common Z into shared module`
3. **Reference issues** — if your PR fixes an issue, include `Fixes #123`.
4. **Update docs** — if you add or change behavior, update the relevant docs.
5. **Add tests** — your PR must include tests for new or changed code.
6. **Pass CI** — all checks must pass before merging.
7. **Get a review** — at least one maintainer must approve.

### PR Checklist

```markdown
- [ ] Code follows style guidelines (ruff check passes)
- [ ] Tests added/updated and passing
- [ ] Documentation updated (README, docs/, CLI reference)
- [ ] CHANGELOG.md updated
- [ ] No new warnings or errors
- [ ] Backward compatible (or breaking changes documented)
```

## Adding a New Tool

1. **Create the implementation file** in `src/ast_tools/tools/`
2. **Register** in `src/ast_tools/tools/__init__.py` (import + `register_tool()`)
3. **Write tests** in `tests/tools/`
4. **Update docs** — add to README tool table and CLI reference
5. **Update CHANGELOG.md**
6. **Run full test suite** — `pytest tests/ -v`

---

Thank you for contributing to ast-tools! 🚀
