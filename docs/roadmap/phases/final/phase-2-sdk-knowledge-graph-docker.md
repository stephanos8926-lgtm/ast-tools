# Phase 2 Implementation Plan — SDK, Knowledge Graph & Docker (FINAL)

> **Status:** ✅ Final — Audited (Forward ✅, Reverse ✅, Adversarial ✅)  
> **Phase:** 2  
> **Timeline:** 3 weeks  
> **Dependencies:** Phase 1 (data lifecycle commands operational)  
> **Finalized:** 2026-07-31  

---

## Audit Results

| Audit | Findings | Resolution |
|-------|----------|------------|
| **Forward** | 10 findings | ✅ All incorporated |
| **Reverse** | 10 findings (incl. auto-start server, SDK CI pipeline, Docker image tags, arm64, systemd hardening) | ✅ All incorporated |
| **Adversarial** | 8 findings (incl. input sanitization, graph traversal caps, credential masking, digest pinning) | ✅ All incorporated |

## Key Changes from Draft

- SDK `Client()` now auto-starts MCP server if not running (`auto_spawn=True` flag, default True)
- Added SDK direct-import mode for performance (`ast_tools_sdk.direct`)
- Added SDK input sanitization before MCP protocol calls
- Added SDK CI pipeline in GitHub Actions
- SDK version pinned to match core `ast_tools` version
- Knowledge graph traversal has hard caps: `max_depth=10`, `max_results=10000`
- Added project_id scoping to all KG queries (prevents cross-project mixing)
- Docker image: multi-arch (amd64 + arm64), digest pinning in production, read-only config mount
- Docker image tags: `latest`, `stable`, `vX.Y.Z`, `edge`
- Systemd service: separate user + system service files with security hardening (PrivateTmp, ProtectHome, ReadOnlyPaths)
- MCP transport for SDK: auto-detect (stdio for local, TCP for remote + TLS)

## Verification Checklist

- [ ] `pip install sdk/python/` installs cleanly
- [ ] `Client()` connects to running server without manual start
- [ ] `Client(auto_spawn=False)` raises helpful error if no server
- [ ] SDK search, analyze, stats return expected types
- [ ] SDK error handling: MCP errors → Python exceptions with clear messages
- [ ] KG query: BFS depth 3 on 100K symbols < 500ms
- [ ] KG query: max_depth capped at 10 (hard limit)
- [ ] Docker build: `docker buildx build --platform linux/amd64,linux/arm64 .`
- [ ] Docker read-only config mount prevents container tampering
- [ ] Systemd service: `ast-tools server install` + `start` + `status` all work
- [ ] Systemd service: `systemd-analyze security ast-tools` score > 5
- [ ] CI pipeline: SDK tests run in separate job
- [ ] All existing tests pass