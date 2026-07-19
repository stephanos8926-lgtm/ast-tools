cat > /tmp/collect_ast_docs.sh <<'SCRIPT'
#!/usr/bin/env bash

set -euo pipefail

OUT="ast-tools-doc-review-context.txt"

: > "$OUT"

append_file() {
    local file="$1"

    if [[ -f "$file" ]]; then
        {
            echo
            echo "================================================================================"
            echo "FILE: $file"
            echo "================================================================================"
            echo
            cat "$file"
            echo
        } >> "$OUT"
    fi
}

append_section() {
    echo >> "$OUT"
    echo "################################################################################" >> "$OUT"
    echo "$1" >> "$OUT"
    echo "################################################################################" >> "$OUT"
    echo >> "$OUT"
}

append_section "AST-TOOLS DOCUMENTATION REVIEW CONTEXT"

append_section "DOCUMENT INDEX"

find docs -type f | sort >> "$OUT"


append_section "ARCHITECTURE DECISION RECORDS"

for f in \
docs/adrs/0009-reranker-integration.md \
docs/adrs/0010-architecture-governance-engine.md \
docs/adrs/0011-pypi-name-decision-and-publishing-pipeline.md \
docs/adrs/0012-server-architecture-multi-mode.md
do
    append_file "$f"
done


append_section "CURRENT PROJECT STATE"

for f in \
docs/archive/PROJECT_STATE.md \
docs/archive/STATE.md \
docs/archive/SESSION_STATE.md \
docs/archive/WORKFLOW_SUMMARY_2026-07-24.md \
docs/archive/REFACTORING_JOURNAL.md
do
    append_file "$f"
done


append_section "HERMES / AGENT INTEGRATION"

for f in \
docs/archive/RESEARCH_HERMES_MCP_CONTEXT_INJECTION.md \
docs/plans/phase-d-hermes-integration.md \
docs/plans/phase-d-launch.md
do
    append_file "$f"
done


append_section "TOOL DISCOVERY / INTELLIGENCE ARCHITECTURE"

for f in \
docs/specs/tool-discovery-v1.md \
docs/specs/TOOLING_SPEC.md \
docs/specs/incremental-indexing-v1.md \
docs/specs/phase5-knowledge-graph-v1.md \
docs/specs/phase10-2-class-hierarchy-v1.md \
docs/specs/phase10-3-blast-radius-v2.md
do
    append_file "$f"
done


append_section "SERVER ARCHITECTURE"

for f in \
docs/specs/server-architecture-redesign-v1.md \
docs/specs/server-architecture-synthesis-v1.md \
docs/reports/server-architecture-completion.md
do
    append_file "$f"
done


append_section "SECURITY AND AUDIT MATERIAL"

for f in \
docs/specs/audits/forward-audit-comprehensive.md \
docs/specs/audits/reverse-audit-comprehensive.md \
docs/archive/SECURITY_AUDIT_CLI_DEADCODE_20260628.md \
docs/archive/AUDIT_MEDIUM_20260628.md
do
    append_file "$f"
done


append_section "ROADMAP"

for f in \
docs/roadmap/ROADMAP.md \
docs/roadmap/MASTER.SUMMARY.md \
docs/roadmap/planning/LONG_TERM.md \
docs/roadmap/planning/SHORT_TERM.md \
docs/roadmap/planning/RISK_REGISTER.md
do
    append_file "$f"
done


append_section "DOCUMENT SIZE SUMMARY"

wc -l "$OUT" | tee -a "$OUT"

echo
echo "Created: $OUT"
echo "Lines:"
wc -l "$OUT"

SCRIPT

bash /tmp/collect_ast_docs.sh

