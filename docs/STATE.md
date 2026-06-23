# AST-Tools Refactoring State

## Session: 2026-06-23

### ✅ COMPLETED

**Phase 0: Install ast-grep CLI**
- `cargo install ast-grep` completed successfully
- ast-grep v0.44.0 installed at `/home/sysop/.cargo/bin/ast-grep`
- Verified working via `mcp_ast_tools_ast_grep` tool call

**Phase 1: Extract Utility Functions**
- ✅ Phase 1.1: Package structure created
  - `src/ast_tools/__init__.py`
  - `src/ast_tools/core/__init__.py`
  - `src/ast_tools/tools/__init__.py`
  - `src/ast_tools/utils/__init__.py`

- ✅ Phase 1.2: Annotation utils extracted
  - `src/ast_tools/utils/annotations.py`
  - Functions: `_annotation_to_str`, `_get_function_signature`, `_extract_all_names`

- ✅ Phase 1.3: File and impact utils extracted
  - `src/ast_tools/utils/file_utils.py`: `find_python_files`, `is_test_file`, `file_to_module`, `filter_top_level`
  - `src/ast_tools/utils/impact.py`: `build_reverse_deps`, `get_transitive_deps`, `classify_risk`

**Phase 1.4: Backward Compatibility**
- Added wrapper functions in `ast_tools_server.py` to maintain existing call sites
- All 32 tests passing without modification

**Phase 2: Extract Simple Tools** ✅ COMPLETE
- ✅ Extracted `codebase_summary` to `src/ast_tools/tools/codebase_summary.py`
- ✅ Extracted `project_info` to `src/ast_tools/tools/project_info.py`
- ✅ Extracted `ast_refactor_extract_interface` to `src/ast_tools/tools/ast_refactor_extract_interface.py`
- ✅ Extracted `ast_generate_stub` to `src/ast_tools/tools/ast_generate_stub.py`
- ✅ Created tool registry in `src/ast_tools/tools/__init__.py`
- ✅ Updated `call_tool()` dispatcher to use registry
- ✅ Updated test imports to use extracted tools
- ✅ All 114 tests passing

Commits:
1. `refactor: extract utility functions to ast_tools.utils package`
2. `fix: align classify_risk thresholds with original implementation`
3. `refactor: Phase 2 complete — extract codebase_summary, project_info, ast_refactor_extract_interface to tools package`
4. `refactor: complete Phase 2 — extract ast_generate_stub to tools package`

### 📋 NEXT STEPS

**Phase 3: Extract Core Tools** (READY TO START)
- Extract `ast_read`, `ast_edit`, `ast_grep` tool implementations to `src/ast_tools/tools/`
- Update registry and dispatcher
- Verify all tests still pass

**Phase 4: Extract Remaining Tools** (not started)
- Extract `structural_analysis`, `find_references`, `impact_analysis`, `module_imports`

**Phase 5: Server Refactor + Tests** (not started)
- Refactor server initialization
- Add integration tests for modular architecture

### 🔧 KEY DECISIONS

- Used backward-compat wrapper pattern instead of updating all call sites
- This minimizes risk and keeps the diff focused on extraction, not refactoring
- Future phases can remove wrappers and call utils directly
- Tool registry pattern: all extracted tools register themselves in `src/ast_tools/tools/__init__.py`
- `call_tool()` dispatcher checks registry first, then falls back to inline handlers for remaining tools