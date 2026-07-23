# Grovello product delivery roadmap

This document converts the product constitution into an executable delivery sequence. `AGENTS.md` remains the controlling instruction. Architecture changes require an ADR; product-owner decisions are recorded here and must be reflected in both languages.

## 1. Confirmed positioning

| Level | Canonical term | Meaning |
| --- | --- | --- |
| Product | Enterprise Growth OS | One governed system for domestic and international enterprise growth |
| International capability | Global Go-to-Market & Revenue Growth | Market entry, demand, pipeline, revenue, retention, and learning across countries |
| First golden acceptance journey | Global B2B Growth | The first complete, measurable end-to-end journey |
| Replaceable reference fixture | Fictional Northstar Industrial workspace entering the German B2B market | Acceptance data with a demanding buying cycle, not the product boundary |

“Foreign Trade” is not the umbrella English category. “Export sales” and “international sales” may describe narrower workflows. “外贸” may be used in Chinese customer-facing context when it improves comprehension, but it must not redefine the product or canonical model.

The golden journey is intentionally specific enough to test. It must never hard-code:

- an industry, origin country, destination market, language, or currency;
- physical goods when the same canonical model can represent services or software;
- provider-specific channel fields inside shared business objects;
- China-export assumptions in permissions, taxonomies, workflows, or UI routes.

## 2. Reference fixture

The canonical public seed fixture is the fictional **Northstar Industrial** workspace, representing an industrial automation supplier evaluating and entering the German B2B market. It should exercise:

- multilingual brand, product, offer, certification, case-study, pricing, and knowledge evidence;
- market selection, ICP, account criteria, buying committees, goals, budgets, and approval policies;
- website, SEO, GEO, content, video, social, advertising, lead discovery, and outbound;
- long-cycle qualification, technical questions, meetings, quotes, negotiation, contracts, orders, invoices, and payments;
- onboarding, adoption, customer health, renewal or repeat purchase, expansion, and referral;
- attribution, margin, retention, experiment evaluation, and the next AI strategy decision.

Real company data is not required for the architecture. If real data is later used, it must be authorized, sanitized, secret-free, and excluded from public fixtures unless the owner explicitly approves publication.

## 3. End-to-end operator journey

1. Create an organization and workspace; configure locale, time zone, currency, team, roles, and policies.
2. Onboard the brand, products, offers, price books, claims, evidence, assets, knowledge, cases, and commercial rules.
3. Define target markets, languages, ICPs, account criteria, buying committees, goals, budgets, KPIs, and risk appetite.
4. Connect owned properties, analytics, communication channels, social and ad accounts, CRM, calendars, and commercial systems.
5. Collect market, keyword, question, competitor, account, news, event, and intent signals with source and freshness metadata.
6. Generate an AI strategy and battle plan with assumptions, expected impact, cost, evidence, risks, owners, and approval gates.
7. Execute approved content, SEO, GEO, page, video, social, advertising, lead discovery, enrichment, and outreach workflows.
8. Resolve visitors, companies, contacts, leads, messages, replies, and meetings into one identity graph and customer timeline.
9. Score, route, qualify, nurture, and convert demand into CRM opportunities with human and AI sales collaboration.
10. Produce governed quotes, negotiations, contracts, orders, invoices, payments, and recognized revenue events.
11. Run onboarding, success, health monitoring, retention, renewal or repeat purchase, expansion, advocacy, and referral.
12. Attribute revenue and margin to touchpoints and experiments, evaluate retention and cost, and feed evidence into the next strategy and budget cycle.

## 4. Delivery sequence and phase gates

The sequence is dependency-driven, not a reduced product scope. Later domains remain part of the target architecture from day one. A phase may be developed in parallel where dependencies permit, but its exit gate cannot be skipped.

| Phase | Outcome | Required deliverables | Exit gate |
| --- | --- | --- | --- |
| 0. Product foundation | One enforceable product and engineering baseline | Constitution, bilingual console, domain navigation, API/workflow/agent/connector boundaries, capability status | CI passes; seed data is labeled; no external capability is falsely claimed |
| 1. Organization and access | Safe multi-workspace operation | Organization, workspace, user, team, role, policy, session, audit, tenant isolation | Authorized and unauthorized paths, tenant isolation, audit, recovery, and admin flows pass |
| 2. Shared business truth | All agents work from the same facts | Brand, product, offer, price book, market, ICP, evidence, knowledge, assets, cases, import and versioning | A complete business profile can be created, validated, versioned, retrieved, and cited without conflicting copies |
| 3. Goals and governance | Execution has measurable intent and authority | Goals, budgets, KPI definitions, approval matrix, consent, suppression, risk classes, cost limits | Every proposed external action resolves purpose, owner, budget, policy, approval, and measurable outcome |
| 4. Connector platform | Providers can be added without changing domain logic | Registry, manifest, auth references, capability and risk contracts, health, rate limits, webhooks, idempotency, sandbox, official API and browser-fallback rules | A representative read, write, webhook, failure, retry, revocation, and audit test passes through the same versioned contract |
| 5. Traffic engine | Approved strategy produces measurable demand | Content, website/pages, SEO, GEO, video, publishing, social operations, advertising, creative and experiment variants | A plan becomes published or launched assets; impressions, visits, engagement, cost, variants, and source lineage return to canonical events |
| 6. Lead intelligence | Anonymous demand and target accounts become governed prospects | Visitor/company resolution, account discovery, contact enrichment, validation, deduplication, source, legal basis, scoring | A lead is traceable to source and purpose, deduplicated, policy-eligible, scored, and connected to account/contact identity |
| 7. Outreach and conversations | Prospects can enter a measurable two-way journey | Email, supported multichannel sequences, scheduling, inbox, reply classification, opt-out, bounce, suppression, handoff | An approved sequence sends, receives and classifies a reply, respects suppression, creates a timeline, and can stop or hand off safely |
| 8. CRM and opportunity | Qualified conversations become managed pipeline | Lifecycle, routing, tasks, meetings, qualification, opportunity stages, forecast, AI sales assistance | A qualified lead becomes an opportunity with owner, history, next action, forecast, evidence, and loss/win reason |
| 9. Commercial and revenue | Pipeline reaches verified economic outcome | Quote, discount approval, contract, order, invoice, payment, currency, tax references, revenue and margin events | One opportunity closes through governed commercial records to reconciled payment/revenue without inventing financial truth |
| 10. Customer growth | Revenue continues into retained value | Onboarding, milestones, adoption, health, support context, renewal/repeat purchase, expansion, advocacy, referral | A customer has an owned success plan, health evidence, risk action, and a measured retention, expansion, or referral outcome |
| 11. Data and intelligence | The system can explain performance | Identity graph, event taxonomy, metric registry, lineage, attribution, cost, margin, experiments, reports, data quality | A revenue result is reproducibly attributed with known uncertainty; reports reconcile to source events and expose data quality |
| 12. AI decision cycle | Evidence changes the next action | Decision context, recommendations, plan generation, forecast scenarios, evaluation, budget reallocation, approval, rollback | The system proposes a new plan from real outcomes, explains evidence and uncertainty, passes policy, and records accepted or rejected decisions |
| 13. Open-source release | Others can operate and extend the real core | License decision, install path, migrations, fixtures, extension SDK/contracts, security docs, upgrade/rollback, contributor and release process | A clean environment can self-host, run the golden journey, replace providers, upgrade safely, and reproduce verification without a private author service |

The approved P2-D architecture, security, and delivery boundary is specified in the [Workspace Onboarding and Structured Import implementation baseline](workspace-onboarding-import-baseline.md). P2-D1 implements isolated persistence and source verification; P2-D2 adds governed mapping, bounded parsing, deterministic validation, exact deduplication, and redacted review evidence; P2-D3 adds immutable dry-run change sets, policy approval handoff, durable apply/cancellation/compensation, canonical business-truth writes, and exact profile activation snapshots. P2-D4 adds the bilingual thin-BFF operator journey and has passed local multi-service acceptance across PostgreSQL, Temporal, private versioned MinIO, and ClamAV, including audit/outbox lineage and fresh-workspace exact activation. Onboarding and imports remain `foundation`, not `operational`, until production identity, general approval, runbooks, and non-development deployment evidence are connected.

## 5. First golden-path acceptance contract

The first journey is complete only when all of the following are operational with real internal state and appropriately connected or controlled test providers. Labeled simulations may support development, but they do not satisfy the final gate.

### Business setup

- A new workspace can configure business identity, product, offer, evidence, target market, ICP, goal, budget, policy, and ownership.
- Agents retrieve versioned business truth and cite the evidence used for claims, answers, quotes, and recommendations.

### Strategy and execution

- Market signals produce a reviewable strategy with assumptions, cost, impact forecast, risk, owner, and approval state.
- One approved battle plan creates and distributes channel-specific assets rather than copying one generic output.
- SEO and GEO retain keyword/question intent, claims, citations, page relationships, publication status, and measurable search/answer outcomes.

### Demand and conversations

- A visitor or discovered account can become a deduplicated account/contact/lead with source, purpose, consent or legal basis, and suppression status.
- At least one inbound and one outbound route create unified conversations, replies, tasks, and meetings.
- Provider failure, rate limiting, credential revocation, retry, cancellation, and unsubscribe behavior are visible and auditable.

### Sales and revenue

- Qualification converts a lead into an opportunity without losing its acquisition and conversation lineage.
- Quote, approval, contract, order, invoice, and payment records remain linked, versioned, permissioned, and auditable.
- Revenue and margin come from commercial records or connected systems, never from model inference.

### Customer and learning

- A won customer enters onboarding and has adoption, health, retention, expansion, and referral signals.
- Attribution connects cost and touchpoints to pipeline and revenue with an explicit model and uncertainty.
- Experiment and retention evidence changes a subsequent AI recommendation, budget, or plan; a human can accept, edit, reject, pause, or roll back the decision.

### System quality

- Normal, loading, empty, partial, failed, unauthorized, approval, retry, cancellation, and recovery states are implemented.
- Tenant isolation, secret handling, consent, suppression, idempotency, audit, accessibility, internationalization, observability, backup, migration, and rollback checks pass.
- Capability status changes only with evidence. A UI route, connector manifest, agent prompt, or successful demo call is not equivalent to an operational capability.

## 6. Connector coverage principle

Grovello keeps a broad channel architecture while validating connector classes in a controlled order. The connector registry must support owned web properties, search, social, advertising, email, messaging, CRM, calendar, commerce, finance, analytics, storage, knowledge, and model providers. Operational status is granted per connector account and capability after provider-specific verification.

The first reference integration bundle is fixed: Grovello-owned pages and event intake, standards-based email send/reply, a calendar booking adapter, generic signed webhooks, native CRM/opportunity records, native commercial records, and manual or connected payment reconciliation. Provider-specific production accounts are selected when authorized access exists and are verified independently. Browser automation is a controlled fallback, never a promise to bypass platform restrictions.

## 7. Decision register

### Confirmed

| ID | Decision |
| --- | --- |
| POS-001 | Grovello remains an Enterprise Growth OS, not an export-only or industrial-only product |
| POS-002 | The international capability is named Global Go-to-Market & Revenue Growth |
| POS-003 | The first golden acceptance journey is Global B2B Growth |
| POS-004 | Industrial automation is replaceable reference data, not canonical product structure |
| POS-005 | Industry, origin, destination, language, currency, and provider are configurable data |
| POS-006 | The public fixture is the fictional Northstar Industrial workspace; real data is optional and never required for architecture |
| POS-007 | Default autonomy uses the R0–R4 risk tiers defined in the system blueprint |
| POS-008 | The first provider-neutral reference integration bundle is fixed in the system blueprint |
| POS-009 | The canonical product brand and code namespace are Grovello and `grovello` |
| POS-010 | Grovello is distributed under `AGPL-3.0-only`, selected by the product owner on July 19, 2026 |

### Remaining owner inputs

| ID | Input needed | Why it matters |
| --- | --- | --- |
| EXT-001 | Authorized provider accounts, credentials, budgets, and optional real business data | Required only when enabling specific production connectors; does not change architecture |

AI agents must not fabricate external access or silently change the legal license. They may prepare provider-neutral configuration, comparisons, prototypes, and reversible groundwork while keeping the deployment dependency explicit.

## 8. Scope evolution

After the Global B2B Growth journey is operational, additional golden journeys can reuse the shared core:

1. Global B2B services and SaaS, adding trials, subscriptions, seats, usage, and recurring revenue where required.
2. Cross-border B2C commerce, adding catalog, cart, checkout, tax, fulfillment, returns, marketplace settlement, and consumer lifecycle.
3. Partner and channel growth, adding recruitment, territory, deal registration, enablement, incentives, and partner attribution.
4. Domestic-market variants, reusing the same model with market-appropriate channels, policies, language, and commercial flows.

These journeys extend the product; they do not fork it into disconnected applications.
