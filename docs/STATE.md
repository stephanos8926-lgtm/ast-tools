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
  - Functions: `_annotation_to_str`, `_function_signature`, `_extract_all_names`

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

**Phase 3: Extract Core Tools** ✅ COMPLETE
- ✅ Extracted `ast_read` to `src/ast_tools/tools/ast_read.py`
- ✅ Extracted `ast_edit` to `src/ast_tools/tools/ast_edit.py`
- ✅ Extracted `ast_grep` to `src/ast_tools/tools/ast_grep.py`
- ✅ Updated test imports (`test_e2e.py`, `test_phase3_polish.py`)
- ✅ Fixed `_extract_all_names()` to actually parse `__all__` (was returning all names)
- ✅ All 114 tests passing

**Phase 4: Extract Remaining Tools** ✅ COMPLETE
- ✅ Extracted `structural_analysis` to `src/ast_tools/tools/structural_analysis.py`
- ✅ Extracted `find_references` to `src/ast_tools/tools/find_references.py`
- ✅ Extracted `impact_analysis` to `src/ast_tools/tools/impact_analysis.py`
- ✅ Extracted `module_imports` to `src/ast_tools/tools/module_imports.py`
- ✅ Updated registry and dispatcher
- ✅ All 114 tests passing

**Commits:**
1. `refactor: extract utility functions to ast_tools.utils package` (826a0fa)
2. `fix: align classify_risk thresholds with original implementation` (445d64f)
3. `refactor: Phase 2 complete — extract codebase_summary, project_info, ast_refactor_extract_interface to tools package` (09adaf1)
4. `refactor: complete Phase 2 — extract ast_generate_stub to tools package` (884c16b)
5. `refactor: Phase 3 complete — extract ast_read, ast_edit, ast_grep to tools package` (ee53c43)

### 📋 NEXT STEPS

**Phase 5: Server Refactor + Tests** (READY TO START)
- Refactor server initialization
- Add integration tests for modular architecture
- Remove backward-compat wrappers from `ast_tools_server.py`
- Verify all tools work through the registry

### 🔧 KEY DECISIONS

- Used backward-compat wrapper pattern instead of updating all call sites
- This minimizes risk and keeps the diff focused on extraction, not refactoring
- Future phases can remove wrappers and call utils directly
- Tool registry pattern: all extracted tools register themselves in `src/ast_tools/tools/__init__.py`
- `call_tool()` dispatcher checks registry first, then falls back to inline handlers for remaining tools
- `__all__` filtering: `_extract_all_names()` now correctly parses `__all__` assignment (fixed in Phase 3)