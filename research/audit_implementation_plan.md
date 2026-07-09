
# Implementation Plan: Auto-Fix Pipeline Remediation
**Generated:** 2026-07-08
**Based on:** Forward, Reverse, Adversarial, and Edge Cases audits

---

## 🔴 CRITICAL (2 issues) — Immediate priority

### C1: Double Mutation in RuffFixer.analyze()
**Finding FWD-07:** Ruff check --fix runs TWICE — once with file args (modifies disk), once with stdin (piped). Files are mutated before the fix action is created.
**Fix:** 
- Remove `ruff check --fix` from file-arg command (use `ruff check --output-format=json` READ-ONLY)
- Only run `ruff check --fix --stdin-filename` via stdin to capture output WITHOUT modifying disk
- The FixEngine.apply_fix() writes the fixed content, so we don't need the tool to do it

### C2: Double Mutation in TypeScriptFixer.analyze()
**Finding FWD-08:** ESLint --fix modifies files in-place before we capture the diff.
**Fix:**
- Similar to Ruff: use `eslint --format=json` READ-ONLY for diagnostics
- Only fix via `eslint --stdin --fix --stdin-filename` to capture output

---

## 🟠 HIGH (16 issues) — Week 1

### H1: Stub verify() methods (FWD-04, FWD-05)
**Finding:** Base verify() returns empty list. Convergence detection is broken. Loop may infinite-iterate.
**Fix:** For each concrete fixer:
- RuffFixer: `ruff check --output-format=json` → count remaining issues
- TypeScriptFixer: `eslint --format=json` → count remaining issues  
- GoFixer: `golangci-lint run --out-format=json` → count remaining
- RustFixer: `cargo clippy --message-format=json` → count remaining
- CppFixer: `clang-tidy --checks='*'` → count remaining

### H2: Oscillation detection (EDG-10)
**Finding:** Fixer oscillation (A changes → B changes back → A changes → ...) hits max_iterations.
**Fix:** Add fixpoint detection: if the same file gets changed in iterations N and N-1 by different tools, warn and break early.

### H3: Tool timeout (EDG-07)
**Finding:** No timeout on _run_command. Tools can hang indefinitely.
**Fix:** Add `timeout=120` to all subprocess.run() calls.

### H4: Content validation (ADV-02)
**Finding:** No validation before writing fixed content. Corrupted output can damage source files.
**Fix:** Validate fixed_content:
- Not empty (unless original was empty)
- Valid UTF-8
- Same line count ±25% (heuristic guard)
- No null bytes

### H5: Symlink traversal (ADV-03)
**Finding:** rglob() follows symlinks. Could read/write outside project.
**Fix:** Use `path.resolve() relative_to project_root` to verify files are within project boundaries. Add `follow_symlinks=False` to rglob (Python 3.12+ supports this).

### H6: File locking (ADV-04)
**Finding:** No concurrent access protection.
**Fix:** Use `portalocker` or `fcntl.flock()` on each file before writing. Skip with warning if locked.

### H7: Large file protection (EDG-04, ADV-06)
**Finding:** No size limits. Multi-GB files cause OOM.
**Fix:** Check `file_path.stat().st_size` before reading. Skip files > 10MB with warning.

### H8: Backup mechanism (REV-07)
**Finding:** No backup before applying fixes.
**Fix:** Before writing, copy original to `{file}.ast-tools.bak` or a `.ast-tools-backups/` directory.

### H9: Incremental mode (REV-09)
**Finding:** No 'only changed files' mode. Re-processes entire project each time.
**Fix:** Track file hash in metadata. Skip files with unchanged hash since last fix run.

### H10: Plugin system (REV-10)
**Finding:** No way to register custom fixers without forking.
**Fix:** Add `fixers.register_fixer(name, class)` function and a `--custom-plugin` CLI argument. Document protocol.

### H11: LSP integration (REV-11)
**Finding:** No textDocument/codeAction for fixes.
**Fix:** Add LSP `codeAction` handler that calls FixEngine on the current file.

### H12: .gitignore respect (REV-15)
**Finding:** Fixes all files including gitignored/virtualenv/node_modules.
**Fix:** Use `pathspec` library to check .gitignore patterns before including files.

### H13: Double write in GoFixer (FWD-09)
**Finding:** golangci-lint --fix writes to disk, then apply_fix() writes again.
**Fix:** Similar to C1/C2: use read-only mode for analysis, apply via our own write.

---

## 🟡 MEDIUM (10 issues) — Week 2

### M1: Path resolution (FWD-01)
**Finding:** Paths resolved relative to CWD, not project_root.
**Fix:** Always resolve paths relative to project_root in CLI command.

### M2: Error accumulation (FWD-03)
**Finding:** _collect_errors reset each iteration.
**Fix:** Store errors in instance variable, not getattr/setattr pattern.

### M3: Stale format detection (FWD-06)
**Finding:** Ruff fix then format may see stale original.
**Fix:** Fix then format in the same pass — run format after fix on the same content.

### M4: Silent tool absence (ADV-08)
**Finding:** Missing tools skip silently unless verbose.
**Fix:** Print warning to stderr when tool not found. Add --strict mode that fails.

### M5: Binary file detection (EDG-03)
**Finding:** Extension-only detection passes binary files to tools.
**Fix:** Check first 512 bytes for null byte (binary detection heuristic) before processing.

### M6: Read-only file skip (EDG-05)
**Finding:** Read-only files skipped silently.
**Fix:** Check `os.access(file, os.W_OK)` before attempting, warn if not writable.

### M7: Encoding handling (EDG-06)
**Finding:** Non-UTF8 files throw UnicodeDecodeError.
**Fix:** Try UTF-8 first, fall back to Latin-1, warn about encoding guess.

### M8: Incomplete check/diff mode (EDG-09)
**Finding:** Check/diff mode breaks after one iteration.
**Fix:** Run full converge loop in hidden mode, then report results.

### M9: .gitignore patterns (REV-14)
**Finding:** No per-language skip/ignore patterns.
**Fix:** Support `exclude_patterns` in config section.

### M10: Parallel execution (REV-08)
**Finding:** Single-threaded per-file processing.
**Fix:** Use `concurrent.futures.ThreadPoolExecutor` for independent file processing.

---

## 🟢 LOW (9 issues) — Week 3 / Nice-to-have

### L1: Language validation (FWD-02)
**Finding:** Unknown language IDs silently ignored.
**Fix:** Validate --lang against registry before creating context.

### L2: Temp file cleanup (ADV-05)
**Finding:** No temp cleanup on failure.
**Fix:** Use context managers for temporary files.

### L3: Unicode normalization (ADV-07)
**Finding:** No path normalization.
**Fix:** Use unicodedata.normalize('NFC', path) on all path operations.

### L4: Empty dir handling (EDG-01)
**Finding:** Already handled correctly.
**Fix:** NO ACTION NEEDED

### L5: No-match handling (EDG-02)
**Finding:** Already handled correctly.
**Fix:** NO ACTION NEEDED

### L6: Empty file handling (EDG-08)
**Finding:** Already handled correctly.
**Fix:** NO ACTION NEEDED

### L7: Dry run report (REV-13)
**Finding:** Partial implementation with --diff.
**Fix:** Add --report flag that generates summary markdown.

### L8: MCP tool exposure (REV-12)
**Finding:** Not yet exposed through MCP server.
**Fix:** Add `fix_code` and `fix_check` MCP tools.

### L9: Language validation in CLI (REV-14)
**Finding:** Partially implemented.
**Fix:** Add validation, test coverage.

---

## Effort Summary

| Priority | Count | Estimated Effort |
|----------|-------|-----------------|
| 🔴 CRITICAL | 2 | 4 hours |
| 🟠 HIGH | 13 | 40 hours |
| 🟡 MEDIUM | 10 | 20 hours |
| 🟢 LOW | 7 | 10 hours |
| **Total** | **32** | **74 hours (~2 weeks)** |

## Recommended Sprint Plan

### Sprint A (Week 1): 🔴 Critical + 🟠 High Priority
- C1: Fix double mutation in RuffFixer (2h)
- C2: Fix double mutation in TypeScriptFixer (2h)
- H1: Implement verify() for all fixers (8h)
- H2: Oscillation detection (2h)
- H3: Tool timeout protection (1h)
- H4: Content validation (2h)
- H5: Symlink protection (2h)
- H6: File locking (3h)
- H7: Large file protection (1h)
- H8: Backup mechanism (3h)
- H9: Incremental mode (4h)
- H10: Plugin system infrastructure (4h)
- H11: LSP integration (6h)
- H13: Double write fix (2h)

### Sprint B (Week 2): 🟡 Medium Priority + Remaining
- M1-M10: All medium issues (20h)
- L7-L8: MCP + report (4h)

### Sprint C (Week 3): 🟢 Low Priority
- L1-L3, L9: Remaining low issues (6h)

---

## Post-Fix Testing Plan

1. **Forward pass test:** Full `ast fix --check` on ast-tools repo itself → should return 0
2. **Double mutation test:** File timestamps should only change ONCE per fix run
3. **Convergence test:** Known-lint files should converge in <5 iterations
4. **Oscillation test:** Create artificial A→B→A pattern → should detect and break
5. **Symlink test:** Create symlinked file → should warn and skip
6. **Large file test:** Create 100MB .py file → should skip with clear message
7. **Missing tool test:** Run without installed tools → should advise installation
8. **Concurrent test:** Two fix engines on same files → should detect lock
9. **Backup test: Fix file → verify .bak exists → restore works
10. **Encoding test:** Latin-1 file → should warn and skip gracefully

---
