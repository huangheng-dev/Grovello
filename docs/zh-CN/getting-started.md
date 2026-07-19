# 快速开始

## 环境要求

- Node.js 24 LTS 与 pnpm 11
- 完整环境需要 Docker Engine 与 Compose v2
- 本地运行 API/Worker 推荐 Python 3.13（基础阶段兼容 3.12）

## 只启动管理端

```bash
pnpm install --frozen-lockfile
pnpm --filter @grovello/web dev
```

打开 `http://localhost:3000/en/command/dashboard`。中文地址为 `/zh-CN/command/dashboard`，也可以在右上角头像菜单切换。当前总览数值会明确标注为种子数据。

## 完整自托管基础环境

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- 产品入口：`http://localhost:8080/en/command/dashboard`
- OpenAPI：`http://localhost:8080/openapi.json`
- API 健康检查：`http://localhost:8080/api/v1/system/health`
- Temporal UI：`http://localhost:8233`

默认环境包含 Web、API、Worker、PostgreSQL/pgvector、Valkey、Temporal 和 Nginx，不会暗中连接任何模型或营销平台。

## 开发访问契约

阶段 1 访问端点要求已认证主体、会话和工作区上下文。在 OIDC 适配器接入以前，非生产环境提供一个明确仅限开发的契约：

```bash
curl http://localhost:8080/api/v1/workspaces/current/access \
  -H "X-Grovello-Dev-Subject: northstar-owner" \
  -H "X-Grovello-Dev-Session: local-session" \
  -H "X-Workspace-ID: 00000000-0000-4000-8000-000000000001"
```

这些 Header 只用于选择带标签的种子访问记录，绝不能视为生产身份认证。生产环境会拒绝开发身份契约，直到配置并验证 OIDC 会话适配器。

## 可选平台与规模组件

```bash
docker compose -f compose.yaml -f compose.platform.yaml --profile platform up --build
docker compose -f compose.yaml -f compose.platform.yaml --profile scale up --build
```

`platform` 增加对象存储、Keycloak、OpenFGA；`scale` 增加 OpenSearch、ClickHouse、Kafka。非本地部署前必须替换所有默认凭据。

## 工程检查

```bash
pnpm typecheck
pnpm test
pnpm lint
pnpm build
```

Python 服务应分别创建虚拟环境，以 editable + `dev` extra 安装，然后执行 `ruff check` 与 `pytest`。每个服务的 `pyproject.toml` 已固定生产依赖版本。

生产环境还必须配置 TLS、外部密钥、OIDC、细粒度授权、数据库备份、异机对象存储、OpenTelemetry，并替换开发凭据。存在页面、Schema 或连接器契约，不代表第三方平台已经连接。
