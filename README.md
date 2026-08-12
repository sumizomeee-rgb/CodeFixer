# CodeFixer

CodeFixer 是一个通用的 Bug 自动修复与交付平台。

Web 管理界面与 API 同源，第一版正式服务端口统一为 `9522`。

它从外部工单系统收录 Bug，通过独立的 Discovery 与 Repair Agent 自主反查和修改唯一代码源，经过验证与 Review 后，按项目配置生成 Patch 和/或创建普通 GitLab MR。

## 规范文档

CodeFixer 的第一版施工以以下规范共同作为基准：

1. [产品与技术设计 SPEC](docs/design-spec.md)
2. [工程就绪规范](docs/engineering-readiness-spec.md)
3. [仓库结构与依赖规范](docs/architecture/repository-structure.md)
4. [Web 设计系统与交互规范](docs/design/design-system.md)
5. [测试、回归与自测策略](docs/testing/test-strategy.md)

## 第一版边界

- 工单来源：Redmine、TAPD。
- 修改源：Git、SVN。
- Agent Runtime：Claude Code、Codex、OpenCode。
- 最终动作：Patch、GitLab MR。
- 执行方式：全自动或待用户点击一次开始。
- 一个 Bug 只修改一个代码源，但可以执行多个最终动作。
- 不实现 GitHub PR、自动合并 MR、SVN 直接提交和多修改源任务。

## 当前实现

工程基础与 V1 核心流水线已经进入可运行实现：

- FastAPI + SQLite WAL + migrations。
- Redmine / TAPD 增量收单与长期 Task 身份。
- Scope Discovery / Formal Discovery / Repair / Review 独立 Agent 会话；前两阶段通过固定路径调查文档交接。
- Claude Code / Codex / OpenCode 独立 CLI Adapter。
- Git 独立 worktree；SVN lease + 清理策略。
- 平台真实 diff、越权路径检查、验证命令与验证污染隔离。
- `changed` 与严格证据化 `no_change` 两种健康终态。
- Freeze Change：不可变 patch、文件内容快照、hash、verification、review。
- Patch 幂等交付。
- GitLab MR 多目标交付、partial success、远端对账与防重复创建。
- Freeze 前/后不同的崩溃恢复策略与 SQLite Scheduler。
- 实时维修控制台、任务证据 Drawer、Provider、Project、Settings 自助配置界面。
- Delivery-only retry：冻结后交付失败可以只重试外部动作，不重新调用 Agent。

## 开发与迁移

CodeFixer 不依赖 GitHub Actions、PR 或特定托管平台作为开发门禁。质量标准由仓库文档和本地测试定义。

宿主机尽量只要求：

- 64 位 CPython 3.12+
- Node.js 22 + npm
- 实际启用的外部 CLI：Git、SVN、Claude Code、Codex、OpenCode

项目依赖默认安装在仓库目录内：

- `backend/.venv`
- `frontend/node_modules`

这两个目录都应在新机器重新生成，不跨机器复制。

### Bootstrap

```powershell
.\scripts\bootstrap.ps1
```

```bash
./scripts/bootstrap.sh
```

需要完整浏览器测试环境：

在对应入口后追加 `--with-browser`。

需要从源码准备 production build：

在对应入口后追加 `--production`。

### 启动

```powershell
.\scripts\run.ps1 --build
```

Linux：

```bash
backend/.venv/bin/python scripts/run.py --build
```

### 自测

快速回归：

Windows 使用 `.\scripts\test.ps1`，Linux 使用 `./scripts/test-fast.sh`；两个入口都只调用项目虚拟环境，不回退到系统 `python`。

完整浏览器 / E2E / visual：

```bash
python scripts/test.py --all
```

Windows：

```powershell
.\scripts\test.ps1 --all
```

完整 E2E 使用临时 `CODEFIXER_DATA_ROOT`，不会覆盖真实任务数据库。

## 配置原则

- 共享项目只保存 `pathBinding` / `executableRef` / `SecretRef` 等稳定引用。
- 当前机器的仓库路径和可执行程序可以放在 local override。
- Secret 明文独立存储，Web API 只返回 `configured` 状态。
- 运行中 TaskRun 冻结输入；配置热更新只影响后续 Run。

## 外部真实环境验证

本地回归覆盖 Fake Redmine/TAPD/GitLab、真实 Git worktree、Scheduler/Recovery、changed/no_change、取消、Repair/Review 循环和交付幂等。

部署到公司环境后仍应补一轮真实 smoke：

- SVN CLI + 真实工作副本。
- Redmine / TAPD 真实只读凭据。
- GitLab 项目、Token、目标分支和 MR 权限。
- 实际启用的 Claude Code / Codex / OpenCode CLI 登录状态与权限。
