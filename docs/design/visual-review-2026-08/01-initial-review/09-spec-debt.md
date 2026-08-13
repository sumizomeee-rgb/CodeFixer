# 09 · 规范欠账对照表

> 逐条比对 `docs/design/design-system.md` 与 `frontend/src/` 的实现。
> 状态标记：**✅ 已落地** / **◐ 部分** / **❌ 未落地** / **✳️ 反向违反**（实现做了规范明确禁止的事）

统计：全部 **86** 条可核查要求中，✅ **21**、◐ **19**、❌ **39**、✳️ **7**。**完整落地率 24%**。

---

## §2 视觉概念：Repair Signal System

| 要求 | 状态 | 证据 |
|---|---|---|
| 连续诊断轨道 | ✳️ | `.rail-line` 每个 stage 各自一截，不连续。见 [03 §1.2](03-signal-system.md) |
| 信号节点 | ◐ | 有节点，但印着数字 1–8，是 Stepper 不是信号 |
| 冻结产物的"封存"语义 | ❌ | `freeze_change` 阶段在 rail 上**不存在**；抽屉里 Frozen Change 是普通卡片 |
| 外部副作用的"越界输出"语义 | ❌ | `.failure-effects` 是灰色 `<code>`，`--side` 色零使用 |
| 可追踪的证据引用 | ◐ | `.evidence-card` 存在，但无 `EV-00x` 编号、无引用回链 |
| 局部扫描/脉冲动效 | ◐ | 只有一个 5px 点在 pulse，无扫描 |
| 品牌感来自结构节奏，不是插画 | ✅ | 无插画，方向正确 |

### §2.1 视觉关键词逐项自评

| 关键词 | 达成 | 说明 |
|---|---|---|
| precise | ◐ | 布局齐整，但 16 种圆角 / 17 种字号破坏精密感 |
| kinetic | ❌ | **全站 1 个动画、2 条 transition**。这是最彻底的未达成 |
| engineered | ◐ | 有 mono 数据、有卡片角标 01–04，方向对；但字体未加载导致质感落空 |
| calm under load | ◐ | 沉静做到了，但沉静过头变成"静止" |
| traceable | ❌ | 无证据编号、无引用链、timeline 事件是英文 raw event |
| slightly futuristic | ❌ | 圆角胶囊 + 柔和大投影 = 2019 SaaS |
| **not** cyberpunk | ✅ | 没有霓虹 |
| **not** generic SaaS | ✳️ | **这一条是反向违反的** —— 见 [00 §3](00-verdict.md) |
| **not** Material clone | ✅ | 不是 Material |

---

## §3 色彩系统

| 要求 | 状态 | 证据 |
|---|---|---|
| 所有颜色通过 semantic token，组件禁止直接写业务色值 | ✳️ | 硬编码 `#aa1f2e` / `#2868d8` / `#d97757` / `#4f8b73` 4 组品牌色 + 15 处 `rgba(30,40,33,…)` 字面量 |
| §3.1 Light neutral 9 值 | ◐ | 7 值精确对齐；`text-secondary` / `text-tertiary` 两值偏离；`surface-raised` 未定义 |
| §3.1 Dark neutral 9 值 | ◐ | 8 值对齐；`surface-raised` 未定义 |
| §3.2 signal 六级色阶 | ◐ | **只实现 2 级**（`signal-500` + `signal-50`），缺 100/300/600/700 |
| §3.2「禁止把所有卡片都涂成 signal」 | ✅ | 遵守了 |
| §3.3 七个状态色 | ✅ | **七个值逐位相同**，这是做得最规范的一处 |
| §3.3「`no_change` 必须有独立颜色」 | ◐ | 色值有，但 UI 上 `no_change` 结果**没有专属呈现**（见 [05](05-pages-dashboard-tasks.md)） |
| §3.3「`partial_delivery` = failed 主 + side-effect 辅」 | ❌ | `--side` 零使用，partial 只显示 failed |
| §3.4「正文和关键状态文本必须满足可读对比」 | ✳️ | 状态色当文字用，白底 ~3.2:1，未达 4.5:1。见 [02 §3.1b](02-foundation.md) |
| §3.4「颜色不是状态唯一载体，必须同时有形状/图标/文字」 | ✳️ | `.health i` 三态只靠圆点颜色；`.preflight-mini i` 同；checkbox 无形状区分 |
| §3.4「Light/Dark 分别验证，不允许简单反色」 | ✳️ | 暗色只换 11 个中性变量，**7 个状态色直接沿用亮色** |

---

## §4 字体与数字

| 要求 | 状态 | 证据 |
|---|---|---|
| §4.1 UI 正文系统无衬线，中英稳定字宽 | ✳️ | 声明 Inter 但**零加载**，实际 Segoe UI + 微软雅黑混排，字宽不稳定 |
| §4.1 数据/代码/SHA/耗时用等宽 | ◐ | 部分用了 `ui-monospace`，但工单号、路径、耗时多处仍是 sans |
| §4.1「标题不用过度粗黑，通过空间和层级建立权重」 | ✳️ | `h1{font-weight:750;letter-spacing:-.045em}` —— 750 是超粗，负字距让中文粘连 |
| §4.2 Type Scale 八档 | ✳️ | **17 种字号**，其中 body 级 14px 只有 1 处；9px 26 处、8px 2 处 |
| §4.3 tabular numerals | ❌ | 全站 `font-variant-numeric` **0 处**。3 秒轮询下数字宽度跳动 |

---

## §5 Layout

| 要求 | 状态 | 证据 |
|---|---|---|
| §5.1 baseline 1440×900 | ✅ | 该尺寸下可用 |
| §5.1 保证 1280×720 可用 | ◐ | 176px 侧栏未降级，内容区仅剩 1104px，任务标题截断 |
| §5.1 保证 1024×768 可用 | ✳️ | 侧栏仍常开，内容区 848px，`22-projects-sm` 卡片挤压 |
| §5.1「低于 960px 不能内容溢出不可操作」 | ✳️ | **420px 下三处内容被底部 tabbar 完全遮挡**（[04 §6.1](04-shell.md)）—— 这是明确违反 |
| §5.2 常态 72px icon rail | ✳️ | 固定 176px 常显 label。**本评审建议改规范而非改实现**，见 [10 §2](10-spec-upgrade.md) |
| §5.2 hover/focus 显 label | ✳️ | tooltip CSS 还在 `styles.css`，被 `product.css` 变成常显，成为死代码 |
| §5.2 可固定展开 216px | ❌ | 无展开/折叠 |
| §5.2「内容区宽度充分留给 timeline/diff」 | ◐ | 有 `max-width:1580px`，但全站一个值，长文本被拉成整行 |
| §5.2「模式控制器始终强识别，不抢占视线」 | ✳️ | 被 `margin-left:auto` 推到右上角与其它控件挤在一起，识别度低 |

---

## §6 StageRail【最重要的组件】

规范原文：**"StageRail 是 CodeFixer 最重要的产品视觉组件。它不是普通 Stepper。"**

| §6.1 每个节点可表达 | 状态 |
|---|---|
| stage ID | ✅ label 有 |
| 状态 | ✅ |
| **attempt 数** | ❌ |
| 实际耗时 | ✅ `meta` 有 |
| **当前 runner/agent** | ❌ |
| **是否产生 Artifact** | ❌ |
| **是否发生 repair loop** | ❌ |
| **是否有 failure/side effect** | ◐ failed 有描边色，side effect 无 |

| §6.2 形态 | 状态 | 证据 |
|---|---|---|
| 已完成：实心节点 + **连续实线** | ◐ | 节点实心 ✅；线不连续 ✳️ |
| 当前：**双层节点**，内核缓慢 pulse | ◐ | 单层圆 + 5px 内点 pulse（几乎不可见） |
| queued：空心节点 | ✅ | |
| skipped：**短虚线与斜杠** | ❌ | `.stage-skipped` CSS **完全不存在** |
| failed：**节点断开** + 断点处 **error notch** | ❌ | 只改描边色，轨道不断，无 notch |
| reconciling：**沿节点边缘慢速 traveling signal** | ❌ | 只改描边色，静止 |
| superseded：整段降透明 + **新 run 分叉引用** | ❌ | 类型定义里有 `superseded`，CSS 无规则 |
| **节点不印数字** | ✳️ | 印了 1–8。规范给的示意图是 `●━━●━━◉──○──○`，没有数字 |

| §6.3 Repair Loop | 状态 |
|---|---|
| **不得在 Rail 上假装成一次线性通过** | ✳️ **明确违反** —— 现在就是线性一遍 |
| 主轨道下方 loop band | ❌ |
| 详情页可展开每轮 | ❌ |
| 任务卡显示 `Repair loop ×2` | ❌ |

| §6.4 Motion | 状态 |
|---|---|
| 当前阶段低频运动表现"系统仍活着" | ◐ 有，但 5px 点的缩放看不见 |
| 禁止无限高速流光 | ✅ |
| 禁止全屏粒子 | ✅ |
| 禁止每个卡片同时发光 | ✅ |
| 禁止 loading 时改变布局 | ◐ 无 loading 态，无从违反 |
| `prefers-reduced-motion` 改静态强调 | ✅ 用 `@media(no-preference)` 包裹，**写法正确** |

**额外发现（规范未提但属实现硬伤）**：12 个 stage 中 **4 个被 UI 丢弃**（`workspace_prepare` / `no_change_verify` / `pre_delivery_check` / `freeze_change`）。其中 `freeze_change` 是 §11 专门用一节要求的核心语义。

---

## §7 Execution Mode Controller

| 要求 | 状态 | 证据 |
|---|---|---|
| 「不是普通 toggle」 | ✳️ | 就是一个圆角胶囊按钮，与其它按钮无区别 |
| §7.1 显示当前收录仍进行 | ❌ | |
| §7.1 显示**待开始数量** | ✳️ | 组件支持 `pending` 参数，`App.tsx:64` **不传** |
| §7.1 显示"不会调用 Agent/修改代码/交付"的简短说明 | ❌ | |
| §7.2 切到全自动的确认展示**队列数** | ❌ | 模态只有一句话 |
| §7.2 展示 **ready 项目数** | ❌ | |
| §7.2 展示**并发上限** | ❌ | |
| §7.3 切回时显示「新任务将等待开始 · N 个已授权任务继续运行」 | ✳️ | toast 只说"已切换为待我开始" |

→ 改法见 [04 §4](04-shell.md) 与 [07 §4.2](07-controls-overlays.md)。

---

## §8–§14 产品组件

| 组件 | 规范章 | 状态 | 说明 |
|---|---|---|---|
| TaskCard | §8 | ◐ | 存在两套并存的行布局（`.task-card` 与 `.task-row.simple-row`），CSS 都在，只有后者渲染 |
| FailureSurface | §9 | ◐ | 有组件，缺 `retryable` 标识、缺证据段、缺 stderr 折叠 |
| NoChangeSurface | §10 | ❌ | **组件不存在**。`no_change` 结果与 `succeeded` 视觉相同 |
| Freeze Change | §11 | ❌ | 无独立视觉；rail 上无该阶段 |
| Delivery Visual Language | §12 | ◐ | 有 `.delivery-target`，但 Patch / MR / PR 三种视觉相同 |
| §12.3 Side Effects | §12.3 | ❌ | `--side` 零使用 |
| Evidence UI | §13 | ◐ | 有卡片，无编号无回链 |
| Diff | §14 | ❌ | 无 diff 视图 |

---

## §15 Motion Tokens

| 要求 | 状态 |
|---|---|
| 定义 duration / easing token | ❌ 一个都没有，全是字面量 `.18s` / `.15s` / `1.8s` |
| signal 动效 1200–1800ms | ◐ 唯一的 pulse 是 1800ms，落在区间内 |

---

## §16 Surface 与圆角

| 要求 | 状态 | 证据 |
|---|---|---|
| 四档 `4 / 7 / 10 / 14` | ✳️ | **16 种像素值** + `50%` + `999px` |
| 大多数工作区用 `sm/md` | ✳️ | 9px×15、10px×15、12px×7、15px×5、16px×4、18px×3 |
| 只有 Dialog/浮层/模式控制器可用 `lg` | ✳️ | `.empty-state{18px}`、`.project-card{16px}`、`.settings-card{16px}` 都用了 lg 以上 |
| **「避免满屏圆角卡片」** | ✳️ | 见下表 |
| **「列表中的连续信息优先通过线、分组和间距组织，不把每一行包进独立胶囊」** | ✳️ | **五处违反** |

五处"每行一个胶囊"：

| 位置 | 行数 |
|---|---|
| `.task-row.simple-row` | 任务列表 8 行 |
| `.dependency-row` | 设置页依赖 4–7 行 |
| `.delivery-target` | 交付目标 1–3 行 |
| `.artifact-list > div` | 产物列表 |
| `.timeline .event` | 时间线事件 |

做对的一处：`.metric` 用了共享容器 + `border-right`。

---

## §17 Shadow

| 要求 | 状态 | 证据 |
|---|---|---|
| 层级主要靠 surface tone / border / spacing，少量 shadow | ◐ | 边框用得好；但卡片都带了投影 |
| 只有浮层/dialog/popover 使用明显 shadow | ✳️ | `.control-card{0 10px 34px rgba(30,40,33,.04)}`、`.project-ledger-card{…045}` —— 4% 透明度的大投影，**看不见但让边缘发灰** |
| 暗色尤其避免重阴影 | ◐ | 暗色 `--shadow` 有单独值，但 `.segmented .selected` 的黑投影在黑底上完全失效 |

---

## §18 Icon

| 要求 | 状态 |
|---|---|
| 统一一套线性 icon 库 | ◐ 全内联 SVG，stroke-width 1.5/1.6/1.8/2 混用，viewBox 24 与 20 混用 |
| 自定义 CodeFixer mark | ✳️ **存在两个互不相干的 mark**（`RepairMark` 组件 vs `favicon.svg`） |
| 自定义 StageRail node glyph | ✳️ 用的是数字 1–8 |
| 自定义 freeze/change mark | ❌ |
| 自定义 side-effect indicator | ❌ |
| 自定义 execution mode glyph | ❌ 只有一个圆点 |
| 禁止大量 emoji 作为正式图标 | ✅ 遵守 |

---

## §19 空态

规范给了三段具体文案。逐条对照：

| 规范文案 | 实现 | 状态 |
|---|---|---|
| `暂无 Bug 任务` / `工单轮询正常 · 上次检查 18 秒前` | 有标题，**无"轮询正常 · 上次检查"这一行** | ◐ |
| `当前没有需要处理的失败` | 首页 `.all-clear` 有类似表达 | ✅ |
| `还没有工单来源` / `添加 Redmine 或 TAPD 后…` / `[添加工单来源]` | 文案基本一致，有按钮 | ✅ |
| 「空态不是营销插画」 | 无插画 | ✅ |
| 五种语义不同的空态用了**同一个** `.empty-state` | — | ✳️ 规范未明说，但违反其精神 |

**"上次检查 18 秒前"这一行缺失是有实质影响的**——它是规范设计里让"没有任务"读起来像"系统待命"而非"系统坏了"的唯一手段。

---

## §20 Loading

| 要求 | 状态 |
|---|---|
| **优先 skeleton，布局与最终内容一致** | ✳️ **全站 0 个 skeleton** |
| 实时状态请求用局部 signal，不用全屏 spinner | ◐ 没有全屏 spinner（因为根本没有 loading 态） |
| 超过 1 秒才出现用户可读 loading caption | ✳️ 设置页 `正在读取配置…` 立即显示；其余三页**直接闪错误空态** |

---

## §21 Toast

| 要求 | 状态 | 证据 |
|---|---|---|
| Toast 只用于瞬时操作反馈 | ✳️ | **不会自己消失**，只能点掉，不"瞬时" |
| 任务失败/MR partial/readiness failed **不允许只靠 Toast** | ✅ | 这三类都有持久 UI，遵守了 |

---

## §22 Dialog 与危险操作

| 需要二次确认的场景 | 实现 |
|---|---|
| 切换到全自动且会排队已有任务 | ◐ 有确认，但不说队列数 |
| **取消 running task** | ✳️ **有入口，无确认** —— `TasksPage.tsx:33` 的 `.danger-button` 直接 `void act('cancel')`，一点即执行 |
| rerun 会产生新外部动作版本 | ❌ 无确认（`retry-delivery` 同样直接执行） |
| 删除本地产物 | ❌ |
| 清理已知远程 side effect | — 未实现该功能 |

**「取消任务」是全站最危险的一个按钮**：它会终止正在跑的 Repair Agent。规范 §22 把它列为必须二次确认的场景并给了完整文案示例，实现是**裸按钮直接执行**。改法见 [07 §4.2](07-controls-overlays.md)。

| 要求 | 状态 | 证据 |
|---|---|---|
| **「Dialog 必须说出结果」**，不写"确定吗？" | ◐ | 有描述句，但**按钮文字是"确认"** —— 规范精神是让用户看按钮就知道后果 |
| 规范示例：`取消正在运行的 Task #248625？` + `当前 Repair Agent 将被终止，未交付修改会被清理。` | ❌ | 无此级别的具体化 |

---

## §23 Accessibility

| 要求 | 状态 | 证据 |
|---|---|---|
| 所有交互可键盘操作 | ◐ | 都是原生 button，可 Tab；但**模态无焦点陷阱**，Tab 会跑到背后页面 |
| focus ring 不被 `outline:none` 吞掉 | ◐ | 有一条 focus-visible 规则，但**对比度 1.3:1**（24% 透明橙）且只覆盖 8 类选择器 |
| **状态不只依赖颜色** | ✳️ | `.health` 三态、`.preflight-mini` 三态、checkbox —— 都只有颜色 |
| **Dialog 正确 focus trap/restore** | ✳️ | 无 trap、无 restore、Esc 不关、body 不锁滚 |
| Tooltip 不是唯一信息来源 | ✅ | 未依赖 tooltip |
| icon-only action 有 accessible name | ◐ | `.icon-btn` 有 `aria-label`；`.concurrency-control` 的 ± 有；部分 SVG 缺 `aria-hidden` |
| **Rail 可用文本/ARIA 读取阶段与状态** | ✳️ | `.stage-rail` 有 `aria-label="任务阶段"`，但**每个 stage 的状态没有可读文本**——屏幕阅读器只能读到"准备 43秒"，读不出"已完成" |
| reduced motion | ✅ | 唯一的动画正确包裹 |
| 不用低对比灰字展示重要失败原因 | ✳️ | `side_effects` 是 `--muted` 灰色小字；失败码 `--failed` 白底 3.2:1 |

---

## §24 主题

| 要求 | 状态 | 证据 |
|---|---|---|
| 三态 `light / dark / system` | ✳️ | 只有 `dark:boolean` 二态，**无 system** |
| **用户选择保存在浏览器** | ✳️ | `useState(false)`，刷新即丢，`localStorage` 零使用 |
| 主题切换不能刷新页面 | ✅ | 遵守 |
| Design Token 用 CSS custom properties | ✅ | 遵守 |
| **组件禁止在 JSX 中通过三元表达式复制两套色值** | ✅ | 检查了全部 TSX，无此问题 |

---

## §25 Visual Regression Baselines

规范要求冻结 11 个 baseline。当前状态：**◐ 设施已搭好，但只用了 1/11。**

已有的部分（做得对，值得保留）：

- `frontend/playwright.config.ts` 已配置 `expect.toHaveScreenshot({animations:'disabled'})`、`viewport 1440×900`、`locale zh-CN`、`timezoneId Asia/Singapore` —— **这四项设置完全正确**，是 baseline 可复现的前提
- `package.json` 已有 `test:visual` 脚本（`playwright test --grep @visual`）
- `e2e/phase0.spec.ts:52` 有 1 个 `@visual` 测试
- `e2e/phase0.spec.ts-snapshots/` 下有 2 张基线

缺口是**数量与可复现性**：

| # | 问题 | 证据 |
|---|---|---|
| 1 | 11 个 baseline 只做了 1 个（`dashboard-light`） | 仅 1 处 `@visual` |
| 2 | **快照跨平台不可复用** | 目录下同时存在 `dashboard-light-chromium-linux.png`（138KB）与 `dashboard-light-chromium-win32.png`（49KB）—— 同一页面两个平台差 3 倍体积，说明字体渲染完全不同 |
| 3 | 无 dark 基线 | `phase0.spec.ts` 里切了主题、截了 proof 图，但没有 `@visual` 断言 |
| 4 | 依赖真实后端数据 | 断言里写死了 `【4.7】【商城】购买礼包后偶现红点未刷新` 等真实工单标题，数据一变测试全红 |
| 5 | `proof()` 截图与 baseline 混淆 | `test-results/proof/` 下的图是调试产物，不是受版本控制的基线 |

第 2 条是**最需要先解决的**——它正是 [10 §1](10-spec-upgrade.md) 主张自托管字体的直接证据：字体不固定，baseline 就没有意义。

| 规范要求的 baseline | 已有 `@visual` | 本次评审是否已有对应截图 |
|---|---|---|
| `dashboard-light` | ✅ | ✅ `01-dashboard-light-full` |
| `dashboard-dark` | ❌ | ✅ `01-dashboard-dark-full` |
| `task-list-running` | ❌ | ✅ `06-tasks-light-full` |
| `task-list-failed` | ❌ | ✅ `07-tasks-light-failed` |
| `task-detail-changed` | ❌ | ✅ `08-task-drawer-*` |
| `task-detail-no-change` | ❌ | ✅ `09-task-drawer-nochange-*` |
| `task-detail-repair-loop` | ❌ | ❌ 无（因为 UI 不表达 loop） |
| `task-detail-partial-delivery` | ❌ | ❌ 无 |
| `project-preflight-ready` | ❌ | ◐ `13-project-workbench-*` 部分覆盖 |
| `project-preflight-failed` | ❌ | ❌ |
| `execution-mode-confirm` | ❌ | ✅ `12-mode-confirm` |

> 本次评审用的 Playwright 截图脚本（含 `page.route()` mock）可以直接补进 `e2e/`——见 [11 §5](11-roadmap.md)。设施不用从零建，只需把 mock 与 `@visual` 断言接上。

---

## §27 Phase 0 必须完成的组件

规范原文：**"这些组件先用 fixtures 构建和测试，不等待真实 API。"**

**`frontend/src/components/` 目录存在但是空的。** `frontend/src/design-system/` 下只有两个文件：`StageRail.tsx`（20 行）、`ModeController.tsx`（10 行）。

全部 UI 代码集中在 5 个页面文件里，共 707 行 TSX，其中 `ProjectsPage.tsx` 一个文件 235 行 / 25KB，**单行最长 1011 字符**（`ProvidersPage.tsx` 更极端，单行 3017 字符）。这是"组件层不存在，一切内联"的直接体现。

### Design primitives（14 个）

| 组件 | 状态 |
|---|---|
| Button | ❌ 只有 5 条散落 CSS |
| IconButton | ❌ 只有 `.icon-btn` CSS |
| Input | ✳️ 原生，`.form-grid input` 有样式，但无组件、label 未关联 |
| Select | ✳️ 原生，**下拉箭头是系统样式** |
| SegmentedControl | ◐ 有 `.segmented` CSS，无组件 |
| Dialog | ✳️ 有 CSS，无组件，**无 focus trap / Esc / 锁滚** |
| Tooltip | ❌ |
| Popover | ❌ |
| Surface | ❌ |
| Divider | ❌ |
| Badge | ✳️ **七套并存**（`.task-status` / `.status-pill` / `.delivery-status` / `.muted-tag` / `.path-chip` / `.readiness-badge` / `.delivery-tags`） |
| StatusDot | ✳️ 三套（`.mode-dot` / `.health i` / `.ready-dot`），且**只有颜色没有形状** |
| Skeleton | ❌ **零** |
| CodeText | ❌ |

**14 个 primitive：0 个作为组件存在。**

### Product patterns（9 个）

| 组件 | 状态 |
|---|---|
| ExecutionModeController | ◐ 10 行，`pending` 未接入 |
| StageRail | ◐ 20 行，§6 的 8 项形态要求达成 2 项 |
| TaskCard | ◐ 有 CSS 无组件，且两套并存 |
| FailureSurface | ◐ 内联在 `TasksPage.tsx:16`，非独立组件 |
| NoChangeSurface | ❌ |
| EvidenceRow | ◐ 内联 |
| SideEffectBadge | ❌ |
| ArtifactRow | ◐ 内联 |
| PreflightCheckRow | ◐ 内联为 `.dependency-row` |

**9 个 pattern：2 个是独立组件，0 个完整达标。**

---

## §28 视觉验收原则

规范明确列出**不接受**的四种完成标准。逐条核对：

| 规范禁止的标准 | 当前是否踩中 |
|---|---|
| 「功能都有，之后再统一美化」 | ✳️ **踩中** —— 三层 CSS 层层覆盖正是"先跑起来再说"的产物 |
| 「套一个 Admin Template 先跑起来」 | ✳️ **踩中** —— 176px 侧栏 + 圆角胶囊导航 + 卡片网格是标准 Admin 骨架 |
| 「用状态颜色就算设计系统」 | ✳️ **踩中** —— 七个状态色是全站最规范的部分，其余 §6/§7/§16/§20/§27 全面欠账 |
| 「页面截图差异太多所以关掉 visual test」 | — 从未开启 visual test，无从关闭 |

规范给的接受路径是「Phase 0 定语法 → 各阶段按语法实现 → 阶段六统一 polish，而不是推倒重做」。

**现状是 Phase 0 被跳过了**：语法（primitives）没建，各页面各自实现，于是 polish 阶段必须做的事变成"补建 Phase 0"。这不是推倒重做——[11](11-roadmap.md) 的施工顺序正是按"先补语法层，再逐页对齐"排的。

---

## 汇总：按严重度排序的欠账 Top 12

| 序 | 欠账 | 规范章 | 影响 |
|---|---|---|---|
| 1 | 字体声明与加载脱节 | §4.1 | 全站质感落空 |
| 2 | StageRail 8 项形态达成 2 项 | §6.2 | 最重要组件不成立 |
| 3 | Phase 0 primitives 0/14 | §27 | 一切不一致的根因 |
| 4 | 动效仅 1 个 | §15/§6.4 | "kinetic"关键词完全未达成 |
| 5 | 暗色状态色未调 | §3.4 | 暗色不可用 |
| 6 | 无 skeleton，闪错误空态 | §20 | 功能性缺陷 |
| 7 | `freeze_change` 阶段消失 | §11/§6 | 核心产品语义不可见 |
| 8 | Repair Loop 假装线性 | §6.3 | 明确违反 |
| 9 | 万物皆胶囊（5 处） | §16 | "死板"的直接来源 |
| 10 | 状态只靠颜色（3 处） | §3.4/§23 | 无障碍 + 可读性 |
| 11 | Dialog 无 trap/Esc/锁滚 | §23 | 无障碍 |
| 12 | 主题不持久、无 system | §24 | 每次打开都要重设 |

→ 施工顺序见 [11-roadmap.md](11-roadmap.md)。
