# Phase 5 Implementation Plan — Monetization & Advanced Features (FINAL)

> **Status:** ✅ Final — Audited (Forward ✅, Reverse ✅, Adversarial ✅)  
> **Phase:** 5  
> **Timeline:** 4 weeks  
> **Dependencies:** Phase 4 (agent ecosystem, multi-machine operational)  
> **Finalized:** 2026-07-31  

---

## Audit Results

| Audit | Findings | Resolution |
|-------|----------|------------|
| **Forward** | 3 findings (Stripe option, concept extraction experimental) | ✅ All incorporated |
| **Reverse** | 4 findings (grace period, trial mechanism, metering API, purchase flow) | ✅ All incorporated |
| **Adversarial** | 4 findings (key cracking, tier bypass, tenant isolation, degradation UX) | ✅ All incorporated |

## Key Changes from Draft

- License system: asymmetric keys (RSA-4096), `license_id` in JWT for revocation lookup
- Grace period: 30 days after license expiry before feature degradation
- Free tier trial: `ast-tools license trial Pro --days 14` for offline trial
- Degradation UX: expired licenses show clear upgrade prompt, NOT crashes
- Config file overrides for tier are explicitly rejected (only signed JWT is valid)
- SaaS multi-tenant: tenant ID middleware on every endpoint, row-level security in DB
- Self-hosted purchase: web store page (Stripe Checkout) → generates signed license key
- Usage metering: per-user, per-day API call count stored in local analytics DB
- Concept extraction: clearly marked as EXPERIMENTAL, requires explicit `--llm` flag

## Feature Gating Matrix (Final)

| Feature | Free | Team ($29) | Pro ($49) | Enterprise |
|---------|------|-----------|-----------|------------|
| MCP Server | ✅ | ✅ | ✅ | ✅ |
| CLI | ✅ | ✅ | ✅ | ✅ |
| Python SDK | ✅ | ✅ | ✅ | ✅ |
| All 43 analysis tools | ✅ | ✅ | ✅ | ✅ |
| Raw stats (CSV/JSON/TEXT) | ✅ | ✅ | ✅ | ✅ |
| Config/Doc/Curator/Vacuum | ✅ | ✅ | ✅ | ✅ |
| Local backup/restore | ❌ | ✅ | ✅ | ✅ |
| Markdown reports | ❌ | ✅ | ✅ | ✅ |
| DOCX/PDF reports | ❌ | ✅ | ✅ | ✅ |
| Encrypted backup | ❌ | ❌ | ✅ | ✅ |
| Remote backup (S3) | ❌ | ❌ | ✅ | ✅ |
| Web Dashboard | ❌ | ❌ | ✅ | ✅ |
| Multi-machine | ❌ | ❌ | ✅ | ✅ |
| Pro Dashboard | ❌ | ❌ | ✅ | ✅ |
| Concept extraction | ❌ | ❌ | ✅ | ✅ |
| SaaS Hosting | ❌ | ❌ | ❌ | ✅ |
| SSO/SAML | ❌ | ❌ | ❌ | ✅ |
| Dedicated Support | ❌ | ❌ | ❌ | ✅ |

## Verification Checklist

- [ ] Free tier: all core tools work without any license file
- [ ] Free tier: `ast-tools insights --format markdown` with clear "upgrade" prompt
- [ ] License activation: `ast-tools license activate <key>` → tier features unlocked
- [ ] License expiry: 30-day grace period with daily warning
- [ ] License expiry after grace period: clear upgrade prompt, no crash
- [ ] Config file: `tier: pro` in config.yaml is IGNORED (only JWT is valid)
- [ ] License revocation: license_id added to block list → features revert to free
- [ ] SaaS: Tenant A cannot access Tenant B's data
- [ ] SaaS: Stripe test checkout → license key generated → works at CLI
- [ ] Concept extraction: `ast-tools kg concepts --llm local` returns meaningful results
- [ ] Pro Dashboard: all sections render (overview, index browser, dep explorer, backup mgr, curator controls)
- [ ] VS Code extension: commands registered in command palette
- [ ] All existing tests pass