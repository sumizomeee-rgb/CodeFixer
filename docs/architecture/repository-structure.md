# CodeFixer 仓库结构与依赖规范

> 文档状态：V1
> 最后更新：2026-08-12
> 关联：`docs/design-spec.md`、`docs/engineering-readiness-spec.md`

## 1. 目标

本规范定义 CodeFixer 第一版源码、协议、测试、部署与文档的物理布局和依赖方向。

目录的目的不是“分类好看”，而是防止：

- 领域状态机绑定具体平台。
- API 层直接操作数据库。
- Agent Adapter 偷偷参与业务决策。
- 前端页面自行发明状态语义。
- 测试只能通过真实网络或真实工作区运行。
- Artifact Schema 散落在代码实现中。
- Windows/Linux 路径或 Secret 渗入共享配置。

## 2. 顶层目录

```text
CodeFixer/
├─ backend/
│  ├─ pyproject.toml
│  ├─ uv.lock
│  ├─ src/
│  │  └─ codefixer/
│  │     ├─ main.py
│  │     ├─ api/
│  │     ├─ domain/
│  │     ├─ application/
│  │     ├─ orchestration/
│  │     ├─ protocols/
│  │     ├─ adapters/
│  │     └─ infrastructure/
│  └─ tests/
│     ├─ unit/
│     ├─ contract/
│     └─ integration/
├─ frontend/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ src/
│  │  ├─ app/
│  │  ├─ pages/
│  │  ├─ features/
│  │  ├─ entities/
│  │  ├─ design-system/
│  │  ├─ components/
│  │  └─ lib/
│  ├─ tests/
│  └─ e2e/
├─ contracts/
│  ├─ artifacts/
│  ├─ api/
│  ├─ config/
│  └─ fixtures/
├─ tests/
│  ├─ scenarios/
│  ├─ fixtures/
│  ├─ fake-services/
│  ├─ golden/
│  └─ performance/
├─ deploy/
│  ├─ systemd/
│  ├─ env/
│  └─ scripts/
├─ scripts/
├─ docs/
│  ├─ architecture/
│  ├─ design/
│  ├─ testing/
│  ├─ operations/
│  └─ adr/
├─ config/
│  ├─ defaults/
│  └─ examples/
├─ .github/
│  └─ workflows/
├─ README.md
└─ .gitignore
```

运行时数据不得放入源码目录；正式默认位于配置解析后的 `storage.dataRoot`。

## 3. Backend 分层

### 3.1 `domain/`

纯领域模型与规则。

建议结构：

```text
domain/
├─ tasks/
│  ├─ models.py
│  ├─ states.py
│  ├─ failures.py
│  └─ policies.py
├─ delivery/
├─ projects/
├─ tickets/
├─ artifacts/
└─ common/
```

允许依赖：

- Python 标准库。
- 极少量无 IO 的基础类型库。
- domain 内部模块。

禁止依赖：

- FastAPI。
- SQLAlchemy/aiosqlite。
- httpx。
- gitlab/redmine SDK。
- subprocess。
- 具体 Agent CLI。
- filesystem implementation。
- `api/`、`adapters/`、`infrastructure/`。

领域对象不保存 Web 文案、CSS 状态或数据库 row object。

### 3.2 `application/`

用例层，描述“系统要做什么”。

建议：

```text
application/
├─ commands/
│  ├─ start_task.py
│  ├─ cancel_task.py
│  ├─ retry_task.py
│  └─ update_execution_mode.py
├─ queries/
├─ services/
└─ ports/
```

`ports/` 定义核心依赖接口，例如：

- TicketRepository
- TaskRepository
- ArtifactStore
- Clock
- UnitOfWork
- TicketProvider
- ModificationSourceProvider
- AgentRuntime
- VerificationRunner
- FinalActionProvider

应用层可以依赖 domain 与 ports，不依赖具体 Adapter。

### 3.3 `orchestration/`

CodeFixer 的执行控制平面。

建议：

```text
orchestration/
├─ pipeline/
│  ├─ engine.py
│  ├─ stages.py
│  ├─ transitions.py
│  └─ checkpoints.py
├─ scheduler/
│  ├─ dispatcher.py
│  ├─ leases.py
│  └─ recovery.py
├─ reconciliation/
└─ concurrency/
```

职责：

- Stage 顺序。
- lease。
- worker 调度。
- retry policy。
- crash recovery。
- input fingerprint。
- checkpoint 判断。
- delivery aggregate。

禁止：

- 根据 `"tapd"`、`"svn"`、`"claude"` 等字符串承担具体平台流程。
- 直接拼 REST URL。
- 直接执行 shell。
- 存放 UI 展示逻辑。

### 3.4 `protocols/`

平台内部稳定协议的 Python 绑定和校验器。

```text
protocols/
├─ artifacts/
├─ entries/
├─ schemas/
└─ versioning/
```

Canonical Schema 位于仓库顶层 `contracts/`；这里可以包含加载、验证、版本转换和 Pydantic 模型。

禁止复制一份与 `contracts/` 不同步的 Schema。

### 3.5 `adapters/`

所有具体外部实现。

```text
adapters/
├─ tickets/
│  ├─ redmine/
│  └─ tapd/
├─ sources/
│  ├─ git/
│  └─ svn/
├─ agents/
│  ├─ claude_code/
│  ├─ codex/
│  └─ opencode/
├─ knowledge/
│  └─ http/
├─ verification/
│  └─ local_command/
└─ delivery/
   ├─ patch/
   └─ gitlab_mr/
```

每个 Adapter 目录建议包含：

```text
adapter.py
config.py
capabilities.py
errors.py
```

复杂 Adapter 可再拆 client、mapper、reconciler。

Adapter 必须实现 application port；不能反向要求 application import 具体实现。

### 3.6 `infrastructure/`

通用技术基础设施，不包含业务平台语义。

```text
infrastructure/
├─ db/
│  ├─ migrations/
│  ├─ repositories/
│  └─ unit_of_work.py
├─ config/
├─ secrets/
├─ filesystem/
├─ process/
├─ logging/
├─ http/
├─ security/
└─ runtime/
```

例：

- SQLite migration/WAL。
- atomic file replace。
- path resolve。
- process group cancellation。
- structured logging。
- secret store。
- HTTP retry primitive。

GitLab 的业务 API 仍属于 `adapters/delivery/gitlab_mr`，而不是 generic `infrastructure/http`。

### 3.7 `api/`

仅负责 transport。

```text
api/
├─ routers/
├─ schemas/
├─ dependencies/
├─ websocket/
├─ middleware/
└─ errors.py
```

职责：

- request validation。
- auth/IP/CSRF boundary。
- command/query 调用。
- domain failure → HTTP envelope。
- WebSocket event transport。

禁止在 router 中：

- 直接 `SELECT/UPDATE`。
- 调用 subprocess。
- 写 Artifact。
- 直接执行外部交付动作。
- 实现状态机。

`main.py` 只负责 application composition、lifespan、router mount、SPA/static hosting。

## 4. Backend 依赖方向

规范方向：

```text
api ───────────────┐
                   ▼
               application ◄──── orchestration
                   ▲                 │
                   │                 │
domain ◄───────────┘                 │
                                     │
adapters ── implements ports ────────┘
infrastructure ─ implements ports ───┘
```

更严格地说：

- `domain` 不知道任何外层。
- `application` 知道 `domain` 与抽象 port。
- `orchestration` 使用 application/domain/port。
- `adapters` 实现 port。
- `infrastructure` 实现通用 port。
- `api` 调 application。
- `main` 是 composition root，可以组装所有层。

可以使用自动 import-boundary test 防止逆向依赖。

## 5. Frontend 结构

### 5.1 `app/`

应用壳：

- Router。
- Query client。
- Theme provider。
- WebSocket provider。
- error boundary。
- AppShell。
- 全局模式控制器。
- 全局快捷键。

### 5.2 `pages/`

路由页面，只负责页面级编排：

```text
pages/
├─ dashboard/
├─ tasks/
├─ task-detail/
├─ projects/
├─ ticket-providers/
├─ agents/
├─ final-actions/
└─ settings/
```

页面不得自行复制 Design Token 或直接写业务 API 字符串。

### 5.3 `entities/`

前端领域表示：

```text
entities/
├─ task/
├─ task-run/
├─ stage-run/
├─ project/
├─ provider/
└─ delivery/
```

包含：

- TypeScript 类型。
- normalize/mapper。
- selector。
- entity-level display model。

Canonical ID 与枚举来自 generated contracts 或单一共享映射。

### 5.4 `features/`

用户动作或复杂交互：

```text
features/
├─ execution-mode-switch/
├─ start-task/
├─ retry-task/
├─ cancel-task/
├─ inspect-diff/
├─ inspect-failure/
└─ configure-project/
```

Feature 可以组合 entities 和 design-system，不应依赖另一个 page。

### 5.5 `design-system/`

CodeFixer 的视觉底座：

```text
design-system/
├─ tokens/
├─ primitives/
├─ patterns/
├─ motion/
├─ icons/
└─ theme/
```

这里只放跨业务复用、具有稳定视觉语义的组件。

例如：

- Button
- Surface
- Badge
- Tooltip
- Dialog
- SegmentedControl
- StatusDot
- RailNode
- Duration
- CodeBlock
- DiffSurface
- SideEffectBadge

具体 `TaskCard` 如果强绑定任务领域，应放 `entities/task/ui` 或 `components/`，而不是硬塞 Design System。

### 5.6 `components/`

跨页面但具有产品语义的复合组件：

- StageRail。
- TaskCard。
- FailureSurface。
- ArtifactList。
- DeliveryTargets。
- EvidencePanel。
- AttemptTimeline。

## 6. Contracts

`contracts/` 是跨语言单一事实源。

建议：

```text
contracts/
├─ artifacts/
│  ├─ evidence-ref.schema.json
│  ├─ task-discovery.schema.json
│  ├─ gate.schema.json
│  ├─ no-change-report.schema.json
│  ├─ repair-result.schema.json
│  ├─ verification.schema.json
│  ├─ review.schema.json
│  ├─ change-manifest.schema.json
│  └─ final-result.schema.json
├─ api/
│  └─ openapi-baseline.json
├─ config/
│  └─ codefixer-config.schema.json
└─ fixtures/
```

规则：

- Schema 有 `$id` 与明确版本。
- unknown enum 必须失败。
- 后端 Pydantic 与前端 TypeScript 由 Schema/OpenAPI 派生或通过测试证明一致。
- generated 文件放明确的 generated 目录，并由脚本重建。
- 手改 generated 文件视为错误。

## 7. 测试目录

Backend 测试靠近 backend：

```text
backend/tests/
├─ unit/
├─ contract/
└─ integration/
```

跨系统产品语义放顶层：

```text
tests/
├─ scenarios/
│  ├─ SCN-001-changed-patch-success/
│  └─ ...
├─ fixtures/
│  ├─ repos/
│  ├─ tickets/
│  └─ configs/
├─ fake-services/
│  ├─ fake_gitlab/
│  ├─ fake_ticket_server/
│  └─ fake_agent/
├─ golden/
│  ├─ artifacts/
│  └─ timelines/
└─ performance/
```

Frontend：

```text
frontend/tests/
frontend/e2e/
```

视觉 snapshot 建议跟 Playwright test 共存，避免另建无映射的图片仓库；如需要集中审阅，可由 CI 生成 report artifact。

## 8. 运行时目录

源码仓库禁止依赖固定 runtime layout，但默认 `storage.dataRoot` 下推荐：

```text
data/
├─ codefixer.db
├─ tasks/
├─ workspaces/
├─ repositories/
├─ artifacts/
├─ logs/
├─ tmp/
└─ locks/
```

规则：

- `tasks/` 保存 TaskRun Artifact。
- `workspaces/` 只保存可清理隔离工作区。
- `repositories/` 保存受管理 clone/materialization repo。
- `tmp/` 可在启动 recovery 后清理。
- Artifact 不与临时 workspace 混放。
- 数据库只保存可解释的逻辑/相对路径与必要绝对运行路径，不写无法跨平台解释的混合路径。

## 9. 配置与 Secret

仓库中允许：

```text
config/defaults/
config/examples/
```

本地运行时：

- machine override 不进 Git。
- Secret 不进普通 YAML/JSON。
- `.env` 仅允许开发期且必须 gitignored；生产使用明确 Secret provider。
- API 对 Secret 只返回 configured 状态。

日常业务配置直接保存**服务运行机器**上的绝对路径：

```text
localizationSource.path
modificationWorkspace.path
finalActions[type=patch].outputDirectory
```

这些路径属于 `.local/config.json` 的机器配置，不提交 Git；Web 客户端看到的“本地路径”始终指 CodeFixer 服务主机，而不是访问浏览器的电脑。内部 `executableBindings` 仍可使用稳定 Ref，但不暴露在日常项目 UI 中。迁移到另一台机器时重新配置路径，不在共享 SPEC 或默认配置中写死 Windows 盘符。

## 10. Migration

Migration 只能向前追加，禁止修改已经发布的历史 migration。

建议：

```text
backend/src/codefixer/infrastructure/db/migrations/
  0001_initial.sql
  0002_add_delivery_checkpoint.sql
```

每次 migration 必须有：

- fresh install test。
- previous schema → current test。
- rollback/backup 指引；SQLite V1 可不支持自动 down migration，但必须能说明恢复路径。

## 11. Stable Script Entrypoints

开发者与 CI 不应记忆几十条底层命令。

`scripts/` 提供稳定入口，至少：

```text
scripts/bootstrap
scripts/dev
scripts/lint
scripts/typecheck
scripts/test-fast
scripts/test-all
scripts/test-scenarios
scripts/test-e2e
scripts/test-visual
scripts/build
scripts/readiness
```

Windows 可提供 `.ps1`，Linux 提供 `.sh`；核心逻辑尽量复用 Python/Node 跨平台脚本，避免两份行为漂移。

## 12. 禁止事项

- 不建立 `utils.py` 作为无限垃圾桶。
- 不建立 `services.py` 存所有业务。
- 不把 Adapter 注册和业务状态机混在一个文件。
- 不让 React page 直接持有所有 fetch/state/render。
- 不在 component 内 hardcode 后端 enum 推断。
- 不在测试中默认访问公司真实 Redmine/TAPD/GitLab。
- 不把真实 Token 写 fixture。
- 不让 tests 依赖执行顺序。
- 不让 runtime data 写进 repo。
- 不因“V1 快”跳过 migration、contract 或 recovery 边界。

## 13. 新模块放置决策

新增代码时按顺序问：

1. 它是业务事实/规则吗？→ `domain`
2. 它是用例吗？→ `application`
3. 它控制阶段/调度/恢复吗？→ `orchestration`
4. 它是某个外部系统实现吗？→ `adapters`
5. 它是通用 IO/DB/进程技术吗？→ `infrastructure`
6. 它只是 HTTP/WS transport 吗？→ `api`
7. 它是稳定跨阶段数据协议吗？→ `contracts` + `protocols`

不能回答时先写 ADR，不得先随意放进 `common`。
