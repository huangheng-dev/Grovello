# 完整技术栈

这套基线面向高能力、国际化、可自托管的 Growth OS。规模组件是可选演进层，不是本地开发的强制负担。

| 层级 | 技术基线 | 职责 |
| --- | --- | --- |
| Web | Node.js 24 LTS、Next.js 16 App Router、React 19、TypeScript 6.0 | 管理端、SSR、语言路由、会话界面、薄 BFF |
| UI 状态与表单 | next-intl、TanStack Query/Table、React Hook Form、Zod、Zustand、Material Symbols | 双语、服务端状态、复杂表格、校验表单、本地状态、图标 |
| 业务 API | Python 3.13、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、HTTPX | 版本化 API、领域服务、校验、事务、外部 HTTP |
| 持久工作流 | Temporal | 长任务、定时器、重试、审批等待、取消、补偿 |
| Agent 运行时 | LangGraph | 有边界的推理、状态图、工具选择、评估、人工中断 |
| 事务数据 | PostgreSQL 18 + pgvector | 业务事实源、关系完整性、RLS 纵深防御、初期语义检索 |
| 缓存与协调 | Valkey | 缓存、限流、短期协调，不保存业务真相 |
| 对象存储 | S3 兼容接口；MinIO 参考配置 | 图片、视频、文档、导出与渲染资产 |
| 搜索 | 初期 PostgreSQL；规模化 OpenSearch | 达到实际负载后提供全文与混合检索 |
| 分析 | 初期 PostgreSQL 投影；规模化 ClickHouse | 高量行为、归因与增长分析 |
| 事件 | 初期事务 Outbox；规模化 Kafka + Debezium | 向多个持久消费者可靠分发领域事件 |
| 身份 | OIDC/OAuth 2.1/SAML；Keycloak 参考实现 | 登录、联合身份、MFA、企业 SSO |
| 授权 | 应用授权守卫 + OpenFGA | 工作区、对象关系、Agent 与连接器权限 |
| 密钥 | 本地环境引用；生产 OpenBao | 密钥生命周期与动态凭据 |
| 外部集成 | 版本化 Connector、REST/GraphQL、Webhook、MCP、Playwright 降级 | 可替换、受策略和审计约束的外部能力 |
| 媒体 | FFmpeg Worker；TTS/图片/视频供应商适配器 | 确定性媒体处理和可选生成服务 |
| 可观测性 | OpenTelemetry、Prometheus、Grafana、Loki、Tempo、Sentry 兼容错误端 | 统一链路、指标、日志、成本、失败与审计证据 |
| 工程交付 | pnpm、Turborepo、Ruff、Pytest、Vitest、Playwright、Docker Compose | 可复现开发、测试、构建与自托管 |
| 规模交付 | Kubernetes、Helm、KEDA、Argo CD、OpenTofu | 横向 Worker、GitOps、IaC 与弹性伸缩 |
| 供应链 | GitHub Actions、Dependabot/Renovate、SBOM、Trivy、Cosign | CI、依赖审查、镜像扫描、来源与签名 |

明确边界：Next.js 不承担业务后端；LangGraph 不替代 Temporal；MCP 不替代所有集成协议；没有真实规模前不强制 Kafka/OpenSearch/ClickHouse/Kubernetes；浏览器自动化不得绕过平台规则。
