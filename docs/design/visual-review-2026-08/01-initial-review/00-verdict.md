# 00 · 总体诊断

## 一、五条根因

界面上能看到的几十处问题，可以收敛到五条根因。修根因比逐处修表象有效得多。

### 根因 1：字体声明与实际加载脱节

`frontend/src/styles.css` 第一行：

```css
:root{font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;...}
```

`frontend/index.html` 里**没有任何 `<link rel="stylesheet">` 或 `@font-face`**。Inter 从未被加载。

实际渲染结果：
- Windows 中文环境 → 拉丁字符落到 **Segoe UI**，中文落到 **微软雅黑**。
- 两者 x-height、字重轴、字面宽度都不匹配，中英混排（本产品几乎每一行都是中英混排：`redmine-main #48217`、`verification_failed`、`GitLab MR`）时基线与灰度都在跳。
- 微软雅黑在小字号下（本站主力字号是 9/10/11px）灰度极重、笔画糊，这是"死板 + 廉价"最大的单一来源。

而 `frontend-design` 明确禁止 Inter/system fonts 这类通用选择。**当前状态是"想用 Inter 但连 Inter 都没用上"，是最差的一档。**

→ 解法见 [02-foundation.md §1](02-foundation.md)。

### 根因 2：三层 CSS 层层覆盖，令牌形同虚设

引入顺序（`main.tsx`）：

```
styles.css (14 KB)  →  product.css (19 KB)  →  simplify.css (26 KB)  →  ai-picker.css (0.6 KB)
```

四个文件全部**单行压缩**（`styles.css` 1 行、`product.css` 60 行、`simplify.css` 27 行），无法阅读、无法维护，人和 AI 都改不动。

覆盖链的实际后果，举三个已确认的例子：

| 选择器 | styles.css | product.css | simplify.css | 结果 |
|---|---|---|---|---|
| `.app-shell` grid | `72px 1fr / 74px 1fr` | `72px 1fr / 176px minmax(0,1fr)` | — | 图标导轨被改成常展开侧栏，但 `styles.css` 里的 tooltip 逻辑还留着 |
| `.mode-controller` | `margin:auto`（居中） | `margin-left:auto`（贴右） | — | 规范里的"顶栏中心权威控件"被推到角落，权重塌了 |
| `.task-row` 列数 | — | `92px 1fr 150px 100px 28px`（5 列） | `.simple-row{92px 1fr 28px}`（3 列） | 两套并存，改一处不生效 |

`.navrail button span` 更典型：`styles.css` 定义它是 hover 才出现的绝对定位 tooltip，`product.css` 把它 `position:static;opacity:1` 变成常显 label。**死代码留在文件里，读代码的人无法判断哪套生效。**

→ 解法见 [11-roadmap.md §1](11-roadmap.md)（CSS 重组）。

### 根因 3：设计规范未落地，退化为通用 Admin Template

`design-system.md` §28 明确列为"不接受"的两条：

> - 功能都有之后再统一美化
> - 套一个 Admin Template 先跑起来

当前实现恰好是这两条的结果。规范 §27 要求 Phase 0 先完成 14 个 design primitives（Button / IconButton / Input / Select / SegmentedControl / Dialog / Tooltip / Popover / Surface / Divider / Badge / StatusDot / Skeleton / CodeText）和 9 个 product patterns：

```
frontend/src/components/        ← 空目录
frontend/src/design-system/     ← 只有 ModeController.tsx (10 行) + StageRail.tsx (20 行)
```

所以每个页面各自用裸 `<button className="ghost framed">`、裸 `<input>`、裸 `<select>` 拼装，一致性靠 CSS 选择器碰运气。

→ 完整对照见 [09-spec-debt.md](09-spec-debt.md)。

### 根因 4：视觉密度失控——把"信息密集"做成了"字小"

字号分布（四个 CSS 全量统计）：

| 字号 | 出现次数 |
|---|---|
| **10px** | **33** |
| **11px** | **27** |
| **9px** | **26** |
| 12px | 16 |
| 8px | 2 |
| 14px | **1** |
| 34 / 27 / 24 / 22 / 21 / 20 / 18 / 17 / 16 / 15 / 13px | 各 1–4 |

规范 §4.2 定义的 Type Scale 是 `display 32 / page-title 24 / section-title 16 / body 14 / caption 12 / micro 11 / mono 12`——**七档，最小 11px，正文 14px**。

实现里 9px + 10px 合计 59 处，而 body 级的 14px 只出现 **1 次**。这就是"死板"的第二大来源：**所有文字都被压成同一个小灰块，没有主次，没有呼吸，看久了眼睛累。**

同时 `h1{font-size:34px}` 又超出规范的 32px 上限，且 `letter-spacing:-.045em` 收得过紧——34px 配 -4.5% 字距在中文标题上会出现字面粘连（截图 `01-dashboard-light-full` 的"维修控制台"四字可见）。

**结论：不是密度高，是层级塌了。** 一个真正高密度的工业界面（Linear、Datadog、Vercel Dashboard）主力正文都在 13–14px，靠**行高、分隔线、留白节奏**做密度，不靠缩字号。

→ 解法见 [02-foundation.md §2](02-foundation.md)。

### 根因 5：形状与色彩没有系统

**圆角 16 种像素值 + 3 种特殊值**（规范 §16 只允许 `4 / 7 / 10 / 14` 四档）：

```
9px×15  10px×15  50%×14  999px×7  12px×7  8px×6  11px×6  15px×5
6px×4   16px×4   18px×3  14px×2   13px×2  7px×1  4px×1   3px×1
22px×1  17px×1   0 10px 10px 0 ×1
```

9px 和 10px 各 15 处、11px 和 12px 各 6–7 处——**这些差 1px 的值人眼分不清，但会让整体轮廓显得"没对齐"，是廉价感的隐形来源。**

规范 §16 同时写明：

> 避免满屏圆角卡片；列表中的连续信息优先通过线、分组和间距组织，不把每一行包进独立胶囊。

现状恰好相反：任务列表 8 行 = 8 个独立圆角块，项目页 3 个项目 = 3 张带阴影卡片，设置页 4 个功能 = 4 张 310px 高的卡片。

**色彩失控**：
- `--side:#c258a0`（规范 §3.3 的 `status-side-effect`）在令牌里定义了，**全站零使用**。
- 硬编码第三方品牌色 4 处：`#d97757`(Claude) ×2、`#4f8b73`(OpenCode) ×2、`#aa1f2e`(Redmine)、`#2868d8`(TAPD)。这几个色和产品色系（暖灰 + `#f4603c` 橙红）毫无关系，`#2868d8` 那块纯蓝在整页暖调里像贴上去的。
- 暗色主题**只覆盖 11 个变量**，7 个状态色（success / nochange / warning / failed / reconcile / side / signal）全部沿用亮色值，在 `#0e1110` 底上饱和度和对比度都不对。

→ 解法见 [02-foundation.md §3–4](02-foundation.md) 与 [08-motion-theme.md §2](08-motion-theme.md)。

---

## 二、量化取证汇总

| 维度 | 现状 | 规范要求 | 差距 |
|---|---|---|---|
| Web 字体加载 | **0 个** | 未明确（规范升级点） | 全站 fallback |
| 字号档位 | 17 种，主力 9/10/11px | 7 档，正文 14px | 层级崩塌 |
| 圆角档位 | **16 种** px 值 | 4 档（4/7/10/14） | 4× 冗余 |
| `@keyframes` | **1 个**（pulse） | §15 定义 5 档 motion token | 几乎无动效 |
| `transition` 声明 | **2 处** | 所有交互态需过渡 | 全站硬切 |
| 暗色覆盖变量 | 11 / 20 | 全量 | 状态色未适配 |
| design primitives | **0 / 14** | §27 Phase 0 必须 | 未开工 |
| product patterns | 2 / 9 | §27 Phase 0 必须 | 未开工 |
| 死 CSS 文件 | 3 个（10.4 KB） | — | 需清理 |
| 未样式化原生控件 | 2 处 checkbox | §27 primitives 覆盖 | 蓝色 ✓ 破坏体系 |
| tabular numerals | 未启用 | §4.3 明确要求 | 数字跳动 |
| skeleton loading | 0 处 | §20 优先 skeleton | 只有文字"正在读取…" |
| 主题态 | light / dark | §24 light / dark / **system** + 持久化 | 缺 system、刷新丢失 |
| visual baseline | 未冻结 | §25 要求 11 个 | 无回归保护 |

死 CSS 文件（未被 `main.tsx` 引入，但仍在仓库里）：

```
frontend/src/phase1.css        6091 B
frontend/src/phase2.css        2458 B
frontend/src/final-actions.css 1867 B
```

---

## 三、做得对、必须保留的部分

评审不是全盘否定。以下几处**质量明显高于平均水平，改版时要保护**：

1. **失败码文案体系**（`TasksPage.tsx:14-15`）——11 种 `failure code` 各配 `failureTitle` + `failureHint`，中文写得准确、克制、可执行（"到项目的『范围与验证策略』放行目标目录或扩展名，再创建新任务"）。这是全站文案水平最高的地方，**视觉改版只该给它更好的呈现结构，一个字都不要动**。

2. **Secret 边界的 UI 表达**（`ProvidersPage.tsx:93` 的 `.secret-boundary-note`）——"保存后界面只知道『已配置』，无法读回真实值"。把 `README.md` 「配置原则」的安全边界翻译成了用户能懂的一句话，配锁形图标。**这个模式应该推广**（见 [07](07-controls-overlays.md) §3）。

3. **`favicon.svg` 的心电图 mark**——黑方块 + 橙色折线 + 两端圆点。这个"信号 / 心跳"语义**比 `App.tsx` 里的 `RepairMark`（双半圆 + 锯齿缝）更贴近规范 §2 的 Repair Signal System 概念**。改版应以 favicon 为准统一品牌 mark（见 [04](04-shell.md) §2）。

4. **`--signal:#f4603c` 这个主色本身选得好**——暖橙红，在暖灰底（`#f5f6f4`）上既有工业感又不刺眼，和"修复 / 信号"语义契合，且明确避开了 `frontend-design` 禁止的紫色渐变。**不要换主色**，要做的是给它一套完整的色阶（现在只有 `--signal` 和 `--signalSoft` 两级）。

5. **`product.css` 顶部那行注释**：

```css
/* CodeFixer identity: an industrial repair ledger, not an icon-only web launcher. */
```

**这句话就是对的方向**——"工业修复账本"。问题是下面 19 KB 的 CSS 没有兑现它。本评审提出的方向（[01-direction.md](01-direction.md)）本质上是把这句注释真正做出来。

---

## 四、缺陷分类总览

后续分册按这十类组织：

| 类 | 名称 | 严重度 | 分册 |
|---|---|---|---|
| A | 字体与排版层级 | 🔴 高 | [02](02-foundation.md) |
| B | 形状 / 色彩 / 间距系统 | 🔴 高 | [02](02-foundation.md) |
| C | StageRail 与信号系统缺席 | 🔴 高 | [03](03-signal-system.md) |
| D | Shell 与导航权重错位 | 🟡 中 | [04](04-shell.md) |
| E | 页面级排版与信息结构 | 🟡 中 | [05](05-pages-dashboard-tasks.md) [06](06-pages-projects-providers-settings.md) |
| F | 与 design-system.md 的欠账 | 🔴 高 | [09](09-spec-debt.md) |
| G | 响应式硬伤（xs 遮挡 / 断词） | 🔴 高 | [04](04-shell.md) §5 |
| H | 原生控件未样式化 | 🔴 高 | [07](07-controls-overlays.md) §2 |
| I | 模态 / 抽屉 / 暗色态 | 🟡 中 | [07](07-controls-overlays.md) [08](08-motion-theme.md) |
| J | 品牌 mark 不一致 | 🟢 低 | [04](04-shell.md) §2 |
