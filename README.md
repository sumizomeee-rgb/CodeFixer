# CodeFixer

CodeFixer 是一个通用的 Bug 自动修复与交付平台。

它从外部工单系统收录 Bug，通过独立的 Discovery 与 Repair Agent 自主反查和修改唯一代码源，经过验证与 Review 后，按项目配置生成 Patch 和/或创建普通 GitLab MR。

项目当前处于设计阶段，产品语义、状态机、Artifact 协议、并发模型和交付边界见：

- [产品与技术设计 SPEC](docs/design-spec.md)

## 已确定的第一版边界

- 工单来源：Redmine、TAPD。
- 修改源：Git、SVN。
- Agent Runtime：Claude Code、Codex、OpenCode。
- 最终动作：Patch、GitLab MR。
- 执行方式：全自动或待用户点击一次开始。
- 一个 Bug 只修改一个代码源，但可以执行多个最终动作。
- 不实现 GitHub PR、自动合并 MR、SVN 直接提交和多修改源任务。

## 仓库状态

当前仓库只有设计文档，尚未开始功能实现。
