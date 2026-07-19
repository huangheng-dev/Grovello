# Technology stack

The baseline is selected for a high-capability, international, self-hostable Growth OS. Optional scale components are not mandatory local dependencies.

| Layer | Baseline | Responsibility |
| --- | --- | --- |
| Web | Node.js 24 LTS, Next.js 16 App Router, React 19, TypeScript 6.0 | Product console, SSR, locale routing, session surface, thin BFF |
| UI state and forms | next-intl, TanStack Query/Table, React Hook Form, Zod, Zustand, Material Symbols | Bilingual UX, server-state cache, dense tables, validated forms, local UI state, icons |
| Business API | Python 3.13 target, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, HTTPX | Versioned APIs, domain services, validation, persistence, outbound HTTP |
| Durable workflows | Temporal | Long-running execution, timers, retries, approval waits, cancellation, compensation |
| Agent runtime | LangGraph | Bounded reasoning, state graphs, tool selection, evaluation, human interruption |
| Transactional data | PostgreSQL 18 + pgvector | Business source of truth, relational integrity, RLS defense-in-depth, initial semantic retrieval |
| Cache and coordination | Valkey | Cache, rate limits, short-lived coordination; never business truth |
| Object storage | S3-compatible API; MinIO reference profile | Images, video, documents, exports, rendered assets |
| Search | PostgreSQL first; OpenSearch scale profile | Full-text and hybrid retrieval when measured load justifies it |
| Analytics | PostgreSQL projections first; ClickHouse scale profile | High-volume behavioral and attribution analytics |
| Events | Transactional outbox first; Kafka + Debezium scale profile | Reliable domain event distribution to multiple durable consumers |
| Identity | OIDC/OAuth 2.1/SAML compatible; Keycloak reference | Login, federation, MFA, enterprise SSO |
| Authorization | Application guards + OpenFGA | Workspace, object, relationship, agent, and connector permissions |
| Secrets | Environment references locally; OpenBao production profile | Secret lifecycle and dynamic credentials |
| Provider integration | Versioned connectors, REST/GraphQL, webhooks, MCP, Playwright fallback | Replaceable external capabilities with policy and audit |
| Media | FFmpeg workers; provider adapters for TTS/image/video | Deterministic transforms and optional generative media providers |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Tempo, Sentry-compatible error sink | Correlated traces, metrics, logs, costs, failures, audit evidence |
| Delivery | pnpm, Turborepo, Ruff, Pytest, Vitest, Playwright, Docker Compose | Reproducible development, test, build, and self-hosting |
| Scale delivery | Kubernetes, Helm, KEDA, Argo CD, OpenTofu | Horizontal queues, GitOps, infrastructure as code, autoscaling |
| Supply chain | GitHub Actions, Dependabot/Renovate, SBOM, Trivy, Cosign, pinned actions/images | CI, dependency review, image scanning, provenance and signing |

### Explicit non-choices

- Next.js is not the business backend.
- LangGraph is not the durable workflow engine.
- MCP is not the universal integration transport.
- Kafka, OpenSearch, ClickHouse, and Kubernetes are not enabled merely to look enterprise.
- Browser automation is not used to evade platform restrictions or replace a healthy official API.
