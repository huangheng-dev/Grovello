# Grovello

**面向全球市场拓展与营收增长的开源多智能体企业增长操作系统。**

[English](./README.md) · [系统架构](./docs/zh-CN/architecture.md) · [完整系统蓝图](./docs/zh-CN/product-system-blueprint.md) · [产品交付路线图](./docs/zh-CN/product-delivery-roadmap.md) · [完整技术栈](./docs/zh-CN/technology-stack.md) · [快速开始](./docs/zh-CN/getting-started.md)

Grovello 围绕共享业务上下文和可衡量的收入结果，统一协调内容、SEO、GEO、视频、社交媒体、广告、潜客开发、CRM、销售、客户成功、留存和增长实验。

## 产品定位

- **产品品牌：**Grovello，读作 **grow-VELL-oh**。
- **产品总类：**服务国内与全球市场增长的企业增长操作系统（Enterprise Growth OS）。
- **全球市场能力域：**全球市场拓展与营收增长（Global Go-to-Market & Revenue Growth）。
- **第一条黄金验收闭环：**全球 B2B 增长（Global B2B Growth），从企业入驻、市场情报开始，贯通获客、销售、收入、留存、归因和下一轮 AI 策略。
- **参考数据：**虚构的 Northstar Industrial（北辰工业）工作区，一家工业自动化供应商评估并进入德国 B2B 市场。它只是可替换的验收数据，不是工业品专用或仅限出口业务的产品边界。

“外贸”可以出现在面向中国用户的具体业务语境中，但不是 Grovello 的英文产品总类。行业、产品类型、来源国和目标市场都必须是可配置业务数据，不能写死在领域模型中。

## 当前状态

Grovello 正处于正式工程基础建设阶段。仓库会明确区分已验证、模拟、规划中以及依赖第三方账号的能力；存在页面或接口契约不代表外部平台已经接通。

## 核心架构

- Next.js 与 React 提供英文优先、支持简体中文的产品体验。
- FastAPI 提供版本化业务 API 和模块化领域核心。
- Temporal 承担确定性的持久化业务工作流。
- LangGraph 承担 Agent 推理与 Agent 级人工中断。
- PostgreSQL 是业务事实源，所有派生存储都必须可以重建。
- 连接器隔离平台、模型、MCP 工具和浏览器自动化降级能力。

## 快速开始

```bash
pnpm install
pnpm dev
```

管理端位于 `http://localhost:3000`，默认进入英文，可通过语言切换打开简体中文。

API 和完整自托管环境见[中文快速开始](./docs/zh-CN/getting-started.md)。

开发顺序、阶段门禁和黄金闭环完成标准见[产品交付路线图](./docs/zh-CN/product-delivery-roadmap.md)。

## 许可证

Grovello 采用 [GNU Affero General Public License v3.0 only](./LICENSE) 许可。项目政策和托管服务相关义务请参阅[许可证决策说明](./docs/zh-CN/licensing.md)。
