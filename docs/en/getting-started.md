# Getting started

## Prerequisites

- Node.js 24 LTS and pnpm 11
- Docker Engine with Compose v2 for the full stack
- Python 3.13 for native API/worker development (3.12 remains supported during foundation development)

## Web console

```bash
pnpm install --frozen-lockfile
pnpm --filter @grovello/web dev
```

Open `http://localhost:3000/en/command/dashboard`. Chinese is available at `/zh-CN/command/dashboard` and from the profile menu. Current dashboard values are explicitly seed data.

To connect a locally running production build of the web console to the development API through the thin server-side BFF, explicitly enable the development identity contract:

```powershell
$env:GROVELLO_API_BASE_URL="http://127.0.0.1:8000/api/v1"
$env:GROVELLO_ALLOW_DEVELOPMENT_IDENTITY="true"
$env:GROVELLO_DEVELOPMENT_SUBJECT="northstar-owner"
$env:GROVELLO_DEVELOPMENT_SESSION="local-web-session"
$env:GROVELLO_DEVELOPMENT_WORKSPACE_ID="00000000-0000-4000-8000-000000000001"
pnpm --filter @grovello/web start -- --hostname 127.0.0.1 --port 3200
```

The browser calls only the same-origin BFF. Development identity and workspace headers are added server-side and never shipped in the browser bundle. If the explicit switch or API is unavailable, Brand & Market pages show an unavailable state instead of substituting mock records.

## Full self-hosted foundation

```bash
copy .env.example .env
docker compose up --build
```

- Product gateway: `http://localhost:8080/en/command/dashboard`
- API schema: `http://localhost:8080/openapi.json`
- API health: `http://localhost:8080/api/v1/system/health`
- Temporal UI: `http://localhost:8233`

The default stack contains the web app, API, worker, PostgreSQL/pgvector, Valkey, Temporal, and Nginx. It does not silently connect model or marketing providers.

## Development access contract

Phase 1 access endpoints require an authenticated subject, session, and workspace context. Until the OIDC adapter is connected, non-production environments expose an explicitly development-only contract:

```bash
curl http://localhost:8080/api/v1/workspaces/current/access \
  -H "X-Grovello-Dev-Subject: northstar-owner" \
  -H "X-Grovello-Dev-Session: local-session" \
  -H "X-Workspace-ID: 00000000-0000-4000-8000-000000000001"
```

These headers select labeled seed access records and must never be treated as production authentication. Production rejects the development identity contract until a verified OIDC session adapter is configured.

The Compose development API runs migrations and the idempotent fictional access seed before starting. For native development, run the same explicit seed after migrations:

```bash
alembic upgrade head
python -m grovello.development_seed
```

Migration `0009` aligns canonical ORM metadata with the deployed schema without rewriting tenant
data or RLS policies. Maintainers can verify migration parity with `alembic check`; a clean checkout
at head reports no new upgrade operations.

The seed creates only the Northstar organization, workspace, development owner, role, permissions, team, membership, and baseline policy needed to satisfy tenant and audit foreign keys. It is rejected when `GROVELLO_ENVIRONMENT=production` and does not create business, product, customer, or revenue claims.

## Shared business truth contract

Phase 2 foundation endpoints use the same session and workspace headers. The current profile endpoint returns canonical object IDs, selected versions, exact citations, and validation gaps:

```bash
curl http://localhost:8080/api/v1/business-truth/profile \
  -H "X-Grovello-Dev-Subject: northstar-owner" \
  -H "X-Grovello-Dev-Session: local-session" \
  -H "X-Workspace-ID: 00000000-0000-4000-8000-000000000001"
```

Writes additionally require `business_truth.write`, an `Idempotency-Key`, a business purpose, and a change summary. Every accepted version records actor and request lineage, an audit event, and a transactional outbox event. Seed fixtures remain labeled and do not make real product, certification, customer, or market claims.

The six Brand & Market navigation entries now read this profile contract and support governed object creation and immutable version updates. This is an administration slice for shared business truth; imports, persistent workspace onboarding, knowledge chunking pipelines, full approval workflows, and external provider synchronization remain outside the current operational claim. The Asset Library interface is described separately below and remains a `foundation` capability.

## Workspace onboarding and import foundation

P2-D1 and P2-D2 provide versioned foundation endpoints at `/api/v1/workspace-onboarding` and `/api/v1/import-jobs`. Starting business setup and every import mutation requires a narrow permission and `Idempotency-Key`. An import job accepts only UTF-8 CSV (`text/csv`) or a versioned Grovello JSON package (`application/json`), with a default 25 MiB limit configured by `GROVELLO_IMPORT_MAX_SOURCE_BYTES`.

The browser or client uploads source bytes directly through the returned constrained private POST grant. Calling `/api/v1/import-jobs/{job_id}/complete` starts durable exact-object verification and malware scanning; a clean source stops at `ready_for_mapping`. An authorized owner can create an immutable mapping at `/api/v1/import-jobs/{job_id}/mapping`, start background parsing and validation at `/api/v1/import-jobs/{job_id}/validation`, and read a bounded, redacted preview and issue report from that validation route. CSV requires an explicit comma, semicolon, tab, or pipe delimiter. Grovello JSON requires a matching `schemaVersion`, `locale`, `objectType`, and `recordCount` manifest. Row, column, scalar-byte, nesting, and preview limits use the `GROVELLO_IMPORT_` settings documented in `.env.example`.

Validation stops at `ready_for_review`. It performs no apply, creates no change set or canonical business record, and cannot activate the workspace profile.

## Asset finalization and download contract

Completing an upload verifies its exact provider object and runs malware scanning, but intentionally
stops at `ready_to_finalize`. `POST /api/v1/assets/upload-sessions/{upload_session_id}/finalize`
accepts only a clean session, requires `asset.write` and an `Idempotency-Key`, and additionally
requires `asset.approve` when the requested Asset status is `active`.

The durable finalization Saga promotes the verified object to a workspace-scoped immutable key,
transactionally creates or updates the canonical Asset and its immutable version/file binding, and
then removes the exact staging version. A database-commit failure removes only the promoted version
after confirming that it was not bound. Finalization records audit and transactional outbox evidence.

`GET /api/v1/assets/{asset_id}/versions/{asset_version_id}/download` requires `asset.download` and
issues a short-lived private grant only when the exact Asset, version, and Blob are active, clean, and
available. Draft versions and unsafe or unavailable Blobs fail closed. The Asset Library UI uses a
server-side BFF for catalog, status, finalization, history, and download authorization while the
browser sends file bytes only to a constrained S3-compatible presigned POST. The interface remains
a `foundation` capability because the general approval workflow and production identity provider are
not yet connected.

## Optional platform and scale profiles

Before starting the `platform` profile, set distinct, generated values for the four blank object-storage
credentials in the ignored `.env` file:

```text
GROVELLO_OBJECT_STORAGE_ROOT_USER
GROVELLO_OBJECT_STORAGE_ROOT_PASSWORD
GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID
GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY
```

The root credentials are used only by MinIO and the one-shot initializer. The API receives only the
application credentials, whose policy is limited to the configured private bucket. Browser uploads
use the exact, comma-separated origins in `GROVELLO_OBJECT_STORAGE_CORS_ALLOWED_ORIGINS`; keep that
list aligned with the deployed web origins and never replace it with `*` in a production profile.

```bash
docker compose -f compose.yaml -f compose.platform.yaml --profile platform up --build
docker compose -f compose.yaml -f compose.platform.yaml --profile scale up --build
```

The platform profile adds object storage, an internal ClamAV malware scanner, Keycloak, and OpenFGA. MinIO exposes its S3-compatible API at
`http://localhost:9000` and its administration console at `http://localhost:9001`. The initializer creates
the configured bucket, enables versioning, keeps anonymous access disabled, and provisions the scoped
application account. Object-storage readiness is available at
`/api/v1/system/object-storage/health`. ClamAV is not published to the host; scanner readiness is available at
`/api/v1/system/asset-scanner/health`. Allow at least 3 GiB of memory for signature loading and scanning.
The scale profile adds OpenSearch, ClickHouse, and Kafka.

The Compose reference uses `GROVELLO_OBJECT_STORAGE_SSE_MODE=none` only for local development. Production
configuration validation requires HTTPS and either `sse-s3` or `sse-kms`; production credentials belong in
external secret references, not `.env` or Compose source.

## Quality commands

```bash
pnpm typecheck
pnpm test
pnpm lint
pnpm build
```

For Python services, create a virtual environment and install each service in editable mode with its `dev` extra, then run `ruff check` and `pytest`. Exact production Python dependencies are pinned in each service `pyproject.toml`.

## Production notes

Terminate TLS at a trusted ingress, use external secret references, configure OIDC and authorization, create database backups, send object storage off-host, enable OpenTelemetry, and replace development credentials. Pages, schemas, or connector contracts do not imply that third-party platforms are connected.
