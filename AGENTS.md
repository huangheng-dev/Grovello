# Grovello Product and Engineering Constitution

This file is the controlling instruction for AI coding agents, automation, maintainers, and contributors in this repository. Current explicit instructions from the product owner take precedence. Changes to the product boundary or core architecture require an Architecture Decision Record (ADR).

## 1. Product definition

Grovello is an open-source, multi-agent Growth OS. It shares brand knowledge, product data, ideal customer profiles, customer identity, consent, commercial facts, and revenue outcomes across the enterprise. Governed workflows and versioned connectors coordinate content, SEO, GEO, video, social, advertising, lead development, CRM, sales, customer success, retention, and experimentation. Real revenue, margin, retention, and experiment results drive the next strategy cycle.

The canonical product brand is **Grovello**, pronounced **grow-VELL-oh**. Product copy uses `Grovello`; code packages, modules, environment variables, and runtime identifiers use the lowercase `grovello` or uppercase `GROVELLO` namespace as appropriate.

The product category remains **Enterprise Growth OS**. Its international-market capability is **Global Go-to-Market & Revenue Growth**, and its first golden acceptance journey is **Global B2B Growth**. This hierarchy is deliberate:

- Grovello serves enterprise growth across domestic and international markets; it is not limited to export businesses.
- "Foreign Trade" is not the canonical English product category. Use global go-to-market, global B2B growth, cross-border growth, international sales, or export sales only where their narrower meaning is intended.
- The first golden journey proves a complete cross-border B2B loop. It is an integration and acceptance priority, not a boundary that removes other growth models or channels.
- The default public fixture is the fictional Northstar Industrial workspace: an industrial automation supplier evaluating and entering the German B2B market. Industry, origin country, destination market, and product type remain configuration and data, never hard-coded domain structure.

Grovello is not a copywriting tool, bulk sender, social scheduler, CRM skin, prompt wrapper, dashboard-only demo, or a collection of disconnected agents.

Open source is a delivery and collaboration model. It is not permission to weaken the product loop, remove channels, hide required services behind a private API, or make the self-hosted core unusable.

## 2. Non-negotiable growth loop

Every core capability must map its inputs, governed execution, output, owner, permissions, and measurable feedback to this loop:

```text
Goals and budgets
→ market, customer, and competitive intelligence
→ AI growth strategy and battle plans
→ content / SEO / GEO / video / social / ads / outbound
→ publishing, media spend, and multichannel outreach
→ visitors, accounts, contacts, leads, and unified conversations
→ qualification, nurture, CRM opportunities, and sales collaboration
→ quotes, negotiation, contracts, orders, invoices, and payments
→ onboarding, customer success, retention, expansion, and referrals
→ revenue attribution, cost, experiment results, and health signals
→ the next strategy and budget allocation
```

Generation, publication, sending, or lead creation alone never constitutes a completed business loop.

### 2.1 First golden acceptance journey

The first end-to-end acceptance journey is **Global B2B Growth**:

```text
workspace and business onboarding
→ brand, product, offer, evidence, and knowledge
→ target market, ICP, buying committee, goals, and budget
→ market and competitive intelligence
→ AI strategy, plan, risk review, and approval
→ content / SEO / GEO / social / ads / lead discovery / outreach
→ visitors, accounts, contacts, leads, and conversations
→ qualification, meetings, opportunities, and sales collaboration
→ quotes, negotiation, contracts, orders, invoices, and payments
→ onboarding, customer success, renewal, expansion, and referral
→ attribution, margin, retention, and experiment evidence
→ the next strategy and budget decision
```

The reference fixture is the fictional Northstar Industrial workspace described above, but acceptance must be repeatable with another B2B product, service, software offer, origin country, and destination market without changing the canonical domain model.

The complete product-system blueprint is maintained in `docs/en/product-system-blueprint.md` and `docs/zh-CN/product-system-blueprint.md`. Delivery order, phase gates, owner inputs, and measurable exit criteria are maintained in `docs/en/product-delivery-roadmap.md` and `docs/zh-CN/product-delivery-roadmap.md`. An implementation may deepen a phase without weakening the final loop, but it must not claim golden-path completion while a downstream revenue or learning stage is simulated.

## 3. Fixed product domains

The product, navigation, permissions, APIs, events, and data model retain these ten top-level domains:

1. Growth Command: overview, growth journeys, architecture, goals, budgets, AI decisions, battle plans, approvals.
2. Brand & Market: brand rules, products, offers, price books, markets, localization, ICP, enterprise knowledge, digital assets.
3. Content & Traffic: content factory, website/page factory, SEO, GEO, video matrix, publishing.
4. Channels & Advertising: channel accounts, social operations, paid media.
5. Leads & Outreach: lead discovery, enrichment, email, multichannel outbound, unified inbox.
6. Customers & Revenue: CRM, opportunities, AI sales, quotes, contracts, orders, invoices, payments.
7. Customer Growth: onboarding, success, health, retention, renewal, expansion, referrals.
8. Data & Intelligence: shared data, attribution, reports, experiments, market and competitor intelligence.
9. Automation Runtime: runs, durable workflows, agents, templates, connectors, model routing, public APIs.
10. Organization & Governance: workspaces, members, roles, policies, consent, security, audit, settings.

Domains may gain capabilities. They must not be silently removed, merged into unrelated concepts, or collapsed into a single generic agent.

## 4. Shared business objects

Modules reference canonical IDs rather than storing conflicting private copies. Core objects include:

- Organization, Workspace, User, Team, Role, Permission, Policy, Approval, Consent, Suppression, Secret, AuditEvent.
- Brand, Product, Offer, PriceBook, CaseStudy, KnowledgeDocument, KnowledgeChunk, Asset, ICP, Market.
- Goal, Budget, Strategy, Campaign, Brief, Content, ContentVariant, Page, Keyword, Question, Claim, Evidence, Citation, Publication, AdCampaign, Creative, Touchpoint, Message, Conversation, Experiment.
- Account, Contact, Lead, CustomerIdentity, Activity, Opportunity, Meeting, Quote, Contract, Order, Invoice, Payment, RevenueEvent, OnboardingPlan, CustomerHealth, Renewal, Expansion, Referral.
- Agent, AgentVersion, Workflow, WorkflowVersion, Run, Task, ToolCall, Connector, ConnectorAccount, ModelConfig, PromptVersion, MetricDefinition, MetricEvent, AttributionResult, Report, Insight, Recommendation.

Every important execution record carries workspace, actor, business purpose, run and idempotency identifiers, input versions, model/tool/connector lineage, approval state, cost, outcome, failure details, business linkage, timestamps, and audit metadata.

## 5. Architecture boundaries

- Next.js and React own web experience, SSR, localization, sessions, and a thin BFF. They do not own business truth.
- FastAPI owns versioned business APIs and domain application services.
- The backend starts as a modular monolith plus independently deployable workers. Service extraction requires a measured scaling, isolation, or ownership reason.
- Temporal owns deterministic durable workflows, timers, retries, compensation, cancellation, and long-lived approvals.
- LangGraph owns model reasoning graphs, agent state, model/tool selection, checkpoints, and agent-level human interruption.
- PostgreSQL is the transactional source of truth. Valkey, OpenSearch, ClickHouse, caches, vector indexes, and projections are rebuildable derivatives.
- External providers are accessed through versioned connectors. Official APIs and webhooks precede Playwright fallback automation.
- MCP is an agent-tool protocol, not a replacement for transactional APIs, webhooks, event streams, or database access.
- Models are accessed through a provider-neutral Model Router. Domain code must not depend on one model vendor.

## 6. Formal technology baseline

- Web: Node.js 24 LTS, Next.js 16 App Router, React 19, TypeScript 6.0, next-intl, TanStack, React Hook Form, Zod, Zustand, Material Symbols.
- API: Python 3.13 target, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, HTTPX.
- Durable orchestration: Temporal. Agent runtime: LangGraph with durable PostgreSQL checkpoints.
- Data: PostgreSQL 18 + pgvector, Valkey, S3-compatible object storage. OpenSearch and ClickHouse are scale profiles, not initial sources of truth.
- Events: transactional outbox from day one; Kafka/Debezium when durable multi-consumer event streaming is enabled.
- Identity and security: OIDC/SAML-compatible provider, Keycloak reference profile, OpenFGA for fine-grained authorization, OpenBao for production secrets.
- Delivery: Docker Compose for reproducible self-hosting; Helm/Kubernetes/KEDA/Argo CD/OpenTofu profiles as scale requires.
- Observability: OpenTelemetry across API, workflow, agent, connector, and web boundaries.

Changing this baseline requires an ADR covering impact, migration, compatibility, security, rollback, and product-owner approval.

## 7. Reliability, safety, and compliance

- All tenant-owned tables contain `workspace_id`; PostgreSQL row-level security is defense in depth, not a substitute for service authorization.
- HTTP requests never execute long generation, crawling, media, publishing, sending, or bulk synchronization inline.
- Workflows and consumers are idempotent. External calls have bounded timeouts, classified errors, retry policy, and compensation where applicable.
- Outbound messages, budgets, discounts, contracts, destructive actions, sensitive exports, and high-risk agent tools support policy-driven approval.
- Secrets never enter source code, browser bundles, prompts, logs, screenshots, seed data, or public issues.
- Contact source, legal basis, consent, suppression, unsubscribe, retention, and deletion are first-class data.
- Browser automation must not evade platform controls, steal data, impersonate people, conceal unsubscribe, or bypass risk systems.
- Prompt injection, untrusted page content, tool escalation, tenant leakage, and model data policy are explicit threat-model concerns.

## 8. Internationalization

English is the source language. Simplified Chinese is a first-class locale. UI strings use message keys; locale routes use `/en` and `/zh-CN`. Product behavior changes update both locale resources and both language documentation. Business content variants are versioned records, not UI translations.

## 9. Open-source requirements

- The core remains self-hostable without an author-controlled private service.
- Provider, connector, agent, workflow, importer/exporter, renderer, webhook, and API extension contracts are public and versioned.
- Repository history contains no real credentials, customer data, personal machine paths, unlicensed assets, or unverifiable binaries.
- Claims distinguish verified, experimental, simulated, planned, and third-party-dependent capabilities.
- Dependencies are reviewed for license, security, maintenance, size, and replacement cost. Lockfiles and reproducible images are required.
- The product owner selects the project license. AI agents must not add or change `LICENSE` without explicit approval.

## 10. Required change alignment

Before implementation, identify: objective, product domain, shared objects, inputs, actions, outputs, feedback path, permissions/approval, and verification. Reject changes that create data islands, fake closure, provider lock-in, unbounded agents, hidden external dependencies, or unverified capability claims.

Definition of Done includes relevant normal, loading, empty, failed, partial, unauthorized, approval, retry, cancellation, mobile, accessibility, schema, migration, contract, idempotency, audit, testing, documentation, and capability-status behavior.
