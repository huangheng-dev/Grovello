# Grovello complete product-system blueprint

This blueprint fixes the target product architecture before feature implementation. It defines the complete closed loop, responsibilities, contracts, states, governance, recovery, and UI entry points. Implementation may be incremental; the target architecture may not be silently narrowed. `AGENTS.md` remains the controlling instruction.

## 1. Architecture closure

Grovello uses one product, one canonical business model, one durable workflow plane, many bounded agents, and versioned provider connectors.

```text
Enterprise Growth OS
├─ Shared business truth
├─ Growth command and policy
├─ Specialized agent reasoning
├─ Durable workflow execution
├─ Provider-neutral connectors
├─ Customer and revenue operations
└─ Outcome, attribution, experiment, and learning feedback
```

The first golden journey is Global B2B Growth. The default public fixture is the fictional **Northstar Industrial** workspace: an industrial automation supplier evaluating and entering a German B2B market. The company, industry, origin, market, language, currency, and channels are replaceable data.

## 2. Complete domain map

| Domain | Owns | Consumes | Produces | Primary UI entry |
| --- | --- | --- | --- | --- |
| Growth Command | Goals, budgets, strategies, plans, decisions, approvals | Outcomes, insights, constraints | Approved priorities and executions | Overview, Growth Journeys, Goals, Decisions, Plans, Approvals |
| Brand & Market | Brand, product, offer, price book, market, ICP, evidence, knowledge, assets | Business imports and owner edits | Versioned business truth | Guidelines, Products & Offers, Markets & Localization, ICP, Knowledge, Assets |
| Content & Traffic | Briefs, content variants, pages, keywords, questions, claims, citations, publications | Strategy, business truth, market intent | Traffic assets and measurable touchpoints | Content Factory, Sites, SEO, GEO, Video, Publishing |
| Channels & Advertising | Channel accounts, social operations, ad campaigns, audiences, creatives, spend | Approved assets, budgets, policies | Delivery receipts, reach, engagement, cost, conversion events | Accounts, Social, Advertising |
| Leads & Outreach | Accounts, contacts, leads, enrichment, sequences, messages, conversations | ICP, intent, consent, channel capabilities | Qualified demand and meetings | Lead Discovery, Email, Multichannel Outbound, Unified Inbox |
| Customers & Revenue | CRM activity, opportunities, meetings, quotes, contracts, orders, invoices, payments | Qualified demand and commercial rules | Pipeline, recognized outcomes, revenue and margin events | Accounts & Opportunities, AI Sales, Commercial Operations |
| Customer Growth | Onboarding, milestones, adoption, health, renewal, repeat purchase, expansion, referral | Won customers, product usage, support and billing signals | Retention, expansion and advocacy outcomes | Success, Retention & Renewal, Expansion & Referrals |
| Data & Intelligence | Identity graph, event taxonomy, metrics, attribution, reports, experiments, market intelligence | Every domain event and external signal | Trusted evidence, insights and recommendations | Data Center, Attribution, Reports, Experiments, Intelligence |
| Automation Runtime | Agents, workflows, runs, tasks, connectors, models, templates, APIs | Approved intents and domain commands | Durable execution, lineage, cost, failure and result records | Runs, Workflows, Agents, Marketplace, Connectors, Models, Developer |
| Organization & Governance | Organizations, workspaces, members, roles, policies, consent, secrets, audit | Identity, owner policy and legal configuration | Authorization, approval, suppression and audit decisions | Members, Compliance, Audit, Settings |

No domain stores a private copy of another domain's canonical object. Cross-domain interaction uses IDs, versioned APIs, commands, domain events, and projections.

## 3. Golden journey workflow graph

| Durable workflow | Trigger | Required state | Success event | Compensation or recovery |
| --- | --- | --- | --- | --- |
| Business onboarding | Workspace created | Brand, market and policy drafts | `BusinessProfileActivated` | Preserve draft, report validation gaps |
| Market intelligence | Market selected or scheduled refresh | Sources, freshness policy, ICP | `MarketBriefPublished` | Mark stale/partial evidence; never fabricate gaps |
| Strategy planning | Goal, budget or material signal | Evidence, constraints, forecast model | `GrowthPlanApproved` | Revise, reject, expire or supersede plan |
| Asset production | Approved campaign brief | Claims, citations, channel specs | `AssetVariantApproved` | Re-render, quarantine unsupported claim, restore prior version |
| Channel execution | Approved asset or sequence | Connector health, authorization, budget, consent | `TouchpointRecorded` | Retry safely, pause account, cancel schedule, reconcile receipt |
| Lead intelligence | Visitor, discovered account or import | Source, purpose, identity, legal basis | `LeadQualified` or `LeadRejected` | Merge duplicate, suppress, delete or request review |
| Conversation and meeting | Inbound message or approved outreach | Contact, channel, routing and response policy | `MeetingBooked` or `ConversationResolved` | Stop sequence, honor opt-out, hand off, reopen |
| Opportunity management | Qualified lead or meeting | Account, owner, stage rules, evidence | `OpportunityWon` or `OpportunityLost` | Reopen with audit, reassign, age out, preserve reason |
| Order to cash | Accepted commercial proposal | Approval, price version, customer and tax context | `PaymentReconciled` and `RevenueRecognized` | Void, credit, amend, refund or escalate discrepancy |
| Customer growth | Opportunity won or order activated | Success owner, milestones, entitlement | `RenewalWon`, `ExpansionWon`, or `ReferralCreated` | Risk playbook, escalation, offboarding, reason capture |
| Attribution and learning | Outcome or evaluation window closed | Events, cost, revenue, model version | `LearningEvidencePublished` | Recompute projection, expose uncertainty, preserve prior result |
| Next-cycle decision | New evidence or planning cadence | Goal state, learning, constraints | `StrategyDecisionRecorded` | Accept, edit, reject, pause or roll back |

Temporal owns these long-lived states, timers, retries, cancellation, compensation, signals, and approvals. LangGraph may be invoked within bounded activities, but never becomes the ledger for commercial or workflow truth.

## 4. Agent topology

Agents specialize; no omnipotent central agent owns the system. A Growth Decision Agent assembles proposals but executes nothing without workflow and policy authority.

| Agent group | Responsibilities | Mandatory boundaries |
| --- | --- | --- |
| Market Intelligence | Market, demand, competitor, event, company and intent research | Cite source, freshness and confidence; separate fact from inference |
| Strategy & Planning | Goals, scenarios, channel mix, budget proposal, battle plans | State assumptions, expected impact, uncertainty and approval needs |
| Brand Guardian | Terminology, voice, claims, exclusions, evidence and localization checks | Reject unsupported claims; never invent certification or customer proof |
| Content | Briefs, copy, images and channel variants | Use approved facts; preserve variant and prompt/model lineage |
| SEO | Intent, keywords, clusters, pages, internal links and technical recommendations | Optimize for qualified outcomes, not unbounded page volume |
| GEO | Questions, entities, claims, citations, answer visibility and referral quality | Preserve evidence and source quality; do not conflate GEO with SEO |
| Video | Script, storyboard, voice, captions, assets and render plan | Rights, likeness, disclosure and approval before publishing |
| Social & Publishing | Calendar, channel adaptation, publishing and response proposals | Connector policy, frequency, identity and moderation controls |
| Advertising | Audience, creative, experiment and budget proposals | Budget caps, attribution, prohibited audiences and human approval at risk thresholds |
| Lead Research & Enrichment | Account discovery, contact enrichment, validation and scoring | Source, legal basis, deduplication, accuracy and suppression checks |
| Outreach | Personalization, sequences, timing and next-action proposals | Consent/legal basis, unsubscribe, frequency, deliverability and brand policy |
| Conversation | Classify, draft replies, route, schedule and escalate | No impersonation; disclose or require review according to workspace policy |
| Sales | Meeting preparation, qualification, objections and next steps | Human commercial authority; no fabricated terms or commitments |
| Commercial Document | Proposal and quote drafts, contract data assembly | Approved price/version, permissions, legal templates and signature boundaries |
| Customer Success | Onboarding, milestones, health, risk and expansion proposals | Customer context, entitlement, service policy and human escalation |
| Attribution & Experiment | Attribution, evaluation, anomalies and learning summaries | Model version, uncertainty, data quality and reproducibility |
| Compliance & Risk | Policy evaluation, sensitive data, consent, suppression and tool risk | Can block execution; cannot be bypassed by another agent |
| Evaluation | Offline/online quality, regressions, safety, cost and outcome checks | Independent datasets and versioned results before promotion |

Every agent has versioned input/output schemas, allowed tools, model policy, token/cost/time limits, evaluation gates, interruption rules, and audit lineage.

## 5. Connector architecture

The connector registry is broad by design and provider-neutral. It covers:

| Class | Capabilities |
| --- | --- |
| Owned web | Page publish/update/unpublish, forms, webhooks, sitemap, conversion events |
| Search and answer discovery | Search performance, indexing, keyword/question data, AI-answer evidence |
| Social and community | Publish, comment/reply, inbox, profile/account health, analytics where authorized |
| Advertising | Campaign, audience, creative, budget, delivery, conversion and cost sync |
| Email | SMTP/API send, mailbox/reply sync, bounce, complaint, unsubscribe, deliverability |
| Messaging | Approved business messaging send/receive, templates, identity and opt-out |
| CRM and calendar | Account/contact/opportunity sync, activity, meeting, availability and booking |
| Company and contact data | Search, enrichment, validation, provenance and confidence |
| Commerce and finance | Product/order/invoice/payment/refund/reconciliation and accounting events |
| Analytics and data | Event collection, import/export, warehouse, BI and attribution feeds |
| Storage and knowledge | Documents, assets, permissions, revisions, retrieval and citations |
| Models and media | Text, structured output, embedding, image, audio, video and moderation |

Every connector declares manifest version, provider, account, capabilities, configuration schema, secret references, scopes, outbound hosts, risk, legal/data notes, rate limits, idempotency behavior, health, webhook support, sandbox behavior, result schema, reversibility, and capability status.

Provider order is official API, webhook, standards-based protocol, authorized export/import, then controlled browser fallback. Browser automation never bypasses provider controls. Connector installation grants configuration access, not automatic execution authority.

The first reference integration bundle is architecturally fixed: Grovello-owned pages and event intake, standards-based email send/reply, a calendar booking adapter, generic signed webhooks, native CRM/opportunity records, native commercial records, and manual or connected payment reconciliation. Provider-specific social, ad, search, messaging, CRM, and finance adapters plug into the same contracts. Actual production accounts are deployment inputs, not missing architecture.

## 6. Data and event spine

PostgreSQL is the transactional source of truth. The identity graph links anonymous visitor, account, contact, lead, conversation, opportunity, customer, order, and revenue identities. Merge, split, alias and deletion actions are audited and reversible where policy allows.

The minimum event spine is:

```text
SignalObserved
→ StrategyProposed / StrategyDecisionRecorded
→ AssetCreated / AssetApproved
→ PublicationDelivered / AdDeliveryObserved / MessageDelivered
→ VisitObserved / AccountIdentified / LeadQualified
→ ReplyReceived / MeetingBooked / OpportunityCreated
→ QuoteAccepted / ContractExecuted / OrderConfirmed
→ InvoiceIssued / PaymentReconciled / RevenueRecognized
→ OnboardingMilestoneReached / HealthChanged
→ RenewalWon / ExpansionWon / ReferralCreated
→ AttributionCalculated / ExperimentEvaluated / LearningEvidencePublished
```

Business writes and their outbox events commit atomically. Consumers and workflows use idempotency keys. Projections carry schema/version lineage and can be rebuilt. Revenue, margin, payment, consent and contract truth never come from an LLM.

## 7. Default autonomy and approval policy

The default is risk-tiered autonomy, not full automation or universal manual review.

| Tier | Examples | Default authority |
| --- | --- | --- |
| R0 Read/Analyze | Retrieval, classification, forecasting, internal reporting | Automatic within access policy |
| R1 Draft/Internal | Draft content, plans, replies, reports, internal tasks | Automatic creation; human can edit or delete |
| R2 Reversible External | Scheduled publishing, low-volume approved outreach, sandbox changes | Policy approval; first run and material change require review |
| R3 Commercial/Sensitive | Ad budget change, bulk send, discount, quote, contract, export, identity merge | Explicit human approval with limits and evidence |
| R4 Prohibited | Bypass controls, deceptive identity, unlawful scraping, secret exposure, invented revenue, unauthorized payment | Never executable |

Workspace policy can become stricter. It may relax R2 within explicit limits after successful evaluations; it cannot relax R4. Every approval records proposal version, evidence, approver, scope, expiry and resulting execution.

## 8. Frontend information architecture

The ten left-navigation domains remain stable. Two entries make the approved positioning operable:

- **Growth Journeys** under Growth Command shows the golden-loop stages, readiness, owner inputs, blockers, runs and acceptance evidence.
- **Markets & Localization** under Brand & Market configures market, region, language, currency, regulation, channel availability, commercial conventions and market-entry assumptions.

Every operational page uses context-specific content while retaining a shared interaction grammar:

```text
Page identity and business outcome
→ scope filters and create/import/connect actions
→ overview / records / workflows / analytics / settings as relevant
→ status, owner, policy, approval and capability evidence
→ normal / empty / loading / partial / failed / unauthorized states
→ audit, lineage and feedback to the growth journey
```

Dashboard summarizes outcomes; Growth Journeys owns cross-domain progress; module pages own domain work; Run Center owns execution diagnostics; Approval Center owns human authority; Data & Intelligence owns explanation and learning. The workspace and locale remain in the top-right profile surface; navigation groups remain expandable with remembered state.

## 9. Reliability and recovery closure

- HTTP endpoints enqueue long work; they never block on crawling, media, publishing, bulk outreach or model chains.
- Temporal provides retry, backoff, timeout, cancellation, compensation, pause/resume, signals and versioning.
- External writes use idempotency or a local deduplication ledger and save provider receipts.
- Ambiguous timeouts enter reconciliation, not blind retry.
- Connector credentials can be revoked without deleting business history.
- Partial campaign success is preserved per item and can be retried selectively.
- Webhooks are authenticated, deduplicated, ordered where needed and replayable.
- The outbox prevents lost domain events; dead letters retain reason, payload reference, owner and recovery action.
- Backups, schema migrations, workflow versioning and rollback are release gates.
- Observability links request, run, workflow, agent, tool, connector, cost and business outcome identifiers.

## 10. Definition of architecture-complete

The upfront architecture is complete when every promised capability maps to:

1. a fixed product domain and UI entry;
2. canonical input and output objects;
3. a command/event contract and durable workflow owner;
4. bounded agents and allowed tools where reasoning is required;
5. connector capabilities and provider-status truth where external execution is required;
6. authorization, risk, consent, approval and audit rules;
7. idempotency, failure, cancellation, reconciliation and compensation behavior;
8. measurable outcome, attribution and next-cycle feedback;
9. capability-status and end-to-end verification evidence;
10. bilingual documentation and migration compatibility.

Implementation incompleteness is tracked by capability status and roadmap phase. It must not be converted into undefined architecture or hidden behind a generic agent.

## 11. Remaining owner-only inputs

The product architecture has defaults for fixture, autonomy, connector contracts and first reference integration bundle. Two categories still require owner input without creating an architecture gap:

- production provider accounts, credentials, budgets and authorized business data when real connectors are enabled;
- explicit selection of the repository license before legal open-source distribution.

AI agents may prepare configuration and comparisons but cannot fabricate access or choose the legal license without approval.
