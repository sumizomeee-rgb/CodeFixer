# CodeFixer

CodeFixer 是一个通用的 Bug 自动修复与交付平台。

Web 管理界面与 API 同源，第一版正式服务端口统一为 `9522`。

它从外部工单系统收录 Bug，通过独立的 Discovery 与 Repair Agent 自主反查和修改唯一代码源，经过验证与 Review 后，按项目配置生成 Patch 和/或创建普通 GitLab MR。

## 第一版边界

- 工单来源：Redmine、TAPD。
- 修改源：Git、SVN。
- Agent Runtime：Claude Code、Codex、OpenCode。
- 最终动作：Patch、GitLab MR。
- 执行方式：全自动或待用户点击一次开始。
- 一个 Bug 只修改一个代码源，但可以执行多个最终动作。
- 不实现 GitHub PR、自动合并 MR、SVN 直接提交和多修改源任务。

## 开发与迁移

CodeFixer 优先保证**项目自包含、可换机器、可换托管平台**，不把 GitHub Actions 当成运行依赖或硬门禁。

最小宿主环境：

- Python `3.12+`
- Node.js `20.19+` 或 `22.12+`（推荐 Node 22）
- npm

然后在仓库根目录执行：

```bash
python scripts/bootstrap.py
```

Windows PowerShell：

```powershell
.\scripts\bootstrap.ps1
```

bootstrap 默认把依赖放在项目内：

```text
backend/.venv/          Python venv + site-packages
frontend/node_modules/  npm dependencies
```

`npm install/npm ci` 的默认行为就是本地安装到当前项目 `node_modules`；Python `venv` 也会在指定目录中建立独立 interpreter/site-packages。迁移时不要复制这两个机器相关目录，而是在新机器重新跑 bootstrap。

需要完整浏览器测试时：

```bash
python scripts/bootstrap.py --with-browser
```

需要从源码生成 production 前端：

```bash
python scripts/bootstrap.py --production
```

更完整的迁移、Secret 和软门禁约定见 [开发与迁移约定](docs/development-policy.md)。

## 自动检查策略

`.github/workflows/ci.yml` 只是 advisory quality checks：

- push 到 main：轻量 backend/frontend 检查；失败用于提示，不把仓库锁成不可开发状态。
- 手工触发：可额外运行 Browser/E2E/visual。
- workflow 无 `contents: write`，不会自动 commit/push。
- 没有 nightly 强制任务，也没有 CodeFixer 自己要求的 branch protection。

发布候选仍应主动完成完整回归，但日常开发以本地自测 + 文档约定为主。

## 当前实现进度

已完成/已接入：

- FastAPI + SQLite WAL + migrations。
- `/api/health`、`/api/readiness` 与 React SPA 同源托管。
- React/Vite UI 与 Repair Signal Design System。
- 配置、SecretRef、Project CRUD 与 Preflight。
- 持久化 Ticket/Task/TaskRun 基础事实层。
- Task 列表、详情、Start/Cancel 控制面。
- Redmine/TAPD TicketProvider 与确定性项目路由第一版。
- pytest、Vitest、Playwright 测试底座。

## 规范文档

- [产品与技术设计 SPEC](docs/design-spec.md)
- [工程就绪规范](docs/engineering-readiness-spec.md)
- [仓库结构与依赖规范](docs/architecture/repository-structure.md)
- [Web 设计系统与交互规范](docs/design/design-system.md)
- [测试、回归与自测策略](docs/testing/test-strategy.md)
- [开发与迁移约定](docs/development-policy.md)

若旧工程文档仍出现 `blocking CI` / `main_red` 等早期措辞，以 `docs/development-policy.md` 的软门禁原则为准；后续会逐步清理旧措辞，不影响产品领域语义。
