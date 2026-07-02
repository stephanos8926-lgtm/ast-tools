# ⚠️ AST-TOOLS USAGE RULES — READ BEFORE EDITING

**STOP:** If you are about to edit AST-Tools source code, read this first.

---

## 🚫 DO NOT MODIFY AST-TOOLS UNLESS:

1. **You have explicit permission** from the user (Steven Page)
2. **You are fixing a verified bug** (test fails, then you fix)
3. **You are adding a requested feature** (user asked for it)
4. **You are updating documentation** (docs/ folder only)

---

## ✅ WHAT YOU CAN DO (Safe Operations)

### 1. **Use AST-Tools MCP Tools** — OK ✅
```json
{
  "tool": "ast_grep",
  "args": {"pattern": "def $FUNC", "lang": "python"}
}
```
Calling MCP tools is **always safe** — you're using the API, not changing code.

### 2. **Read AST-Tools Documentation** — OK ✅
```bash
cat docs/AST_TOOLS_QUICKSTART.md
cat docs/ENHANCED_DEAD_CODE.md
```
Reading docs is **always safe**.

### 3. **Run Tests** — OK ✅
```bash
cd ast-tools
source .venv/bin/activate
pytest tests/ -v
```
Running tests is **always safe** (read-only).

### 4. **Check Tool Status** — OK ✅
```python
from ast_tools.tools import TOOL_REGISTRY
print(f"Available tools: {len(TOOL_REGISTRY)}")
```
Inspecting the tool registry is **always safe**.

---

## ❌ WHAT YOU CANNOT DO (Dangerous Operations)

### 1. **DO NOT Edit Source Code** — ⛔ FORBIDDEN
```python
# BAD: Don't do this
patch(path="src/ast_tools/tools/semantic_search.py", ...)
write_file(path="src/ast_tools/cli.py", ...)
```
**Unless:** You have explicit permission + a test that fails first.

**Why:** AST-Tools is a **shared infrastructure tool** used by:
- NexusAgent (multi-agent dev system)
- FORGE / FCEE (self-improving AI pipeline)
- Multiple production projects

Breaking changes here break **everything**.

---

### 2. **DO NOT Add Dependencies** — ⛔ FORBIDDEN
```toml
# BAD: Don't modify pyproject.toml
[project.optional-dependencies]
new-dep = ["some-package"]
```
**Unless:** User explicitly asked for it + security audit completed.

**Why:** Dependency changes affect:
- Multi-machine sync (workstation ↔ server)
- Build reproducibility
- Security surface area

---

### 3. **DO NOT Change Tool Signatures** — ⛔ FORBIDDEN
```python
# BAD: Don't change function signatures
def semantic_search(query, k=10):  # OLD
def semantic_search(query, k=10, new_param=True):  # NEW - BREAKS THINGS
```
**Unless:** Backward-compatible + user approved + tests updated.

**Why:** Other agents/cron jobs depend on exact signatures.

---

### 4. **DO NOT "Improve" or "Refactor"** — ⛔ FORBIDDEN
```python
# BAD: Don't "clean up" code you didn't write
# "This could be more efficient..."
# "Let me modernize this..."
```
**Unless:** User explicitly requested the refactor.

**Why:** "Improvements" often:
- Break existing functionality
- Change behavior subtly
- Introduce regressions

---

## 🛠️ WHAT TO DO INSTEAD

### If You Need AST-Tools to Do Something New:

**Option 1: Use Existing Tools Creatively**
```markdown
Instead of: "I need a new tool for X"
Try: "I can combine ast_grep + ast_read to achieve X"
```

**Option 2: Request a Feature**
```markdown
Tell the user: "AST-Tools doesn't support X yet. Should I:
(a) Work around it with existing tools
(b) Request a new tool implementation
(c) Use an alternative approach"
```

**Option 3: Use Alternative Tools**
```markdown
If AST-Tools can't do it, use:
- search_files (grep equivalent)
- read_file (understand before editing)
- patch (surgical edits, manual but safe)
```

---

## 📋 CURRENT AST-TOOLS STATUS

**Version:** 1.3.0 (as of 2026-06-29)  
**Tools:** 41 total (including enhanced dead code detection)  
**Test Status:** 409/409 passing  
**Location:** `~/Workspaces/ast-tools/`  
**Server Sync:** Manual rsync (not auto-synced)  

**Key Features:**
- ✅ Semantic search (hybrid FTS5 + vector)
- ✅ Structural editing (Python-only, libcst-backed)
- ✅ Enhanced dead code detection (6 FP reductions)
- ✅ Impact analysis (change risk assessment)
- ✅ Multi-language support (12+ languages for search)

**Limitations:**
- ⚠️ `ast_edit` is **Python-only** (no TS/JS editing yet)
- ⚠️ Tree-sitter grammars must be installed per-language
- ⚠️ Server may lag behind workstation (manual sync)

---

## 🔍 HOW TO CHECK IF AST-TOOLS IS WORKING

```bash
# 1. Check tool count (should be 41)
cd ~/Workspaces/ast-tools
source .venv/bin/activate
python -c "from ast_tools.tools import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"

# 2. Test a simple search
hermes mcp call ast-tools ast_grep '{"pattern": "def $FUNC", "lang": "python", "limit": 1}'

# 3. Verify semantic search works
hermes mcp call ast-tools semantic_search '{"query": "test", "k": 1}'
```

**Expected output:**
- Tool count: 41
- ast_grep: Returns at least 1 function definition
- semantic_search: Returns results (not error)

**If broken:**
- Check logs: `tail ~/.hermes/logs/mcp-stderr.log`
- Verify venv: `which python` should point to `.venv/bin/python`
- Reinstall deps: `uv pip install -e .`

---

## 📚 DOCUMENTATION FILES

**Read these instead of modifying code:**

| File | Purpose |
|------|---------|
| `docs/AST_TOOLS_QUICKSTART.md` | **Start here** — usage guide |
| `docs/ENHANCED_DEAD_CODE.md` | Dead code detection (Phase 1) |
| `docs/COMPETITIVE_FEATURE_PARITY.md` | Feature comparison vs competitors |
| `references/phase1-enhanced-dead-code.md` | Implementation details |
| `references/ast-tools-usage/SKILL.md` | Hermes skill documentation |

---

## 🆘 IF YOU'RE UNSURE

**Ask yourself:**
1. "Did the user explicitly ask me to modify AST-Tools?"
2. "Is there a test that fails which I'm fixing?"
3. "Am I using the tool (OK) or changing the tool (⛔)?"

**If unsure, ask the user:**
> "I notice AST-Tools doesn't support X. Should I:
> (a) Work around it with existing tools
> (b) Request a feature implementation
> (c) Use an alternative approach"

---

## 🎯 GOLDEN RULE

**AST-Tools is infrastructure, not your playground.**

Treat it like you'd treat the Linux kernel:
- Use the APIs (MCP tools) ✅
- Read the docs ✅
- Report bugs ✅
- **Don't hack on it unless you're a maintainer** ⛔

**You are a user of AST-Tools, not a maintainer.** Act accordingly.

---

**Last updated:** 2026-06-29  
**Maintained by:** Steven Page + Lucien (RapidWebs Lead Digital Architect)  
**Questions?** Check `docs/AST_TOOLS_QUICKSTART.md` or ask the user.