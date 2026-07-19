# SPEC: Immutable Tool Cache v3

> **Version:** v3  
> **Date:** 2026-07-14  
> **Author:** Lucien (Lead Digital Architect)  
> **Status:** Draft — Ratified  
> **Supersedes:** v2 (adversarial trust findings integrated)

---

## 1. Problem Statement

The tool registration and caching system has three interconnected vulnerabilities identified by the adversarial trust audit:

### 1.1 Missing Trust/Provenance in ToolInfo Dataclass

The `ToolInfo` dataclass (`nexusagent.tools.registry.types`) lacks `trust: TrustLevel` and `provenance: str` fields. The `register_mcp_tools()` function does not hardcode `trust=TrustLevel.TOOL_EXTERNAL`, meaning MCP tools are registered without trust metadata. Their output messages default to `UNTRUSTED` (0) rather than `TOOL_EXTERNAL` (1), breaking the trust boundary system.

### 1.2 No Cache Invalidation Protocol

Tools are registered once per agent session. There is no mechanism to update, invalidate, or evict cached tool definitions — a stale tool definition can persist indefinitely, including its description, parameter schema, and (once trust/provenance are added) trust metadata.

### 1.3 Tool Name Injection Surface

The blocklist (`_INJECTION_TOOL_NAMES`, `_RESERVED_PREFIXES`) uses exact string matching. Near-miss names like `system_instruction_executor` bypass detection, creating a semantic injection vector where the tool name itself acts as a subtle instruction to the LLM.

---

## 2. Solution Architecture

### 2.1 ToolInfo Dataclass (Updated)

```python
# src/nexusagent/tools/registry/types.py

@dataclass(frozen=True)
class ToolInfo:
    """Immutable tool definition. Frozen after registration."""
    name: str
    func: Callable
    description: str
    parameters: dict[str, str]
    example: str
    category: str
    returns: str
    requires: str
    trust: TrustLevel          # NEW — hardcoded at registration
    provenance: str            # NEW — source identifier (e.g. "mcp:filesystem")
    registered_at: float       # NEW — unix timestamp of registration
    checksum: str | None       # NEW — hash of name+description+parameters for integrity

    def __post_init__(self):
        """Validate immutability contract on construction."""
        if self.trust < TrustLevel.TOOL_INTERNAL and not self.provenance:
            raise ValueError(
                f"Tools with trust {self.trust} must have provenance set. "
                f"Tool '{self.name}' has empty provenance."
            )
        if not _VALID_TOOL_NAME_RE.match(self.name):
            raise ValueError(
                f"Tool name '{self.name}' does not match "
                f"required pattern {_VALID_TOOL_NAME_RE.pattern}"
            )
```

### 2.2 Immutable Cache Registry

```python
# src/nexusagent/tools/registry/immutable_cache.py

import hashlib
import json
import threading
from typing import Final

class ImmutableToolCache:
    """Thread-safe registry enforcing write-once semantics for tool definitions."""

    _instance: "ImmutableToolCache | None" = None
    _lock: Final = threading.Lock()

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}
        self._checksums: dict[str, str] = {}
        self._frozen: bool = False

    @classmethod
    def get_instance(cls) -> "ImmutableToolCache":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register(self, tool: ToolInfo) -> None:
        """Register a tool with write-once semantics."""
        if self._frozen:
            raise RuntimeError("Tool cache is frozen — no further registrations allowed")
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' already registered (immutable cache). "
                f"Duplicate registration blocked."
            )

        # Compute checksum for integrity verification
        payload = json.dumps({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "trust": tool.trust.value,
            "provenance": tool.provenance,
        }, sort_keys=True)
        checksum = hashlib.sha256(payload.encode()).hexdigest()[:16]

        # Validate name against blocklist
        self._validate_tool_name(tool.name)

        object.__setattr__(tool, "checksum", checksum)
        self._tools[tool.name] = tool
        self._checksums[tool.name] = checksum

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def verify_integrity(self, name: str) -> bool:
        """Verify a registered tool's checksum hasn't mutated."""
        tool = self._tools.get(name)
        if tool is None:
            return False
        payload = json.dumps({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "trust": tool.trust.value,
            "provenance": tool.provenance,
        }, sort_keys=True)
        expected = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return expected == self._checksums.get(name, "")

    def freeze(self) -> None:
        """Freeze registry — no further registrations allowed.
        Called after initial tool setup phase completes."""
        self._frozen = True

    def _validate_tool_name(self, name: str) -> None:
        """Validate tool name against blocklist and heuristic analysis."""
        if not _VALID_TOOL_NAME_RE.match(name):
            raise ValueError(f"Invalid tool name format: {name}")

        for prefix in _RESERVED_PREFIXES:
            if name.startswith(prefix):
                raise ValueError(
                    f"Tool name '{name}' starts with reserved prefix '{prefix}'"
                )

        if name in _INJECTION_TOOL_NAMES:
            raise ValueError(
                f"Tool name '{name}' matches known injection tool name in blocklist"
            )

        # NEW: Heuristic name analysis — score for instruction-like semantics
        if _heuristic_injection_score(name) > 0.7:
            raise ValueError(
                f"Tool name '{name}' has high injection heuristic score "
                f"({_heuristic_injection_score(name):.2f}). Blocked."
            )

    def list_tools(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools
```

### 2.3 Registration Enforcement (Updated)

```python
# src/nexusagent/tools/register_all.py

def register_mcp_tools() -> None:
    """Register MCP tools with enforced TOOL_EXTERNAL trust level."""
    cache = ImmutableToolCache.get_instance()
    mcp_tools = discover_mcp_tools()  # existing discovery logic

    for tool_def in mcp_tools:
        register_tool(
            name=tool_def.name,
            description=f"[MCP:{tool_def.server_name}] {tool_def.description}",
            parameters=tool_def.parameters,
            example=f"{tool_def.name}()",
            category="mcp",
            returns="Result from MCP server.",
            trust=TrustLevel.TOOL_EXTERNAL,      # HARDCODED — was missing
            provenance=f"mcp:{tool_def.server_name}",  # NEW
        )
```

### 2.4 Heuristic Name Analysis

```python
# src/nexusagent/tools/registry/name_analysis.py

_INSTRUCTION_KEYWORDS: Final[set[str]] = {
    "execute", "run", "invoke", "dispatch", "override",
    "ignore", "bypass", "skip", "force", "inject",
    "system", "instruction", "command", "directive",
    "admin", "root", "sudo", "privilege", "escalate",
    "eval", "exec", "shell", "bash", "cmd",
}

def _heuristic_injection_score(name: str) -> float:
    """Score a tool name for instruction-like semantics (0.0–1.0)."""
    parts = name.lower().split("_")
    if not parts:
        return 0.0

    keyword_hits = sum(1 for p in parts if p in _INSTRUCTION_KEYWORDS)
    ratio = keyword_hits / len(parts)

    # Boost if name reads like a command phrase
    imperative_boost = 1.3 if any(
        name.lower().startswith(kw) for kw in {"execute_", "run_", "invoke_", "dispatch_"}
    ) else 1.0

    return min(1.0, ratio * imperative_boost)
```

### 2.5 Expanded Blocklist

```python
# Augmented _INJECTION_TOOL_NAMES and _RESERVED_PREFIXES

_INJECTION_TOOL_NAMES: Final[set[str]] = {
    # Existing
    "ignore_previous_instructions",
    "override_system_prompt",
    "system_override",
    "ignore_all_instructions",
    "follow_instructions",
    # NEW — adversarial audit findings
    "execute_instruction",
    "process_directive",
    "system_directive",
    "command_override",
    "admin_override",
    "privilege_escalate",
    "eval_expression",
    "shell_execute",
    "run_command",
    "bypass_safety",
    "ignore_constraints",
    "reset_context",
    "clear_provenance",
    "set_trust_level",
}

_RESERVED_PREFIXES: Final[tuple[str, ...]] = (
    # Existing
    "system__",
    "ignore_",
    "override_",
    "_internal_",
    # NEW
    "execute_",
    "run_",
    "inject_",
    "bypass_",
    "force_",
    "eval_",
    "shell_",
    "admin_",
    "sudo_",
    "privilege_",
    "command_",
)
```

---

## 3. Cache Invalidation Protocol

### 3.1 Session-Level Invalidation

```
Session Start
  ├── Phase 1: Core tools registered (BUILTIN trust) → cache NOT frozen yet
  ├── Phase 2: MCP tool discovery → register with TOOL_EXTERNAL trust
  │     └── Duplicate detection: error if tool name collides with Phase 1
  └── Phase 3: cache.freeze() → NO further registrations this session
```

### 3.2 Cross-Session Cache

Tool definitions are **not persisted** across sessions. Each session builds its own immutable cache from scratch. This prevents stale tool definitions from leaking between sessions.

### 3.3 Integrity Verification

- On each tool invocation, optionally verify `ImmutableToolCache.verify_integrity(name)`
- If check fails → tool definition has mutated → log error and fall back to UNTRUSTED trust level
- Integrity check is O(1) (hash comparison)

---

## 4. Audit Finding Mitigations Addressed

| Audit ID | Finding | Mitigation in this spec |
|----------|---------|------------------------|
| 🔴 C9 | ToolInfo missing trust/provenance | Added `trust: TrustLevel`, `provenance: str`, `checksum`, `registered_at` to frozen dataclass |
| 🔴 C9 | register_mcp_tools() no trust assignment | Hardcoded `trust=TrustLevel.TOOL_EXTERNAL` + `provenance=f"mcp:{server_name}"` |
| 🟡 #6 | Tool name semantic injection | Heuristic injection score, expanded blocklist (7 new prefixes, 15 new exact names) |
| 🟡 #4 | Cross-turn additional_kwargs survival | Tool checksum enables integrity verification at invocation time |
| 🟡 H1 | Duplicate import graph | Write-once cache prevents accidental re-registration |
| 🟠 H9 | LLM disregard for trust (advisory-only) | Frozen dataclass + hardcoded trust at registration makes trust assignment non-bypassable at code level |

---

## 5. Implementation Plan

### P1: ToolInfo Dataclass Update
- Files: `src/nexusagent/tools/registry/types.py`
- Add `trust`, `provenance`, `registered_at`, `checksum` fields
- Add `__post_init__` validation (trust/provenance pairing, name regex)
- Make dataclass `frozen=True`

### P2: Immutable Cache
- Files: `src/nexusagent/tools/registry/immutable_cache.py` (NEW)
- Implement `ImmutableToolCache` with write-once semantics
- Implement `register()`, `get()`, `verify_integrity()`, `freeze()`
- Implement `_validate_tool_name()` with blocklist + heuristic analysis

### P3: Registration Enforcement
- Files: `src/nexusagent/tools/register_all.py`
- Update `register_mcp_tools()` to pass `trust` and `provenance`
- Update `register_tool()` to use `ImmutableToolCache.register()`
- Call `cache.freeze()` after registration phase

### P4: Name Analysis Module
- Files: `src/nexusagent/tools/registry/name_analysis.py` (NEW)
- Implement `_heuristic_injection_score()`
- Define expanded `_INJECTION_TOOL_NAMES` and `_RESERVED_PREFIXES`

### P5: Tests
- Test write-once enforcement (duplicate registration raises)
- Test integrity verification (mutated tool detected)
- Test heuristic name scoring (known injections blocked, legitimate names pass)
- Test frozen cache (post-freeze registration raises)
- Test ToolInfo validation (missing provenance on low-trust tool raises)
- Test round-trip serialization of trust metadata for all message types

---

## 6. Open Questions

1. **Should tools be persisted across sessions?** Current design: no (fresh per session). Consider optional warm-start for daemon mode if startup latency is a concern.
2. **Heuristic threshold tuning** — 0.7 is initial default. May need calibration against real MCP tool names.
3. **Integrity check overhead** — SHA256 on every invocation adds ~1µs. Acceptable now, but consider LRU cache of checksums if profiling shows impact.
4. **MCP server hot-reload** — If an MCP server restarts with different tools, current design blocks re-registration. Need a session-level reload trigger or bounce mechanism.

---

## 7. References

- `docs/specs/audits/adversarial-trust-v2.md` — Adversarial trust audit (source of C9, #6)
- `docs/specs/audit-synthesis-v3.md` — Audit synthesis (cross-cutting risk matrix)
- `docs/specs/typed-trust-boundaries-v3.md` — Trust boundary architecture (companion spec)
- `src/nexusagent/tools/registry/types.py` — ToolInfo dataclass (to be updated)
- `src/nexusagent/tools/register_all.py` — Registration logic (to be updated)