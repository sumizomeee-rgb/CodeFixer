# CodeFixer 工程就绪规范

> 文档状态：V2.1 规范性补充
> 最后更新：2026-08-12
> 适用范围：CodeFixer 第一版正式施工前的工程基线
> 上位文档：`docs/design-spec.md`
>
> 本文把“产品与技术设计已确定”转换为“仓库可以长期、可回归地施工”的工程约束。
> 与 `design-spec.md` 冲突时，仅在本文明确覆盖的工程组织、设计系统、测试门禁和实施顺序范围内，以本文为准；产品语义、领域状态、Artifact 协议、幂等与交付语义仍以 `design-spec.md` 为准。

## 1. 目的

CodeFixer 进入功能施工前必须先冻结四类基础设施：

1. 仓库目录与依赖方向。
2. Web 设计系统与交互语法。
3. 测试、回归和视觉基线。
4. 开发、CI、自测和发布门禁。

目标不是继续扩张产品范围，而是让后续 Agent 或工程师能够端到端施工，而不在功能开发过程中反复重构仓库骨架、UI 基础组件和测试策略。

## 2. 开工判定

只有以下条件全部成立，第一版 Feature Coding 才视为 `ready_for_implementation`：

- `docs/architecture/repository-structure.md` 已生效。
- `docs/design/design-system.md` 已生效。
- `docs/testing/test-strategy.md` 已生效。
- 后端、前端、contracts、tests、deploy 的根目录按规范建立。
- Backend 可启动并暴露 `/api/health` 与 `/api/readiness`。
- Frontend 可生产构建，并由 Backend 同源托管。
- SQLite migration harness 可在空数据库和已有数据库上运行。
- pytest、Vitest Browser Mode、Playwright 均能在 CI 形态运行。
- 至少一个 Scenario fixture 能从空环境跑通到预期终态。
- 至少一个关键页面具有视觉 golden baseline。
- 代码格式化、类型检查、静态检查和测试命令被统一为稳定脚本入口。
- Windows 开发与 Linux CI/部署不依赖某台机器的绝对路径或 Secret。

Phase 0 不要求接通真实 Redmine、TAPD、GitLab 或真实 Agent；允许使用 Fake Adapter 和 deterministic fixture。

## 3. 工程原则

### 3.1 领域核心不依赖具体平台

`domain` 与 `application` 不得 import Redmine、TAPD、GitLab、Claude、Codex、OpenCode、Git CLI 或 SVN CLI 的具体实现。

具体平台只允许出现在 `adapters` 与 `infrastructure`。

禁止在 orchestration 主状态机中增加：

```python
if provider == "tapd":
...
if source == "svn":
...
if agent == "claude":
...
```

核心通过稳定接口和 capability 驱动。

### 3.2 协议是一等公民

所有跨阶段 JSON、配置 Schema、API 公开 DTO 与稳定枚举属于 `contracts`。

以下内容不得只以 Python/TypeScript 私有类型存在：

- TicketSnapshot
- task-discovery
- gate
- no-change-report
- repair-result
- verification
- review
- change-manifest
- delivery result
- final-result
- public API error envelope
- config schema

协议变更必须显式增加 schema/protocol version，并有兼容或迁移测试。

### 3.3 数据事实与 UI 展示分离

数据库状态、领域结果和失败码是事实；UI 标签、颜色、图标、动效只是映射。

UI 不得创造后端不存在的伪状态，不得通过视觉“猜测”任务成功。

### 3.4 外部副作用必须可对账

任何可能产生 Patch、远程 ref、GitLab branch、MR 或费用的动作，都必须先有本地 intent/checkpoint，再执行外部调用，之后确认结果。

测试环境必须能够模拟“调用成功但本地确认前进程崩溃”。

### 3.5 默认可测试

新模块设计时必须能注入：

- clock
- id generator
- filesystem root
- subprocess runner
- HTTP transport
- provider/adapter
- external service fake

领域逻辑不得通过全局单例、隐式当前目录或真实网络才能测试。

## 4. Phase 0：Engineering Foundation

Phase 0 是正式阶段一之前的强制阶段。

### 4.1 仓库骨架

建立并提交：

```text
backend/
frontend/
contracts/
tests/
deploy/
scripts/
docs/
```

详细布局见 `docs/architecture/repository-structure.md`。

### 4.2 Backend 最小纵切

实现最小可运行链路：

```text
config load
  → database migration
  → FastAPI startup
  → /api/health
  → /api/readiness
  → SPA fallback
  → graceful shutdown
```

要求：

- 不包含真实业务特定判断。
- 配置默认层、本地覆盖层和 Secret 引用层可加载。
- `storage.dataRoot` 解析规则符合主 SPEC。
- SQLite 启用 WAL。
- 日志有结构化基础字段和 request/task correlation 能力。

### 4.3 Frontend 最小纵切

实现：

- AppShell。
- 明/暗主题。
- Design Tokens。
- 全局模式控制器的静态/Mock 状态。
- StageRail。
- TaskCard。
- FailureSurface。
- Empty/Loading/Error skeleton。
- 响应式桌面布局。

此阶段不追求完整业务页面，但基础组件必须已经体现 CodeFixer 视觉语言，禁止先搭 generic admin template 再在阶段六整体换皮。

### 4.4 Test Harness

Phase 0 必须同时建立：

- backend unit test harness。
- contract/schema test harness。
- integration temp database。
- fake Git repository helper。
- fake SVN working copy helper；若 CI 无 SVN，则先提供 capability skip，并在 Linux integration job 启用。
- fake TicketProvider。
- fake AgentRuntime。
- fake GitLab service/API。
- scenario runner。
- frontend component test harness。
- Playwright E2E。
- Playwright visual regression。

### 4.5 CI 基线

第一版 CI 至少分为：

```text
lint
typecheck
backend-unit
backend-contract
backend-integration
frontend-unit
frontend-browser
e2e
visual
build
```

允许基于耗时合并 job，但逻辑门禁不能消失。

PR 必须通过快速门禁；真实外部服务测试不进入普通 PR blocking job。

## 5. 实施阶段覆盖

主 SPEC 第 24 节实施阶段调整为：

### Phase 0：工程基础与设计系统

- 仓库目录与依赖方向。
- Contracts 基线。
- Design System 与关键基础组件。
- Test Harness 与第一批 Scenario。
- CI、构建、健康检查与最小部署骨架。

验收：达到本文第 2 节全部开工条件。

### 阶段一：骨架与配置

沿用主 SPEC，但所有新增代码必须落入已冻结目录；配置页面使用既有 Design System，不另造组件体系。

### 阶段二：收单与任务控制

除主 SPEC 验收外，新增：

- provider contract tests。
- 模式切换 scenario。
- lease/restart scenario。
- 控制台与任务时间线 E2E。

### 阶段三：双 Agent 与无修改分支

新增：

- AgentRuntime contract suite。
- Discovery protocol golden fixtures。
- `no_change` positive-evidence regression。
- prompt/entry 文件不得包含拼接正文的测试。

### 阶段四：修改、验证与 Review

新增：

- Git worktree isolation scenarios。
- SVN isolation/lease scenarios。
- unauthorized change scenarios。
- verify → repair → review bounded-loop scenarios。
- candidate/freeze hash regression。

### 阶段五：最终动作

新增：

- Patch atomic/idempotent scenarios。
- GitLab materialization/cherry-pick scenarios。
- partial success。
- crash between external call and confirmation。
- reconciliation without duplicate MR。
- delivery-only retry。

### 阶段六：体验与生产验收

阶段六不是第一次做视觉，而是：

- 动效节奏与细节 polish。
- 跨页面视觉一致性。
- 性能、可访问性和极端数据密度优化。
- 完整 visual golden review。
- 真实工单灰度。
- 安装、升级、回滚与故障演练。

## 6. Definition of Done

任何 Feature 不以“代码写完”作为完成。

至少满足：

- 行为符合 SPEC。
- 公开协议有 Schema/类型。
- 关键领域逻辑有 unit/contract test。
- 涉及跨组件流程时有 integration 或 scenario coverage。
- 用户可见关键路径有 E2E。
- 视觉关键面有 visual baseline 或明确说明不适合视觉快照。
- 新失败码可在 UI 显示用户可读摘要。
- 外部副作用路径有幂等与 recovery 测试。
- 文档与配置示例同步。
- 不产生 machine-specific path/secret。
- lint/typecheck/test/build 全部通过。
- 自测记录中列出已验证路径与已知限制。

## 7. Regression Gate

### 7.1 PR Blocking

普通 PR 至少阻断于：

- formatting/lint。
- typecheck。
- backend unit + contract。
- frontend unit/component。
- 受影响 Scenario。
- build。

影响状态机、Artifact、Scheduler、Delivery、Design System 时必须额外运行对应完整回归集合。

### 7.2 Main/Nightly

Main 或 nightly 运行：

- 全 Scenario Regression Suite。
- Linux E2E。
- visual regression。
- browser matrix 的精选关键路径。
- Git/SVN workspace isolation。
- crash/restart/reconciliation。
- performance smoke。
- accessibility smoke。

### 7.3 Release Candidate

发布候选必须：

- 全量 regression 通过。
- 无未解释 visual diff。
- migration upgrade + rollback rehearsal 通过。
- Linux systemd install/restart/health/readiness 通过。
- 用 Fake 外部系统完成完整 changed/no_change/failed/partial_delivery 四类旅程。
- 至少完成一组受控真实环境灰度后才能标记生产 ready。

## 8. 视觉质量门禁

视觉不是验收末尾的主观加分项。

关键页面必须具备：

- 明色与暗色主题。
- 1440×900 主桌面 baseline。
- 至少一个窄桌面/小窗口布局检查。
- 空、加载、正常、失败、部分交付、长文本、超多阶段/attempt 状态。
- reduced-motion 行为。
- 键盘 focus 可见。
- 关键对比度与语义可读性。

视觉快照只覆盖稳定、可解释的界面；时间、随机数、实时 duration 等易变内容在 snapshot 模式下使用固定 clock/fixture。

Golden 更新必须作为显式评审行为，不允许测试失败时自动无脑覆盖。

## 9. Scenario Registry

Scenario ID 稳定，不因文件重命名改变。

V1 最低集合：

```text
SCN-001 changed_patch_success
SCN-002 changed_gitlab_single_target_success
SCN-003 changed_patch_and_multi_mr_success
SCN-004 discovery_unresolved
SCN-005 discovery_source_mismatch
SCN-006 no_change_already_fixed
SCN-007 no_change_insufficient_evidence
SCN-008 repair_unauthorized_change
SCN-009 verification_failed_then_repair_success
SCN-010 review_needs_repair_then_success
SCN-011 repair_cycle_exhausted
SCN-012 base_changed_before_delivery
SCN-013 gitlab_partial_success
SCN-014 crash_during_repair
SCN-015 crash_after_mr_remote_success_before_local_confirm
SCN-016 restart_reconcile_no_duplicate_mr
SCN-017 cancel_running_agent
SCN-018 two_tasks_same_git_repo_isolated
SCN-019 svn_exclusive_lease
SCN-020 delivery_only_retry_failed_target
SCN-021 ticket_updated_supersedes_run
SCN-022 no_change_upstream_fixed_during_run
```

每个 Scenario fixture 至少定义：

- ticket snapshot。
- project/config snapshot。
- repository fixture。
- external service behavior。
- expected stage timeline。
- expected terminal status/result。
- expected artifacts。
- expected side effects。
- expected retry/reconciliation behavior。

## 10. 冻结策略

以下内容在 Phase 0 完成后视为第一版冻结接口，除非通过明确架构变更：

- 顶层源码目录。
- domain/application/adapters/infrastructure 依赖方向。
- Artifact/Contract 存放位置。
- Design Token 命名层。
- Scenario ID 规则。
- CI 稳定命令入口。
- visual baseline 环境。
- `9522` 正式端口。
- 主 SPEC 的规范阶段 ID。

允许后续扩展组件和 Adapter，但不得绕过这些边界。

## 11. 端到端施工要求

当进入正式施工后，可以由单个 Agent 或多个 Agent 端到端实现，但每一轮必须遵守：

1. 先读取主 SPEC、本文及对应目录/测试/设计规范。
2. 只实现当前阶段范围。
3. 每完成一个纵切，立即补测试并运行。
4. UI 功能完成时同时完成交互态，不把视觉全部延期。
5. 任何外部副作用功能先写 Fake/Scenario，再接真实 Adapter。
6. 阶段结束前执行该阶段完整 regression gate。
7. 只有测试、构建、视觉与文档均达到 DoD 才进入下一阶段。

最终交付不是“仓库里有代码”，而是：

- Windows 开发可运行。
- Linux 正式部署可运行。
- Web 视觉达到 Design System。
- changed/no_change/failed/partial_delivery 核心路径可演示。
- 自动回归可重复运行。
- 重启/失败/重试不会制造重复外部副作用。
- 安装、配置、升级、故障处理文档完整。
