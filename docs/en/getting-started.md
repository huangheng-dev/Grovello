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

## Optional platform and scale profiles

```bash
docker compose -f compose.yaml -f compose.platform.yaml --profile platform up --build
docker compose -f compose.yaml -f compose.platform.yaml --profile scale up --build
```

The platform profile adds object storage, Keycloak, and OpenFGA. The scale profile adds OpenSearch, ClickHouse, and Kafka. Change all default credentials before any non-local deployment.

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
