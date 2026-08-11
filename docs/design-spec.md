# CodeFixer 产品与技术设计 SPEC

> 文档状态：V2 初版
> 最后更新：2026-08-11
> 适用范围：CodeFixer 第一版实现与后续扩展
> 本文是产品语义、任务协议和技术边界的唯一设计基准。

## 1. 产品定义

### 1.1 一句话定位

CodeFixer 是一个通用的 Bug 自动修复与交付平台：它持续接收外部缺陷工单，让 Agent 自主反查唯一修改源中的真实实现，完成修复、验证与独立审查，最后按项目配置生成 Patch 和/或创建 GitLab MR。

CodeFixer 不是某个业务项目的专用脚本，也不是一个把工单和源码拼成大 Prompt 的包装器。平台负责冻结输入、隔离工作区、控制权限、编排阶段、验证产物、记录证据和执行交付；Agent 负责阅读任务档案、自主调查和修改代码。

### 1.2 要解决的核心痛点

1. 仅把 Bug 单号或标题交给 LLM，模型往往无法可靠推断真正的仓库、模块、调用链和版本边界。
2. 传统关键词匹配、文件名 Glob 和 LLM 自评分无法形成可信的定位结论。
3. Agent 修改、测试、Review、生成 Patch、Cherry-pick 和创建 MR 分散在多个手工步骤中，容易遗漏或留下脏工作区。
4. 多个 Bug 同时处理时，共享工作副本、内存队列和模糊状态会造成互相污染、重复执行或不可恢复。
5. 不同项目的工单平台、代码来源、验证命令和交付方式不同，核心流程不能绑定某个业务项目、TAPD、Redmine、SVN 或 GitLab 的固定字段。
6. 自动化不能把“没有查到”误报成“Bug 不存在”，也不能在部分交付失败时伪装成成功。

### 1.3 成功标准

第一版完成后，用户应能：

- 配置一个或多个工单来源。
- 配置多个项目，每个项目定义一个修改源和一个或多个最终动作。
- 选择“全自动”或“待我开始”。
- 让多个任务在资源上限内并发运行。
- 查看每个任务当前阶段、每次尝试、输入快照、Agent 产物、验证结果和失败原因。
- 对一个 Bug 完成以下两种健康终态之一：
  - 代码已修改并且所有最终动作成功。
  - 有充分证据证明当前基线无需修改。
- 对失败任务看到可读原因、失败阶段、证据路径、外部副作用和建议处理方式。
- 在修正配置或外部问题后安全重试，不重复创建 Patch 或 MR。

## 2. 已确认的产品决策

| 决策 | 结论 |
|---|---|
| 产品名称 | `CodeFixer`，不绑定任何业务项目 |
| 管理形态 | Web 管理界面 |
| 执行模式 | 全自动 / 待我开始 |
| 手动启动语义 | 点击一次开始后，任务自动执行完整流程，不逐阶段等待审批 |
| Bug 与修改源 | 一个 Bug 任务必须且只能绑定一个修改源 |
| 最终动作 | 一个任务可以配置一个或多个最终动作 |
| 第一版最终动作 | `patch`、`gitlabMr` |
| GitLab MR 类型 | 普通 MR，不创建 Draft MR |
| 多目标分支 | 一个 `gitlabMr` 动作可向多个目标分支分别创建 MR |
| MR 失败 | 任意必需 MR 目标失败，整个任务失败 |
| GitHub PR | 第一版不实现，也不作为占位分支混入核心流程 |
| 反查失败 | 任务失败并给出原因，不进入人工文件勾选等待态 |
| Bug 已不存在 | 只有证据充分时才健康完成为 `no_change` |
| 并发 | 单任务阶段有序执行；不同任务可并发；冻结修改后的独立最终动作可有界并发 |

## 3. 设计原则

### 3.1 文档交接，不灌上下文

平台为每个阶段生成固定路径的入口文档。启动 Agent 时只传入口文件的绝对路径和一条最小启动指令，禁止把工单正文、调查正文、源码正文和知识库响应重新拼接进命令行 Prompt。

### 3.2 Agent 自主调查，平台做确定性门禁

Discovery Agent 自己读取工单档案和唯一修改源，自主搜索与反查。平台不替 Agent 决定文件清单，但会检查工单中的显式路径、堆栈符号、错误码、模块名、版本、附件和关联提交是否得到处理。

### 3.3 调查结论不是修改授权

Discovery 产物只是第二阶段的定位线索。Repair Agent 必须在本次隔离工作区重新读取和核实当前基线，不能仅凭 Discovery 文档修改文件。

### 3.4 状态与结果分离

`completed` 是任务生命周期状态，`changed` 和 `no_change` 是业务结果。反查失败、证据不足和无法复现不能使用 `no_change`。

### 3.5 所有最终动作消费同一份冻结修改

Patch 和 GitLab MR 必须从同一份经过验证和 Review 的不可变修改快照生成，禁止各自重新读取一个可能已经变化的工作区。

### 3.6 外部副作用由平台执行

Agent 不获得 GitLab Token，不自行创建远程分支或 MR。平台只相信自身采集的 Git diff、SVN diff、命令退出码、文件校验和及 GitLab API 返回结果。

### 3.7 抽象到接口，不提前建设插件市场

第一版使用稳定接口和仓库内适配器注册表。新增平台时实现新适配器，不在核心状态机中增加 `if tapd`、`if svn` 一类业务分支；第一版不建设动态插件安装市场。

## 4. 核心领域模型

### 4.1 TicketProvider

工单来源实例，负责：

- 增量拉取 Bug。
- 按外部 ID 获取最新详情。
- 冻结标题、描述、评论、附件元数据、关联单、版本和原始字段。
- 提供外部更新时间或版本号作为幂等依据。
- 把平台无关的原始数据转换为统一 `TicketSnapshot`。

第一版内置 Redmine 和 TAPD 适配器，但核心流程只依赖 `TicketProvider` 契约。

### 4.2 Project

项目是一个可执行策略集合，包含：

- 带优先级的工单路由规则。
- 唯一 `ModificationSource`。
- 可选知识源。
- Discovery、Repair、Review 使用的 Agent profile。
- 允许修改的路径与文件类型。
- 验证命令和超时。
- 修复循环上限。
- 一个或多个 `FinalAction`。
- 并发与共享资源限制。

项目配置不包含任何 CodeFixer 核心代码无法理解的隐式约定。业务特定规则应写入项目策略文档或适配器配置。

路由规则必须产生唯一结果：

- 没有项目匹配时，任务以 `project_not_found` 失败。
- 多个项目匹配时，选择数值最高的优先级。
- 多个最高优先级规则并列时，任务以 `project_ambiguous` 失败。
- 用户修正项目绑定后必须创建新 TaskRun，Agent 无权改变绑定。

### 4.3 ModificationSource

一个任务必须绑定且只能绑定一个修改源。修改源定义：

- 类型：`git` 或 `svn`。
- 当前机器上的仓库/工作副本位置。
- 基线获取方式。
- 隔离工作区策略。
- 允许读取和修改的根目录。
- 路径白名单、黑名单和扩展名约束。
- 可选的知识源关联。

任务开始后不能由 Agent 静默切换修改源。若证据表明路由到错误修改源，任务以 `source_mismatch` 失败。

“唯一修改源”不等于“只能修改一个文件”。Repair Agent 可以修改该源内任意数量的授权文件。

### 4.4 FinalAction

最终动作消费冻结修改快照。第一版只支持：

- `patch`：生成 Patch 文件。
- `gitlabMr`：把任务提交按 Cherry-pick MR 语义投递到一个或多个 GitLab 目标分支。

配置中的所有已启用最终动作都是必需动作。任意动作失败，任务失败；已经成功的外部交付不会被隐藏或回滚。

项目必须至少配置一个最终动作；动作 ID 在项目内唯一。每次 TaskRun 冻结动作配置 hash，生成单调递增的动作版本。

### 4.5 AgentRuntime

Agent Runtime 只负责：

- 把公共阶段请求转换为对应 CLI 参数。
- 配置该阶段的工作目录和工具权限。
- 启动、超时、取消并清理子进程。
- 解析统一的运行结果、费用和 usage。

Claude Code、Codex、OpenCode 分别实现适配器。适配器不得预读业务文件、替 Agent 选择仓库或改写阶段工作流。

### 4.6 Task、TaskRun 与 StageRun

- `Task`：一个外部 Bug 在 CodeFixer 中的长期记录。
- `TaskRun`：一次基于冻结工单、策略和代码基线的完整执行。
- `StageRun`：某个阶段的一次尝试。
- `DeliveryActionRun`：最终动作的一次执行。
- `DeliveryTargetRun`：`gitlabMr` 中某个目标分支的子执行。

重试会创建新 attempt 或新 TaskRun，旧产物和证据永久保留。

## 5. 全局执行模式

### 5.1 待我开始

系统持续轮询并收录 Bug，但只完成轻量的工单持久化：

- 不调用 Agent。
- 不准备写工作区。
- 不修改代码。
- 不运行测试。
- 不执行最终动作。

任务状态为 `awaiting_start`。用户可：

- 开始单个任务。
- 批量开始选中任务。
- 忽略或归档不需要处理的工单。

点击开始后，平台先刷新工单与仓库，再创建新的 TaskRun。等待期间不冻结旧代码，因此任务放置较久并不会天然使用过期仓库。

### 5.2 全自动

新收录且匹配项目规则的 Bug 自动进入 `queued`，随后执行完整流水线。成功路径不需要用户点击。

全自动不会绕过：

- 修改源路由。
- Discovery 证据门禁。
- 修改范围校验。
- 项目验证命令。
- 独立 Review。
- 基线变化检查。
- 最终动作成功条件。

定位失败、验证失败、Review 超过修复循环或交付失败最终都会成为 `failed`。

### 5.3 模式切换

从“待我开始”切到“全自动”时：

- 已经收录且仍为开放状态的 `awaiting_start` 任务也进入队列。
- 界面在确认区域显示将被排队的任务数量。
- 每个任务真正开始时重新获取工单和代码基线。
- 已关闭、已忽略或已归档的任务不自动恢复。

从“全自动”切到“待我开始”时：

- 新收录任务进入 `awaiting_start`。
- 已经授权的 `queued` 或 `running` 任务继续完成。
- 用户仍可单独请求取消；取消是停止后续动作并尽力清理，不承诺回滚已经产生的 Patch、远程分支或 MR。

每个 TaskRun 保存 `execution_mode_snapshot`，运行中不受全局开关后续变化影响。

## 6. 任务流水线

### 6.1 主流程

```text
ingest
  → prepare
  → discovery
  → assess
      ├─ change_required
      │    → workspace_prepare
      │    → repair
      │    → verify
      │    → review(mode=change)
      │    ↘ 有界返回 repair
      │    → pre_delivery_check
      │    → freeze_change
      │    → deliver
      │    → finalize(completed, changed)
      │
      ├─ no_change_claim
      │    → no_change_verify
      │    → review(mode=no_change)
      │    → finalize(completed, no_change)
      │
      └─ unresolved
           → finalize(failed)
```

### 6.2 阶段定义

| 阶段 | 执行者 | 主要输入 | 主要输出 | 写权限 |
|---|---|---|---|---|
| `ingest` | 平台 | 外部工单 | 当前工单记录 | 数据库 |
| `prepare` | 平台 | 最新工单、项目配置、当前基线 | 冻结快照、入口文档、输入指纹 | 任务产物目录 |
| `discovery` | Discovery Agent | Discovery 入口路径 | `task-discovery.md/json` | Discovery 输出目录 |
| `assess` | 平台 | Discovery 产物与确定性门禁 | `change_required / no_change_claim / unresolved` | 数据库 |
| `no_change_verify` | Repair/Verifier Agent | 固定入口路径 | `no-change-report.md/json` | 阶段输出目录 |
| `workspace_prepare` | 平台 | 修改源与冻结基线 | 隔离工作区 manifest | 工作区 |
| `repair` | Repair Agent | Repair 入口路径 | 代码修改、`repair-result.json` | 唯一隔离工作区 |
| `verify` | 平台命令执行器 | 候选修改快照、验证配置 | `verification.md/json` | 验证临时目录 |
| `review` | 独立 Agent 会话 | 候选修改或 no-change 报告 | `review.md/json` | Review 输出目录 |
| `pre_delivery_check` | 平台 | 最新工单、修改源基线、动作目标 | 稳定性检查或新一轮尝试 | 数据库与阶段目录 |
| `freeze_change` | 平台 | 已验证工作区 | 不可变 diff、commit、checksum | 冻结目录 |
| `deliver` | 平台动作执行器 | 冻结修改与动作配置快照 | Patch/MR 结果 | 配置的外部目标 |
| `finalize` | 平台 | 全部阶段和动作结果 | 任务终态、索引、清理结果 | 数据库与产物目录 |

### 6.3 Discovery Agent

Discovery 是所有修复任务的固定阶段，不是高级开关。

职责：

- 完整读取冻结工单、评论、附件清单和项目策略。
- 在唯一修改源内搜索与工单相关的模块、符号、配置、资源、协议和历史变更。
- 结合堆栈、错误码、页面名、版本、关联提交等线索形成证据链。
- 指出可能的复现链、根因方向、受影响边界和待核实内容。
- 输出一个明确结论：
  - 找到足够可信的修改范围。
  - 当前基线可能已经无需修改。
  - 无法可靠定位。

Discovery 不得：

- 修改代码。
- 创建分支、提交、Patch 或 MR。
- 把“搜索不到”声明为 Bug 不存在。
- 静默跳到另一个修改源。

### 6.4 Discovery 确定性门禁

平台从工单快照提取可机械核对的强线索：

- 显式文件路径、仓库或模块名。
- 堆栈中的类、函数和行号。
- 错误码、协议名、配置键。
- UI、Prefab、场景、资源名。
- 版本号、关联提交、MR、变更记录。
- 附件中明确引用的对象。

Discovery 未覆盖强线索时允许同一 Agent 补查一次。补查后仍无法定位则失败，不无限循环，也不按读取文件数生成伪置信度。

### 6.5 Repair 与有界修复循环

Repair Agent 只能修改唯一隔离工作区内允许的路径。平台在 Agent 结束后自行采集变更，并拒绝：

- 修改白名单外路径。
- 修改禁止扩展名。
- 触碰仓库凭据、CodeFixer 配置或任务产物协议。
- 没有任何有效 diff，却声称完成修复。

`verify` 或 `review` 可以把报告写入下一次 Repair 的固定入口文档并回到 Repair。配置项 `max_repair_attempts` 默认 3，包含第一次 Repair；总耗时和费用预算同时生效。超过任一上限后任务失败，不能形成死循环。

每次 Repair 结束后，平台先生成只读的候选修改快照。Verify 和 `review(mode=change)` 都读取这份候选快照；它不是最终交付包，后续 Repair 会使旧候选快照失效。

### 6.6 Freeze Change

通过验证和 Review 后，平台创建不可变交付包，至少包含：

- 基线 revision/SHA。
- 修改源已经存在时的有序 commit SHA 列表；SVN 或异仓库场景可以为空。
- 完整 diff。
- 修改文件列表。
- 删除、新增和重命名列表。
- 验证结果。
- Review 结果。
- 内容 SHA-256。
- 本次策略与最终动作配置版本。

最终动作只能消费这个交付包，不能重新读取可变工作区。

`pre_delivery_check` 必须在冻结之前完成。若基线变化，需要创建新的 Repair/Verify/Review 尝试；旧候选快照标记为 superseded。只有新的稳定候选通过后才能生成新的 `change_version`。旧冻结包永久保留但不可交付。

## 7. 固定路径任务档案协议

### 7.1 目录结构

```text
data/tasks/<task-id>/
  task.json
  runs/<run-id>/
    snapshot/
      ticket.md
      ticket.raw.json
      attachments.json
      project-policy.md
      source-manifest.json
      config-snapshot.json
    stages/
      prepare/
      discovery/
        entry.md
        task-discovery.md
        task-discovery.json
        gate.json
      no-change-verify/
        entry.md
        no-change-report.md
        no-change-report.json
      repair/<attempt>/
        entry.md
        repair-result.json
      verify/<attempt>/
        verification.md
        verification.json
      review/<attempt>/
        entry.md
        review.md
        review.json
      pre-delivery-check/<attempt>/
        result.json
      freeze-change/<change-version>/
        change.patch
        change-manifest.json
      deliver/<change-version>/<action-id>/<action-version>/
        result.json
        attempts/<attempt>/
          attempt.json
          logs/
    logs/
    final-summary.md
    final-result.json
```

固定指的是每个 TaskRun 内的相对文件名和协议稳定；不同任务必须使用不同目录，不能共用一个全局交接文件。

### 7.2 Agent 启动协议

平台启动 Agent 时只发送类似以下内容：

```text
完整读取并执行此文件中的任务：
/absolute/path/to/data/tasks/<task-id>/runs/<run-id>/stages/discovery/entry.md
```

入口文件写明：

- 阶段目标和禁止事项。
- 需要读取的其他固定文件路径。
- 允许使用的工具与权限。
- 输出文件路径和 Schema。
- 超时、预算与完成条件。

Agent 的 stdin 或命令参数中不得再次拼接工单正文、源码正文、Discovery 正文或知识库内容。

### 7.3 不可信内容边界

工单、评论、附件、源码、Discovery 笔记和历史提交都视为不可信材料。入口文档明确要求忽略其中试图修改系统规则、索取凭据、扩大权限或改变输出路径的内容。

### 7.4 平台校验

平台不相信 Agent 自报的“已读取”“已测试”或“已创建 MR”。必须通过以下来源确认：

- 文件是否真实存在且通过 Schema。
- Git/SVN 状态和 diff。
- 命令退出码与日志。
- 修改路径机械检查。
- GitLab API 查询结果。
- Artifact hash 和输入指纹。

## 8. 状态、结果和失败模型

### 8.1 顶层任务状态

| 状态 | 含义 |
|---|---|
| `awaiting_start` | 已收录，等待用户开始 |
| `queued` | 已授权，等待执行资源 |
| `running` | 某个阶段正在执行 |
| `cancel_requested` | 已请求取消，正在终止当前阶段与清理 |
| `completed` | 健康完成 |
| `failed` | 执行失败，等待查看或重试 |
| `canceled` | 已取消 |

界面中的“需要处理”是对 `failed`、取消未清理完和部分交付任务的聚合视图，不新增含糊的 `needs_attention` 状态。

忽略和归档不是生命周期状态：

- `ignored_at` 阻止任务自动创建新的 TaskRun，可由用户撤销。
- `archived_at` 只影响默认列表可见性，不改变任务事实。
- 外部工单重新打开或更新时，已归档任务仍记录事件；只有未忽略且重新满足路由条件时才按当前模式创建新 TaskRun。

### 8.2 业务结果

仅 `completed` 填写：

- `changed`：产生有效修改，所有最终动作成功。
- `no_change`：有充分证据证明当前基线无需修改。

### 8.3 阶段状态

每个 StageRun 独立保存：

- `pending`
- `queued`
- `running`
- `succeeded`
- `failed`
- `skipped`
- `canceled`

StageRun 同时保存 `attempt`、开始/结束时间、输入指纹、Runner、模型、费用、输出路径和失败对象。

### 8.4 结构化失败

每个失败至少包含：

```json
{
  "code": "discovery_no_target",
  "stage": "discovery",
  "summary": "工单描述中的登录流程无法在当前修改源中定位",
  "details_path": ".../failure.md",
  "evidence_paths": [".../task-discovery.md", ".../gate.json"],
  "retryable": false,
  "suggested_action": "检查工单路由或补充复现信息",
  "side_effects": []
}
```

`summary` 面向用户说人话；原始 stderr 和脱敏 API 响应放入日志，不直接挤进卡片。

### 8.5 失败分类

至少支持：

- `ticket_fetch_failed`
- `project_not_found`
- `project_ambiguous`
- `ticket_changed_during_run`
- `source_not_found`
- `source_mismatch`
- `discovery_no_target`
- `discovery_ambiguous`
- `insufficient_evidence`
- `workspace_prepare_failed`
- `agent_timeout`
- `agent_protocol_invalid`
- `repair_no_valid_diff`
- `unauthorized_change`
- `verification_failed`
- `review_rejected`
- `repair_cycle_exhausted`
- `base_changed_conflict`
- `patch_failed`
- `gitlab_mr_commit_failed`
- `gitlab_mr_push_failed`
- `gitlab_mr_create_failed`
- `provider_unavailable`
- `cleanup_failed`

## 9. Bug 已不存在或已经修复

### 9.1 健康无修改结果

允许的 `no_change_reason`：

- `already_fixed`：当前基线已经包含可识别的修复。
- `not_present_on_current_baseline`：工单描述的错误路径在当前基线客观不存在。
- `not_applicable_to_source`：有证据证明工单不适用于路由到的版本或代码基线。
- `upstream_fixed_during_run`：运行期间基线更新，重新验证后确认上游已修复。

### 9.2 必需证据

`no_change` 至少包含：

- 当前修改源和冻结 revision/SHA。
- 关键代码或配置证据。
- 可执行验证及其结果；如果项目没有测试能力，必须有项目级显式豁免和替代证据。
- 可能的修复提交、MR 或版本记录；找不到时说明。
- 为什么不需要 Patch 或 MR。
- 独立 Review 的通过结论。

`not_present_on_current_baseline` 不能以全文搜索无结果为依据。至少需要一项当前状态证据和一项独立佐证，例如：

- 当前调用链、配置入口或可执行检查证明该错误路径不可达。
- 历史提交、版本说明或旧符号记录证明相关逻辑已删除或替换。
- 可重复的复现步骤在目标基线上稳定不再出现，并记录运行环境。

`not_applicable_to_source` 只用于“修改源绑定正确，但工单明确针对另一个版本、平台或被项目策略排除的组件”。如果真正需要修改的代码位于另一个修改源，则必须是 `source_mismatch` 失败。

`allowNoAutomatedTests` 只豁免项目缺少自动测试套件，不能豁免当前任务所需运行环境不可用。无测试项目仍必须提供配置中预先声明的编译、静态检查、历史证据或人工可复核的替代验证。

### 9.3 不能算无修改的情况

以下一律失败：

- 搜索不到相关文件。
- Agent 无法判断。
- 缺少运行环境导致无法复现。
- 工单描述过少且没有其他证据。
- Discovery 在多个模块之间无法消歧。
- GitLab Cherry-pick 返回 empty，但尚未证明全部修改已存在。

`no_change` 时所有最终动作标记为 `skipped`，原因固定为 `no_change_required`。

## 10. 并发、租约与工作区

### 10.1 并发模型

- 单个 TaskRun 的普通阶段按顺序执行。
- 不同 TaskRun 可并发。
- `freeze_change` 之后，彼此独立的最终动作可有界并发。
- `gitlabMr` 的不同目标分支可有界并发；单个目标内的 commits 必须按顺序串行 Cherry-pick。

所有最终动作先通过一次无副作用的全局交付预检，然后统一进入执行。动作并发开始后，即使其中一个失败，其他已经调度的动作仍运行到可确认的终态，平台最后统一聚合结果。

配置至少包含：

- 全局最大并发任务数，默认 3。
- 每个 AgentRuntime 的并发上限。
- 每个 TicketProvider 的请求限流。
- 每个 GitLab connection 的请求限流。
- 每个项目或修改源的并发上限。
- 可选命名资源锁，例如共享测试服、固定端口和数据库。

### 10.2 Git 工作区

每个任务使用独立 Git worktree 和唯一平台分支。允许同一仓库的多个任务并发；共享 clone 的 fetch、prune 和 worktree 元数据修改只持有短时仓库锁。

### 10.3 SVN 工作区

SVN 必须使用独立任务工作副本或受管理的工作副本池。若某种 SVN 布局无法可靠隔离，则该修改源必须配置为独占 lease，但不影响其他修改源的任务并发。

### 10.4 持久化调度

SQLite 是任务事实来源，`asyncio.Queue` 只能作为唤醒优化，不能作为唯一队列。

Worker 领取 StageRun 时写入：

- lease owner。
- lease 到期时间。
- heartbeat。
- 行版本。

使用事务和 compare-and-swap 防止两个 Worker 执行同一阶段。服务重启后：

- 未开始的 queued 阶段可恢复。
- 只读阶段可根据输入指纹重试。
- 可能已经产生写操作或费用的阶段先对账，再决定续跑或失败。
- 不允许盲目重放 GitLab MR 创建请求。

### 10.5 基线变化

`prepare` 时刷新工单和代码基线。`pre_delivery_check` 在任何最终动作产生副作用前再次检查工单、修改源和全部动作目标：

- 无变化：继续交付。
- 能自动更新且无冲突：重新应用修改，并重新执行 verify 与 review。
- 更新后 diff 为空且能证明上游已经修复：转 `completed/no_change`。
- 冲突或无法证明安全：以 `base_changed_conflict` 失败。

`freeze_change` 完成后先执行所有最终动作的无副作用 preflight。只要 preflight 发现目标已漂移，整组动作都不得开始，返回 `pre_delivery_check`。一旦任一动作写出 Patch、创建分支或发出其他外部副作用，本次运行就不能再转为 `no_change`；后续漂移只能使对应动作失败。

## 11. 验证与独立 Review

### 11.1 项目验证配置

项目可配置多个验证步骤：

```yaml
verification:
  timeoutSeconds: 1200
  steps:
    - id: unit
      command: ["python", "-m", "pytest"]
      workingDirectory: "."
      required: true
    - id: build
      command: ["npm", "run", "build"]
      workingDirectory: "frontend"
      required: true
```

命令使用参数数组，不使用未经解析的 shell 字符串。每步记录 stdout、stderr、退出码、耗时和产物路径。

没有自动测试的项目必须显式配置：

```yaml
verification:
  allowNoAutomatedTests: true
  reason: "历史项目暂无自动测试，使用编译和独立 Review 作为替代门禁"
```

不能因为配置缺失而悄悄跳过验证。

### 11.2 Review

Review 使用统一的 `review` stage、独立 Agent 会话和只读权限。`mode=change` 检查候选修改，`mode=no_change` 检查无修改报告。两种模式使用同一个 Review profile、目录协议和状态模型。

Review 检查：

- 修改是否针对工单问题。
- 是否越过允许范围。
- 是否遗漏明显边界。
- 验证是否足以支撑交付。
- 是否引入高风险副作用。
- 无修改结论是否有正向证据。

Review 输出 `approved`、`needs_repair` 或 `rejected`。`needs_repair` 在预算内回到 Repair；`rejected` 或循环耗尽后任务失败。

## 12. 最终动作：Patch

### 12.1 配置

```yaml
type: patch
id: primary-patch
outputDirectory: "/configured/output/path"
filenameTemplate: "{ticket_provider}-{ticket_id}-{run_id}.patch"
overwrite: false
```

可配置项：

- 输出目录。
- 文件名模板。
- 是否允许覆盖。
- Git 或 SVN 对应的 Patch 格式选项。

输出目录是当前部署机路径，由管理员配置并在保存时执行可写性预检。工单内容不能直接成为未净化路径。

### 12.2 执行

- 只消费 `freeze_change`。
- 先写同目录临时文件，再原子改名。
- 记录文件大小、SHA-256、修改文件数和下载地址。
- 相同幂等键且内容 hash 相同时，重试直接复用已有文件。
- 同名文件内容不同且 `overwrite=false` 时失败，不静默覆盖。

## 13. 最终动作：GitLab MR

### 13.1 行为定义

动作类型固定为 `gitlabMr`。它先从冻结修改确定性地产生一组 delivery commits，再复刻 GitLab Web 的 Cherry-pick 后创建 MR 流程：

```text
冻结修改 → 有序 delivery commits
  → 对每个目标分支：
       从目标分支创建临时分支
       → 按最旧到最新 Cherry-pick 全部 commits
       → 从临时分支向目标分支创建普通 MR
```

目标分支绝不能被平台直接修改。MR 创建成功即表示该目标交付成功，不等待 MR 合并。

### 13.2 配置

```yaml
type: gitlabMr
id: main-gitlab-mr
connectionRef: company-gitlab
projectPath: group/project
materializationRepository: "/local/git/repository"
pathMappings:
  - from: "."
    to: "."
targetBranches:
  - main
  - release/current
assignee:
  username: reviewer
titleMode: latestCommitSubject
removeSourceBranch: true
maxTargetConcurrency: 2
```

可配置项：

- GitLab connection 引用。
- GitLab project path/ID。
- 修改源到 Git 仓库的物化路径与路径映射。
- 一个或多个目标分支。
- MR assignee。
- MR 标题和描述模板。
- 合并后是否删除临时分支。
- 目标分支并发上限。

`connectionRef` 只引用服务端秘密，不保存明文 Token。

### 13.3 Commit 可见性

GitLab API 必须能够解析本任务的 commit SHA。平台在动作前负责：

- 修改源本身是同一 GitLab Git 仓库时，创建并发布受控任务 commit/ref。
- 修改源是 SVN 或另一个仓库时，只把冻结修改通过 `pathMappings` 物化到配置的 Git 仓库，创建任务 commits 并发布到受控暂存 ref。

此过程属于平台，不由 Agent 执行。生成的 delivery commits 记录在 `DeliveryActionRun`，不回写或改变不可变 `freeze_change`；所有目标分支必须使用完全相同的 commit 序列。平台必须确认 commits：

- 非空。
- 无重复。
- 按最旧到最新排序。
- 与冻结修改 hash 一致。
- 已能通过 GitLab Commits API 获取。

### 13.4 每个目标分支的步骤

1. 加载项目并确认目标分支存在。
2. 按幂等键查询是否已有本动作创建的 MR。
3. 从目标分支当前 HEAD 创建临时分支。
4. 按顺序 Cherry-pick 全部 commits。
5. 任意 commit 失败时停止，禁止创建只包含部分 commits 的 MR。
6. 使用最新 commit subject 作为默认标题。
7. 创建普通 MR，设置 assignee 和 `remove_source_branch`。
8. 再次查询确认 MR，保存 IID、URL、源/目标分支和 commits。

### 13.5 临时分支命名

遵循：

```text
cherry-pick-<最新commit前8位>
cherry-pick-<最新commit前8位>-2
...
cherry-pick-<最新commit前8位>-100
```

名称已存在时递增后缀。连续 100 个名称均被占用则该目标失败。

### 13.6 MR 描述与幂等键

默认描述包含：

- CodeFixer 任务 ID。
- 外部工单 ID 和链接。
- 完整 commit 列表。
- 修复与验证摘要。
- 不可见的稳定 delivery key。

```html
<!-- codefixer-delivery-key: <task>/<run>/<action-version>/<target> -->
```

网络中断或服务重启后，平台按本地记录、delivery key、源分支和目标分支查询所有状态的 MR。确认不存在匹配对象后才能重建。

### 13.7 失败与清理

临时分支创建成功后、MR 创建完成前发生错误时，平台尝试删除临时分支。清理失败不得覆盖主失败；结果记录：

- 原失败原因。
- 遗留分支名。
- `cleanupRequired=true`。
- 清理 API 的脱敏错误。

成功创建的 MR 不自动关闭或回滚。

### 13.8 多目标与部分成功

每个目标分支使用统一粗状态：

- `pending`
- `running`
- `reconciling`
- `succeeded`
- `failed`

当前子步骤单独保存在 `step`：

- `preflight`
- `materializing_commits`
- `creating_source_branch`
- `cherry_picking`
- `creating_mr`
- `cleaning_up`
- `done`

示例：三个目标中两个 MR 成功、一个冲突：

- `gitlabMr.status = failed`。
- `gitlabMr.outcome = partial_success`。
- `task.status = failed`。
- 两个成功 MR 的链接保留。
- 重试默认只执行失败目标。

目标返回 Cherry-pick empty 时，除非额外证明所有修改已存在并符合幂等记录，否则按失败处理，不能直接转换为 `no_change`。

## 14. 取消与重试

### 14.1 取消

- `awaiting_start`、`queued` 可立即取消。
- `running` 先进入 `cancel_requested`，终止 Agent 进程组和当前命令，不再启动新阶段。
- 清理隔离工作区后进入 `canceled`。
- 已经产生的 Patch、远程分支或 MR 不自动删除；必须在 `side_effects` 中列出。
- `completed` 和 `failed` 不提供“取消”，只提供重新运行或重试。

### 14.2 自动重试

仅对明确的瞬时错误自动重试，例如：

- 网络超时。
- API 限流。
- Runner 非业务性崩溃。
- Worker lease 过期且外部对账确认没有副作用。

定位歧义、验证失败、Review 拒绝和配置错误不盲目自动重试。

### 14.3 人工重试

- 输入指纹不变时，可从安全检查点续跑。
- 工单、策略、修改源基线或最终动作配置变化时，必须创建新 TaskRun 并从 `prepare` 开始。
- Delivery 部分失败默认只重试失败动作/目标。
- 已成功动作不重复。
- 用户想为已关闭的成功 MR 再创建一个 MR，属于“重新交付”，必须创建新的动作版本。

Delivery-only 重试沿用原 TaskRun 和 `change_version`，创建新的 deliver StageRun/DeliveryTarget attempt；Task 从 `failed` 回到 `queued`，全部必需动作最终成功后可转为 `completed/changed`。输入或配置发生变化时不得使用 Delivery-only 重试。

## 15. 适配器架构

### 15.1 接口

核心只依赖：

- `TicketProvider`
- `ModificationSourceProvider`
- `KnowledgeProvider`
- `AgentRuntime`
- `VerificationRunner`
- `FinalActionProvider`

每个适配器声明 capability，例如是否支持增量游标、附件、历史日志、隔离工作区、多目标交付和取消。

### 15.2 第一版内置适配器

| 类别 | 第一版 |
|---|---|
| 工单 | Redmine、TAPD |
| 修改源 | Git、SVN |
| 知识源 | 无、HTTP 知识服务 |
| Agent | Claude Code、Codex、OpenCode |
| 验证 | 受控本地命令 |
| 最终动作 | Patch、GitLab MR |

业务知识服务若启用，只是一个 HTTP `KnowledgeProvider`。核心代码、Prompt 协议和 UI 不出现业务项目专属语义。

### 15.3 Runner 公共协议

Prompt plan 冻结：

- stage ID。
- Agent profile 和实际模型。
- 入口文档路径。
- 工作目录。
- 权限清单。
- 输出路径与 Schema。
- 超时和预算。

不同 Runner 只转换 CLI 细节，不能修改业务输入或阶段职责。

## 16. 配置体系

### 16.1 配置分层

采用三层：

1. Git 管理的默认配置：只放跨机器默认值和 Schema 版本。
2. 当前机器本地配置：路径、端口、CLI 位置、项目启停和 Web 保存项，不进 Git。
3. Secret 配置：Token、API Key 和凭据引用，不进入普通配置响应和日志。

本地配置对默认配置做深度合并；保存时只写相对默认值的最小覆盖，并使用同目录临时文件加原子替换。

### 16.2 顶层结构

```yaml
schemaVersion: 1

execution:
  mode: awaitingStart
  maxConcurrentTasks: 3
  maxRepairAttempts: 3

ticketProviders: []
agentProfiles: []
knowledgeProviders: []
connections: []
projects: []
```

`execution.mode`：

- `automatic`
- `awaitingStart`

### 16.3 配置快照

每次 TaskRun 在 `prepare` 冻结：

- 有效项目配置。
- Agent profiles。
- 修改源。
- 验证命令。
- 最终动作。
- 连接引用的非秘密元数据。
- 配置版本/hash。

运行中热重载只影响后续 TaskRun。

## 17. 持久化模型

第一版使用 SQLite WAL，数据库保存元数据与索引，大文件放任务产物目录。

核心表：

- `ticket_records`：外部工单当前视图和游标。
- `ticket_snapshots`：不可变工单版本。
- `tasks`：长期任务与当前顶层状态。
- `task_runs`：每次执行及输入指纹。
- `stage_runs`：阶段和 attempt。
- `artifacts`：路径、类型、hash、大小和来源。
- `delivery_action_runs`：最终动作结果。
- `delivery_target_runs`：GitLab 每目标分支结果。
- `task_events`：用户可读时间线。
- `worker_leases`：执行租约和 heartbeat。
- `provider_cursors`：工单来源增量游标。

工单幂等键为：

```text
provider_instance_id + external_ticket_id
```

工单更新创建新 snapshot，不覆盖已经运行的 TaskRun 输入。

数据库必须保证：

- 同一个 Task 同时最多一个 active TaskRun。
- `(task_run_id, change_version, action_id, action_version, target_key)` 唯一。
- 同一个 StageRun attempt 只能被一个有效 lease 持有。

## 18. API 设计

主要接口：

```text
GET    /api/health
GET    /api/readiness

GET    /api/settings
PUT    /api/settings/execution-mode

GET    /api/projects
POST   /api/projects
PUT    /api/projects/:id
POST   /api/projects/:id/preflight

GET    /api/tasks
GET    /api/tasks/:id
POST   /api/tasks/:id/start
POST   /api/tasks/start-batch
POST   /api/tasks/:id/cancel
POST   /api/tasks/:id/retry
POST   /api/tasks/:id/rerun

GET    /api/tasks/:id/artifacts
GET    /api/tasks/:id/events
GET    /api/tasks/:id/diff

POST   /api/providers/:id/test
POST   /api/actions/:id/test

GET    /api/events
WS     /api/ws
```

所有写接口使用版本号或 ETag 防止覆盖并发修改。Secret 字段只返回 `configured: true/false`。

## 19. Web 管理界面

### 19.1 视觉方向

界面采用“自动维修控制塔”而不是普通后台模板：

- 大胆但克制的高对比色，用于区分运行、成功、失败和外部副作用。
- 顶部保留一个强识别度的全局模式控制器。
- 任务阶段使用连续轨道和真实耗时，不用虚假的线性百分比。
- 失败卡片优先显示结论、影响和下一步，再展开原始日志。
- 页面有适度动态反馈和个性化图形语言，但不牺牲密度与可读性。
- 支持明亮/暗色主题，记忆用户选择。

不得直接复制其他项目的皮肤。

### 19.2 导航

- 控制台
- 任务
- 项目
- 工单来源
- Agent 与知识源
- 最终动作
- 系统设置

### 19.3 控制台

顶部全局模式控制器：

```text
[ 待我开始 ]  ←→  [ 全自动 ]
```

显示：

- 当前模式说明。
- 待开始任务数量。
- 运行中任务和并发槽。
- 最近 24 小时：交付成功、无修改完成、失败、部分交付。
- 需要处理列表。

切换到全自动时明确显示将排队的现有任务数量，但不把“旧任务”误解为冻结的旧仓库。

### 19.4 任务列表

筛选：

- 待开始
- 排队
- 运行中
- 已完成：已修改
- 已完成：无需修改
- 失败
- 已取消
- 部分交付

卡片显示：

- 工单号和标题。
- 项目与唯一修改源。
- 当前阶段和本阶段耗时。
- 总尝试次数。
- 业务结果或失败摘要。
- Patch 路径和 MR 链接摘要。

### 19.5 任务详情

任务详情按时间顺序展示：

1. 工单快照。
2. 路由与冻结基线。
3. Discovery 结论和门禁。
4. 每次 Repair/Verify/Review 循环。
5. 冻结修改及 Diff。
6. 每个最终动作和每个 GitLab 目标分支。
7. 清理结果与外部副作用。

失败页必须直接回答：

- 在哪个阶段失败。
- 为什么失败。
- 已经做了什么。
- 是否产生 Patch、分支或 MR。
- 是否可重试。
- 建议先修什么。

`no_change` 页面必须展示正向证据，不能只显示“没有发现问题”。

## 20. 安全边界

- Discovery 只读修改源。
- Repair 只写隔离工作区。
- Review 只读候选修改快照或 no-change 报告及其证据。
- Agent 不接触工单、GitLab 或仓库凭据。
- 最终动作由平台适配器使用凭据。
- 外部内容统一按不可信输入处理。
- 命令使用参数数组和允许列表，禁止由工单拼任意 shell。
- Path 必须 resolve 后验证仍在授权根目录。
- 附件有类型、大小和数量限制。
- 日志和 API 不回传 Token、Authorization header 或凭据文件内容。
- Web 第一版按可信内网单管理员设计，但至少支持 IP allowlist、CSRF 防护和危险操作二次确认。
- 删除任务默认只删除数据库索引和可安全删除的本地产物；已创建 MR、远程分支和外部 Patch 不静默删除。

## 21. Windows 开发与 Linux 部署

### 21.1 目标形态

- Windows 用于本地开发和测试。
- Linux 部署机运行正式服务和 Agent CLI。
- React/Vite 构建产物由 FastAPI 同源托管。
- 第一版使用一个 Uvicorn Worker；后台调度依赖 SQLite lease，不依赖多进程内存共享。
- 使用用户级 systemd 服务，`Restart=on-failure`。

### 21.2 运行时

- Python 版本和依赖通过 `pyproject.toml` 与 `uv.lock` 固定。
- Windows 和 Linux 分别创建 `.venv`，禁止复制虚拟环境。
- 前端使用锁文件执行 `npm ci` 和生产构建。
- Claude Code、Codex、OpenCode、Git、SVN 在部署用户下独立预检。
- CLI 登录状态属于部署机运行环境，不写入仓库。

### 21.3 路径

- 代码使用 `pathlib.Path`。
- 数据库不保存无法解释的 Windows/Linux混合路径。
- 项目配置中的机器路径只进入本地覆盖。
- Agent 入口传执行机上真实绝对路径。
- 任务包若迁移到另一台机器，必须重新物化入口路径，不能直接沿用旧绝对路径。

### 21.4 进程与取消

- POSIX 使用独立进程组，取消和超时终止整个子进程树。
- Windows 使用等价的进程组/Job 控制。
- systemd 停止超时必须大于平台优雅清理窗口。
- 服务启动时先完成数据库迁移、目录权限和 Worker lease 恢复。
- 用户级服务需要确认 lingering，保证机器重启后无需交互登录即可启动。

### 21.5 发布链路

正式发布遵循：

```text
Windows 开发与测试
  → Git commit
  → push GitHub
  → Linux git pull --ff-only
  → uv sync --frozen
  → npm ci / npm run build
  → systemctl --user restart
  → health/readiness/功能验证
```

不在部署机直接修改源码，不复制本机 `.venv`，不把运行数据提交到 Git。

## 22. 可观测性与审计

每次任务必须可回答：

- 使用了哪个工单 snapshot。
- 使用了哪个项目配置版本。
- 基于哪个代码 revision/SHA。
- 每阶段由哪个 Runner/模型执行。
- Agent 实际耗时、费用和退出原因。
- 修改了哪些文件。
- 运行了哪些验证命令。
- Review 为什么通过或拒绝。
- 交付了哪些 Patch/MR。
- 哪些外部副作用需要清理。

事件通过 WebSocket 推送；数据库保存结构化事件，详细 stdout/stderr 写文件并按大小轮转。

建议指标：

- 收录到开始的等待时长。
- 各阶段 P50/P95 时长。
- Discovery 成功率。
- `no_change` 比例及复核通过率。
- 首轮修复通过率。
- 平均修复循环数。
- Patch/GitLab MR 成功率。
- 部分交付率。
- 每任务 Agent 费用。

## 23. 第一版非目标

- GitHub PR。
- 自动合并 MR。
- 自动关闭或修改外部 Bug 工单。
- 多用户角色权限系统。
- 一个 Bug 同时修改多个修改源。
- 动态第三方插件市场。
- 分布式多节点 Worker。
- 让 Agent 自己持有平台 Token 或决定最终目标分支。
- SVN 直接 commit。

这些能力以后可通过现有接口扩展，但第一版不为它们预写无实现的 UI 或状态。

## 24. 实现阶段

### 阶段一：骨架与配置

- FastAPI、SQLite migration、React/Vite。
- 默认配置、本地覆盖、Secret 引用。
- 项目、Provider、Agent、最终动作管理和 Preflight。
- Linux systemd 与健康检查。

验收：Windows/Linux 均可启动，配置保存不污染 Git，Secret 不回传。

### 阶段二：收单与任务控制

- Redmine/TAPD Adapter。
- 幂等收录和游标。
- 全自动/待我开始。
- 持久化队列、lease、取消与恢复。
- 控制台和任务时间线。

验收：两种模式、模式切换和并发队列符合本文。

### 阶段三：双 Agent 与无修改分支

- 固定路径 Artifact 协议。
- Discovery、门禁、Repair。
- `no_change` 验证与独立 Review。
- Runner 统一协议。

验收：定位失败明确失败；已修复 Bug 能以证据健康完成；Agent 命令不包含拼接正文。

### 阶段四：修改、验证与 Review

- Git/SVN 隔离工作区。
- 修改范围校验。
- 验证命令。
- 有界 Repair 循环。
- Freeze Change。

验收：同修改源并发任务互不污染，验证失败不会进入交付。

### 阶段五：最终动作

- 原子 Patch。
- GitLab commit 物化。
- Cherry-pick 多目标普通 MR。
- 部分成功、幂等重试与失败清理。

验收：Patch + 多目标 GitLab MR 消费同一冻结修改；任一 MR 失败使任务失败并保留成功结果。

### 阶段六：体验与生产验收

- 完整 Web 视觉与交互。
- 日志、指标、成本和产物清理策略。
- Linux 安装/升级/回滚文档。
- 真实工单灰度。

验收：全自动成功路径无需点击，所有异常都能在界面回答“哪里失败、为什么、产生了什么、怎么处理”。

## 25. 第一版总体验收

必须全部满足：

1. CodeFixer 核心和公共 UI 中没有任何业务项目专属判断。
2. 一个任务始终只有一个修改源。
3. 一个任务可同时配置 Patch 和 GitLab MR。
4. 多个任务可按配置并发运行。
5. Agent 只收到固定入口路径，不收到平台拼接的大上下文。
6. Discovery 找不到或无法消歧时任务失败并给出结构化原因。
7. `no_change` 有当前基线证据并通过独立 Review。
8. Repair 修改越权时任务失败。
9. 验证和 Review 未通过时不能交付。
10. Patch 与所有 MR 消费同一冻结修改。
11. GitLab MR 是普通 MR，并按目标分支创建临时分支和 Cherry-pick commits。
12. 任一 GitLab 目标失败时任务失败，已成功 MR 保留且可只重试失败目标。
13. 服务重启不会重复运行同一阶段或重复创建 MR。
14. Windows 开发和 Linux 正式运行使用同一依赖锁，机器路径与 Secret 不进入公开仓库。
15. Web 能清楚展示阶段、尝试、失败、无修改证据、部分交付和外部副作用。

## 26. 规范标识与关键定义

### 26.1 命名规范

- 领域状态、阶段 ID、失败码和 JSON 枚举统一使用 `snake_case`。
- 配置文件字段统一使用 `camelCase`。
- Artifact 目录名使用阶段 ID 的连字符形式仅限文件系统展示；数据库和 Schema 仍保存规范 `snake_case` ID。
- UI 使用中文标签，但 API 永远返回规范 ID。

规范阶段 ID：

```text
prepare
discovery
assess
no_change_verify
workspace_prepare
repair
verify
review
pre_delivery_check
freeze_change
deliver
finalize
```

### 26.2 TaskRun 创建时点

- 待我开始模式：用户点击开始时创建 TaskRun，并立即冻结 `execution_mode_snapshot`，状态为 `queued`。
- 全自动模式：工单通过唯一项目路由后立即创建 TaskRun，状态为 `queued`。
- TaskRun 被 Worker 领取后才执行 `prepare`；`prepare` 获取当时最新工单和代码基线，因此排队时长不会冻结旧代码。
- 同一个 Task 同时最多存在一个 `queued` 或 `running` TaskRun。

### 26.3 输入指纹

`input_fingerprint` 是以下值按规范 JSON 排序后计算的 SHA-256：

- TicketSnapshot 内容 hash。
- 项目有效配置 hash。
- ModificationSource ID 与基线 revision/SHA。
- 阶段协议版本。
- Agent profile、Runner 和实际模型。
- 前序必需 Artifact 的 hash。

某项变化会使依赖它的安全检查点失效。

### 26.4 安全检查点

安全检查点是：

- StageRun 状态为 `succeeded`。
- 输入指纹仍一致。
- 输出 Artifact 存在且 hash 一致。
- 不包含状态不确定的外部副作用。
- 后续配置没有要求从更早阶段重跑。

### 26.5 Change Version 与 Action Version

- 每次 `freeze_change` 成功生成新的单调递增 `change_version`。
- 同一冻结修改下，动作配置 hash 变化生成新的 `action_version`。
- Delivery 幂等键：

```text
task_run_id / change_version / action_id / action_version / target_key
```

### 26.6 三类基线

- `modification_base`：Repair 实际读取和修改的 Git/SVN revision。
- `materialization_base`：异仓库 `gitlabMr` 把冻结 diff 转换成 Git commits 时使用的暂存仓库基线。
- `delivery_target_head`：每个 GitLab 目标分支在 `pre_delivery_check` 记录的 HEAD。

三者必须分别记录，不能用一个 `base_branch` 字段混用。

## 27. 状态转换与工单生命周期

### 27.1 TaskRun 状态

TaskRun 使用：

- `queued`
- `running`
- `superseded`
- `completed`
- `failed`
- `canceled`

Task 顶层状态表示当前 active run；没有 active run 时表示最后一次业务状态。

### 27.2 主要转换表

| 当前状态 | 事件 | 条件 | 新状态 |
|---|---|---|---|
| 无 | 收录工单 | 待我开始且唯一路由成功 | `awaiting_start` |
| 无 | 收录工单 | 全自动且唯一路由成功 | `queued` |
| 无 | 收录工单 | 无路由/路由并列 | `failed` |
| `awaiting_start` | 用户开始 | 工单仍 eligible | `queued` |
| `queued` | Worker 领取 | lease 成功 | `running` |
| `running` | 全流程成功 | 所有动作成功 | `completed/changed` |
| `running` | 无修改复核成功 | 未产生交付副作用 | `completed/no_change` |
| `running` | 阶段失败 | 重试用尽或不可重试 | `failed` |
| `failed` | 安全重试 | 输入不变且有检查点 | `queued` |
| `failed` | 重新运行 | 任一输入变化 | 新 TaskRun `queued` |
| `awaiting_start/queued` | 用户取消 | 无运行阶段 | `canceled` |
| `running` | 用户取消 | 完成终止与清理 | `canceled` |

### 27.3 工单 eligibility

每个 TicketProvider 把外部状态归一化为：

- `eligible`：仍应由 CodeFixer 处理。
- `ineligible`：已关闭、删除、转为非 Bug 或不再匹配过滤规则。

`prepare` 发现工单已经 ineligible 时：

- 当前 TaskRun 进入 `canceled`。
- `cancel_reason=ticket_ineligible_before_start`。
- 不调用 Agent，不判定 `no_change`。
- 后续重新打开时可以按当前执行模式创建新 TaskRun。

### 27.4 工单运行中更新

- `awaiting_start`：只更新 Task 当前视图；开始时使用最新 snapshot。
- `queued` 且尚未完成 prepare：prepare 使用最新 snapshot。
- `running` 且尚未完成 `pre_delivery_check`：阶段边界发现有效内容更新时，当前 TaskRun 进入 `superseded`。
  - 全自动：立即创建新 TaskRun 并排队。
  - 待我开始：Task 回到 `awaiting_start`。
- `freeze_change` 之后但尚未产生外部副作用：回到 `pre_delivery_check`，使旧 change version 失效。
- 任一最终动作已经产生副作用：当前 TaskRun继续对账和聚合；新工单版本在本次结束后按当前模式创建后续 TaskRun。

“有效内容更新”由 Provider 配置的字段集合决定，纯格式、订阅者或无关时间戳变化不触发 supersede。

### 27.5 已完成任务更新与重新打开

外部工单在 `completed`、`failed` 或 `canceled` 后出现新的有效版本时：

- 保存新 TicketSnapshot 和事件。
- 不改写旧 TaskRun。
- 未 ignored 时按当前模式创建新的 TaskRun 或进入 `awaiting_start`。
- 新运行重新执行 Discovery，不能沿用旧结论直接交付。

### 27.6 忽略与归档

- Ignore 是显式调度策略，保存操作者、原因和时间；阻止自动创建 TaskRun。
- Archive 是展示属性，只把任务移出默认列表。
- Ignore/Archive 不删除 Artifact，也不改变历史 TaskRun 结果。

## 28. V1 Artifact 数据契约

所有 JSON 都必须包含 `schema_version: 1`，并由平台在任务目录写入对应 `*.schema.json`。缺少必填字段、出现未知枚举或引用不存在的 Artifact 时，阶段以 `agent_protocol_invalid` 失败。

### 28.1 EvidenceRef

```json
{
  "id": "ev-001",
  "kind": "source|history|ticket|attachment|verification",
  "location": "可定位的文件、URL 或 Artifact 路径",
  "revision": "可为空的 revision/SHA",
  "locator": "行号、符号、提交或检查步骤",
  "summary": "该证据证明什么",
  "content_sha256": "可为空"
}
```

结论只能引用实际存在的 EvidenceRef ID。

### 28.2 task-discovery.json

```json
{
  "schema_version": 1,
  "decision": "located|no_change_claim|unresolved",
  "source": {
    "id": "project-source",
    "revision": "frozen revision"
  },
  "summary": "调查结论",
  "signals_checked": [
    {
      "signal": "工单中的强线索",
      "status": "covered|not_found|unresolved",
      "evidence_ids": ["ev-001"]
    }
  ],
  "candidate_scope": {
    "paths": ["relative/path"],
    "symbols": ["SymbolName"],
    "reason": "为什么是该范围"
  },
  "evidence": [],
  "unresolved_questions": [],
  "failure": null
}
```

约束：

- `located` 必须有非空 `candidate_scope` 和源码证据。
- `no_change_claim` 必须有当前状态证据，不能只有搜索无结果。
- `unresolved` 必须填写结构化 failure。
- `source.id` 必须等于 TaskRun 冻结的唯一修改源。

### 28.3 gate.json

```json
{
  "schema_version": 1,
  "decision": "pass|supplement|fail",
  "missing_signals": [],
  "supplement_attempted": false,
  "failure": null
}
```

平台生成，不接受 Agent 自报。

### 28.4 no-change-report.json

```json
{
  "schema_version": 1,
  "reason": "already_fixed|not_present_on_current_baseline|not_applicable_to_source|upstream_fixed_during_run",
  "source": {
    "id": "project-source",
    "revision": "revision"
  },
  "claim": "为什么当前基线无需修改",
  "evidence": [],
  "checks": [
    {
      "id": "check-id",
      "status": "passed|not_available",
      "details_path": "relative artifact path"
    }
  ],
  "related_fix": {
    "commit": null,
    "mr_url": null,
    "version": null
  },
  "limitations": [],
  "conclusion": "no_change"
}
```

门禁要求：

- 至少两项独立 EvidenceRef。
- 至少一项直接描述当前基线。
- `limitations` 不能包含会推翻结论的未知项。
- `review(mode=no_change)` 必须 approved。

### 28.5 repair-result.json

```json
{
  "schema_version": 1,
  "outcome": "changed|no_valid_diff|blocked",
  "summary": "本次修改说明",
  "changed_paths_claimed": ["relative/path"],
  "checks_requested": ["verification-step-id"],
  "limitations": []
}
```

平台自行采集真实 diff；`changed_paths_claimed` 只用于交叉检查。

### 28.6 verification.json

```json
{
  "schema_version": 1,
  "candidate_sha256": "sha256",
  "status": "passed|failed",
  "steps": [
    {
      "id": "unit",
      "required": true,
      "status": "passed|failed|skipped",
      "exit_code": 0,
      "duration_ms": 100,
      "stdout_path": "relative path",
      "stderr_path": "relative path"
    }
  ]
}
```

必需步骤任一未通过，整体不得是 passed。

### 28.7 review.json

```json
{
  "schema_version": 1,
  "mode": "change|no_change",
  "input_sha256": "candidate 或 no-change report hash",
  "verdict": "approved|needs_repair|rejected",
  "summary": "审查结论",
  "issues": [
    {
      "severity": "blocking|warning",
      "summary": "问题",
      "evidence_ids": ["ev-001"]
    }
  ]
}
```

`mode=no_change` 不允许 `needs_repair`；证据不足直接 rejected。

### 28.8 change-manifest.json

```json
{
  "schema_version": 1,
  "change_version": 1,
  "modification_source": {
    "id": "project-source",
    "base_revision": "revision"
  },
  "diff": {
    "path": "change.patch",
    "sha256": "sha256"
  },
  "files": [
    {
      "path": "relative/path",
      "operation": "add|modify|delete|rename",
      "content_sha256": "可为空"
    }
  ],
  "source_commits": [],
  "verification_sha256": "sha256",
  "review_sha256": "sha256",
  "config_sha256": "sha256"
}
```

`source_commits` 可为空。GitLab MR 的 delivery commits 属于动作结果，不改变本对象。

### 28.9 delivery result

`DeliveryActionRun`：

```json
{
  "schema_version": 1,
  "action_id": "main-gitlab-mr",
  "action_version": 1,
  "change_version": 1,
  "type": "patch|gitlabMr",
  "status": "pending|running|reconciling|succeeded|failed|skipped",
  "outcome": "success|partial_success|failure|no_change",
  "materialization": {
    "repository_id": null,
    "base_revision": null,
    "staging_ref": null,
    "status": "not_required|planned|pushing|reconciling|confirmed|failed",
    "commits": [],
    "diff_sha256": null,
    "cleanup_required": false
  },
  "targets": [],
  "failure": null
}
```

`DeliveryTargetRun`：

```json
{
  "target_key": "target-branch",
  "idempotency_key": "stable key",
  "status": "pending|running|reconciling|succeeded|failed",
  "step": "preflight|materializing_commits|creating_source_branch|cherry_picking|creating_mr|cleaning_up|done",
  "checkpoint": "planned|branch_intent|branch_confirmed|cherry_pick_intent|cherry_pick_confirmed|mr_intent|mr_confirmed",
  "source_branch": null,
  "target_branch": "target-branch",
  "mr_iid": null,
  "mr_url": null,
  "failure": null
}
```

### 28.10 final-result.json

```json
{
  "schema_version": 1,
  "task_id": "task-id",
  "task_run_id": "run-id",
  "status": "completed|failed|canceled|superseded",
  "result": "changed|no_change 或 null",
  "change_version": "整数或 null",
  "summary": "用户可读总结",
  "failure": null,
  "artifacts": [],
  "side_effects": []
}
```

`change_version` 在 no-change、freeze_change 前失败、取消或 superseded 的运行中为 null；只有 `completed` 才允许 `result` 非 null。

## 29. 交付事务与崩溃恢复

### 29.1 无副作用屏障

在启动任何最终动作前，平台一次性完成：

- 工单版本检查。
- ModificationSource 基线检查。
- 所有 Patch 输出目录检查。
- 所有 GitLab connection、project、assignee、目标分支和 commit 物化能力检查。
- 全部 `delivery_target_head` 记录。

任一项失败时没有动作可以开始。此时仍允许回到 Repair/Verify/Review 或转为有证据的 `no_change`。

### 29.2 动作聚合

- 全部动作 succeeded：`completed/changed`。
- 任一动作 failed 且没有动作 succeeded：`failed`，delivery outcome 为 failure。
- 任一动作 failed 且至少一个动作 succeeded：`failed`，delivery outcome 为 partial_success。
- 任一动作 reconciling：TaskRun 保持 running/reconciling，不得先判成功或失败。
- 所有动作因 `no_change` skipped：`completed/no_change`。

动作开始后，兄弟动作不会因某个动作失败而被强杀；平台等待已调度动作得到确定结果。

### 29.3 外部调用检查点

每个外部副作用使用 outbox 风格：

1. 在数据库事务中写入 intent、幂等键、请求摘要和预期对象。
2. 提交事务。
3. 发起外部调用。
4. 在新事务中保存确认结果。

进程在第 3、4 步之间崩溃时，状态进入 `reconciling`，不能重新发起创建请求。

### 29.4 GitLab 对账

恢复或网络结果不确定时：

1. 先对账 commit 物化暂存 ref。
2. 再按已知 MR IID 查询。
3. 再按 delivery key、源分支和目标分支查询所有状态的 MR，必须遍历完整分页。
4. 再查询计划中的目标临时分支，并核对其 HEAD 是否与本地 intent 记录一致。
5. 找到唯一匹配对象时接管并继续。
6. 找到多个匹配对象时以 `gitlab_result_ambiguous` 失败，禁止再创建。
7. GitLab 查询不可用时保持 reconciling；超过对账预算后以 `gitlab_result_uncertain` 失败，仍禁止重复创建。
8. 只有完整查询明确证明不存在对应外部对象时，才允许新建。

临时分支名虽然复刻 `cherry-pick-<sha>` 规则，但所有权由数据库 intent、project、目标分支、创建时间和分支 HEAD 联合证明。不能仅凭名称删除分支。

Commit 物化使用平台专属暂存 ref：

```text
codefixer/materialize/<task-run-id>/<change-version>/<action-id>/<action-version>
```

推送前先持久化预期 ref、materialization base、冻结 diff hash 和预期 commit 元数据。若 push 成功但确认结果未落库：

- 查询该 ref。
- 逐个读取 commits 并核对顺序、父关系和最终 tree/diff 是否对应冻结 diff hash。
- 完全一致时接管并标记 materialization confirmed。
- ref 存在但内容不同，以 `gitlab_materialization_mismatch` 失败，不覆盖远端 ref。
- 查询结果不确定时保持 reconciling，禁止再次 push。
- 只有数据库 intent 能证明该 ref 属于当前动作时才允许清理。

所有目标 MR 完成后，暂存 ref 按项目保留策略清理；清理失败只设置 `cleanup_required`，不得改写已经确认的 MR 结果。

### 29.5 Patch 对账

- 写入前记录 intent、目标路径和预期 hash。
- 临时文件 fsync 后原子改名。
- 恢复时目标存在且 hash 相同则接管为成功。
- 目标存在但 hash 不同且不允许覆盖时失败。

### 29.6 交付后的配置变化

配置热重载不改变当前 ActionRun。修改目标分支、assignee、模板或路径映射后：

- 旧成功动作保持历史成功。
- 用户若要使用新配置再次交付，创建新 action version。
- 平台明确展示这会产生新的外部对象，不把它伪装成普通重试。

## 30. 分阶段文件与权限矩阵

| 阶段 | Agent profile | 必须自行读取 | 可访问代码 | 写入范围 |
|---|---|---|---|---|
| `discovery` | discovery profile | ticket、project policy、source manifest、附件清单 | 唯一修改源只读视图、受控知识工具 | discovery 输出目录 |
| `no_change_verify` | repair profile 的只读模式 | ticket、Discovery、source manifest | 唯一修改源只读视图、验证工具 | no-change 输出目录 |
| `repair` | repair profile | ticket、Discovery、project policy、workspace manifest、上轮反馈 | 唯一隔离工作区 | 隔离工作区与 repair 输出目录 |
| `review(mode=change)` | review profile | ticket、Discovery、候选 diff、verification | 候选工作区只读视图 | review 输出目录 |
| `review(mode=no_change)` | review profile | ticket、Discovery、no-change report、证据索引 | 唯一修改源只读视图 | review 输出目录 |

附件正文不拼入 Prompt。平台先把允许的附件冻结到 snapshot 目录，入口文件列出路径、类型、大小和 hash，由 Agent 按需读取。

知识服务响应不预取后拼接。Agent 通过受控 KnowledgeProvider 工具查询，平台保存查询参数、响应 Artifact 和 hash。

`entry.md` 本身由平台模板生成并版本化；StageRun 保存模板版本。Agent 不能修改入口文件和前序 Artifact。
