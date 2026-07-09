
# Thought Experiments: Multi-Language Auto-Fix Scenarios
Date: 2026-07-08

## Scenario 1: Python Project — "FastAPI Microservice"

### Context
A team maintains a FastAPI microservice with 50+ files. They need to:
1. Fix linting issues (Ruff)
2. Sort imports (isort/ruff)
3. Format code (Black/ruff)
4. Fix type hints (pyright/mypy)
5. Apply FastAPI-specific fixes (unused path params, response models)

### Current Workflow (Manual)
```bash
# Step 1: Lint
ruff check .
# Step 2: Fix
ruff check --fix .
# Step 3: Format
ruff format .
# Step 4: Type check
pyright .
# Step 5: Fix type issues manually
# Step 6: Re-run lint/format
```

### Pain Points
- Multiple passes needed (fix → format → lint again)
- Type checker runs separately, no auto-fix
- FastAPI rules are in Ruff but need `--unsafe-fixes` for some
- No unified "fix everything" command
- CI needs multiple steps

### Ideal Workflow
```bash
ast fix --all          # Does everything: lint-fix → format → type-fix (where safe)
ast fix --check        # CI mode: validates, exits non-zero if issues
ast fix --diff         # Preview changes
ast fix --only ruff    # Only Ruff fixes
ast fix --only format  # Only formatting
```

---

## Scenario 2: TypeScript/React Project — "Next.js Dashboard"

### Context
A Next.js 14 project with TypeScript, React, Tailwind. Needs:
1. ESLint fixes (with TypeScript ESLint)
2. Prettier formatting
3. Import organization (eslint-plugin-import)
4. React-specific fixes (hooks rules, JSX)
5. TypeScript compiler fixes (unused vars, strict null checks)

### Current Workflow
```bash
# ESLint
npx eslint . --fix
# Prettier
npx prettier --write .
# TypeScript
npx tsc --noEmit
# Manual fix for TS errors
```

### Pain Points
- ESLint + Prettier conflict (need eslint-config-prettier)
- TypeScript compiler doesn't auto-fix
- Import organization is a separate plugin
- Multiple config files (.eslintrc, .prettierrc, tsconfig.json)
- No unified pipeline

### Ideal Workflow
```bash
ast fix --all                    # ESLint fix → Prettier → organize imports → tsc suggestions
ast fix --only eslint            # Just ESLint
ast fix --only prettier          # Just Prettier
ast fix --lang typescript        # Language-specific
```

---

## Scenario 3: Go Project — "gRPC Service"

### Context
A Go gRPC service with protocol buffers. Needs:
1. gofmt formatting
2. goimports for import organization
3. golangci-lint fixes
4. govulncheck for security
5. Protobuf formatting (buf format)

### Current Workflow
```bash
gofmt -w .
goimports -w .
golangci-lint run --fix
buf format -w .
```

### Pain Points
- gofmt and goimports overlap but are separate tools
- golangci-lint has limited auto-fix
- Protobuf formatting is separate
- No convergence loop (fix → re-lint)

### Ideal Workflow
```bash
ast fix --all              # goimports → golangci-lint fix → buf format
ast fix --lang go          # Go-specific
ast fix --proto            # Protobuf files only
```

---

## Scenario 4: Rust Project — "CLI Tool"

### Context
A Rust CLI tool with multiple crates. Needs:
1. rustfmt formatting
2. clippy fixes (`cargo clippy --fix`)
3. Edition migration (`cargo fix --edition`)
4. Import sorting (via rustfmt)
5. Unused code removal

### Current Workflow
```bash
cargo fmt
cargo clippy --fix --allow-dirty --allow-staged
cargo fix --edition
```

### Pain Points
- `cargo fix` and `cargo clippy --fix` are separate
- Edition migration is separate
- No unified convergence loop
- Workspace-level fixes need coordination

### Ideal Workflow
```bash
ast fix --all              # rustfmt → clippy fix → edition migration
ast fix --lang rust        # Rust-specific
ast fix --workspace        # All crates in workspace
```

---

## Scenario 5: C++ Project — "Embedded Firmware"

### Context
C++17 embedded project with CMake. Needs:
1. clang-format
2. clang-tidy fixes
3. include-what-you-use (IWYU)
4. CMake formatting (cmake-format)

### Current Workflow
```bash
clang-format -i **/*.cpp **/*.h
clang-tidy -fix **/*.cpp
iwyu --fix **/*.cpp
cmake-format -i CMakeLists.txt
```

### Pain Points
- Multiple tools, no unified config
- clang-tidy fixes can be unsafe
- IWYU is separate
- CMake formatting is separate
- No cross-file analysis for fixes

### Ideal Workflow
```bash
ast fix --all                    # clang-format → clang-tidy (safe) → IWYU → cmake-format
ast fix --lang cpp               # C++ specific
ast fix --config .clang-tidy     # Use project config
```

---

## Scenario 6: Polyglot Monorepo — "Full Stack App"

### Context
A monorepo with:
- `backend/` — Python (FastAPI)
- `frontend/` — TypeScript (Next.js)
- `shared/` — Go (protobufs)
- `infrastructure/` — Rust (CLI tools)
- `docs/` — Markdown (prettier)

### Current Workflow
```bash
# Run in each directory with different tools
cd backend && ruff check --fix . && ruff format .
cd frontend && npx eslint . --fix && npx prettier --write .
cd shared && goimports -w . && golangci-lint run --fix
cd infrastructure && cargo fmt && cargo clippy --fix
cd docs && npx prettier --write .
```

### Pain Points
- No single command for entire repo
- Different config formats per language
- No cross-language dependency analysis
- CI pipeline is complex

### Ideal Workflow
```bash
ast fix --all                    # Detects languages, runs appropriate fixers
ast fix --backend                # Only Python backend
ast fix --frontend               # Only TypeScript frontend
ast fix --lang python,typescript # Specific languages
ast fix --workspace              # Entire monorepo with proper ordering
```

---

## Key Design Principles from Thought Experiments

### 1. **Convergence Loop is Essential**
All tools need iterative fix → re-analyze until stable (Ruff does this with 10-iteration max)

### 2. **Safety Classification**
- **Safe**: Always apply (formatting, import sorting, unused import removal)
- **Unsafe**: Require explicit flag (type hint changes, semantic modifications)
- **Display Only**: Show but never auto-apply (architecture violations)

### 3. **Language Detection & Orchestration**
Auto-detect project languages, run fixers in dependency order:
- Format first (stable baseline)
- Lint fix (may introduce formatting issues)
- Re-format (converge)
- Type fix (where available)

### 4. **Configuration Unification**
Single config file (`ast-fix.yaml` or section in `pyproject.toml`) that maps to per-language configs

### 5. **MCP/LSP Integration**
Use LSP for:
- Type-aware fixes (TypeScript, Python, Go, Rust)
- Cross-file refactoring
- Semantic analysis

### 6. **CI/CD Integration**
- `--check` mode: exit code 1 if changes needed
- `--diff` mode: output unified diff
- JSON output for tooling
- GitHub Actions integration

### 7. **Extensibility**
Plugin system for:
- Custom language fixers
- Framework-specific rules (FastAPI, React, gRPC)
- Organization-specific rules

### 8. **Performance**
- Parallel execution across files
- Incremental (only changed files)
- Streaming for large codebases
- Worker pool for CPU-bound tools

---

## Industry Needs Summary (2026)

Based on research:
1. **Unified toolchain** — Developers tired of 5+ config files
2. **Auto-fix by default** — "Fix on save" is table stakes
3. **LSP-first** — Language servers as the source of truth
4. **MCP integration** — AI agents need standard tool interfaces
5. **Polyglot support** — Monorepos are standard
6. **Security built-in** — Vulnerability scanning + auto-fix
7. **CI/CD native** — GitHub Actions/GitLab CI first-class
8. **Editor agnostic** — Works in VS Code, Zed, Neovim, JetBrains
9. **Local-first** — No cloud dependency for core features
10. **Extensible** — Plugin system for org-specific rules
