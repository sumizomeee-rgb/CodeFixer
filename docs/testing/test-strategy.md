# CodeFixer 测试、回归与自测策略

> 文档状态：V1.1
> 最后更新：2026-08-12
> 关联：`docs/design-spec.md`、`docs/engineering-readiness-spec.md`

## 1. 测试目标

CodeFixer 的测试重点不是单纯提高覆盖率，而是证明以下事实长期不被破坏：

1. 状态机不会把失败伪装成成功。
2. `no_change` 必须有正向证据。
3. 多任务不会污染同一修改源。
4. 重试、重启和网络不确定不会重复创建 Patch/MR。
5. Agent 不能突破路径和权限边界。
6. Verify/Review 不通过时不能交付。
7. Patch 与所有 MR 消费同一冻结修改。
8. UI 能准确表达后端事实。
9. 已批准的视觉与交互不会被后续修改意外破坏。
10. Windows 开发与 Linux 正式环境保持同一产品语义。

测试体系必须覆盖“正常路径 + 失败路径 + 崩溃恢复 + 外部结果不确定”。

## 2. 测试分层

### 2.1 Unit

目的：快速验证纯规则。

范围：

- domain state transition。
- route resolution。
- input fingerprint。
- failure classification。
- retry policy。
- action aggregation。
- path allow/deny。
- version constraint。
- idempotency key。
- no-change gate。
- config merge。

特点：

- 不访问网络。
- 不启动真实 subprocess。
- 不依赖真实时间。
- 单测通常 <100ms。

### 2.2 Contract

目的：证明接口和协议稳定。

范围：

- Artifact JSON Schema。
- Adapter port contract。
- AgentRuntime contract。
- TicketProvider contract。
- ModificationSourceProvider contract。
- FinalActionProvider contract。
- API error envelope。
- config schema。
- generated TypeScript/Pydantic 一致性。

每个同类 Adapter 必须通过同一套 contract suite。

例如 Claude/Codex/OpenCode 必须共同满足：

```text
start
timeout
cancel
non-zero exit
structured result
usage
working directory
entry file handoff
process cleanup
```

差异只允许在 Adapter 内部。

### 2.3 Integration

目的：验证多个真实基础设施组件组合。

范围：

- FastAPI + SQLite。
- migration。
- DB lease + recovery。
- real local Git CLI。
- real local SVN CLI。
- filesystem atomic write。
- process-group cancellation。
- fake HTTP Ticket/GitLab server。
- SPA static hosting。

Integration 不默认请求公司真实服务。

### 2.4 Scenario Regression

这是 CodeFixer 最重要的产品语义回归层。

Scenario 不是一个函数测试，而是一个完整任务故事。

输入包括：

- TicketSnapshot。
- Project/config。
- fake/real local repository。
- Agent scripted behavior。
- provider behavior。
- GitLab behavior。
- crash injection point。

输出断言：

- Stage timeline。
- TaskRun terminal state。
- business result。
- artifacts。
- hashes。
- side effects。
- retries。
- reconciliation。
- DB facts。

### 2.5 Frontend Component

目的：验证组件在真实浏览器中的行为。

使用 Vitest Browser Mode。

重点：

- loading/empty/error。
- keyboard。
- focus。
- dialog。
- StageRail 状态。
- ExecutionModeController。
- TaskCard。
- FailureSurface。
- NoChangeSurface。
- long content。
- theme。

不测试内部 state variable；从用户可见行为断言。

### 2.6 E2E

使用 Playwright。

测试浏览器真实用户路径：

- 切换模式。
- 开始任务。
- 查看实时阶段。
- 取消。
- Retry/Rerun。
- 查看 Diff/Artifact。
- 部分交付。
- 配置 Preflight。
- Theme。
- WebSocket reconnect。

E2E 使用 deterministic fake backend 或完整本地 stack；普通 CI 不依赖公司内网。

### 2.7 Visual Regression

Playwright screenshot baseline。

目的：保护已经人工批准的视觉质量。

它不是 CSS unit test，也不是“像素必须永远不变”。

覆盖：

- 关键页面。
- 关键状态。
- Light/Dark。
- 典型 viewport。
- 复杂数据密度。

时间、随机 ID、duration、动画使用 fixture/fixed clock 稳定化。

### 2.8 Real-System Smoke

连接真实 Redmine/TAPD/GitLab/Agent 的测试属于受控 smoke，不进入每次 direct-main 提交的默认快速阻断门禁。

运行：

- 手工触发。
- 受保护 CI 环境。
- release candidate。
- 灰度机器。

必须使用专用测试 project/issue/branch，不允许拿生产 Bug 做破坏性测试。

## 3. 测试工具

Backend：

```text
pytest
pytest-asyncio
coverage
```

Frontend：

```text
Vitest
Vitest Browser Mode
Playwright
```

可选辅助：

- JSON Schema validator。
- property-based testing，用于状态/路径/幂等纯函数。
- fake HTTP service。
- import boundary checker。

工具可调整，但测试层级和门禁语义不能因换工具消失。

## 4. Determinism

所有自动测试默认可重复。

需要注入：

```text
FixedClock
DeterministicIdFactory
TempDataRoot
FakeAgentRuntime
FakeTicketProvider
FakeGitLab
ScriptedSubprocess
```

测试不得依赖：

- 本机时区。
- 当前真实日期。
- 本机用户名。
- 当前工作目录。
- 随机可用端口的固定值。
- 未声明的环境变量。
- 测试执行顺序。

临时路径通过测试 fixture 创建。

## 5. Scenario Fixture 格式

建议每个 Scenario 是目录：

```text
tests/scenarios/SCN-015-crash-after-mr-remote-success/
├─ scenario.yaml
├─ ticket.json
├─ project.yaml
├─ repo/
├─ agent-script.yaml
├─ gitlab-script.yaml
├─ expected/
│  ├─ timeline.json
│  ├─ final-result.json
│  ├─ side-effects.json
│  └─ artifacts.json
└─ README.md
```

`scenario.yaml` 示例：

```yaml
id: SCN-015
name: crash_after_mr_remote_success_before_local_confirm

initial:
  executionMode: automatic

faults:
  - at: gitlab.create_mr.after_remote_success
    action: crash_process

expected:
  firstRun:
    taskStatus: running
    deliveryStatus: reconciling
  afterRestart:
    taskStatus: completed
    result: changed
    mrCreateCallCount: 1
```

Scenario runner 可以把同一套 fixture 参数化到不同 Adapter 或 OS capability。

## 6. V1 必测 Scenario

### 6.1 正常交付

```text
SCN-001 changed_patch_success
SCN-002 changed_gitlab_single_target_success
SCN-003 changed_patch_and_multi_mr_success
```

断言：

- verify/review 都通过。
- freeze hash 稳定。
- delivery 只消费 freeze。
- result=changed。

### 6.2 Discovery / Routing

```text
SCN-004 discovery_unresolved
SCN-005 discovery_source_mismatch
```

断言：

- 不进入 Repair。
- 不产生交付。
- failure evidence 可读。

### 6.3 No Change

```text
SCN-006 no_change_already_fixed
SCN-007 no_change_insufficient_evidence
SCN-022 no_change_upstream_fixed_during_run
```

特别断言：

- “搜索不到”不能完成。
- approved Review 必需。
- 无外部 delivery side effect。

### 6.4 Repair / Verify / Review

```text
SCN-008 repair_unauthorized_change
SCN-009 verification_failed_then_repair_success
SCN-010 review_needs_repair_then_success
SCN-011 repair_cycle_exhausted
```

断言：

- 越权修改被平台真实 diff 发现。
- repair attempts 不超过预算。
- 旧 candidate 被 superseded。

### 6.5 Baseline / Ticket Drift

```text
SCN-012 base_changed_before_delivery
SCN-021 ticket_updated_supersedes_run
```

断言：

- 不对漂移 baseline 盲目交付。
- 新 TaskRun 与旧证据分离。

### 6.6 Delivery / Recovery

```text
SCN-013 gitlab_partial_success
SCN-015 crash_after_mr_remote_success_before_local_confirm
SCN-016 restart_reconcile_no_duplicate_mr
SCN-020 delivery_only_retry_failed_target
```

断言：

- partial success 的成功 MR 保留。
- task 仍 failed。
- retry 不重建成功目标。
- create MR 不重复。

### 6.7 Process / Concurrency

```text
SCN-014 crash_during_repair
SCN-017 cancel_running_agent
SCN-018 two_tasks_same_git_repo_isolated
SCN-019 svn_exclusive_lease
```

断言：

- 子进程树终止。
- workspace 清理。
- 同 Git repo worktree 隔离。
- SVN 不安全布局使用 lease。

## 7. Fault Injection

必须提供可控故障点，不靠“拔网线碰运气”。

至少支持：

```text
before_stage_start
after_stage_intent
after_agent_process_start
after_agent_output_before_db_commit
during_verification
after_freeze_write_before_db_confirm
after_patch_rename_before_confirm
after_gitlab_branch_create
after_gitlab_cherry_pick
after_gitlab_mr_remote_success_before_local_confirm
during_cleanup
lease_heartbeat_loss
```

Fault Injection 仅测试环境启用。

每个存在外部副作用的关键 checkpoint 至少有一条 crash/recovery 测试。

## 8. Database Tests

必须测试：

- fresh migration。
- WAL。
- unique constraints。
- one active TaskRun。
- one valid lease owner。
- delivery idempotency unique key。
- transaction rollback。
- restart lease recovery。
- cursor persistence。

Migration 发布后不可篡改历史脚本。

升级测试至少保留最近一个正式版本 fixture；随着版本增长逐步保留关键长期 fixture。

## 9. Git Tests

真实 Git CLI integration 使用临时本地 repo，不需网络。

覆盖：

- base SHA capture。
- worktree create/remove。
- two concurrent worktrees。
- add/modify/delete/rename。
- diff capture。
- dirty source refusal。
- branch/ref collision。
- change reapply。
- conflict。
- commit materialization。

不允许 unit test 把所有 Git 行为都 mock 后宣称 worktree 已验证。

## 10. SVN Tests

在具备 SVN CLI 的 CI job 使用本地 file repository 或本地 server fixture。

覆盖：

- checkout/update。
- revision capture。
- status/diff。
- add/delete。
- revert/cleanup。
- independent working copies。
- exclusive lease fallback。

没有 SVN CLI 的开发机可 skip integration，但 release CI 不可整体缺失 SVN 验证，因为 V1 明确支持 SVN。

## 11. Agent Runtime Tests

每个 Agent Adapter 分两层。

### 11.1 Scripted CLI

测试创建一个假 CLI executable，模拟：

- JSON/stream output。
- stderr。
- timeout。
- exit code。
- child process。
- huge output。
- invalid protocol。
- cancellation。
- usage。

这层属于 direct-main 提交前阻断门禁。

### 11.2 Real CLI Smoke

测试实际安装的 Claude Code/Codex/OpenCode：

- version preflight。
- non-interactive session。
- entry-file instruction。
- read-only/write permission。
- timeout/cancel。

不要求每次 main 施工提交消耗真实模型额度。

## 12. Ticket Provider Tests

所有 TicketProvider 共同 contract：

- stable external ID。
- incremental cursor。
- latest detail fetch。
- comments。
- attachments metadata。
- eligibility。
- meaningful update detection。
- error normalization。
- rate limit。

Redmine/TAPD 使用 fake HTTP/API response fixtures 验证 mapping。

真实环境 smoke 只确认鉴权和基础字段，不修改工单。

## 13. GitLab Delivery Tests

FakeGitLab 必须模拟：

- project。
- branches。
- commits。
- temporary branch。
- cherry-pick。
- MR。
- pagination。
- rate limit。
- timeout。
- request succeeds but response lost。
- duplicate candidate objects。
- cleanup failure。

最关键不变量：

```text
remote create succeeded + local confirm lost
→ restart reconcile
→ create count 仍为 1
```

真实 GitLab smoke 使用专用测试项目。

## 14. Patch Tests

覆盖：

- expected patch content。
- SHA-256。
- temp write + atomic rename。
- same key/same hash reuse。
- same path/different hash/overwrite=false fail。
- crash recovery。
- unsafe filename sanitization。

Golden patch fixture 对跨版本工具差异需谨慎；只冻结 CodeFixer 保证的语义。

## 15. Artifact Contract Tests

每个 Artifact：

- valid minimum fixture。
- valid full fixture。
- missing required。
- unknown enum。
- invalid ref。
- wrong schema_version。
- wrong hash。
- cross-run path reference。
- malicious path traversal。

Agent 输出不能因为“JSON 能 parse”就视为协议有效。

## 16. API Tests

至少：

- health/readiness。
- settings mode。
- projects CRUD/preflight。
- tasks list/detail/start/cancel/retry/rerun。
- artifacts/events/diff。
- Secret redaction。
- ETag/version conflict。
- stable error envelope。
- invalid input。
- not found。
- CSRF/IP policy boundary。

OpenAPI snapshot 可作为 API contract regression，但更新必须审阅。

## 17. WebSocket Tests

覆盖：

- connect。
- reconnect。
- event ordering。
- duplicate event tolerance。
- stale page recovery via REST。
- batching。
- server restart。

WebSocket 只用于实时增量；前端不得因为漏了一条 WS 就永远错误。重连后必须可通过 REST 重建事实。

## 18. Frontend Component Matrix

至少对以下组件做 browser component tests：

### ExecutionModeController

- awaitingStart。
- automatic。
- pending count。
- confirm switch。
- running tasks continue copy。
- disabled/readiness failure。
- keyboard。

### StageRail

- pending。
- running。
- succeeded。
- skipped。
- failed。
- reconciling。
- repair loop 1/2/3。
- superseded。
- reduced motion。

### TaskCard

- all top-level statuses。
- changed/no_change。
- long title。
- partial delivery。
- missing optional metadata。

### FailureSurface

- retryable。
- non-retryable。
- side effects。
- cleanup required。
- long stderr collapsed。

### NoChangeSurface

- evidence。
- related fix missing。
- limitations。
- approved review。

## 19. E2E Journeys

第一版最少：

```text
E2E-001 configure-minimal-project
E2E-002 awaiting-start-to-completed-changed
E2E-003 automatic-mode-ingest-and-run
E2E-004 completed-no-change
E2E-005 failed-verification-and-rerun
E2E-006 partial-delivery-retry-failed-target
E2E-007 cancel-running-task
E2E-008 server-restart-and-recover
E2E-009 theme-persistence
E2E-010 readiness-not-ready
```

E2E 断言用户能看到正确文案和操作，不只断言 API response。

## 20. Visual Regression

固定环境：

```text
OS: Linux CI image
Browser: Chromium
Viewport primary: 1440x900
Locale: zh-CN
Timezone: Asia/Singapore 或固定 UTC，但必须全局统一
Clock: fixed
Animation: reduced/test mode
```

Baseline：

```text
dashboard-light
dashboard-dark
task-list-running
task-list-failed
task-detail-changed
task-detail-no-change
task-detail-repair-loop
task-detail-partial-delivery
project-preflight-ready
project-preflight-failed
execution-mode-confirm
```

规则：

- Snapshot 放版本控制。
- 差异报告保存 CI artifact。
- 禁止 CI 自动更新 baseline。
- 有意视觉变更必须在同一施工提交或紧邻的 golden 更新提交中更新，并在阶段自测报告说明原因。
- 大面积 diff 必须人工打开实际截图审阅。
- 不稳定元素用 fixture/styling freeze，不通过提高巨大容差掩盖。

## 21. Accessibility

自动 smoke 至少覆盖：

- accessible name。
- focus order。
- dialog focus。
- keyboard primary actions。
- color-independent status。
- ARIA stage status。
- reduced motion。

自动化不能证明全部 accessibility，因此 P0 页面 release 前需要人工键盘巡检。

## 22. Performance Smoke

第一版不追求极限 benchmark，但避免明显退化。

固定 fixture：

- 500 tasks list。
- task with 50 events。
- 10 repair attempts 的极端历史 fixture。
- diff with many files/large text。

关注：

- list interaction。
- task detail initial render。
- diff lazy loading。
- WebSocket burst。
- DB query count/latency。

阈值在 Phase 0/第一批实现后基于真实数据冻结，不能现在拍脑袋写毫秒 SLA。

## 23. Coverage

Coverage 是辅助指标，不是产品正确性的替代。

原则：

- domain/application 高覆盖。
- adapter 错误路径有显式测试。
- orchestration 以 Scenario 为主。
- 不为了数字给 trivial getter 写无价值测试。

CI 可以设置最低线，但任何涉及幂等/恢复/权限的未测试分支都不能靠总体 coverage 掩盖。

## 24. Test Naming

Backend：

```text
test_<behavior>__when_<condition>
```

Scenario 使用稳定 ID。

Frontend/E2E 使用用户可读语义。

失败信息应告诉：

- given。
- action。
- expected。
- actual。

## 25. Flaky Test Policy

Flaky 不是“再跑一次就算过”。

发现 flaky：

1. 标记负责人。
2. 保存 trace/log/screenshot。
3. 修 deterministic cause。
4. 如必须 quarantine，不能让该测试永久静默；记录 issue 和过期时间。
5. 核心幂等、recovery、security 测试禁止长期 quarantine。

重试次数只用于诊断，不作为绿色门禁的默认掩盖。

## 26. Direct-Main Pre-Commit Test Selection

默认快速门禁：

```text
lint
typecheck
backend unit
contract
frontend unit/browser selected
affected scenarios
build
```

基于路径可增加：

- `orchestration/` → all core scenarios。
- `contracts/` → all contract + generated sync + scenarios。
- `delivery/` → all delivery/recovery scenarios。
- `design-system/` → frontend browser + visual。
- migrations → migration matrix。
- Agent adapter → adapter contract + fake CLI integration。

如果无法可靠判断 affected scenarios，宁可多跑，不允许漏跑核心回归。

已知失败时禁止主动提交到 `main`。如果 push 后 CI 才发现失败，则暂停无关 Feature，优先恢复 `main` 为绿色。

## 27. Main / Nightly

Main 每次 push：

- full unit/contract/integration。
- full scenario。
- frontend browser。
- E2E。
- visual。
- build。

Nightly 可增加：

- 多浏览器精选 E2E。
- stress concurrency。
- repeated crash injection。
- resource leak。
- real CLI preflight smoke。
- 受控外部服务 smoke（如果凭据环境允许）。

## 28. Release Candidate Gate

必须全绿：

- backend all。
- frontend all。
- scenario all。
- E2E all。
- visual reviewed。
- migration rehearsal。
- Windows dev smoke。
- Linux install/systemd/restart。
- health/readiness。
- artifact cleanup。
- changed/no_change/failed/partial_delivery demos。
- crash/restart/no-duplicate-MR demo。

真实灰度必须记录：

- ticket IDs。
- task/run IDs。
- baseline。
- generated artifacts。
- external MR/Patch。
- manual verification conclusion。

## 29. 自测报告

每个阶段结束产生一份：

```text
docs/testing/reports/<phase>-self-test.md
```

包含：

- commit/SHA。
- 环境。
- 运行命令。
- pass/fail 数。
- Scenario 清单。
- E2E 清单。
- visual diff 结论。
- 手工检查。
- known limitations。
- 未运行项及原因。

“我测过了”不是自测记录。

## 30. 最终交付测试包

第一版交付仓库必须让新机器按文档执行：

```text
bootstrap
test-fast
test-all
build
readiness
```

并得到可理解结果。

测试 fixture、fake service 和 Scenario 是正式项目资产，不在交付时删除。
