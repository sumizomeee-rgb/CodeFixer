# 真实 Agent 受控验收（2026-08-13）

## 结论

CodeFixer 已在 Windows 本机完成一次“假工单 + 隔离本地 Git 仓库 + 真实 Codex CLI + Patch-only”的完整闭环：

`prepare → discovery → repair → verify → review → freeze_change → deliver`

- 工单：`FAKE-CLAMP-001`
- 最终状态：`completed / changed`
- 修复：将错误的百分比边界表达式改为 `min(100, max(0, value))`
- 验证：3 个单元测试通过，验证副产物被清理，候选改动保持不变
- 复核：独立 review Agent 批准
- 交付：仅生成 Patch，未创建 MR，未修改原始仓库
- 运行耗时：约 340 秒；分析、修复、复核分别有独立阶段记录

## 真实运行发现并修复的问题

1. Codex 严格结构化输出不接受条件组合 Schema、无类型的 `const/enum` 与 `uniqueItems`。Agent 使用的四份契约已收敛到受支持子集，平台仍在 Agent 返回后执行自身的确定性语义校验。
2. Agent 失败时原先只留下笼统错误。现在每个 Agent 阶段会保存 `agent-runtime.json`，记录退出码、session、耗时、命令、stderr 与事件，任务失败原因会引用诊断路径。
3. Windows 文本子进程会把 Git Patch 内的 CRLF 自动转换为 LF，导致验证副产物清理后无法恢复冻结候选。进程执行器已改为字节捕获再显式解码，并新增“仓库存储 CRLF”回归测试。

## Windows / Linux 说明

- 本机 Codex CLI 的 `read-only` 与 `workspace-write` Windows 沙箱均出现 `CreateProcessAsUserW error 5`，无法启动 PowerShell。最终受控实验仅在一次性隔离仓库中关闭 Codex 内层沙箱完成；CodeFixer 产品默认沙箱策略没有放宽。
- Linux 不经过 Windows 的 `CreateProcessAsUserW` 路径；通用子进程字节捕获、`pathlib` 路径处理和跨平台测试入口均可在 Linux 使用。部署前仍应在目标 Linux 主机用实际 Agent CLI 做一次同等 smoke test。

## Web UI 验收

- 首页统计、任务筛选、任务详情抽屉、阶段耗时、交付结果、技术产物展开均正常。
- 全自动 / 待我开始切换正常；测试结束恢复为“待我开始”。
- 深浅主题切换正常；测试视口横向溢出为 0；浏览器控制台错误为 0。
- 视觉评价：深色控制台层级清晰、状态色克制且有产品个性，已经达到初版管理端可用审美。后续可把侧栏字符图标统一替换为同一套 SVG，提升精致度。
- 后端与场景测试 37 项通过，前端 TypeScript 检查和 production build 通过。仓库 Vitest 浏览器套件未启动：当前 `node_modules` 缺少 Playwright 固定版本的 Chromium；按 README 重新执行 `python scripts/bootstrap.py --with-browser` 可补齐。真实 UI 流程已由 Codex 内置浏览器完成，不把这个环境依赖误报成应用失败。

截图：

- `task-detail-light.png`：浅色主题下的真实成功任务详情
- `settings-dark.png`：深色设置页与全局执行模式

## 清理约定

验收报告和截图作为可复核证据保留；假仓库、隔离数据库、Patch、Agent 日志、临时脚本和验收服务在测试结束后删除。
