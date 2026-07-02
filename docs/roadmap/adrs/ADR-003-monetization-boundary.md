# ADR-003: Monetization vs Open Source Boundary

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools is currently MIT-licensed open source. The roadmap includes monetization features (reports, dashboard, multi-machine). The boundary between what's free and what's paid must be clear, maintainable, and fair.

## Decision

Adopt a **MIT core + paid extensions model:**

- **Core (MIT license):** MCP server, CLI, all 43+ analysis tools, Python SDK, Docker image, setup/doctor/vacuum/curate commands, SKILL.md files, Hermes plugins, REST API gateway
- **Paid (proprietary license):** Web dashboard, formatted reports (PDF/DOCX), multi-machine support, advanced analytics (concept extraction, cross-repo graph), SaaS hosting
- **Bridge (dual license):** Backup/restore (free base, paid incremental+encrypted), reporting (free raw stats, paid formatted)

### Implementation Strategy

```python
# Feature gating using a capabilities registry
CAPABILITIES = {
    "raw_stats": Feature(tier="free", enabled=True),
    "formatted_reports": Feature(tier="paid", enabled=check_license()),
    "web_dashboard": Feature(tier="pro", enabled=check_license("pro")),
    "multi_machine": Feature(tier="pro", enabled=check_license()),
}
```

### Free Tier Guarantees

- All existing v0.1.0 functionality remains free forever
- The MCP protocol and tools are always free
- CLI is always free
- Raw codebase stats (CSV/JSON/text) are always free
- No artificial rate limits on free tier
- No telemetry, no ads, no data collection

### Paid Tier Value Proposition

Users pay for **presentation, convenience, and scale** — not for essential functionality:
- Formatted reports save time (a few hours/month)
- Dashboard provides at-a-glance insights
- Multi-machine enables CI/CD integration across a fleet
- SaaS removes ops burden

### Consequences

- Positive: Core remains fully open source — community trust maintained
- Positive: Clear upgrade path from free to paid
- Positive: Paid features are additive (not degradations)
- Negative: Dual license management adds complexity
- Negative: License validation requires offline-capable system

## Alternatives Considered

1. **Open core with CLA**: Rejected — CLA discourages contributions
2. **Source available (BSL/MongoDB)**: Rejected — conflicts with community norms for developer tools
3. **Donation-only**: Rejected — insufficient for sustainable development