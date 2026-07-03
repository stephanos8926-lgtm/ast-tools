## Description

<!-- Provide a clear, concise description of the changes. -->

Fixes #(issue)

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that breaks existing behavior)
- [ ] Performance improvement
- [ ] Documentation update
- [ ] Refactoring (no functional changes)

## Checklist

### Code Quality

- [ ] Code follows project style guidelines (`ruff check` passes)
- [ ] Type hints added for all public functions
- [ ] Google-style docstrings for public APIs
- [ ] No new warnings or errors

### Tests

- [ ] Tests added/updated for new or changed code
- [ ] All tests pass (`pytest tests/ -q`)
- [ ] Coverage maintained or improved

### Documentation

- [ ] README updated if tool count or categories changed
- [ ] CLI reference updated if commands changed
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Documentation reflects actual behavior

### Tool Registration

- [ ] Tool registered in `src/ast_tools/tools/__init__.py`
- [ ] Tool schema added (input parameters documented)
- [ ] Backward compatible or breaking changes noted

## Additional Notes

<!-- Any special considerations, migration steps, or context for reviewers. -->