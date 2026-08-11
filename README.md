# CodeFixer

CodeFixer 是一个通用的 Bug 自动修复与交付平台。

Web 管理界面与 API 同源，第一版正式服务端口统一为 `9522`。

它从外部工单系统收录 Bug，通过独立的 Discovery 与 Repair Agent 自主反查和修改唯一代码源，经过验证与 Review 后，按项目配置生成 Patch 和/或创建普通 GitLab MR。

## 规范文档

CodeFixer 的第一版施工以以下规范共同作为基准：

1. [产品与技术设计 SPEC](docs/design-spec.md)  
   定义产品语义、领域模型、任务协议、状态机、Artifact、并发、幂等、交付与部署边界。
2. [工程就绪规范](docs/engineering-readiness-spec.md)  
   定义正式 Feature Coding 前的 Phase 0、Definition of Done、回归门禁和端到端施工要求。
3. [仓库结构与依赖规范](docs/architecture/repository-structure.md)  
   定义 backend/frontend/contracts/tests/deploy 的目录、分层和依赖方向。
4. [Web 设计系统与交互规范](docs/design/design-system.md)  
   定义 CodeFixer 的“Repair Signal / 自动维修控制塔”视觉语言、关键组件、动效和视觉回归基线。
5. [测试、回归与自测策略](docs/testing/test-strategy.md)  
   定义 unit、contract、integration、Scenario Regression、E2E、visual、故障注入和 Release Gate。

仅在对应路径存在的本机 Windows 开发环境中，Agent 还可以读取：

- [本机开发 Agent 参考路径](docs/local-development-references.md)

该文件只用于本机开发辅助，不属于运行依赖，也不得让公开仓库依赖其中的本地项目或绝对路径。

## 已确定的第一版边界

- 工单来源：Redmine、TAPD。
- 修改源：Git、SVN。
- Agent Runtime：Claude Code、Codex、OpenCode。
- 最终动作：Patch、GitLab MR。
- 执行方式：全自动或待用户点击一次开始。
- 一个 Bug 只修改一个代码源，但可以执行多个最终动作。
- 不实现 GitHub PR、自动合并 MR、SVN 直接提交和多修改源任务。

## 当前阶段

产品语义与核心技术边界已经冻结到可施工水平；仓库现在进入 **Phase 0：Engineering Foundation**。

Phase 0 的目标不是实现业务功能，而是先建立：

- 规范源码目录和依赖边界。
- Contracts/Schema 单一事实源。
- FastAPI/SQLite/React 最小纵切。
- CodeFixer Design System 与关键视觉组件。
- pytest/Vitest/Playwright 测试底座。
- Scenario Regression 与故障注入框架。
- CI、构建、health/readiness 和 Linux 部署骨架。

达到 [工程就绪规范](docs/engineering-readiness-spec.md) 的 `ready_for_implementation` 条件后，再按产品 SPEC 的阶段顺序端到端施工。

## 仓库状态

当前仓库仍处于设计与工程基础准备阶段，尚未开始第一版功能实现。
