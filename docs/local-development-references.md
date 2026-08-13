# 本机开发 Agent 参考路径

> 适用范围：仅限在当前 Windows 开发机上参与 CodeFixer 开发的 Agent。
> 文档性质：非规范、非运行依赖、允许包含本机绝对路径。
> 规范优先级：`docs/design-spec.md` 始终高于本文和所有参考工程。

## 1. 使用条件

Agent 只有在本机开发 CodeFixer，并且对应路径通过 `Test-Path -LiteralPath` 检查后，才可以按需读取这些参考材料。

- 路径不存在时直接忽略，不得因此阻塞设计、开发、测试或部署。
- Linux 部署机、CI、其他开发机和 CodeFixer 运行时不得读取或依赖这些路径。
- 不得把参考工程加入 CodeFixer 的 import、构建脚本、启动命令、测试前置条件或运行时调用链。
- 不得复制参考工程中的凭据、内网地址、用户信息、机器路径和环境专属配置。
- 需要采用的思想必须重新表达为 CodeFixer 自身的代码、配置 Schema、测试或规范；不能只写“参照某项目实现”。
- 参考内容与 CodeFixer SPEC 冲突时，以 SPEC 为准，并在 CodeFixer 内独立完成设计修订。

## 2. 可选参考材料

### 2.1 HaruAnalyze

项目根目录：

```text
E:\Such_Proj\Other\HaruAnalyze
```

可参考：

- 前后端工程组织与同源 Web 管理界面思路。
- 双 Agent 反查流程，尤其是第一个任务如何从有限输入自主定位真实问题范围。
- Agent 只接收固定入口文档路径、再自行读取任务档案的交接方式。
- 启动前依赖检查、配置检查、运行状态展示和失败说明。

本机 Windows 开发与 Linux 部署接手材料：

```text
E:\Such_Proj\Other\HaruAnalyze\docs\14-2026-08-06-本机Win开发通用接手提示词.md
```

可参考：

- Windows 开发、Git 同步、Linux 拉取和服务重启的发布链路。
- Python/前端依赖锁、虚拟环境隔离、systemd 用户服务和健康检查。
- 部署前后检查、失败诊断与回滚意识。

只吸收通用流程，不复制其中的项目名、端口、主机、目录、服务名或命令参数。CodeFixer 的正式端口固定为 `9522`，部署约定以自身 SPEC 为准。

### 2.2 HaruPulse

项目根目录：

```text
E:\Such_Proj\Other\HaruPulse
```

可参考：

- 可复用的前后端架构、配置分层和管理界面组织方式。
- 后台任务、状态展示、部署材料与工程化约束中适合 CodeFixer 的通用模式。
- 视觉个性化与高信息密度并存的 Web 交互处理。

读取时应围绕当前 CodeFixer 任务定向查看相关文件，禁止无边界扫描整个项目。

### 2.3 GitLab Cherry-pick 历史原型脚本

脚本路径：

```text
E:\WorkProject\branches\Branch_Stems\HaruTrunkGitLua\doc\cherry_pick_mr.py
```

仅可参考：

- 从目标分支创建临时分支。
- 按顺序 Cherry-pick commits。
- Git 命令的非交互执行与远端认证复用方式。
- 临时分支、Commit 和远端副作用的确认思路。

该脚本只用于理解历史流程，CodeFixer 不得直接调用、import 或要求部署它，也不得复刻其中的 MR、目标分支和 assignee 交互。当前 `gitlabPush` 只推送受控任务分支并返回 Commit URL；幂等、并发、外部副作用对账和崩溃恢复均以 CodeFixer SPEC 为准。

## 3. Agent 使用步骤

1. 先完整阅读 `docs/design-spec.md`，确定当前任务的规范边界。
2. 判断当前问题是否确实需要参考既有实现；不需要时不要读取外部项目。
3. 对目标路径执行存在性检查，只读取与当前问题直接相关的最小文件范围。
4. 把可复用思想转化为 CodeFixer 自身设计或实现，不保留跨仓库代码依赖。
5. 提交前检查变更中是否意外出现参考工程路径、私有地址、凭据或业务专属耦合。

本文中的绝对路径是有意保留的本机开发索引，是 `docs/design-spec.md` 所述“公开默认配置和运行时不得包含机器路径”规则的唯一文档型例外；它不改变 CodeFixer 的可移植性与自包含要求。
