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

若要让本地生产构建的 Web 控制台通过服务端薄 BFF 连接开发 API，必须显式启用开发身份契约：

```powershell
$env:GROVELLO_API_BASE_URL="http://127.0.0.1:8000/api/v1"
$env:GROVELLO_ALLOW_DEVELOPMENT_IDENTITY="true"
$env:GROVELLO_DEVELOPMENT_SUBJECT="northstar-owner"
$env:GROVELLO_DEVELOPMENT_SESSION="local-web-session"
$env:GROVELLO_DEVELOPMENT_WORKSPACE_ID="00000000-0000-4000-8000-000000000001"
pnpm --filter @grovello/web start -- --hostname 127.0.0.1 --port 3200
```

浏览器只访问同源 BFF；开发身份和工作区 Header 由服务端添加，不会进入浏览器包。若未开启显式开关或 API 不可用，“品牌与市场”页面会显示不可用状态，不会用 Mock 记录替代。

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

Compose 开发 API 会在启动前执行迁移及可幂等重复执行的虚构访问种子。本地原生开发可在迁移后显式运行同一命令：

```bash
alembic upgrade head
python -m grovello.development_seed
```

迁移 `0009` 在不重写租户数据或 RLS 策略的前提下，使规范 ORM 元数据与已部署 Schema
保持一致。维护者可通过 `alembic check` 验证迁移一致性；处于 head 的干净检出不会产生新的
升级操作。

该种子只创建满足租户和审计外键所需的 Northstar 组织、工作区、开发所有者、角色、权限、团队、成员关系和基础策略；当 `GROVELLO_ENVIRONMENT=production` 时会被拒绝，也不会创建任何企业、产品、客户或收入声明。

## 共享业务事实契约

阶段 2 基础端点复用同一组会话与工作区 Header。当前资料端点会返回规范对象 ID、选定版本、精确引用与完整性缺口：

```bash
curl http://localhost:8080/api/v1/business-truth/profile \
  -H "X-Grovello-Dev-Subject: northstar-owner" \
  -H "X-Grovello-Dev-Session: local-session" \
  -H "X-Workspace-ID: 00000000-0000-4000-8000-000000000001"
```

写入还必须具备 `business_truth.write` 权限，并提供 `Idempotency-Key`、业务目的与变更摘要。每个已接受版本都会记录操作者与请求血缘，同时写入审计事件和事务 Outbox 事件。种子资料始终明确标注，不代表真实产品、认证、客户或市场声明。

“品牌与市场”的六个核心入口现已读取该资料契约，并支持受治理的对象创建和不可变版本更新。下文说明的“企业配置”和“导入”高级入口，以受治理操作流程扩展了这一管理纵向切片。它们仍是 `foundation` 能力；知识切块流水线、通用审批工作流和外部供应商同步仍不在当前可运营声明内。素材库界面也在下文单独说明，当前仍是 `foundation` 能力。

## 工作区入驻与导入基础

P2-D1 至 P2-D4 在 `/api/v1/workspace-onboarding` 和 `/api/v1/import-jobs` 提供版本化基础端点，并在 `/en/brand/business-setup`、`/en/brand/imports` 及其 `/zh-CN` 对应地址提供双语薄 BFF 操作入口。启动企业资料配置以及每项导入 Mutation 都需要窄权限和 `Idempotency-Key`。导入作业只接受 UTF-8 CSV（`text/csv`）或带版本的 Grovello JSON 包（`application/json`），默认 25 MiB 限制由 `GROVELLO_IMPORT_MAX_SOURCE_BYTES` 配置。

浏览器或客户端通过返回的受约束私有 POST 授权直接上传来源字节。调用 `/api/v1/import-jobs/{job_id}/complete` 后，会启动持久化精确对象核验与恶意文件扫描；干净来源停在 `ready_for_mapping`。授权所有者可在 `/api/v1/import-jobs/{job_id}/mapping` 创建不可变映射，在 `/api/v1/import-jobs/{job_id}/validation` 启动后台解析与校验，并从同一路由读取有界、脱敏的预览和问题报告。CSV 必须显式选择逗号、分号、Tab 或竖线分隔符；Grovello JSON 的 Manifest 必须提供并匹配 `schemaVersion`、`locale`、`objectType` 和 `recordCount`。行、列、标量字节、嵌套和预览限制通过 `.env.example` 中的 `GROVELLO_IMPORT_` 设置配置。

校验会停在 `ready_for_review`，直到授权所有者创建不可变 Dry-run Change Set。激活写入要求记录带策略版本的审批决定；持久化 Temporal 工作流把选定记录应用到规范业务事实，并支持取消与精确补偿。工作区资料激活仍是独立的精确快照门禁；缺少有效 Product、Offer、Market 或 ICP 选择时会拒绝激活。本地已核验流程覆盖来源上传、恶意文件扫描、映射、校验、Change Set 审查、应用、补偿、激活、审计事件和事务 Outbox 事件。生产身份、通用审批、运行手册和非开发部署证据接通以前，该能力仍只能标记为 `foundation`。

## 素材最终化与下载契约

完成上传后会核验精确的供应商对象并执行恶意文件扫描，但会有意停在
`ready_to_finalize`。`POST /api/v1/assets/upload-sessions/{upload_session_id}/finalize`
只接受扫描结果为干净的会话，并要求 `asset.write` 权限与 `Idempotency-Key`；若请求将
素材设为 `active`，还必须具备 `asset.approve` 权限。

持久化最终化 Saga 会把已核验对象提升到工作区隔离的不可变 Key，在同一数据库事务中
创建或更新规范 Asset、不可变版本及文件绑定，然后删除暂存区的精确对象版本。数据库提交
失败时，补偿 Activity 会先确认对象尚未绑定，再只删除本次提升的精确版本。最终化同时写入
审计和事务 Outbox 证据。

`GET /api/v1/assets/{asset_id}/versions/{asset_version_id}/download` 要求
`asset.download` 权限，并且只有精确 Asset、版本和 Blob 同时处于 active、clean、available
状态时才签发短时私有下载授权。草稿版本、不安全或不可用 Blob 均会关闭式拒绝。素材库界面通过
服务端 BFF 读取目录、状态、最终化、历史和下载授权，浏览器只把文件字节发送到受约束的
S3-compatible 预签名 POST。由于通用审批工作流和生产身份提供方尚未接入，该界面仍标记为
`foundation` 能力。

## 可选平台与规模组件

启动 `platform` Profile 前，需要在被 Git 忽略的 `.env` 文件中为以下四个空白配置填写互不相同的随机值：

```text
GROVELLO_OBJECT_STORAGE_ROOT_USER
GROVELLO_OBJECT_STORAGE_ROOT_PASSWORD
GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID
GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY
```

Root 凭据只提供给 MinIO 和一次性初始化容器；API 只接收应用凭据，并且该账号只能操作配置的私有 Bucket。
浏览器上传只允许 `GROVELLO_OBJECT_STORAGE_CORS_ALLOWED_ORIGINS` 中逗号分隔的精确来源；该列表必须
与实际部署的 Web 来源保持一致，生产 Profile 不得用 `*` 代替。

```bash
docker compose -f compose.yaml -f compose.platform.yaml --profile platform up --build
docker compose -f compose.yaml -f compose.platform.yaml --profile scale up --build
```

`platform` 增加对象存储、内部 ClamAV 恶意文件扫描器、Keycloak、OpenFGA。MinIO 的 S3-compatible API 位于
`http://localhost:9000`，管理控制台位于 `http://localhost:9001`。初始化器会创建指定 Bucket、启用版本控制、
关闭匿名访问，并建立受限的应用账号。对象存储就绪状态可通过
`/api/v1/system/object-storage/health` 查看。ClamAV 不向宿主机发布端口；扫描器就绪状态可通过
`/api/v1/system/asset-scanner/health` 查看。请为签名加载和扫描至少预留 3 GiB 内存。
`scale` 增加 OpenSearch、ClickHouse、Kafka。

Compose 参考配置中的 `GROVELLO_OBJECT_STORAGE_SSE_MODE=none` 仅用于本地开发。生产配置校验要求 HTTPS，
并启用 `sse-s3` 或 `sse-kms`；正式凭据必须来自外部 Secret 引用，不得写入 `.env` 或 Compose 源码。

## 工程检查

```bash
pnpm typecheck
pnpm test
pnpm lint
pnpm build
```

Python 服务应分别创建虚拟环境，以 editable + `dev` extra 安装，然后执行 `ruff check` 与 `pytest`。每个服务的 `pyproject.toml` 已固定生产依赖版本。

生产环境还必须配置 TLS、外部密钥、OIDC、细粒度授权、数据库备份、异机对象存储、OpenTelemetry，并替换开发凭据。存在页面、Schema 或连接器契约，不代表第三方平台已经连接。
