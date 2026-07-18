# rw-ast-tools Documentation Portal

Enterprise-grade interactive documentation portal for the rw-ast-tools MCP server.

## Usage

Open `index.html` in any modern browser. No build steps, no server required — all dependencies load from CDN.

## Features

- **7 interactive tabs**: Dashboard, Architecture, Tools, CLI, Performance, Roadmap, Guide
- **5 interactive charts**: Radar (system health), Doughnut (tool distribution), Line (growth), Bar (latency, index size)
- **Mermaid diagrams**: Component architecture, sequence diagram (query path), flowchart (index pipeline)
- **Search + filter**: 77 tools in a live-searchable, category-filterable grid
- **Dark/light mode**: Persisted to localStorage
- **Animated counters**: Stats animate on load
- **Responsive**: Works on desktop and mobile
- **CDN-only deps**: Tailwind CSS, Chart.js, Mermaid — no build steps

## Tech Stack

| Library | CDN | Purpose |
|---------|-----|---------|
| Tailwind CSS | `cdn.tailwindcss.com` | Styling & layout |
| Chart.js | `cdn.jsdelivr.net/npm/chart.js@4.4.7` | Interactive charts |
| Mermaid | `cdn.jsdelivr.net/npm/mermaid@11.4.1` | Architecture diagrams |
| Inter + JetBrains Mono | Google Fonts | Typography |

## Tabs

| Tab | Content |
|-----|---------|
| **Dashboard** | Project stats, radar chart, tool distribution, growth chart, quick links |
| **Architecture** | Three server modes, tech stack, Mermaid component diagram, sequence diagram, deployment config |
| **Tools** | Searchable catalog of all 77 MCP tools across 10 categories |
| **CLI** | 11 commands with examples, format options, workflow examples |
| **Performance** | Speed benchmarks, latency comparison, index size, competitive positioning matrix |
| **Roadmap** | Timeline from v0.1.0→v1.0.0, market sizing charts, revenue projections |
| **Guide** | Quick install (source/pip), Hermes/Claude Code/Gemini CLI integration, environment reference |

Generated: 2026-07-14