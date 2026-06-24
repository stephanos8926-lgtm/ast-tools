# Phase 8: Reverse Audit — Gaps & Edge Cases

## Executive Summary

**Verdict:** ✅ **FEASIBLE with refinements** — 5 gaps identified, all fixable.

---

## 1. Missing Dependencies

### ⚠️ Gap 1: No Conan Tokens Installed

**Issue:** `tiktoken` available but Conan Tokens (better multi-model support) not installed.

**Impact:** Can only count OpenAI-style tokens, may be inaccurate for Gemini/Gemma.

**Fix:**
```bash
uv pip install conan-tokens
```

**OR** use conservative estimates (1 symbol = 300 tokens, over-estimate by 20%).

---

### ⚠️ Gap 2: No `numpy` Import in Proposed Code

**Issue:** Embeddings are `np.ndarray` but `numpy` not explicitly in requirements.

**Check:**
```bash
cd /home/sysop/Workspaces/ast-tools && grep numpy requirements.txt
```

**Fix:** Add to `requirements.txt` if missing.

---

## 2. Security Concerns

### ⚠️ Gap 3: Hook Script Injection Risk

**Scenario:** `context-injector-hook.sh` reads conversation context, could expose sensitive data.

**Risk:** If hook logs output or writes to temp files, API keys/symbols could leak.

**Mitigation:**
1. Hook script must NOT log to stdout (only stderr for errors)
2. NEVER write context to temp files
3. Use `set -euo pipefail` for safety
4. Restrict file permissions: `chmod 700`

**Template:**
```bash
#!/bin/bash
set -euo pipefail
# Context injector hook for ast-tools
# Reads: $ASTOOLS_DB_PATH, $QUERY
# Writes: Appends to $HERMES_CONTEXT_FILE
# NO logging, NO temp files

python3 - <<'PYTHON'
import os
import sys
from pathlib import Path

query = os.environ.get('ASTOOLS_QUERY', '')
db_path = Path(os.environ.get('ASTOOLS_DB_PATH', ''))

# Inject context here - NO print statements
# Write directly to Hermes context file

sys.exit(0)  # Silent success
PYTHON
```

---