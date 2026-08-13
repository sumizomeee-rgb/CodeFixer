# CodeFixer 产品与技术设计 SPEC

> 文档状态：V2 对齐稿
> 最后更新：2026-08-13
> 适用范围：CodeFixer 第一版实现与后续扩展
> 本文是产品语义、任务协议和技术边界的唯一设计基准。

## 1. 产品定义

### 1.1 一句话定位

CodeFixer 是一个通用的 Bug 自动修复与交付平台：它持续接收外部缺陷工单，先利用独立的定位源反查真实实现，再在唯一的本机修改工作区完成修复、验证与独立审查，最后按仓库能力生成 Patch、推送可供人工 Cherry-pick 的 GitLab Commit 和/或 GitHub PR。

CodeFixer 不是某个业务项目的专用脚本，也不是一个把工单和源码拼成大 Prompt 的包装器。平台负责冻结输入、隔离工作区、控制权限、编排阶段、验证产物、记录证据和执行交付；Agent 负责阅读任务档案、自主调查和修改代码。

### 1.2 要解决的核心痛点

1. 仅把 Bug 单号或标题交给 LLM，模型往往无法可靠推断真正的仓库、模块、调用链和版本边界。
2. 传统关键词匹配、文件名 Glob 和 LLM 自评分无法形成可信的定位结论。
3. Agent 修改、测试、Review、生成 Patch、Cherry-pick 和创建 MR/PR 分散在多个手工步骤中，容易遗漏或留下脏工作区。
4. 多个 Bug 同时处理时，共享工作副本、内存队列和模糊状态会造成互相污染、重复执行或不可恢复。
5. 不同项目的工单平台、代码来源、验证命令和交付方式不同，核心流程不能绑定某个业务项目、TAPD、Redmine、SVN 或 GitLab 的固定字段。
6. 自动化不能把“没有查到”误报成“Bug 不存在”，也不能在部分交付失败时伪装成成功。

### 1.3 成功标准

第一版完成后，用户应能：

- 在新增流水线时配置或复用一个或多个工单接入。
- 配置多条流水线；每条流水线分别定义一个工单入口、一个定位源、一个本机修改工作区、验证策略和一个或多个最终动作。
- 选择“全自动”或“待我开始”。
- 在系统设置中只选择一个当前模型，由所有 LLM 阶段统一使用。
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
| 默认服务端口 | `9522`，Web 与 API 同源 |
| 执行模式 | 全自动 / 待我开始 |
| 当前模型 | 全局只选择一个 `execution.currentModelId`；流水线和阶段都不单独选择模型 |
| 模型生效范围 | `scope_discovery`、`discovery`、`no_change_verify`、`repair`、`review` 等所有 LLM 调用统一使用当前模型；各阶段仍保持独立会话 |
| 模型切换 | Worker 领取 TaskRun 并进入 `prepare` 时解析并冻结模型；排队前和 `awaiting_start` 阶段不冻结 |
| 手动启动语义 | 点击一次开始后，任务自动执行完整流程，不逐阶段等待审批 |
| 流水线输入 | Bug 反馈源、定位源、本机修改工作区是三个独立概念，必须在同一条流水线内分别配置 |
| 流水线与任务 | 全部流水线共用一个全局任务账本；流水线是任务的绑定与筛选维度，不创建第二套任务列表 |
| Bug 与修改工作区 | 一个 Bug 任务必须且只能绑定一个本机修改工作区；Agent 不得静默切换 |
| 仓库类型 | 用户只选本机目录；平台自动识别 SVN、GitLab Git、GitHub Git 或其他 Git，不要求手选类型 |
| 最终动作 | 一个任务可以配置一个或多个最终动作 |
| 最终动作能力 | `patch` 对全部修改工作区可用；`gitlabPush` 仅 GitLab Git 可用；`githubPr` 仅 GitHub Git 可用 |
| GitLab 交付 | 平台只推送受控任务分支并返回 Commit URL；用户在 GitLab Web 手动 Cherry-pick，不自动创建 MR |
| GitHub PR | 普通 PR，只在 GitHub 修改工作区上开放；它仍有自己的目标分支和 PR 状态契约 |
| 交付日志 | TAPD Bug 使用 `fix/#B`，TAPD 其他单使用 `feat/#S`，Redmine 全部使用 `fix/#`；LLM 只生成模块名和修改摘要 |
| 任务结论 | 每个终态任务都有简洁结论；已修改任务另外提供二级交付结果弹窗和仓库相对修改路径清单 |
| 反查失败 | 任务失败并给出原因，不进入人工文件勾选等待态 |
| Bug 已不存在 | 只有证据充分时才健康完成为 `no_change` |
| LLM 并发 | 全局 LLM 调用池默认 4；所有 Runtime 和所有任务共享，非 LLM 阶段不占槽 |
| 基线批次 | 短时间内进入同一修改工作区的任务共享第一个任务冻结的 Git SHA / SVN revision，再在独立工作区并发 |
| 其他并发 | 单任务阶段有序执行；不同任务可并发；冻结修改后的独立最终动作可有界并发 |

## 3. 设计原则

### 3.1 文档交接，不灌上下文

平台为每个阶段生成固定路径的入口文档。启动 Agent 时只传入口文件的绝对路径和一条最小启动指令，禁止把工单正文、调查正文、源码正文和知识库响应重新拼接进命令行 Prompt。

### 3.2 Agent 自主调查，平台做确定性门禁

Discovery Agent 自己读取工单档案和流水线配置的只读定位源，自主搜索与反查。平台不替 Agent 决定文件清单，但会检查工单中的显式路径、堆栈符号、错误码、模块名、版本、附件和关联提交是否得到处理。定位结论必须显式映射到流水线唯一的本机修改工作区，不能把定位源偷换成修改目录。

### 3.3 调查结论不是修改授权

Discovery 产物只是第二阶段的定位线索。Repair Agent 必须在本次隔离工作区重新读取和核实当前基线，不能仅凭 Discovery 文档修改文件。

### 3.4 状态与结果分离

`completed` 是任务生命周期状态，`changed` 和 `no_change` 是业务结果。反查失败、证据不足和无法复现不能使用 `no_change`。

### 3.5 所有最终动作消费同一份冻结修改

Patch、GitLab Push 和 GitHub PR 必须从同一份经过验证和 Review 的不可变修改快照生成，禁止各自重新读取一个可能已经变化的工作区。

### 3.6 外部副作用由平台执行

Agent 不获得工单平台或代码托管凭据，不自行创建远程分支、MR 或 PR。平台只相信自身采集的 Git diff、SVN diff、命令退出码、文件校验和及托管平台返回结果。

### 3.7 抽象到接口，不提前建设插件市场

第一版使用稳定接口和仓库内适配器注册表。新增平台时实现新适配器，不在核心状态机中增加 `if tapd`、`if svn` 一类业务分支；第一版不建设动态插件安装市场。

### 3.8 吸收经验，不依赖参考工程

本文已经把调研阶段验证过的设计经验收敛为 CodeFixer 自身规范，包括双阶段 Agent、固定入口文档、依赖预检、配置分层、Linux 服务化部署和 GitLab Cherry-pick MR 协议。参考工程与一次性脚本只属于设计输入，不是构建或运行依赖。

CodeFixer 的仓库、安装包和部署文档必须自包含：

- 不得要求读取仓库之外的本地项目、提示词文档或脚本才能理解或运行系统。
- 不得 import、调用或复制执行某台机器上的参考脚本；相关行为必须由仓库内代码和本 SPEC 定义。
- 公开默认配置不得出现开发者盘符、用户名、内网地址或机器绝对路径。
- 运行所需第三方程序、服务和包必须通过依赖清单、适配器契约与 Preflight 明示。
- 当前机器的路径和凭据只允许出现在不入 Git 的本地覆盖与 Secret 存储中。
- 本地覆盖统一放在仓库根目录 `.local/`：非秘密配置为 `.local/config.json`，工单来源 Secret 为 `.local/secrets.json`；整个目录必须被 Git 忽略。

### 3.9 单一当前模型，独立会话

模型选择属于全局运行设置，不属于 Pipeline，也不属于某个阶段。用户只选择一个“当前模型”；平台把该选择解析为具体 Agent Runtime、模型 ID 和可执行命令。

同一个 TaskRun 中所有需要 LLM 的阶段使用同一个已解析模型，但每个阶段仍分别启动独立会话、分别记录 usage、费用、耗时和失败原因。独立会话用于职责隔离与审计，不意味着用户需要为不同阶段配置不同模型。

Pipeline、Task、Stage 的 UI 和公共配置不得重新引入“为 Scope / Discovery / Repair / Review 分别选模型”的交互。

## 4. 核心领域模型

### 4.1 TicketProvider

工单来源实例，负责：

- 增量拉取 Bug。
- 按外部 ID 获取最新详情。
- 冻结标题、描述、评论、附件元数据、关联单、版本和原始字段。
- 提供外部更新时间或版本号作为幂等依据。
- 把平台无关的原始数据转换为统一 `TicketSnapshot`。

第一版内置 Redmine 和 TAPD 适配器，但核心流程只依赖 `TicketProvider` 契约。

工单平台的地址、工作区和认证必须在“添加/编辑 Bug 反馈源”交互内一次完成：Redmine 直接填写服务地址与 API Token；TAPD 直接填写工作区与账号密码或 Token。Secret 只写入当前机器 `.local/secrets.json`，界面不暴露 `SecretRef`、凭据名称或独立凭据管理卡片，也不回显真实值。

### 4.2 Pipeline

流水线是 CodeFixer 的一等可执行策略集合。它把原本分散的来源与动作组装成一条可理解、可体检、可运行的修复线路：

```text
TicketProvider + 路由范围
  → LocalizationSource
  → ModificationWorkspace
  → Verification
  → FinalAction[]
```

每条流水线包含：

- 名称、稳定 ID、启用状态和配置版本。
- 唯一工单入口：一个 `providerRef` 与带优先级的工单匹配规则。
- 唯一 `LocalizationSource`。
- 唯一 `ModificationWorkspace`。
- 允许修改的路径与文件类型。
- 验证命令和超时。
- 修复循环上限。
- 一个或多个 `FinalAction`。
- 可选并发与共享资源限制。

`TicketProvider` 是当前部署机上的可复用接入连接，不被某条流水线私有。多条流水线可以引用同一个 TAPD/Redmine 连接并用不同匹配范围分流；每张工单最终必须且只能绑定一条已启用流水线。流水线也可以引用相同的定位源或物理修改工作区，但同一物理工作区仍按规范化仓库身份共享 `BaselineCohort`、短时刷新锁和必要的独占 lease。

Pipeline **不配置 Agent profile 或阶段模型**。范围调查、正式定位、Repair、No-change Verify 和 Review 等 LLM 阶段统一使用系统全局当前模型；它们之间的职责隔离通过独立会话、权限和入口协议实现，而不是通过流水线级模型选择实现。

流水线配置不包含任何 CodeFixer 核心代码无法理解的隐式约定。业务特定规则应写入流水线策略文档或适配器配置。

路由规则必须产生唯一结果：

- 没有流水线匹配时，任务以 `pipeline_not_found` 失败。
- 多条流水线匹配时，选择数值最高的优先级。
- 多条最高优先级规则并列时，任务以 `pipeline_ambiguous` 失败。
- 明显冲突（例如同一反馈源存在多条同优先级 catch-all）必须在流水线保存或体检时阻止；只有依赖实际工单字段才能发现的歧义才允许在收录时失败。
- 用户修正流水线绑定后必须创建新 TaskRun，Agent 无权改变绑定。
- 停用流水线只阻止新工单进入；已经排队或运行的 TaskRun 继续使用自己的冻结快照完成或明确失败。

### 4.3 LocalizationSource

定位源是双 Agent 反查阶段的只读调查范围，负责回答“Bug 真正落在哪个模块、路径和实现”。它与最终允许写入的物理目录是两个独立配置：

- 定位源可以是代码搜索目录、只读仓库、索引或知识服务。
- `scope_discovery` 与 `discovery` 只在定位源授权范围内自主调查并输出证据。
- 定位结果必须给出到 `ModificationWorkspace` 的确定性映射；无法映射、映射到多个工作区或证据指向另一条流水线时，以 `source_mismatch` 或 `discovery_failed` 结束。
- 即使定位源与修改工作区碰巧指向同一目录，配置、权限和阶段职责仍分别表达，平台不得把两个字段合并成一个“代码位置”。

### 4.4 ModificationWorkspace

一个任务必须绑定且只能绑定一个本机修改工作区。普通用户只选择或填写物理目录，平台执行确定性识别：

1. 用 `git rev-parse --show-toplevel` 判断是否为 Git 工作区，并读取 `origin`。
2. 对 Git remote 执行无副作用托管能力探测：标准 SaaS host 可直接识别；自建服务先按 remote host 探测 GitLab health/capability，再用当前机器已认证的 `gh repo view` 探测 GitHub Enterprise。只有单一探测成功才标记 `gitlab` 或 `github`，不能仅凭仓库名猜测。
3. 非 Git 时用 `svn info` 判断是否为 SVN working copy，标记 `svn`。
4. 都无法识别时保存失败，展示实际探测命令、退出摘要和修复建议。

识别结果包含 `vcsKind=git|svn`、`hostingKind=gitlab|github|other|none`、仓库根路径、remote 元数据和经探测确认的 `webBaseUrl`。`webBaseUrl` 必须保留自建服务真实的 HTTP/HTTPS scheme，不能因为 `origin` 是 SSH 就默认拼成 HTTPS；它用于生成 Commit、分支和 PR 的 Web 链接。识别结果是平台探测事实，不是用户手填的“代码类型”。内部 CLI binding 可由部署配置覆盖，但日常流水线 UI 不展示 `pathBindings`、`repositoryRef` 或 `executableRef`。

托管识别结果按规范化 remote URL 缓存在本机配置中，remote 改变即失效并重新探测。自建服务无法确定、两个探测都成功或网络受限时标记 `gitOther` / `ambiguous`，只开放 Patch，并在工作区卡片显示实际探测证据与重试按钮；不要求用户另填 GitLab/GitHub connection。

修改工作区还定义基线获取、隔离策略、允许读写根目录、路径白名单/黑名单和扩展名约束。任务开始后 Agent 不能静默切换工作区；“唯一修改工作区”不等于“只能修改一个文件”，Repair Agent 可以修改其中任意数量的授权文件。

### 4.5 FinalAction

最终动作消费冻结修改快照：

- `patch`：全部已识别修改工作区均可用，用户直接选择本机输出目录。
- `gitlabPush`：仅 `hostingKind=gitlab` 可选，复用修改工作区与 `origin`，推送平台生成的受控任务分支并返回 Commit URL，不配置目标分支。
- `githubPr`：仅 `hostingKind=github` 可选，复用修改工作区与 `origin`，用户选择一个或多个目标分支。

SVN 与 `gitOther` 不允许通过额外选择一个 Git 仓库绕过能力约束；修改工作区和交付仓库始终是同一个物理来源。动作不可用时 UI 应说明识别结果和原因，而不是继续展示必然失败的表单。

配置中的所有已启用最终动作都是必需动作。任意动作失败，任务失败；已经成功的外部交付不会被隐藏或回滚。

“必需动作”只指 Pipeline `finalActions` 中由用户配置的动作。平台自动创建的 `__fallback_patch__` 是恢复动作，不进入必需动作成功计数，也不参与“任一必需动作失败”的递归判断。

`partial_success` 是交付 outcome，不是健康任务状态：至少一个必需动作成功且至少一个失败时，Task 仍为 `failed`，但列表可用“部分交付”快捷筛选这一类失败，并保留全部成功链接和仅重试失败目标的入口。

GitLab Push 或 GitHub PR 进入终态 `failed` 后，平台必须从同一份 `freeze_change` 生成保底 Patch。保底 Patch 是恢复产物，不满足原远端动作，也不把 Task 改成成功：

- 远端动作失败且没有其他必需动作成功：Task 为 `failed`，delivery outcome 为 `fallback_available`。
- 至少一个必需动作成功、至少一个失败：Task 为 `failed`，delivery outcome 仍为 `partial_success`，并额外记录 `fallbackAvailable=true`。
- 远端结果尚在 `reconciling` 时不得提前判失败；超过对账预算进入终态失败后再生成保底 Patch。
- 用户已经取消 TaskRun 时不启动新的保底动作；已存在的 Patch 仍保留。

`gitlabPush` 只有一个由平台生成的远端任务分支，不存在目标分支或部分成功。`githubPr` 的多目标仍先在动作内部聚合：全部目标成功时动作 `succeeded/success`；至少一个目标失败时动作 `failed`，若同时有成功目标则 outcome 为 `partial_success`，否则为 `failure`。Task 聚合只把该远端动作计为一个失败的必需动作，并保留全部目标明细。

流水线必须至少配置一个最终动作；动作 ID 在流水线内唯一。每次 TaskRun 冻结动作配置 hash，生成单调递增的动作版本。

### 4.6 AgentRuntime 与当前模型

Agent Runtime 只负责：

- 把公共阶段请求转换为对应 CLI 参数。
- 配置该阶段的工作目录和工具权限。
- 启动、超时、取消并清理子进程。
- 解析统一的运行结果、费用和 usage。

`agentProfiles` 是平台内部的“可用模型 → Runtime 配置”注册表，用于把 `execution.currentModelId` 解析为 `runtime`、`model`、`executableRef`、超时和必要运行参数。它不是 Pipeline 的阶段配置，也不要求普通用户维护一组 Profile。

每个内部模型配置必须声明 `executableRef`，引用当前机器 `executableBindings` 中的 CLI 命令与版本检查规则；不得在共享配置中保存某台机器的 CLI 绝对路径。

Claude Code、Codex、OpenCode 分别实现 Runtime 适配器。Runtime 是执行通道，不是用户选择层级；Web 中“当前模型”只展示模型语义，不把 `Codex`、`Claude Code`、`OpenCode` 与具体模型混成同一级选项。适配器不得预读业务文件、替 Agent 选择仓库或改写阶段工作流。

### 4.7 Task、TaskRun 与 StageRun

- `Task`：一个外部 Bug 在 CodeFixer 中的长期记录。
- `TaskRun`：一次基于冻结工单、策略、代码基线和当前模型的完整执行。
- `StageRun`：某个阶段的一次尝试。
- `DeliveryActionRun`：最终动作的一次执行。
- `DeliveryTargetRun`：`githubPr` 中某个目标分支的子执行；`gitlabPush` 没有目标分支子执行。

重试会创建新 attempt 或新 TaskRun，旧产物和证据永久保留。

## 5. 全局执行设置

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

这里的“刷新仓库”按第 10.2 节加入或创建 `BaselineCohort`，同源同时开始的任务不会各自重复刷新。

### 5.2 全自动

新收录且匹配唯一流水线规则的 Bug 自动进入 `queued`，随后执行完整流水线。成功路径不需要用户点击。

全自动不会绕过：

- 流水线路由、定位源与修改工作区绑定。
- Discovery 证据门禁。
- 修改范围校验。
- 流水线验证命令。
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
- 用户仍可单独请求取消；取消是停止后续动作并尽力清理，不承诺回滚已经产生的 Patch、远程分支、MR 或 PR。

每个 TaskRun 保存 `execution_mode_snapshot`，运行中不受全局开关后续变化影响。

### 5.4 当前模型

全局执行设置必须且只能有一个 `execution.currentModelId`。

用户语义只有一个动作：**选择当前模型**。系统设置直接显示当前值并允许单选切换，不提供“添加模型”“启用 Agent”“为不同阶段选择模型”等二级管理交互。

当 Worker 开始执行一个 TaskRun 时，平台解析当时的 `currentModelId`，得到具体 Runtime、模型 ID 与 CLI binding。本 TaskRun 后续所有 LLM 调用都使用这一解析结果：

- `scope_discovery`
- `discovery`
- `no_change_verify`
- `repair`
- `review(mode=change)`
- `review(mode=no_change)`

各阶段必须是独立会话，因此 session、usage、费用、耗时和失败仍按 StageRun 分别记录。运行过程中用户切换全局当前模型，不改变已经开始执行的 TaskRun；新模型从之后开始执行的 TaskRun 生效。

尚未进入执行的任务不需要提前冻结模型，避免长时间排队后仍使用过期的用户选择。

## 6. 任务流水线

### 6.1 主流程

```text
ingest
  → prepare
  → scope_discovery
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
| `prepare` | 平台 | 最新工单、流水线配置、定位源、cohort 基线、当前模型 | 冻结快照、入口文档、输入指纹 | 任务产物目录 |
| `scope_discovery` | 范围调查 Agent（独立会话） | 范围调查入口路径 | `scope-discovery.md/json` | 范围调查输出目录 |
| `discovery` | 正式定位 Agent（独立会话） | Discovery 入口路径；其中只引用范围调查产物路径 | `task-discovery.md/json` | Discovery 输出目录 |
| `assess` | 平台 | Discovery 产物与确定性门禁 | `change_required / no_change_claim / unresolved` | 数据库 |
| `no_change_verify` | 独立 Agent 会话 | 固定入口路径 | `no-change-report.md/json` | 阶段输出目录 |
| `workspace_prepare` | 平台 | 修改工作区与 cohort 冻结基线 | 隔离工作区 manifest | 工作区 |
| `repair` | Repair Agent（独立会话） | Repair 入口路径 | 代码修改、`repair-result.json` | 唯一隔离工作区 |
| `verify` | 平台命令执行器 | 候选修改快照、验证配置 | `verification.md/json` | 验证临时目录 |
| `review` | Review Agent（独立会话） | 候选修改或 no-change 报告 | `review.md/json` | Review 输出目录 |
| `pre_delivery_check` | 平台 | 最新工单、修改工作区基线、动作目标 | 稳定性检查或新一轮尝试 | 数据库与阶段目录 |
| `freeze_change` | 平台 | 已验证工作区 | 不可变 diff、commit、checksum | 冻结目录 |
| `deliver` | 平台动作执行器 | 冻结修改与动作配置快照 | Patch、GitLab Push、GitHub PR 结果 | 配置的外部目标 |
| `finalize` | 平台 | 全部阶段和动作结果 | 任务终态、索引、清理结果 | 数据库与产物目录 |

所有标注为 Agent 的阶段都使用同一个 TaskRun 当前模型快照；“范围调查 / 正式定位 / Repair / Review”描述的是阶段职责，不是不同模型配置。

### 6.3 双 Agent 反查：范围调查与正式定位

工单反查固定拆成两个独立 Agent 会话，不是把 Discovery 与 Repair 合称“双 Agent”，也不是高级开关：

1. `scope_discovery` 负责快速识别大致模块、候选路径与检索入口，只产出定位线索。
2. `discovery` 负责正式定位。它完整读取固定路径的范围调查文档，再从当前冻结基线重新读取源码、核实线索并形成证据链。

两个会话必须分别启动、分别记录 session、模型用量、费用和失败原因，但**统一使用 TaskRun 已解析的当前模型**。第一阶段产物是不可信的调查笔记，不是代码事实、正式证据或对第二阶段的指令；第二阶段不能仅凭笔记下结论。

Pipeline 中不再存在 `agents.scopeDiscovery`、`agents.discovery`、`agents.repair`、`agents.review` 之类的阶段模型角色键。平台不得因阶段不同而静默换模型；如果未来需要实验性多模型策略，必须作为新的明确产品能力重新设计，不能借旧 Profile 字段回流。

平台不得把第一阶段正文拼进第二阶段 Prompt。第二阶段入口文档只写范围调查产物的绝对路径及其信任边界，Runtime 仍只收到入口文档绝对路径和最小启动指令。范围调查失败时任务以 `scope_discovery_failed` 结束；正式定位无法反查时以 `discovery_unresolved` 结束，界面展示阶段、原因、已核实线索和建议动作。

正式 Discovery 职责：

- 完整读取冻结工单、评论、附件清单和流水线策略。
- 在只读定位源内搜索与工单相关的模块、符号、配置、资源、协议和历史变更，并给出到唯一修改工作区的映射。
- 结合堆栈、错误码、页面名、版本、关联提交等线索形成证据链。
- 指出可能的复现链、根因方向、受影响边界和待核实内容。
- 输出一个明确结论：
  - 找到足够可信的修改范围。
  - 当前基线可能已经无需修改。
  - 无法可靠定位。

两个 Discovery 阶段均不得：

- 修改代码。
- 创建分支、提交、Patch、MR 或 PR。
- 把“搜索不到”声明为 Bug 不存在。
- 静默跳到另一个定位源或修改工作区。

### 6.4 Discovery 确定性门禁

平台从工单快照提取可机械核对的强线索：

- 显式文件路径、仓库或模块名。
- 堆栈中的类、函数和行号。
- 错误码、协议名、配置键。
- UI、Prefab、场景、资源名。
- 版本号、关联提交、MR、变更记录。
- 附件中明确引用的对象。

正式 Discovery 未覆盖强线索时允许正式定位 Agent 补查一次。补查仍通过新的固定入口文件发起，不把遗漏线索或旧报告正文拼入命令行 Prompt。补查后仍无法定位则失败，不无限循环，也不按读取文件数生成伪置信度。

### 6.5 定位结论到修改能力的门禁

`assess` 不只判断“是否找到文件”，还必须判断定位结论能否由唯一 `ModificationWorkspace` 完成。配置、Prefab、场景、资源清单、脚本和普通文本资产都属于可修改文件；平台不得仅因为它们“不是代码”而失败。只要目标位于修改工作区、格式可安全处理、流水线策略允许且验证方式成立，就继续进入 Repair。

最终判定责任属于平台 `assess` 门禁，不接受 Agent 自报“应该能改”作为授权。门禁按下列确定性能力判断：

- UTF-8/项目声明编码的文本文件可由通用文本修改能力处理，但仍受路径、扩展名、大小和生成文件策略限制。
- JSON、YAML、XML 等结构化文本必须能重新解析，并在流水线验证中执行相应语法/Schema 检查。
- Unity 文本序列化的 Prefab/Scene 只有在流水线明确允许相应扩展名、文本格式可解析且存在 YAML/流水线验证时才可修改。
- 二进制 Prefab、专有资源和需要 GUI 编辑器保存的资产，只有注册了支持该格式的确定性 writer、可做非交互 round-trip，并配置了验证命令时才允许修改；只读 parser 不等于 writer。
- “验证方式成立”指流水线在任务开始前已有能够检查该类变更的必需验证步骤或显式的、可审计替代门禁，不允许 Agent 临时声明“肉眼看起来没问题”。

Agent 负责提供文件格式、目标路径和所需工具的证据；平台结合流水线策略和适配器 capability 作最终允许/拒绝决定。

在 Repair 前已经能够确定以下情况时，必须在 `assess` 失败，不能浪费写会话或伪造空 diff：

| 情况 | 失败码 | 用户交互 |
|---|---|---|
| 真正目标位于另一个工作区 | `source_mismatch` | 展示定位证据，提供“编辑流水线并重新运行” |
| 一次修复必须同时修改多个工作区 | `multiple_workspaces_required` | 列出所需工作区；第一版不做部分修改 |
| 文件在工作区内但被根目录/扩展名策略禁止 | `workspace_policy_blocked` | 精确显示被阻止的路径和策略项 |
| 二进制、专有格式或必须通过编辑器交互修改，当前适配器无法安全写入 | `unsupported_artifact_change` | 显示格式、所需工具和人工处理建议 |
| 真正动作发生在管理后台、数据库、密钥、运行环境或其他外部系统 | `external_change_required` | 标为“需要外部处理”，保留证据和复核步骤 |
| 应修改生成源，但生成源不在当前工作区 | `generated_source_outside_workspace` | 同时展示生成文件与真实生成源 |

如果上述事实只能在 Repair 深入读取后发现，Repair 必须输出 `outcome=blocked`、稳定 `blocking_code` 和 EvidenceRef；平台重新执行同一套 capability/policy 判定，确认后在 `repair` 阶段以相同失败码结束。失败阶段记录“事实在哪一阶段被确认”，失败码记录“为什么不可修”，二者不得互相替代。

这些情况都不能转为 `no_change`：Bug 仍然存在，只是当前流水线配置或平台能力无法完成修复。

### 6.6 Repair 与有界修复循环

Repair Agent 只能修改唯一隔离工作区内允许的路径。平台在 Agent 结束后自行采集变更，并拒绝：

- 修改白名单外路径。
- 修改禁止扩展名。
- 触碰仓库凭据、CodeFixer 配置或任务产物协议。
- 没有任何有效 diff，却声称完成修复。

`verify` 或 `review` 可以把报告写入下一次 Repair 的固定入口文档并回到 Repair。配置项 `max_repair_attempts` 默认 3，包含第一次 Repair；总耗时和费用预算同时生效。超过任一上限后任务失败，不能形成死循环。

每次 Repair 结束后，平台先生成只读的候选修改快照。Verify 和 `review(mode=change)` 都读取这份候选快照；它不是最终交付包，后续 Repair 会使旧候选快照失效。

### 6.7 Freeze Change

通过验证和 Review 后，平台创建不可变交付包，至少包含：

- 基线 revision/SHA。
- 修改工作区已有的有序 commit SHA 列表；SVN 场景可以为空。
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
      pipeline-policy.md
      localization-source-manifest.json
      modification-workspace-manifest.json
      config-snapshot.json
    stages/
      prepare/
      scope-discovery/
        entry.md
        scope-discovery.md
        scope-discovery.json
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
<执行机生成的任务入口绝对路径>
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

平台不相信 Agent 自报的“已读取”“已测试”或“已创建 MR/PR”。必须通过以下来源确认：

- 文件是否真实存在且通过 Schema。
- Git/SVN 状态和 diff。
- 命令退出码与日志。
- 修改路径机械检查。
- GitLab push 返回、Git remote 状态或已认证 GitHub CLI 的确定性查询结果。
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

StageRun 同时保存 `attempt`、开始/结束时间、输入指纹、Runner、实际模型、费用、输出路径和失败对象。即使同一 TaskRun 的 LLM 阶段模型相同，也必须逐阶段保存实际执行事实，便于审计 Runtime 是否按规范执行。

### 8.4 结构化失败

每个失败至少包含：

```json
{
  "code": "discovery_no_target",
  "stage": "discovery",
  "summary": "工单描述中的登录流程无法在当前定位源中可靠定位到修改工作区",
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
- `pipeline_not_found`
- `pipeline_ambiguous`
- `ticket_changed_during_run`
- `localization_source_not_found`
- `modification_workspace_not_found`
- `source_mismatch`
- `multiple_workspaces_required`
- `workspace_policy_blocked`
- `unsupported_artifact_change`
- `external_change_required`
- `generated_source_outside_workspace`
- `discovery_no_target`
- `discovery_ambiguous`
- `insufficient_evidence`
- `workspace_prepare_failed`
- `agent_timeout`
- `agent_protocol_invalid`
- `repair_no_valid_diff`
- `unauthorized_change`
- `verification_environment_unavailable`
- `verification_failed`
- `review_rejected`
- `repair_cycle_exhausted`
- `base_changed_conflict`
- `patch_failed`
- `gitlab_mr_commit_failed`
- `gitlab_mr_push_failed`
- `gitlab_mr_create_failed`
- `github_pr_commit_failed`
- `github_pr_push_failed`
- `github_pr_create_failed`
- `fallback_patch_failed`
- `provider_unavailable`
- `cleanup_failed`

阶段归属按“最早能够确定且不会误判”的原则：

| 边界 | 终止阶段与结果 |
|---|---|
| 保存流水线时工单入口、目录、仓库类型或动作组合无效 | Pipeline Preflight `not_ready`，不创建 TaskRun |
| 排队后本机目录消失、变为只读或无法创建隔离工作区 | `prepare/workspace_prepare` 失败，不调用 Repair |
| SVN/Git 当前布局不能隔离且流水线未允许独占 | `workspace_prepare_failed`，不在共享目录冒险修改 |
| Discovery 已证明需要工作区外、多工作区或外部系统修改 | `assess` 使用第 6.5 节失败码 |
| 只有 Repair 深入读取后才证明无法在工作区内完成 | `repair`，保留同一个语义失败码与 EvidenceRef |
| Agent 返回成功但没有有效 diff | `repair_no_valid_diff`，不能进入 `no_change` |
| 测试 CLI、依赖或验证环境缺失 | `verify` 的 `verification_environment_unavailable`，不消耗 Repair 重试预算 |
| 基线更新后确认上游已经修复 | 经 No-change Verify/Review 后 `completed/no_change` |
| GitLab Push / GitHub PR 远端结果不确定 | 先 `reconciling`；预算耗尽后失败并触发 fallback Patch |
| fallback 目录不可写或磁盘不足 | 保留远端主失败，附加 `fallback_patch_failed` |

## 9. Bug 已不存在或已经修复

### 9.1 健康无修改结果

允许的 `no_change_reason`：

- `already_fixed`：当前基线已经包含可识别的修复。
- `not_present_on_current_baseline`：工单描述的错误路径在当前基线客观不存在。
- `not_applicable_to_workspace`：有证据证明工单不适用于路由到的版本或代码基线。
- `upstream_fixed_during_run`：运行期间基线更新，重新验证后确认上游已修复。

### 9.2 必需证据

`no_change` 至少包含：

- 当前修改工作区和冻结 revision/SHA。
- 关键代码或配置证据。
- 可执行验证及其结果；如果目标工程没有测试能力，必须有流水线级显式豁免和替代证据。
- 可能的修复提交、MR 或版本记录；找不到时说明。
- 为什么不需要 Patch、MR 或 PR。
- 独立 Review 的通过结论。

`not_present_on_current_baseline` 不能以全文搜索无结果为依据。至少需要一项当前状态证据和一项独立佐证，例如：

- 当前调用链、配置入口或可执行检查证明该错误路径不可达。
- 历史提交、版本说明或旧符号记录证明相关逻辑已删除或替换。
- 可重复的复现步骤在目标基线上稳定不再出现，并记录运行环境。

`not_applicable_to_workspace` 只用于“定位源与修改工作区绑定正确，但工单明确针对另一个版本、平台或被流水线策略排除的组件”。如果真正需要修改的代码位于另一个工作区，则必须是 `source_mismatch` 失败。

`allowNoAutomatedTests` 只豁免目标工程缺少自动测试套件，不能豁免当前任务所需运行环境不可用。无测试工程仍必须提供流水线配置中预先声明的编译、静态检查、历史证据或人工可复核的替代验证。

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
- 所有需要启动 Agent CLI 的 StageRun 共享一个全局 LLM 并发池，默认容量为 4。
- `freeze_change` 之后，彼此独立的最终动作可有界并发。
- `githubPr` 的不同目标分支可有界并发；单个目标内的 commits 必须按顺序串行应用。`gitlabPush` 只有一个远端任务分支。

LLM 槽位只覆盖真实 Agent 子进程从启动到退出的区间。排队、工单拉取、基线准备、工作区创建、验证命令、冻结和交付均不占用 LLM 槽；等待 LLM 槽时也不得持有仓库锁、工作区池 lease 或外部资源锁。槽位按入队时间公平发放，使用数据库 lease、heartbeat 和过期回收保证服务重启后不会永久泄漏。一个 TaskRun 不允许两个 LLM 阶段同时执行。

交付先通过一次共享不变量检查，再对每个最终动作独立执行无副作用 Preflight。共享检查只覆盖工单版本、修改工作区基线和冻结修改完整性；失败时任何动作都不能开始。某个动作自己的输出目录、remote、目标分支或认证 Preflight 失败，只使该动作失败，不阻止已经通过 Preflight 的兄弟动作。动作并发开始后，即使其中一个失败，其他已调度动作仍运行到可确认的终态，平台最后统一聚合结果。

配置至少包含：

- 全局最大活跃任务数，用于保护本机进程与磁盘；它与 LLM 池分别限流。
- 全局最大 LLM 调用数 `maxConcurrentLlmCalls`，默认 4，所有 AgentRuntime 共享。
- 可选的 Runtime 二级上限，但不得把同一全局池拆成互不借用的固定配额。
- 每个 TicketProvider 的请求限流。
- 每个 Git remote host 的请求限流。
- 每条流水线或修改工作区的并发上限。
- 可选命名资源锁，例如共享测试服、固定端口和数据库。

### 10.2 同源基线批次与短时锁

同一物理修改工作区在短时间内一起进入 `prepare` 的 TaskRun 必须组成一个 `BaselineCohort`，共享第一个任务解析出的基线版本。默认合批窗口 `baselineCohortWindowMs=2000`，可在全局高级配置中调整。

批次键至少包含规范化仓库根路径、VCS 类型和基线分支/URL；不能仅按 Pipeline ID 合批。凭据只属于当前部署用户的仓库访问环境，不进入 key、日志或任务快照。协议如下：

1. 第一个任务创建 `open` cohort，成为 leader，并取得该批次键对应的短时仓库刷新锁。
2. leader 对 Git 只执行一次 `fetch --prune` 并解析基线 ref 为不可变 commit SHA；对 SVN 只执行一次远端 revision 查询/受控更新并解析为不可变 revision。
3. 从 cohort 创建开始、在合批窗口内进入 `prepare` 的同键任务加入该 cohort。followers 不再次 fetch/update，也不重复竞争仓库刷新锁。
4. 基线解析完成且窗口结束后 cohort 变为 `sealed`，保存 VCS 类型、SHA/revision、resolvedAt 和成员列表；之后到达的任务创建新 cohort。
5. 每个成员基于同一个不可变 SHA/revision创建自己的隔离工作区，然后立即释放共享准备资源并独立并发执行。共享的是版本事实，不是可写目录、分支或 SVN working copy。
6. leader 刷新失败时，该 cohort 的成员获得同一份可读失败证据并按统一退避策略重试；不得让 followers 退化成逐个刷新。新重试批次可以重新选 leader。

仓库刷新锁只保护 fetch/update、基线解析和 worktree/工作副本池元数据操作，不覆盖 Agent、测试或交付。这样同一时刻到达的四个任务可以共同冻结版本 V1 后并发占用四个 LLM 槽，而不是串行等待四次仓库更新。`pre_delivery_check` 仍逐任务检查外部漂移，基线批次不削弱交付前稳定性门禁。

### 10.3 Git 工作区

每个任务使用独立 Git worktree 和唯一平台分支。允许同一仓库的多个任务并发；共享 clone 的 fetch、prune 和 worktree 元数据修改只持有短时仓库锁。

### 10.4 SVN 工作区

SVN 必须使用独立任务工作副本或受管理的工作副本池，并以 cohort 冻结的 revision 执行 `checkout/update -r`。若某种 SVN 布局无法可靠隔离，则该修改工作区必须配置为独占 lease，但不影响其他修改工作区的任务并发；这种降级必须在流水线 Preflight 中明确提示吞吐影响。

### 10.5 持久化调度

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
- 不允许盲目重放 GitLab Push 或 GitHub PR 创建请求。

### 10.6 基线变化

`prepare` 时刷新工单并加入或创建代码基线 cohort。`pre_delivery_check` 在任何最终动作产生副作用前再次检查工单、修改工作区和全部动作目标：

- 无变化：继续交付。
- 能自动更新且无冲突：重新应用修改，并重新执行 verify 与 review。
- 更新后 diff 为空且能证明上游已经修复：转 `completed/no_change`。
- 冲突或无法证明安全：以 `base_changed_conflict` 失败。

`freeze_change` 完成后先执行共享不变量检查，再执行各动作自己的无副作用 Preflight。共享检查失败时整组动作都不得开始；单个目标分支或动作依赖漂移只使对应动作/目标失败，普通 Patch 和其他独立动作仍可执行。一旦任一动作写出 Patch、创建分支或发出其他外部副作用，本次运行就不能再转为 `no_change`；后续漂移只能使对应动作失败。

## 11. 验证与独立 Review

### 11.1 流水线验证配置

流水线可配置多个验证步骤：

```yaml
verification:
  timeoutSeconds: 1200
  steps:
    - id: unit
      executableRef: python-cli
      args: ["-m", "pytest"]
      workingDirectory: "."
      required: true
    - id: build
      executableRef: npm-cli
      args: ["run", "build"]
      workingDirectory: "frontend"
      required: true
```

命令使用参数数组，不使用未经解析的 shell 字符串。每步记录 stdout、stderr、退出码、耗时和产物路径。

没有自动测试能力的流水线必须显式配置：

```yaml
verification:
  allowNoAutomatedTests: true
  reason: "目标工程暂无自动测试，使用编译和独立 Review 作为替代门禁"
```

不能因为配置缺失而悄悄跳过验证。

### 11.2 Review

Review 使用统一的 `review` stage、独立 Agent 会话和只读权限。`mode=change` 检查候选修改，`mode=no_change` 检查无修改报告。两种模式使用同一个 TaskRun 当前模型、目录协议和状态模型；Review 的“独立”指会话与职责独立，不指单独选择另一模型。

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
outputDirectory: "D:/CodeFixerPatches"
overwrite: false
```

可配置项：

- 输出目录。
- 是否允许覆盖。
- Git 或 SVN 对应的 Patch 格式选项。

输出目录在 Patch 动作表单中直接选择或填写，保存到当前机器 `.local/config.json`，不进入公开默认配置。保存时执行创建/可写性预检；工单内容不能直接成为未净化路径。普通用户不接触 `pathBindings` 或目录引用 ID。

### 12.2 执行

- 只消费 `freeze_change`。
- 先写同目录临时文件，再原子改名。
- 记录文件大小、SHA-256、修改文件数和下载地址。
- 文件名固定使用冻结的标准交付日志并追加 `.patch`；仅净化当前操作系统禁止的字符、控制字符和尾部点/空格，不允许 LLM直接提供文件名。
- 路径过长时保留工单标识、修改摘要和提交人，并追加稳定短 hash；同一次运行重试必须得到同名文件。
- 相同幂等键且内容 hash 相同时，重试直接复用已有文件。
- 同名文件内容不同且 `overwrite=false` 时失败，不静默覆盖。

## 13. 最终动作：GitLab Push

### 13.1 行为定义

动作类型固定为 `gitlabPush`。它从冻结修改确定性地产生一个交付 Commit，推送到同一 GitLab 仓库的受控任务分支，并把 Commit URL 交给用户：

```text
冻结修改 → 标准交付日志 → 交付 Commit
  → 推送受控任务分支
  → 返回 Commit URL
  → 用户在 GitLab Web 自行选择目标分支并 Cherry-pick
```

平台不创建 MR、不选择 Cherry-pick 目标分支，也不跟踪用户之后是否完成 Cherry-pick。远端任务分支与 Commit SHA 已确认可访问即表示动作成功。

### 13.2 配置

```yaml
deliveryLog:
  technologyTag: "Lua"
  branchLabel: "主干"
  versionSource: ticketFixVersion
  versionFallback: "v4.8"
  submitterName: "黄永熙"
finalActions:
  - type: gitlabPush
    id: gitlab-push
```

“最终动作”步骤顶部提供一个公共“交付日志”区，填写技术域、分支标签、版本来源/兜底版本和提交人姓名；它属于同一次冻结交付，不在 Patch、GitLab Push、GitHub PR 卡片中重复填写。版本来源第一版支持“固定版本”和“工单修复版本”：TAPD 读取明确映射的修复版本字段，Redmine 读取 `fixed_version.name`；字段为空时必须使用配置的兜底值或在 Preflight 阻止启动，不允许 LLM 猜版本。

动作直接复用流水线唯一的 `ModificationWorkspace`，只在其自动识别为 `hostingKind=gitlab` 后开放。用户不重复选择仓库，不配置目标分支、MR、assignee、GitLab API Token、Project Path 或独立 connection。仓库推送复用部署用户已经配置的 SSH key / Git credential。

`submitterName` 是标准交付日志中 `提交人：` 后面的显示姓名，不等同于 Git Author 或 GitLab 用户名。若同一流水线配置多个最终动作，各动作消费同一冻结值。

### 13.3 标准交付日志

平台冻结统一 Commit subject：

```text
{type}：【{技术域}】【#{工单标识}】【{分支标签}】【{版本}】{模块名} - {修改摘要}  提交人：{姓名}
```

字段规则：

- TAPD Bug：`type=fix`，工单标识为 `B<id>`。
- TAPD 非 Bug：`type=feat`，工单标识为 `S<id>`。
- Redmine：无论 tracker，统一 `type=fix`，工单标识只使用原始 `<id>`，不加字母。
- 技术域、分支标签和版本来自流水线配置或明确的工单字段映射，不由 LLM 猜测。
- LLM 只输出简短的 `module_name` 和 `change_summary`；Review Agent 验证其与冻结修改一致，平台负责固定标点和拼装。
- 姓名来自 `submitterName`；不得从 Git Author、邮箱或 GitLab 用户名反推。

交付日志在 Review 通过后生成一次，写入 `delivery-metadata.json` 并随 `freeze_change` 冻结。Patch 文件名、GitLab Commit subject 和默认 GitHub PR 标题都复用同一字符串，重试时不得重新询问 LLM。

### 13.4 分支、推送与结果

受控分支遵循：

```text
codefixer/<normalized-ticket-key>/<run-short-id>
```

执行步骤：

1. 确认 `origin` 仍指向识别时的同一个 GitLab 项目，并验证 fetch/push 能力。
2. 从冻结基线物化交付 Commit；Commit 必须非空且与 `change-manifest` 完全一致。
3. 检查同名远端分支。分支不存在时执行普通 push；存在且 SHA 与冻结结果相同则幂等复用；存在但 SHA 不同则失败，禁止 force push。
4. 用 `git ls-remote` 确认远端分支 SHA 等于交付 Commit SHA。
5. 使用仓库识别阶段已确认的 `webBaseUrl` 与规范化项目路径生成并保存项目 URL、分支 URL 和 `<project>/-/commit/<sha>` Commit URL；不得擅自把 SSH remote 改写为 HTTPS。

任务分支成功后不自动删除，因为它是人工 Cherry-pick 前保证 Commit 可达的远端引用。用户之后的分支清理不属于当前任务。

### 13.5 失败、对账与保底

网络中断但 push 结果未知时进入 `reconciling`，只通过远端分支 SHA 对账，不盲目重复创建新分支。确认远端 SHA 后转成功；超过预算仍无法确认时转 `failed`。

`gitlabPush` 失败是任务交付失败，并从同一冻结修改生成或复用 fallback Patch。失败结果至少记录当前步骤、脱敏 Git 错误、计划分支、是否存在远端副作用以及 fallback 状态。它只有一个远端结果，不存在目标分支级部分成功。

## 14. 最终动作：GitHub PR

### 14.1 行为与配置

`githubPr` 使用同一份冻结修改，但保留创建 PR 所需的目标分支、多目标、部分成功和幂等状态契约，只在修改工作区自动识别为 `hostingKind=github` 时开放：

```yaml
type: githubPr
id: main-github-pr
targetBranches:
  - main
titleTemplate: "[CodeFixer] {task_id}"
descriptionTemplate: "CodeFixer 自动修复任务 {run_id}。"
```

CodeFixer 不要求用户在 Web 中再次填写 GitHub 仓库或 Token。Git 操作复用 `origin` 和本机 Git 认证，PR 创建复用部署用户现有的 GitHub CLI (`gh`) 非交互认证。Preflight 必须验证 remote 类型、目标分支、push 权限、`gh auth status` 以及 `gh repo view` 指向同一仓库。PR 创建失败是最终动作失败；任何目标失败都会使任务失败，并保留其他已成功 PR。

### 14.2 GitLab 与 GitHub 能力隔离

- GitLab 工作区只显示 Patch 和 GitLab Push。
- GitHub 工作区只显示 Patch 和 GitHub PR。
- SVN 与其他 Git 工作区只显示 Patch。
- 修改工作区重新识别后，已有但不再兼容的动作配置必须阻止保存，不能静默删除或转换。

### 14.3 远端交付失败的保底 Patch

保底策略默认开启，不要求用户事先配置 Patch 动作或目录。保底目录固定为平台托管数据目录：

```text
<storage.dataRoot>/fallback-patches/<sanitized-pipeline-id>/
  <ticket-provider>-<ticket-id>-<run-id>-<change-version>.patch
```

该目录属于 CodeFixer 运行数据，不能创建在被修复仓库内部，也不能进入 Git。启动 Readiness 和流水线 Preflight 必须验证根目录可创建、可写且剩余空间足够。

触发规则：

1. `freeze_change` 已存在。
2. 任一 `gitlabPush` / `githubPr` 动作或目标进入终态 `failed`，包括运行期无副作用 preflight 失败、认证失效、push/create 失败、GitHub 目标分支漂移，以及超过对账预算后的结果不确定。
3. 如果配置的普通 Patch 动作已经成功并且 hash 与当前 `freeze_change` 一致，直接把它登记为 fallback，禁止复制第二份。
4. 如果普通 Patch 动作未配置、未运行或失败，使用上述平台托管目录原子生成一份保底 Patch。
5. 多个远端目标失败时每个 `change_version` 只生成一份保底 Patch，并在其中记录全部触发失败 ID。

保底动作使用保留 ID `__fallback_patch__`，写入独立 `DeliveryActionRun`，包含 `triggeredBy`、Patch path/hash、是否复用普通 Patch 和自身失败原因。目录不可写、磁盘空间不足或原子落盘失败时，原远端失败仍是主失败，并附加 `fallback_patch_failed`；不得用保底失败覆盖或隐藏原始错误。

界面必须直接显示：

```text
交付失败 · 已生成保底 Patch
[下载 Patch] [打开目录] [仅重试失败交付]
```

如果保底也失败，则显示“交付失败，保底 Patch 也未生成”以及两组独立原因。保底成功不允许出现绿色“已完成”，也不自动关闭外部 Bug。

## 15. 取消与重试

### 15.1 取消

- `awaiting_start`、`queued` 可立即取消。
- `running` 先进入 `cancel_requested`，终止 Agent 进程组和当前命令，不再启动新阶段。
- 清理隔离工作区后进入 `canceled`。
- 已经产生的 Patch、远程分支、MR 或 PR 不自动删除；必须在 `side_effects` 中列出。
- `completed` 和 `failed` 不提供“取消”，只提供重新运行或重试。

### 15.2 自动重试

仅对明确的瞬时错误自动重试，例如：

- 网络超时。
- API 限流。
- Runner 非业务性崩溃。
- Worker lease 过期且外部对账确认没有副作用。

定位歧义、验证失败、Review 拒绝和配置错误不盲目自动重试。

### 15.3 人工重试

- 输入指纹不变时，可从安全检查点续跑。
- 工单、策略、定位源快照、修改工作区基线、当前模型或最终动作配置变化时，必须创建新 TaskRun 并从 `prepare` 开始。
- Delivery 部分失败默认只重试失败动作/目标。
- 已成功动作不重复。
- 用户想重新推送已清理的 GitLab 任务分支，或为已关闭的 GitHub PR 再创建一个，属于“重新交付”，必须创建新的动作版本。

Delivery-only 重试沿用原 TaskRun 和 `change_version`，创建新的 deliver StageRun/DeliveryTarget attempt；Task 从 `failed` 回到 `queued`，全部必需动作最终成功后可转为 `completed/changed`。输入或配置发生变化时不得使用 Delivery-only 重试。

## 16. 适配器架构

### 16.1 接口

核心只依赖：

- `TicketProvider`
- `LocalizationSourceProvider`
- `ModificationWorkspaceProvider`
- `KnowledgeProvider`
- `AgentRuntime`
- `VerificationRunner`
- `FinalActionProvider`

每个适配器声明 capability，例如是否支持增量游标、附件、历史日志、隔离工作区、多目标交付和取消。

### 16.2 第一版内置适配器

| 类别 | 第一版 |
|---|---|
| 工单 | Redmine、TAPD |
| 定位源 | 本机只读目录/仓库、HTTP 知识服务 |
| 修改工作区 | 自动识别 GitLab Git、GitHub Git、其他 Git、SVN |
| 知识源 | 无、HTTP 知识服务 |
| Agent Runtime | Claude Code、Codex、OpenCode |
| 验证 | 受控本地命令 |
| 最终动作 | Patch、GitLab Push、GitHub PR |

业务知识服务若启用，只是一个 HTTP `KnowledgeProvider`。核心代码、Prompt 协议和 UI 不出现业务项目专属语义。

### 16.3 Runner 公共协议

Prompt plan 冻结：

- stage ID。
- TaskRun 当前模型 ID、解析后的实际模型与 Runtime。
- 入口文档路径。
- 工作目录。
- 权限清单。
- 输出路径与 Schema。
- 超时和预算。

不同 Runner 只转换 CLI 细节，不能修改业务输入、阶段职责或替换 TaskRun 已冻结的模型。

## 17. 配置体系

### 17.1 配置分层

采用三层：

1. Git 管理的默认配置：只放跨机器默认值、正式服务端口和 Schema 版本。
2. 当前机器本地配置：路径、CLI 位置、流水线启停和 Web 保存项，不进 Git。
3. Secret 配置：Token、API Key 和凭据引用，不进入普通配置响应和日志。

本地配置对默认配置做深度合并；保存时只写相对默认值的最小覆盖，并使用同目录临时文件加原子替换。

### 17.2 顶层结构

```yaml
schemaVersion: 2

server:
  host: "0.0.0.0"
  port: 9522

storage:
  dataRoot: "./data"

execution:
  mode: awaitingStart
  currentModelId: claude-sonnet
  maxConcurrentTasks: 8
  maxConcurrentLlmCalls: 4
  baselineCohortWindowMs: 2000
  maxRepairAttempts: 3

ticketProviders: []
agentProfiles: []
knowledgeProviders: []
executableBindings:
  git-cli:
    command: ["git"]
    versionArgs: ["--version"]
    versionConstraint: null
  svn-cli:
    command: ["svn"]
    versionArgs: ["--version", "--quiet"]
    versionConstraint: null
  python-cli:
    command: ["python"]
    versionArgs: ["--version"]
    versionConstraint: null
  npm-cli:
    command: ["npm"]
    versionArgs: ["--version"]
    versionConstraint: null
  claude-code-cli:
    command: ["claude"]
    versionArgs: ["--version"]
    versionConstraint: null
  codex-cli:
    command: ["codex"]
    versionArgs: ["--version"]
    versionConstraint: null
  opencode-cli:
    command: ["opencode"]
    versionArgs: ["--version"]
    versionConstraint: null
pipelines: []
```

`server.port=9522` 是 CodeFixer 第一版的正式服务约定，前端、API、健康检查、systemd 和部署文档统一使用该端口。自动化测试可临时注入随机端口，不能改写公开默认值或生产服务约定。

`storage.dataRoot` 的相对路径固定相对“有效基础配置文件所在目录”解析，禁止相对进程当前工作目录解析。其规范化绝对路径在启动后不可热修改；变更数据根目录需要停服、迁移并重新启动。

流水线里的定位源路径、修改工作区路径和 Patch 输出目录属于当前机器配置，由相应业务表单直接选择并写入 `.local/config.json`。它们不得出现在公开默认配置或 Git 提交中。Web 可以用目录选择器或文本输入接收路径，但不得要求普通用户先创建 `pathBindings`、再回到流水线里选择一个引用 ID。

`executableBindings` 是平台内部的机器命令注册表。平台优先从部署用户 `PATH` 自动发现 Git、SVN、`gh` 和 Agent CLI；只有自动发现失败或管理员显式覆盖时才写入本机配置。普通设置页不展示“命令”卡片；健康检查正常时只显示能力可用，失败时才在诊断详情展示命令、探测结果和修复方式。当前模型所需的 Claude Code、Codex 或 OpenCode Runtime 必须存在有效 binding。

`agentProfiles` 在第一版保留为内部模型/Runtime 注册结构，用于解析 `currentModelId`。它不是 Pipeline 的可配置角色表，Web 默认不提供 Profile CRUD；用户只操作 `execution.currentModelId`。

版本检查使用以下确定性协议：

1. 以参数数组执行 `command + versionArgs`，超时、非零退出码或无法启动均为失败。
2. 按 stdout、stderr 的顺序，在首个非空输出中提取第一个 `主版本.次版本[.修订版本[.构建版本]]` 数字串；binding 可用 `versionRegex` 覆盖提取规则，但必须包含命名捕获组 `version`。
3. `versionConstraint` 只支持 `> >= = <= <` 与逗号连接的 AND 条件，例如 `>=2.40,<3.0`。
4. 比较时把 2 至 4 段十进制整数补零到 4 段后按数值逐段比较；不把供应商后缀参与比较。
5. 配置了约束却无法提取或比较版本时检查失败；约束为 `null` 时仍必须成功取得并记录版本，只在高级详情中提示“未设置最低版本”，不降低健康状态。

正式发布可以为生产启用依赖写入已验证最低版本；未设置约束本身不是故障。黄灯只表示能力或覆盖范围真实降级，未使用的可选命令显示为灰色，当前全局模型对应的 CLI 必须按 required 检查。

`execution.mode`：

- `automatic`
- `awaitingStart`

`execution.currentModelId`：

- 必须指向一个有效的内部模型配置。
- 全局只能有一个当前值。
- Pipeline 不允许覆盖。
- 所有 LLM 阶段统一消费该值解析出的模型。
- Web 只提供当前模型单选，不暴露阶段 Profile 管理。

`execution.maxConcurrentLlmCalls`：

- 默认值为 4，必须为正整数。
- 是全局共享硬上限，而不是每种 Agent Runtime 各 4 个。
- 修改后只影响新的槽位发放，不中断已经运行的 Agent 调用。

`execution.baselineCohortWindowMs`：

- 默认 2000 ms，允许范围 0 至 10000 ms；0 表示关闭短时合批但仍保留短时仓库锁。
- 只决定同源任务能否共享一次基线解析，不让任务绕过 `pre_delivery_check`。

### 17.3 配置快照

每次 TaskRun 开始执行时冻结：

- 有效流水线配置。
- 全局当前模型：`currentModelId`、实际模型 ID、Runtime、`executableRef` 和影响调用语义的运行参数。
- 修改工作区与自动识别结果。
- 定位源与定位到修改工作区的映射规则。
- `BaselineCohort` ID、冻结 SHA/revision 和解析时间。
- 验证命令。
- 最终动作。
- 配置版本/hash。

运行中热重载只影响后续开始执行的 TaskRun。Pipeline 配置快照中不得重新出现阶段 Agent/模型字段。

### 17.4 依赖检查与 Readiness

依赖检查是平台能力，不是部署人员自行阅读外部文档后完成的隐式步骤。它分为两层：

CodeFixer 的 Python 运行时基线固定为 **64 位 CPython 3.12+**。Bootstrap 必须在创建虚拟环境前校验实现、版本和位宽；启动、测试与 systemd 必须直接调用仓库内 `backend/.venv`，不得在虚拟环境缺失或无效时静默回退到系统 `python`。

1. 全局启动检查由 `GET /api/readiness` 暴露，决定服务是否可接收新任务。
2. 流水线 Preflight 由保存配置、手工体检、切换全自动和 TaskRun `prepare` 调用，决定整条流水线及最终动作是否可执行。

全局检查至少覆盖：

- 配置 Schema、Secret 引用和数据库迁移有效，SQLite WAL 可读写。
- `storage.dataRoot` 的解析基准稳定，数据根目录、Artifact、Workspace 和日志可创建、可写且剩余空间高于阈值。
- 正式进程能够绑定 `9522`，生产模式下前端构建产物存在。
- 当前操作系统支持所选进程隔离与取消方式。
- `execution.currentModelId` 可解析为有效模型配置，其 Runtime CLI 存在、版本满足约束，并在部署用户下具备非交互认证能力。
- 已启用的 Git、SVN、`gh` 和其他必需 CLI 可自动发现或有内部 binding，版本满足约束。
- 必需的外部服务可以解析和连接；检查结果只报告凭据是否可用，不输出凭据内容。

流水线 Preflight 至少覆盖：

- `providerRef` 指向仍存在且已启用的 TicketProvider；连接可用、增量游标能力与筛选字段有效。
- TicketProvider 的地址、工作区和 Secret 已在“工单接入”表单配置，凭据测试成功。
- 路由规则完整；可静态识别的 catch-all、同优先级或空条件冲突必须阻止保存。
- LocalizationSource 可读取，定位结果协议能映射到唯一 ModificationWorkspace。
- ModificationWorkspace 的本机目录存在；Git/SVN 类型与 GitLab/GitHub hosting 类型可自动识别；基线可读取，隔离工作区可创建。
- 全局当前模型及其 Runtime 可用；Pipeline 不检查 `scopeDiscovery/discovery/repair/review` 等阶段 Profile 字段。
- 验证命令的可执行文件、参数、工作目录和超时有效。
- Patch 的本机输出目录可创建且可写。
- GitLab Push 只绑定 GitLab 修改工作区，remote 访问和受控任务分支 push 权限有效；不检查目标分支、MR 或 push options。
- GitHub PR 只绑定 GitHub 修改工作区，目标分支、remote 访问、push 权限和当前部署用户 `gh` 认证有效。
- 允许修改路径和最终动作 ID 不冲突，动作类型符合自动识别出的仓库能力。

每个检查返回稳定的 check ID、`ready|warning|failed`、用户可读原因和修复建议。当前模型检查使用稳定的全局语义，例如 `agent.current` / `agent.current.executable`，不得重新按阶段生成四套 Agent readiness。必需依赖失败时流水线为 `not_ready`：全自动调度不领取该流水线的新任务，手工开始按钮禁用；运行前状态变化则 TaskRun 以 `configuration_not_ready` 失败并保留检查证据。可选知识源不可用只产生 warning，并在任务档案中明确标注降级，不冒充查询成功。

## 18. 持久化模型

第一版使用 SQLite WAL，数据库保存元数据与索引，大文件放任务产物目录。

核心表：

- `ticket_records`：外部工单当前视图和游标。
- `ticket_snapshots`：不可变工单版本。
- `tasks`：长期任务与当前顶层状态。
- `tasks.pipeline_id`：任务唯一绑定的流水线；不得同时绑定多条流水线。
- `task_runs`：每次执行及输入指纹。
- `stage_runs`：阶段和 attempt。
- `artifacts`：路径、类型、hash、大小和来源。
- `delivery_action_runs`：最终动作结果。
- `delivery_target_runs`：GitLab/GitHub 每目标分支结果。
- `task_events`：用户可读时间线。
- `worker_leases`：执行租约和 heartbeat。
- `llm_slot_leases`：全局 LLM 槽位、owner、heartbeat 与过期时间。
- `baseline_cohorts`：同源批次键、状态、合批窗口、leader、冻结 SHA/revision 与失败证据。
- `baseline_cohort_members`：cohort 与 TaskRun 的成员关系。
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

## 19. API 设计

主要接口：

```text
GET    /api/health
GET    /api/readiness

GET    /api/settings
PUT    /api/settings
PUT    /api/settings/execution-mode

GET    /api/pipelines
POST   /api/pipelines
PUT    /api/pipelines/:id
POST   /api/pipelines/:id/preflight
POST   /api/workspaces/detect

GET    /api/providers
POST   /api/providers
PUT    /api/providers/:id
POST   /api/providers/:id/test

GET    /api/tasks?pipelineId=:id&status=:status
GET    /api/tasks/:id
POST   /api/tasks/:id/start
POST   /api/tasks/start-batch
POST   /api/tasks/:id/cancel
POST   /api/tasks/:id/retry
POST   /api/tasks/:id/rerun

GET    /api/tasks/:id/artifacts
GET    /api/tasks/:id/events
GET    /api/tasks/:id/diff

POST   /api/actions/:id/test

GET    /api/events
WS     /api/ws
```

所有写接口使用版本号或 ETag 防止覆盖并发修改。工单接入写接口在同一个表单请求中接收 Token/密码并立刻拆分写入 Secret store；后续读取只返回 `configured: true/false`。当前模型和 LLM 并发池属于全局 settings，不创建 Pipeline 级模型 API。

第一版尚未上线，本次语义重构直接把配置 `schemaVersion` 提升为 2；不提供旧配置自动迁移，也不保留 `/api/projects`、`projects`、`project_id`、`ProjectConfig` 或 `project_*` 失败码的兼容别名。实现必须完整迁移为 `/api/pipelines`、`pipelines`、`pipeline_id`、`PipelineConfig` 和 `pipeline_*`，遇到旧本机配置时明确报 Schema 不兼容并要求按新流水线结构重新配置，避免新旧语义长期并存。

## 20. Web 管理界面

### 20.1 视觉方向

界面采用“自动维修控制塔”而不是普通后台模板：

- 大胆但克制的高对比色，用于区分运行、成功、失败和外部副作用。
- 顶部保留一个强识别度的全局模式控制器。
- 任务阶段使用连续轨道和真实耗时，不用虚假的线性百分比。
- 失败卡片优先显示结论、影响和下一步，再展开原始日志。
- 页面有适度动态反馈和个性化图形语言，但不牺牲密度与可读性。
- 支持明亮/暗色主题，记忆用户选择。

不得直接复制其他项目的皮肤。

### 20.2 导航

第一版主导航只有三个入口：

- 任务
- 流水线
- 设置

不设置独立首页，也不把工单接入做成主导航。TicketProvider、Agent Runtime、CLI binding、知识源等复用资源或机器级能力进入流水线内的次级管理入口、设置或高级配置。

### 20.3 全局运行控制

顶部常驻全局模式控制器：

```text
[ 待我开始 ]  ←→  [ 全自动 ]
```

状态、环境健康和 LLM 容量均为紧凑的全局信息，不为它们单独创建控制台页面。切换到全自动时明确显示将排队的现有任务数量，但不把“旧任务”误解为冻结的旧仓库。

### 20.4 任务列表

任务页是全站唯一任务列表，默认同时展示全部流水线。顶部提供紧凑的流水线筛选器与状态筛选：

- 全部流水线 / 指定流水线。

- 待开始
- 排队
- 运行中
- 已完成：已修改
- 已完成：无需修改
- 失败
- 已取消
- 部分交付

默认排序固定为：

1. `failed`，按 `updated_at` 倒序。
2. `awaiting_start`，按 `updated_at` 倒序。
3. 其余状态按 `updated_at` 倒序。

异常与待授权任务只在同一张账本中置顶并用分隔标注，不复制到第二个列表。选择单一状态筛选时不显示多余的置顶分区。流水线页面的“查看任务”跳转到这个任务页并带入 `pipelineId` 筛选，不创建流水线私有任务页面。

任务行显示：

- 工单号和标题。
- 所属流水线；定位源和修改工作区只在详情中显示，避免列表重复路径信息。
- 运行中显示当前阶段与阶段耗时；终态只显示一行业务结论或失败摘要。
- Patch 路径、Commit SHA、分支和外部链接不进入列表行。

### 20.5 任务详情

任务详情采用两级渐进披露，不把 AI 结论、阶段账本、Commit 元数据和文件清单塞进同一个抽屉，也不叠放两个同时存在的模态层。

**一级弹窗：任务结论**

- 从任务行进入，头部只显示工单身份、标题和终态。
- 终态任务首先显示一句结论，再依次显示“原因”和“修复方案”；每段最多两句，不生成长篇报告。
- 验证只显示一个紧凑事实状态，例如“验证通过”或“验证失败”，不在此重复测试数量和修改文件数量。
- 运行中的任务在同一位置显示阶段轨道；结论尚未冻结时不展示占位文案。
- `changed` 且存在交付记录时，底部主操作为“查看交付结果”；`no_change` 或修改前失败没有空的二级入口。
- 技术阶段、尝试、证据和原始日志仍在一级弹窗的折叠区，默认关闭。

**二级弹窗：交付结果**

- 点击“查看交付结果”后，用交付弹窗替换一级弹窗；不得在一级弹窗上再叠一层。关闭回到任务列表，“返回任务结论”回到一级弹窗。
- 顶部只给最终交付状态和下一步。GitLab Push 成功时主操作是“在 GitLab 查看 Commit”；Patch 成功时是“打开目录”或“下载 Patch”。
- 多个最终动作以紧凑结果行排列，每行只显示动作名称、结果和一个主操作；Commit SHA、远端分支、hash、幂等键进入“技术信息”折叠区。
- GitLab Push 的用户下一步固定说明为“打开 Commit，在 GitLab Web 选择目标分支并 Cherry-pick”；平台不暗示已经合入。
- 最后一个可见区块固定为“修改文件”，使用 `change-manifest.files` 的平台事实，不使用 Agent 自报清单。
- 文件路径必须相对修改仓库根目录，统一 `/`，不带盘符、绝对工作区、远端分支名或仓库名。每行显示操作类型与路径；目录弱化、文件名强调，长路径中段省略，悬停可看完整值，点击复制完整相对路径。
- 默认显示全部文件；超过 12 个时区域内部滚动并提供“复制全部路径”，不把路径清单折叠到不可发现的位置。

两个弹窗都必须支持 `Esc`、明确关闭按钮、焦点圈和键盘焦点回归；切换弹窗不得引起底层任务列表滚动或布局跳变。URL 应保存当前 `taskId` 与 `view=conclusion|delivery`，刷新后恢复同一层级。

失败页必须直接回答：

- 在哪个阶段失败。
- 为什么失败。
- 已经做了什么。
- 是否产生 Patch、GitLab 分支/Commit 或 GitHub PR。
- 是否可重试。
- 建议先修什么。

失败交互按 failure code 给出明确主操作：

- `source_mismatch` / `workspace_policy_blocked`：编辑流水线并以新 TaskRun 重新运行。
- `multiple_workspaces_required` / `unsupported_artifact_change` / `external_change_required`：查看定位证据和人工处理步骤，不显示无意义的“重试 Repair”。
- GitLab Push / GitHub PR 失败且 fallback 成功：突出显示保底 Patch，并提供“仅重试失败交付”；不要求重新调用 LLM。
- `fallback_patch_failed`：同时展示远端失败和本地落盘失败，提供修复存储后重新生成 fallback 的无 LLM 操作。

`no_change` 的一级结论弹窗必须展示正向证据，不能只显示“没有发现问题”；它没有二级交付弹窗。

### 20.6 系统设置与当前模型

模型选择必须是轻量的全局单选控件：

```text
当前模型  [ Claude Sonnet ▼ ]
```

交互约束：

- 页面直接展示当前模型，不要求先进入“模型管理”弹窗。
- 用户选择另一个模型后保存为新的 `execution.currentModelId`。
- 不出现“添加模型”“已添加”“启用 Claude Code/Codex/OpenCode”等 Runtime 管理语义。
- 不在 Pipeline 编辑器中出现 Scope、Discovery、Repair、Review 四个模型下拉框。
- Runtime、CLI 命令、超时等属于系统实现/高级环境配置，默认不与模型选择混排。
- 可在模型旁显示简短能力定位和当前 Runtime 健康状态，但不堆叠价格、上下文窗、参数等非必要信息。

模型列表中的一等实体必须是模型，而不是 Runtime。具体模型映射到 Claude Code、Codex 或 OpenCode 的方式由平台内部模型注册表负责。

同一页面提供一个直观的“并行 AI 调用数”控件，默认 4，对应 `maxConcurrentLlmCalls`。它限制正在运行的 Agent 阶段，不等同于活跃任务数；界面展示当前调用槽使用量和排队量，不暴露 Runtime 分池、lease 或 semaphore 等实现术语。

### 20.7 流水线与工单接入交互

左侧不再提供独立“工单来源”入口。流水线页面以可执行线路为主体，提供次级“管理工单接入”入口；新增流水线的第一步也能原地选择或新增接入，不要求用户跨页面预配置。

工单接入表单直接完成真实业务配置：

- Redmine：名称、服务地址、API Token、轮询设置、测试连接。
- TAPD：名称、工作区、账号密码或 Token、轮询设置、测试连接。
- Token/密码输入框保存后清空，只显示“已配置”；不出现“凭据名称”或全局凭据卡片。
- TicketProvider 可以被多条流水线复用。编辑时显示引用它的流水线；仍被引用时禁止删除，停用或修改连接参数前明确影响范围。

“新增流水线”先填写名称和稳定 ID，再使用连续五步布局，而不是让用户拼内部引用：

1. **工单入口**：选择或原地新增 TAPD/Redmine 接入，并设置匹配范围和优先级。
2. **定位源**：选择只读调查范围，并当场测试可读性；文案明确它只用于反查，不代表实际修改目录。
3. **修改工作区**：选择本机物理目录，立即显示自动识别结果、仓库根、remote 和健康状态；不再展示“代码类型”下拉框。
4. **验证**：配置必需验证步骤，或显式声明无自动测试及可审计替代门禁。
5. **最终动作**：始终可选 Patch；根据识别结果只开放 GitLab Push 或 GitHub PR。公共区填写提交人，Patch 配置输出目录，GitLab Push 无目标分支，GitHub PR 配置目标分支；支持多选动作。

流水线卡片必须一眼展示完整线路，而不是只展示中间两段：

```text
Haru TAPD → 客户端分析仓 → ClientLua GitLab → pytest → Patch + GitLab Push
```

卡片提供编辑、启用/停用、完整体检和“查看任务”。首次启动没有流水线时，任务空态只引导“新增第一条流水线”；流水线向导负责在内部补齐工单接入，不再要求用户先完成两个孤立步骤。

Web 可能从另一台电脑访问部署机，因此“本机目录”始终指 CodeFixer 服务端所在机器的目录，不是浏览器电脑的目录。目录选择器由服务端提供受限浏览 API，只允许浏览管理员配置的根目录并返回服务端规范路径；同时保留可粘贴路径输入。不得使用浏览器文件选择器制造“选中了客户端路径但服务端不可用”的假象。

日常设置页不得出现孤立的“路径”和“命令”卡片。物理路径在使用它的业务步骤中配置；命令仅在依赖失败的诊断详情出现。异步健康检查必须预留稳定高度，刷新期间保留上一份结果并标记检查中，避免卡片动态跳动。

## 21. 安全边界

- Scope/Discovery 只读定位源。
- Repair 只写隔离工作区。
- Review 只读候选修改快照或 no-change 报告及其证据。
- Agent 不接触工单、GitLab、GitHub 或仓库凭据。
- 最终动作由平台适配器使用凭据。
- 外部内容统一按不可信输入处理。
- 命令使用参数数组和允许列表，禁止由工单拼任意 shell。
- Path 必须 resolve 后验证仍在授权根目录。
- 附件有类型、大小和数量限制。
- 日志和 API 不回传 Token、Authorization header 或凭据文件内容。
- Web 第一版按可信内网单管理员设计，但至少支持 IP allowlist、CSRF 防护和危险操作二次确认。
- 删除任务默认只删除数据库索引和可安全删除的本地产物；已推送的 GitLab Commit/远程分支、已创建的 GitHub PR 和外部 Patch 不静默删除。

## 22. Windows 开发与 Linux 部署

### 22.1 目标形态

- Windows 用于本地开发和测试。
- Linux 部署机运行正式服务和 Agent CLI。
- React/Vite 构建产物由 FastAPI 同源托管。
- FastAPI/Uvicorn 对外监听 `9522`，健康检查地址为 `http://<部署主机>:9522/api/health`。
- 第一版使用一个 Uvicorn Worker；后台调度依赖 SQLite lease，不依赖多进程内存共享。
- 使用用户级 systemd 服务，`Restart=on-failure`。

### 22.2 运行时

- Python 版本和依赖通过 `pyproject.toml` 与 `uv.lock` 固定。
- Windows 和 Linux 分别创建 `.venv`，禁止复制虚拟环境。
- 前端使用锁文件执行 `npm ci` 和生产构建。
- Claude Code、Codex、OpenCode、Git、SVN 在部署用户下独立预检。
- CLI 登录状态属于部署机运行环境，不写入仓库。

### 22.3 路径

- 代码使用 `pathlib.Path`。
- 数据库不保存无法解释的 Windows/Linux混合路径。
- 流水线配置中的机器路径只进入本地覆盖。
- Agent 入口传执行机上真实绝对路径。
- 任务包若迁移到另一台机器，必须重新物化入口路径，不能直接沿用旧绝对路径。

### 22.4 进程与取消

- POSIX 使用独立进程组，取消和超时终止整个子进程树。
- Windows 使用等价的进程组/Job 控制。
- systemd 停止超时必须大于平台优雅清理窗口。
- 服务启动时先完成数据库迁移、目录权限和 Worker lease 恢复。
- systemd 的启动后检查必须访问本机 `9522` 的 health 与 readiness；端口占用时服务启动失败并给出占用诊断。
- 用户级服务需要确认 lingering，保证机器重启后无需交互登录即可启动。

### 22.5 发布链路

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

## 23. 可观测性与审计

每次任务必须可回答：

- 使用了哪个工单 snapshot。
- 使用了哪个流水线配置版本。
- 使用了哪个全局当前模型快照，以及解析到哪个 Runtime/实际模型。
- 使用了哪个定位源快照、BaselineCohort，以及基于哪个代码 revision/SHA。
- 每阶段实际由哪个 Runner/模型执行，并验证与 TaskRun 当前模型快照一致。
- Agent 实际耗时、费用和退出原因。
- 修改了哪些文件。
- 运行了哪些验证命令。
- Review 为什么通过或拒绝。
- 交付了哪些 Patch、GitLab Commit、GitHub PR。
- 哪些外部副作用需要清理。

事件通过 WebSocket 推送；数据库保存结构化事件，详细 stdout/stderr 写文件并按大小轮转。

建议指标：

- 收录到开始的等待时长。
- 各阶段 P50/P95 时长。
- Discovery 成功率。
- `no_change` 比例及复核通过率。
- 首轮修复通过率。
- 平均修复循环数。
- Patch / GitLab Push / GitHub PR 成功率。
- 部分交付率。
- 每任务 Agent 费用。
- LLM 槽利用率、排队时长和 lease 回收次数。
- BaselineCohort 成员数、合批命中率和每个 cohort 避免的重复 fetch/update 次数。

## 24. 第一版非目标

- 自动合并 MR/PR。
- 自动关闭或修改外部 Bug 工单。
- 多用户角色权限系统。
- 一个 Bug 同时修改多个修改工作区。
- 动态第三方插件市场。
- 分布式多节点 Worker。
- 让 Agent 自己持有平台 Token 或决定最终目标分支。
- 把 SVN/其他 Git 的冻结修改投递到另一个 GitLab/GitHub 仓库。
- Pipeline/阶段级多模型编排或自动模型路由。
- SVN 直接 commit。

这些能力以后可通过现有接口扩展，但第一版不为它们预写无实现的 UI 或状态。

## 25. 实现阶段

### 阶段一：骨架与配置

- FastAPI、SQLite migration、React/Vite。
- 默认配置、本地覆盖、Secret 引用。
- Pipeline 领域模型与完整语义迁移；流水线内联工单接入、定位源、修改工作区自动识别、验证、最终动作管理和 Preflight。
- 内部模型 Runtime 注册与 CLI binding。
- Linux systemd 与健康检查。

验收：Windows/Linux 均可启动，配置保存不污染 Git，Secret 不回传；用户只需选择一个当前模型。

### 阶段二：收单与任务控制

- Redmine/TAPD Adapter。
- 幂等收录和游标。
- 全自动/待我开始。
- 持久化队列、lease、取消与恢复。
- 全局 4 槽 LLM 池、同源 BaselineCohort 与崩溃后 lease 回收。
- 控制台和任务时间线。

验收：两种模式、模式切换和并发队列符合本文；四个 LLM 调用可并发，同源短时入队任务只刷新一次仓库并共享同一 SHA/revision。

### 阶段三：双 Agent 与无修改分支

- 固定路径 Artifact 协议。
- Scope Discovery、正式 Discovery、门禁、Repair。
- `no_change` 验证与独立 Review。
- Runner 统一协议。

验收：定位失败明确失败；已修复 Bug 能以证据健康完成；Agent 命令不包含拼接正文；所有 LLM 阶段使用同一 TaskRun 当前模型但保持独立会话。

### 阶段四：修改、验证与 Review

- Git/SVN 隔离工作区。
- 修改范围校验。
- 验证命令。
- 有界 Repair 循环。
- Freeze Change。

验收：同修改工作区并发任务共享 cohort 基线但互不污染，验证失败不会进入交付。

### 阶段五：最终动作

- 原子 Patch。
- GitLab commit 物化。
- Cherry-pick 多目标普通 MR。
- GitHub 多目标普通 PR。
- 远端交付失败后的托管 fallback Patch。
- 部分成功、幂等重试与失败清理。

验收：Patch、单分支 GitLab Push 与多目标 GitHub PR 消费同一冻结修改；GitLab Push 返回可打开的 Commit URL，GitHub 任一目标失败使任务失败并保留成功结果；动作只在匹配的自动识别仓库类型上可选；远端失败必有可下载的 fallback Patch，或明确记录其独立落盘失败。

### 阶段六：体验与生产验收

- 完整 Web 视觉与交互。
- 日志、指标、成本和产物清理策略。
- Linux 安装/升级/回滚文档。
- 真实工单灰度。

验收：全自动成功路径无需点击，所有异常都能在界面回答“哪里失败、为什么、产生了什么、怎么处理”。

## 26. 第一版总体验收

必须全部满足：

1. CodeFixer 核心和公共 UI 中没有任何业务项目专属判断。
2. Bug 反馈源、定位源和修改工作区在领域模型中明确分离，并在一条 Pipeline 中组装成完整线路；一个任务始终只绑定一条流水线和一个修改工作区。
3. 平台从物理目录自动识别 SVN、GitLab Git、GitHub Git 或其他 Git，不让用户手选代码类型。
4. 一个任务可同时配置 Patch 和与修改工作区匹配的 GitLab Push 或 GitHub PR；不匹配动作不能保存。
5. Agent 只收到固定入口路径，不收到平台拼接的大上下文。
6. Discovery 找不到或无法消歧时任务失败并给出结构化原因。
7. `no_change` 有当前基线证据并通过独立 Review。
8. Repair 修改越权时任务失败。
9. 验证和 Review 未通过时不能交付。
10. Patch、GitLab Push 与所有 GitHub PR 消费同一冻结修改和交付日志。
11. GitLab Push 只推送受控任务分支并返回 Commit URL，不创建 MR、不选择目标分支、不配置 assignee。
12. GitLab Push 失败或任一 GitHub 目标失败时任务失败；已成功外部结果保留，且可只重试失败交付。
13. 服务重启不会重复运行同一阶段、覆盖远端任务分支或重复创建 GitHub PR。
14. Windows 开发和 Linux 正式运行使用同一依赖锁，机器路径与 Secret 不进入公开仓库。
15. Web 能清楚展示阶段、尝试、失败、无修改证据、部分交付和外部副作用。
16. Web 与 API 的公开默认和正式部署端口统一为 `9522`。
17. 仓库无需任何本机参考项目或参考脚本即可构建、部署和理解；所有必需依赖都有机器可读声明及 Readiness/Preflight 结果。
18. 全局只有一个当前模型；Pipeline 与各 LLM 阶段没有独立模型选择；同一 TaskRun 的所有 LLM 阶段使用同一模型且保持独立会话。
19. 模型选择 UI 只呈现模型，不把 Agent Runtime 当作同级模型选项，也不要求用户管理 Profile。
20. 全局 LLM 并发池默认 4；没有任务在等待槽位时持有仓库锁或工作区 lease。
21. 同一修改工作区在默认 2 秒窗口内进入 `prepare` 的任务共享 leader 冻结的 SHA/revision，且每个任务仍使用独立可写工作区。
22. TAPD/Redmine 的 Token 或密码在反馈源表单内配置；日常设置页没有独立“凭据”“路径”“命令”概念。
23. GitLab Push / GitHub PR 失败不会伪装成成功；平台从同一冻结修改生成或复用 fallback Patch，默认目录不污染被修复仓库。
24. 配置、Prefab、场景和资源文件只要在修改工作区内且可安全处理，就能进入 Repair；工作区外、多工作区、策略禁止、专有二进制或外部系统修改在明确阶段以稳定失败码结束。
25. 主导航只有任务、流水线、设置；任务页是全部流水线共享的唯一账本，支持按流水线筛选且不复制任务列表。
26. “新增流水线”能在一个连续流程内完成工单入口、定位源、修改工程、验证和多个最终动作；没有独立“项目”或“工单来源”一级入口。
27. 公共 Schema、API、数据库字段、失败码和类型名统一使用 Pipeline 语义，不保留 Project 兼容别名。
28. 每个终态任务都有冻结的简洁结论；已修复任务从一级结论弹窗进入替换式二级交付弹窗，界面不叠加模态层。
29. 二级交付弹窗末尾展示来自 `change-manifest` 的完整修改路径清单；所有路径相对仓库根目录、可复制且不含分支名或本机绝对路径。
30. TAPD Bug、TAPD 其他单与 Redmine 的日志映射符合第 13.3 节；Patch 文件名、GitLab Commit 和默认 GitHub PR 标题复用同一冻结日志。

## 27. 规范标识与关键定义

### 27.1 命名规范

- 领域状态、阶段 ID、失败码和 JSON 枚举统一使用 `snake_case`。
- 配置文件字段统一使用 `camelCase`。
- Artifact 目录名使用阶段 ID 的连字符形式仅限文件系统展示；数据库和 Schema 仍保存规范 `snake_case` ID。
- UI 使用中文标签，但 API 永远返回规范 ID。

规范阶段 ID：

```text
prepare
scope_discovery
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

### 27.2 TaskRun 创建时点与当前模型生效时点

- 待我开始模式：用户点击开始时创建 TaskRun，并立即冻结 `execution_mode_snapshot`，状态为 `queued`。
- 全自动模式：工单通过唯一流水线路由后立即创建 TaskRun，状态为 `queued`。
- TaskRun 被 Worker 领取后才执行 `prepare`；`prepare` 获取当时最新工单、代码基线并解析当时的 `execution.currentModelId`。
- 当前模型一旦为该 TaskRun 解析完成，本次运行后续所有 LLM 阶段固定使用该模型；运行中全局切换不影响它。
- queued 但尚未开始执行的 TaskRun 不提前冻结模型，因此用户切换当前模型后，这些后续开始执行的 Run 使用新模型。
- 同一个 Task 同时最多存在一个 `queued` 或 `running` TaskRun。

### 27.3 输入指纹

`input_fingerprint` 是以下值按规范 JSON 排序后计算的 SHA-256：

- TicketSnapshot 内容 hash。
- 流水线有效配置 hash。
- LocalizationSource ID/内容版本。
- ModificationWorkspace identity、BaselineCohort ID 与冻结 revision/SHA。
- 阶段协议版本。
- TaskRun 当前模型快照：`currentModelId`、实际模型、Runtime 和影响调用语义的参数。
- 前序必需 Artifact 的 hash。

某项变化会使依赖它的安全检查点失效。Pipeline 不再通过阶段 Agent Profile 参与指纹；模型变化通过全局当前模型快照进入指纹。

### 27.4 安全检查点

安全检查点是：

- StageRun 状态为 `succeeded`。
- 输入指纹仍一致。
- 输出 Artifact 存在且 hash 一致。
- 不包含状态不确定的外部副作用。
- 后续配置没有要求从更早阶段重跑。

### 27.5 Change Version 与 Action Version

- 每次 `freeze_change` 成功生成新的单调递增 `change_version`。
- 同一冻结修改下，动作配置 hash 变化生成新的 `action_version`。
- Delivery 幂等键：

```text
task_run_id / change_version / action_id / action_version / target_key
```

### 27.6 三类基线

- `localization_snapshot`：定位 Agent 实际读取的只读定位源版本或内容 hash。
- `modification_base`：BaselineCohort 冻结、Repair 实际读取和修改的 Git/SVN revision。
- `delivery_target_head`：每个 GitHub PR 目标分支在 `pre_delivery_check` 记录的 HEAD；GitLab Push 改为记录计划任务分支与预期 Commit SHA。

三者必须分别记录，不能用一个 `base_branch` 字段混用。

## 28. 状态转换与工单生命周期

### 28.1 TaskRun 状态

TaskRun 使用：

- `queued`
- `running`
- `superseded`
- `completed`
- `failed`
- `canceled`

Task 顶层状态表示当前 active run；没有 active run 时表示最后一次业务状态。

### 28.2 主要转换表

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

### 28.3 工单 eligibility

每个 TicketProvider 把外部状态归一化为：

- `eligible`：仍应由 CodeFixer 处理。
- `ineligible`：已关闭、删除、转为非 Bug 或不再匹配过滤规则。

`prepare` 发现工单已经 ineligible 时：

- 当前 TaskRun 进入 `canceled`。
- `cancel_reason=ticket_ineligible_before_start`。
- 不调用 Agent，不判定 `no_change`。
- 后续重新打开时可以按当前执行模式创建新 TaskRun。

### 28.4 工单运行中更新

- `awaiting_start`：只更新 Task 当前视图；开始时使用最新 snapshot。
- `queued` 且尚未完成 prepare：prepare 使用最新 snapshot。
- `running` 且尚未完成 `pre_delivery_check`：阶段边界发现有效内容更新时，当前 TaskRun 进入 `superseded`。
  - 全自动：立即创建新 TaskRun 并排队。
  - 待我开始：Task 回到 `awaiting_start`。
- `freeze_change` 之后但尚未产生外部副作用：回到 `pre_delivery_check`，使旧 change version 失效。
- 任一最终动作已经产生副作用：当前 TaskRun继续对账和聚合；新工单版本在本次结束后按当前模式创建后续 TaskRun。

“有效内容更新”由 Provider 配置的字段集合决定，纯格式、订阅者或无关时间戳变化不触发 supersede。

### 28.5 已完成任务更新与重新打开

外部工单在 `completed`、`failed` 或 `canceled` 后出现新的有效版本时：

- 保存新 TicketSnapshot 和事件。
- 不改写旧 TaskRun。
- 未 ignored 时按当前模式创建新的 TaskRun 或进入 `awaiting_start`。
- 新运行重新执行 Discovery，不能沿用旧结论直接交付。

### 28.6 忽略与归档

- Ignore 是显式调度策略，保存操作者、原因和时间；阻止自动创建 TaskRun。
- Archive 是展示属性，只把任务移出默认列表。
- Ignore/Archive 不删除 Artifact，也不改变历史 TaskRun 结果。

## 29. V1 Artifact 数据契约

所有 JSON 都必须包含 `schema_version: 1`，并由平台在任务目录写入对应 `*.schema.json`。缺少必填字段、出现未知枚举或引用不存在的 Artifact 时，阶段以 `agent_protocol_invalid` 失败。

### 29.1 EvidenceRef

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

### 29.2 task-discovery.json

```json
{
  "schema_version": 1,
  "decision": "located|no_change_claim|unresolved",
  "localization_source": {
    "id": "pipeline-locator",
    "snapshot": "version or content hash"
  },
  "modification_workspace": {
    "id": "pipeline-workspace",
    "baseline_cohort_id": "cohort-id",
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
- `localization_source.id` 必须等于 TaskRun 冻结的定位源；`modification_workspace.id` 必须等于唯一修改工作区。
- `located` 必须证明候选路径如何映射到修改工作区，不能只返回定位源中的路径。

### 29.3 gate.json

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

### 29.4 no-change-report.json

```json
{
  "schema_version": 1,
  "reason": "already_fixed|not_present_on_current_baseline|not_applicable_to_workspace|upstream_fixed_during_run",
  "modification_workspace": {
    "id": "pipeline-workspace",
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
    "review_url": null,
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

### 29.5 repair-result.json

```json
{
  "schema_version": 1,
  "outcome": "changed|no_valid_diff|blocked",
  "summary": "本次修改说明",
  "module_name": "一键培养目标总览",
  "change_summary": "阵容卡片匹配度修复",
  "blocking_code": null,
  "blocking_evidence_ids": [],
  "changed_paths_claimed": ["relative/path"],
  "checks_requested": ["verification-step-id"],
  "limitations": []
}
```

平台自行采集真实 diff；`changed_paths_claimed` 只用于交叉检查。`module_name` 和 `change_summary` 只在 `outcome=changed` 时必填，分别是交付日志中的简短模块名和修改摘要，不得包含固定前缀、工单号、提交人或换行。`outcome=blocked` 时 `blocking_code` 必须是第 6.5 节允许的稳定失败码，且 `blocking_evidence_ids` 非空；`outcome=changed` 时两者必须为空。

### 29.6 verification.json

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

### 29.7 review.json

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

### 29.8 task-conclusion.json

```json
{
  "schema_version": 1,
  "outcome": "changed|no_change|blocked|failed",
  "headline": "已修复阵容卡片匹配度异常",
  "cause": "卡片排序直接使用角色战力，没有应用培养目标权重。",
  "resolution": "统一改用目标匹配度排序，并补充空阵容保护。"
}
```

`headline`、`cause`、`resolution` 都是面向任务一级弹窗的短文本：标题一句，原因和方案各不超过两句。`changed` 结论由最终 Repair 结果与 Review 共同约束并在 Review 通过后冻结；`no_change` 必须引用通过门禁的正向证据；修改前失败或取消由平台根据稳定 failure code 生成同结构的可读结论，不要求额外调用 LLM。验证状态、文件数量和交付链接不写进这三段，分别使用真实 verification、change manifest 和 delivery result 展示。

### 29.9 delivery-metadata.json

```json
{
  "schema_version": 1,
  "conventional_type": "fix",
  "technology_tag": "Lua",
  "ticket_key": "B1250062",
  "branch_label": "主干",
  "version_label": "v4.8",
  "module_name": "一键培养目标总览",
  "change_summary": "阵容卡片匹配度修复",
  "submitter_name": "黄永熙",
  "commit_subject": "fix：【Lua】【#B1250062】【主干】【v4.8】一键培养目标总览 - 阵容卡片匹配度修复  提交人：黄永熙",
  "patch_filename": "fix：【Lua】【#B1250062】【主干】【v4.8】一键培养目标总览 - 阵容卡片匹配度修复  提交人：黄永熙.patch"
}
```

平台根据工单类型、流水线配置和已 Review 的 Repair 字段拼装并冻结；Agent 不直接提供 `commit_subject` 或 `patch_filename`。文件名净化后值必须一并冻结，保证普通 Patch、fallback Patch 和重试一致。

### 29.10 change-manifest.json

```json
{
  "schema_version": 1,
  "change_version": 1,
  "modification_workspace": {
    "id": "pipeline-workspace",
    "baseline_cohort_id": "cohort-id",
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

`source_commits` 可为空。GitLab Push / GitHub PR 的 delivery commits 属于动作结果，不改变本对象。`files[].path` 是二级交付弹窗“修改文件”的唯一事实来源，必须是相对修改仓库根目录的规范化路径，不带分支名。

### 29.11 delivery result

`DeliveryActionRun`：

```json
{
  "schema_version": 1,
  "action_id": "gitlab-push",
  "action_version": 1,
  "change_version": 1,
  "type": "patch|gitlabPush|githubPr|fallbackPatch",
  "status": "pending|running|reconciling|succeeded|failed|skipped",
  "outcome": "success|partial_success|failure|no_change",
  "triggeredBy": [],
  "reusedActionId": null,
  "delivery_commits": [
    {
      "sha": "commit sha",
      "subject": "冻结的标准交付日志",
      "remote_branch": "codefixer/B1250062/run-short-id",
      "commit_url": "https://gitlab.example/group/project/-/commit/sha",
      "branch_url": "https://gitlab.example/group/project/-/tree/codefixer/B1250062/run-short-id"
    }
  ],
  "targets": [],
  "failure": null
}
```

`DeliveryTargetRun` 只供仍具有目标分支语义的 `githubPr` 使用；`gitlabPush` 不创建 target row：

```json
{
  "target_key": "target-branch",
  "idempotency_key": "stable key",
  "status": "pending|running|reconciling|succeeded|failed",
  "step": "preflight|creating_source_branch|cherry_picking|creating_review|cleaning_up|done",
  "checkpoint": "planned|branch_intent|branch_confirmed|cherry_pick_intent|cherry_pick_confirmed|review_intent|review_confirmed",
  "source_branch": null,
  "target_branch": "target-branch",
  "review_kind": "githubPr",
  "review_number": null,
  "review_url": null,
  "failure": null
}
```

### 29.12 final-result.json

```json
{
  "schema_version": 1,
  "task_id": "task-id",
  "task_run_id": "run-id",
  "status": "completed|failed|canceled|superseded",
  "result": "changed|no_change 或 null",
  "delivery_outcome": "success|partial_success|failure|fallback_available|fallback_failed 或 null",
  "change_version": "整数或 null",
  "summary": "用户可读总结",
  "conclusion_artifact": "task-conclusion.json 或 null",
  "delivery_metadata_artifact": "delivery-metadata.json 或 null",
  "failure": null,
  "artifacts": [],
  "side_effects": []
}
```

`change_version` 在 no-change、freeze_change 前失败、取消或 superseded 的运行中为 null；只有 `completed` 才允许 `result` 非 null。

## 30. 交付事务与崩溃恢复

### 30.1 无副作用屏障

在启动任何最终动作前，平台一次性完成共享不变量检查：

- 工单版本检查。
- LocalizationSource 与 ModificationWorkspace 基线检查。
- `freeze_change` 文件、hash、manifest 与配置快照一致性检查。

共享检查任一项失败时没有动作可以开始。此时仍允许回到 Repair/Verify/Review 或转为有证据的 `no_change`。

共享检查通过后，每个动作独立检查并记录：Patch 输出目录；GitLab remote 与受控分支 push 权限；GitHub remote、目标分支、PR 创建能力和本机认证；每个 GitHub 目标的 `delivery_target_head` 以及 GitLab Push 的预期 Commit SHA。动作 Preflight 失败时该动作/目标直接进入终态 `failed`，其他通过检查的动作继续执行。未开始的失败动作没有外部副作用，但只要 `freeze_change` 存在且失败的是远端动作，仍按第 14.3 节生成 fallback。

流水线本来就未通过保存时 Preflight 时不得启动 TaskRun，也不存在可供 fallback 的冻结修改。运行期间才出现的动作依赖失败则属于交付失败。普通 Patch 若已通过自己的 Preflight，必须正常执行；若失败远端动作最终需要 fallback，先尝试复用这个普通 Patch。

### 30.2 动作聚合

- 全部必需动作 succeeded：`completed/changed`。
- 任一必需动作 failed 且没有必需动作 succeeded：先得到 `failed/failure`；若失败中包含远端动作，fallback 成功后改为 `failed/fallback_available`，fallback 也失败则为 `failed/fallback_failed`。
- 任一必需动作 failed 且至少一个必需动作 succeeded：`failed/partial_success`；fallback 只追加 `fallbackAvailable=true`。
- 至少一个必需动作成功时，即使 fallback 失败也保持 `failed/partial_success`，额外记录 `fallbackFailed=true`；原远端失败保持主失败。
- 任一动作 reconciling：TaskRun 保持 running/reconciling，不得先判成功或失败。
- 所有动作因 `no_change` skipped：`completed/no_change`。

动作开始后，兄弟动作不会因某个动作失败而被强杀；平台等待已调度的必需动作得到确定结果，再按需要生成或复用唯一 fallback Patch，最后只基于必需动作计算任务成功与否，并把 fallback 状态作为恢复信息附加。

### 30.3 外部调用检查点

每个外部副作用使用 outbox 风格：

1. 在数据库事务中写入 intent、幂等键、请求摘要和预期对象。
2. 提交事务。
3. 发起外部调用。
4. 在新事务中保存确认结果。

进程在第 3、4 步之间崩溃时，状态进入 `reconciling`，不能重新发起创建请求。

### 30.4 GitLab / GitHub 对账

恢复或网络结果不确定时：

1. 先查询计划中的目标临时分支，并核对其 HEAD 是否与本地 intent 记录一致。
2. GitLab 以 push 返回并已落库的 MR URL 为确认事实；远端分支存在但 MR URL 未确认时，以 `gitlab_result_uncertain` 失败并禁止重复 push。
3. GitHub 通过已认证的 `gh pr view/list` 按 delivery key、源分支和目标分支查询所有状态的 PR。
4. 找到唯一匹配对象时接管并继续。
5. 找到多个匹配对象时以对应的 `gitlab_result_ambiguous` / `github_result_ambiguous` 失败，禁止再创建。
6. 托管平台查询不可用或认证失效时保持 reconciling；超过对账预算后以对应的 `*_result_uncertain` 失败，仍禁止重复创建。
7. 只有适配器能够完整证明不存在对应外部对象时，才允许新建；GitLab push 结果不确定时不能满足此条件。

临时分支名虽然复刻 `cherry-pick-<sha>` 规则，但所有权由数据库 intent、pipeline、目标分支、创建时间和分支 HEAD 联合证明。不能仅凭名称删除分支。

推送前先持久化预期远端分支、GitHub 目标 HEAD、冻结 diff hash 和预期 Commit 元数据。若 push 成功但确认结果未落库，平台只按数据库 intent 对账同一修改工作区的 remote branch；ref 内容不同即失败，禁止覆盖。GitLab 任务分支在成功后保留供人工 Cherry-pick；GitHub 临时分支按流水线保留策略清理。清理失败只设置 `cleanup_required`，不得改写已经确认的外部结果。

### 30.5 Patch 对账

- 写入前记录 intent、目标路径和预期 hash。
- 临时文件 fsync 后原子改名。
- 恢复时目标存在且 hash 相同则接管为成功。
- 目标存在但 hash 不同且不允许覆盖时失败。

### 30.6 交付后的配置变化

配置热重载不改变当前 ActionRun。修改目标分支、模板或动作类型后：

- 旧成功动作保持历史成功。
- 用户若要使用新配置再次交付，创建新 action version。
- 平台明确展示这会产生新的外部对象，不把它伪装成普通重试。

## 31. 分阶段文件与权限矩阵

| 阶段 | 模型 / 会话 | 必须自行读取 | 可访问代码 | 写入范围 |
|---|---|---|---|---|
| `scope_discovery` | TaskRun 当前模型 · 独立会话 | ticket、pipeline policy、localization manifest、附件清单 | 定位源只读视图、受控知识工具 | scope-discovery 输出目录 |
| `discovery` | TaskRun 当前模型 · 独立会话 | ticket、pipeline policy、localization/workspace manifest、附件清单、scope-discovery 产物 | 定位源只读视图与修改工作区只读基线视图 | discovery 输出目录 |
| `no_change_verify` | TaskRun 当前模型 · 独立只读会话 | ticket、Discovery、workspace manifest | 修改工作区只读基线视图、验证工具 | no-change 输出目录 |
| `repair` | TaskRun 当前模型 · 独立写会话 | ticket、Discovery、pipeline policy、workspace manifest、上轮反馈 | 唯一隔离工作区 | 隔离工作区与 repair 输出目录 |
| `review(mode=change)` | TaskRun 当前模型 · 独立只读会话 | ticket、Discovery、候选 diff、verification | 候选工作区只读视图 | review 输出目录 |
| `review(mode=no_change)` | TaskRun 当前模型 · 独立只读会话 | ticket、Discovery、no-change report、证据索引 | 修改工作区只读基线视图 | review 输出目录 |

附件正文不拼入 Prompt。平台先把允许的附件冻结到 snapshot 目录，入口文件列出路径、类型、大小和 hash，由 Agent 按需读取。

知识服务响应不预取后拼接。Agent 通过受控 KnowledgeProvider 工具查询，平台保存查询参数、响应 Artifact 和 hash。

`entry.md` 本身由平台模板生成并版本化；StageRun 保存模板版本。Agent 不能修改入口文件和前序 Artifact。
