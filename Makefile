# AST-Tools Makefile — Development convenience commands
#
# Usage:
#   make fastcheck    — Run smoke tests (~15s, for pre-commit/push sanity)
#   make unit        — Run unit tests (~10s)
#   make integration — Run integration tests (skips smoke, slow, e2e)
#   make test        — Run full test suite (may hit RAM limit on 4GB)
#   make model       — Run slow tests (embedding model required)

.PHONY: fastcheck unit integration test model

# Fast pre-commit gate: smoke + governance + CLI (~15s)
fastcheck:
	uv run --group dev python -m pytest -m "smoke" --no-header -q -p no:xdist -p no:cacheprovider

# Unit tests only (~10s)
unit:
	uv run --group dev python -m pytest -m "unit" --no-header -q -p no:xdist -p no:cacheprovider

# Integration tests (skip smoke, slow, e2e)
integration:
	uv run --group dev python -m pytest -m "integration" --no-header -q -p no:xdist -p no:cacheprovider

# Full test suite (may timeout on 4GB — use tiered targets instead)
test:
	uv run --group dev python -m pytest --tb=short -p no:xdist -p no:cacheprovider

# Model-heavy tests (embedding)
model:
	uv run --group dev python -m pytest -m "slow" --no-header -q -p no:xdist -p no:cacheprovider