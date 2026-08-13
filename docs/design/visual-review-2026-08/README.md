# CodeFixer 视觉与交互评审归档（2026-08）

本目录记录 CodeFixer 管理界面从首次视觉诊断到单一任务账本落地的三轮评审。文档保留历史推理，但不同轮次的结论并不同权；后续轮次可以修正或废止前一轮建议。

## 当前有效结论

优先阅读 [第三轮：单一任务账本](03-single-ledger/15-round3-single-list.md)。当前已经确认：

- 删除重复首页，进入系统直接看到唯一任务账本。
- 异常与待授权任务在同一账本置顶，不复制成第二个列表。
- 全局模式、健康和容量属于紧凑状态，不单独占据首页。
- 真机空库、移动端底栏、失败抽屉和视觉快照必须使用真实 API 契约或正式 fixture 验证。

最新产品语义以 [产品 SPEC](../../design-spec.md) 为准：主导航进一步收敛为“任务 / 流水线 / 设置”，“项目”和独立“工单来源”不再是一等导航对象。

## 目录结构

```text
visual-review-2026-08/
├─ README.md
├─ 01-initial-review/    首轮视觉体系与实现欠账诊断
├─ 02-reassessment/      改造后的降噪与重复信息复评
└─ 03-single-ledger/     当前有效的单一任务账本决策
```

### 01 · 首轮视觉诊断

首轮针对旧版五页面原型和 41 张截图，建立视觉语言、信号系统、页面问题与施工路线。它是历史取证和设计语言参考，不代表当前页面结构仍应保留。

| 文档 | 内容 |
|---|---|
| [00 · 总体诊断](01-initial-review/00-verdict.md) | 五条根因与量化取证 |
| [01 · 美学方向](01-initial-review/01-direction.md) | 视觉态度与设计方向 |
| [02 · 设计基础](01-initial-review/02-foundation.md) | 字体、色彩、圆角、间距与动效令牌 |
| [03 · 信号系统](01-initial-review/03-signal-system.md) | StageRail 与 Repair Signal |
| [04 · 应用外壳](01-initial-review/04-shell.md) | Topbar、导航和响应式 |
| [05 · 首页与任务](01-initial-review/05-pages-dashboard-tasks.md) | 旧首页、任务页和抽屉评审 |
| [06 · 配置页面](01-initial-review/06-pages-projects-providers-settings.md) | 旧项目、来源和设置页面评审 |
| [07 · 控件与浮层](01-initial-review/07-controls-overlays.md) | 表单、按钮、模态、Toast 与空态 |
| [08 · 动效与主题](01-initial-review/08-motion-theme.md) | 暗色与动效建议；其中 system 主题三态已废止 |
| [09 · 规范欠账](01-initial-review/09-spec-debt.md) | 设计规范与实现对照 |
| [10 · 规范升级](01-initial-review/10-spec-upgrade.md) | 对设计规范本身的建议 |
| [11 · 施工路线](01-initial-review/11-roadmap.md) | 当时的施工顺序与验收项 |

### 02 · 降噪复评

第二轮检查首轮改造后的感知变化，并识别重复信息。部分建议随后被第三轮真机取证修正。

| 文档 | 内容 |
|---|---|
| [12 · 复评结论](02-reassessment/12-round2-verdict.md) | 改造前后判断与剩余问题 |
| [13 · 重复信息审计](02-reassessment/13-round2-redundancy.md) | 页面和代码层重复分析 |
| [14 · 降噪执行单](02-reassessment/14-round2-noise-cut.md) | 分级施工建议；作废项见第三轮记录 |

### 03 · 单一任务账本

| 文档 | 内容 |
|---|---|
| [15 · 单一任务账本](03-single-ledger/15-round3-single-list.md) | 首页删除、异常排序、真机空态、移动端修复和回归验收 |

## 结论冲突时如何处理

1. 产品对象、导航、状态和业务边界以 `docs/design-spec.md` 为准。
2. 页面结构以第三轮为准。
3. 第三轮未覆盖的视觉细节，可继续参考第二轮；第二轮未覆盖时再回看第一轮。
4. 历史文档中提到的“首页”“项目”“工单来源”是当时实现的名称，不应据此恢复已废止结构。
5. 评审截图含 mock 数据，只能证明视觉状态；业务字段和流程必须以正式 API、Schema 与 E2E fixture 为准。

## 已明确废止或修正的建议

- 恢复独立首页：废止，任务页是唯一任务列表。
- 首页 StageRail 改紧凑态：废止，真机首页当时并未获得阶段数据。
- 亮色 / 暗色 / 跟随系统三态：废止，只保留亮暗切换。
- 把前端刷新时间称为“工单轮询时间”：废止，除非后端提供真实轮询事实。
- 将所有第三方品牌色视为违规：修正为收敛到令牌层并限制使用范围。
- 将字号机械限制为恰好五档：修正为语义化字号层级。

## 验证材料

正式视觉 fixture 位于 `frontend/e2e/fixtures/visual-control-tower.json`，Playwright 用例与基线位于 `frontend/e2e/`。`frontend/_shots2/` 和一次性审计脚本属于临时复评材料，不是长期事实来源。
