# Grovello

**Open-source, multi-agent Growth OS for global go-to-market and revenue orchestration.**

[简体中文](./README.zh-CN.md) · [Architecture](./docs/en/architecture.md) · [System blueprint](./docs/en/product-system-blueprint.md) · [Delivery roadmap](./docs/en/product-delivery-roadmap.md) · [Technology stack](./docs/en/technology-stack.md) · [Getting started](./docs/en/getting-started.md)

Grovello coordinates content, SEO, GEO, video, social, advertising, lead development, CRM, sales, customer success, retention, and experiments around shared business context and measurable revenue outcomes.

## Product positioning

- **Product brand:** Grovello, pronounced **grow-VELL-oh**.
- **Product category:** Enterprise Growth OS for domestic and international growth.
- **Global-market capability:** Global Go-to-Market & Revenue Growth.
- **First golden acceptance journey:** Global B2B Growth, from business onboarding and market intelligence through acquisition, sales, revenue, retention, attribution, and the next AI strategy cycle.
- **Reference fixture:** the fictional Northstar Industrial workspace, an industrial automation supplier evaluating and entering the German B2B market. It is replaceable acceptance data, not an industry or export-only product boundary.

The English product vocabulary does not use “Foreign Trade” as the umbrella category. Industry, product type, origin country, and destination market remain configurable business data.

## Status

Grovello is in foundation development. The repository distinguishes verified, simulated, planned, and third-party-dependent capabilities. A visible route or contract does not imply that an external platform is connected.

## Architecture

- Next.js and React provide the English-first, bilingual product experience.
- FastAPI provides versioned business APIs and a modular domain core.
- Temporal owns durable deterministic workflows.
- LangGraph owns agent reasoning and agent-level human interruption.
- PostgreSQL is the business source of truth; derived stores remain rebuildable.
- Versioned connectors isolate providers, channels, MCP tools, and browser fallbacks.

## Repository layout

```text
apps/web              Next.js product console
services/api          FastAPI modular business API
services/workers      Temporal, agent, and connector workers
packages              UI, i18n, product config, API client, contracts
docs/en               English documentation
docs/zh-CN            Simplified Chinese documentation
infra                 Compose, observability, and future scale profiles
```

## Quick start

```bash
pnpm install
pnpm dev
```

The web console runs at `http://localhost:3000` and redirects to English by default. Use the language switcher to open Simplified Chinese.

For the API and full self-hosted stack, see [Getting started](./docs/en/getting-started.md).

For the build order, phase gates, and golden-path Definition of Done, see the [product delivery roadmap](./docs/en/product-delivery-roadmap.md).

## License

Grovello is licensed under the [GNU Affero General Public License v3.0 only](./LICENSE). See [the licensing decision](./docs/en/licensing.md) for the project policy and hosted-service implications.
