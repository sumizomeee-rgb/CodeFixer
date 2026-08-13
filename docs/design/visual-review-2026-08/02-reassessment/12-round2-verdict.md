# 12 · 第二轮复评：总判与「感知差」诊断

> 复评对象：codex 依据第一轮评审（00–11 册）完成的一轮视觉改造。
> 复评日期：2026-08-13。
> 复评口径：**视觉与交互体验**。不评功能缺陷、不评后端逻辑、不评安全边界（安全边界只做「有没有被改坏」的确认）。

---

## 〇、取证方式

本轮结论全部有据，取证走两条互不依赖的通道：

**通道 A — 源码全量重读**

```
frontend/src/styles/fonts.css        56 行
frontend/src/styles/tokens.css       84 行
frontend/src/styles/base.css         81 行
frontend/src/styles/shell.css       185 行
frontend/src/styles/components.css  311 行
frontend/src/styles/pages.css       491 行
                                  ──────
                                   1208 行（改造前为 8 个文件层层覆盖）
frontend/src/pages/DashboardPage.tsx  23 行
frontend/src/pages/TasksPage.tsx      42 行
frontend/src/pages/SettingsPage.tsx / ProjectsPage.tsx / ProvidersPage.tsx
```

**通道 B — 41 张 before / after 截图逐张对照**

```
改造前：.local/ui-audit/shots/*.png      41 张（完整留存）
改造后：frontend/_shots2/*.png           41 张（本轮采集）
```

两个目录文件名一一对应，可直接并排比对。

**通道 C — 构建产物核验**

```
frontend/dist/assets/  ← 用于验证字体是否真正打包、体积、分片情况
```

---

## 一、先确认：codex 这轮改对了什么

复评不是找茬。以下六项**质量明确高于改造前，属于净收益，后续任何改动都要保护**。

### 1.1 CSS 架构：从「层层覆盖」收敛为单层（架构级收益）

改造前（第一轮评审根因 2）：

```
styles.css (14 KB, 单行) → product.css (19 KB) → simplify.css (26 KB) → ai-picker.css
+ 三个未引入的死文件 phase1.css / phase2.css / final-actions.css
```

改造后：`styles/` 六文件，职责清晰、**全部换行可读**，死文件与 `preview-dist/` 已删除。

这是本轮最有价值的一项。它本身不产生视觉变化，但它是后续所有视觉改动能否落地的前提——改造前的状态是「人和 AI 都改不动」。

### 1.2 StageRail：从「装饰性刻度」变成真正的信号系统

| 项 | 改造前 | 改造后 | 位置 |
|---|---|---|---|
| 底轨 | 每个 `.stage` 各画一段 `.rail-line`，节点间断裂 | `.rail-track` 单条连续贯穿，`right/left: calc(50%/8)` 精确收口 | `components.css:129` |
| 节点编码 | 圆圈内填数字 `1 2 3…` | **去数字，改形状编码** | `components.css:132` |
| 失败态 | 只换边框色（红圈） | **旋转 45° 方块 + 白色 ✕** | `components.css:148-151` |
| 跳过态 | 完全不存在 | 节点画斜杠 + **线段改虚线** `repeating-linear-gradient` | `components.css:153-154` |
| 运行态 | 5px 内点 + 静态 box-shadow | **外扩呼吸环** `inset:-7px` + `railPulse 1.8s` | `components.css:142` |
| 重试可视化 | 无 | 新增 `.repair-loop-band`，带引出线与折角标记 | `components.css:155-159` |

形状编码是关键——**色盲用户与黑白打印下依然可读**，这是第一轮评审 03 册的核心要求，落地了。

### 1.3 任务列表：胶囊行 → 账本表格

第一轮评审引用规范 §16「列表中的连续信息优先通过线、分组和间距组织，**不把每一行包进独立胶囊**」。

改造后 `pages.css` 的 `.task-table`：

```
grid-template-columns: 112px minmax(280px, 1fr) 110px 30px
+ 行间 1px 细线
+ 行首 3px 状态竖条（::before）
```

8 行任务从「8 个独立圆角块」变成一本连续账。**这是本轮视觉变化最大、也最成功的一处**，与「工业修复账本」的方向锚点直接对应。

### 1.4 四个 product pattern 从无到有

| Pattern | 位置 | 视觉手法 |
|---|---|---|
| `NoChangeSurface` | `TasksPage.tsx:20` | 独立 surface + `=` 印章 + 证据计数 |
| `FrozenChange` | `TasksPage.tsx:21` | `border-block: 3px double`（双线＝封存语义） |
| `FailureSurface` | `TasksPage.tsx:18` | 失败码 + 标题 + 摘要 + 提示 + 外部副作用分区 |
| `RepairLoopBand` | `components.css:155` | 引出线折角 + `--reconcile` 紫色边框 |

`3px double` 表达「封存」是本轮**唯一一处真正称得上有设计巧思的形式选择**，值得表扬。

### 1.5 暗色主题：从 11 个变量补到全量，且状态色单独调值

`tokens.css:51-84` 的暗色块不是简单反相——七个状态色全部重新取值（如 `--failed` 从 `#c63f4e` → `#f06e7a`，提亮 + 降饱和），`--shadow-overlay` 也单独加深。这是正确做法。

### 1.6 可访问性与安全边界

- `base.css:51` 用 `:where(button, a, input, select, textarea, summary):focus-visible` 做**全站兜底焦点环**（`0 0 0 3px canvas, 0 0 0 5px signal` 双环，暗底亮底都可见）
- `base.css:60` 补 `.sr-only`
- `base.css:42` `code, .mono` 启用 `tabular-nums`，数字不再跳动
- `base.css:72` 完整 `prefers-reduced-motion` 兜底
- `components.css:213-232` checkbox 自绘（`appearance:none`），消灭系统蓝 ✓
- **`.secret-boundary-note`（`components.css:266`）经确认零明文占位**，连 `••••••` 都没有渲染，`README.md`「配置原则」的安全边界未被改动

---

## 二、核心诊断：为什么「三小时大改造，变化没想象中大」

这是本轮复评最需要回答的问题。四条主因，按对「感知」的影响权重排序。

### 主因 1：骨架一行没动，改的全是皮肤 —— 决定性原因

把 41 张 before / after 并排看完之后，结论很硬：

> **每一个页面的版式结构 100% 一致。**

具体到首页（`01-dashboard-light-full.png` 前后对照）：

| 版式要素 | 改造前 | 改造后 |
|---|---|---|
| 页面骨架 | 顶栏 + 左侧栏 + 主区 | 完全相同 |
| 首屏顺序 | hero → metrics 横条 → 两栏 content-grid | 完全相同 |
| 主区分栏 | `minmax(0,1fr) 350px` | `minmax(0,1fr) minmax(270px,340px)` |
| 任务区形态 | 卡片纵向堆叠 | 卡片纵向堆叠 |
| 右侧 attention | 卡片纵向堆叠 | 卡片堆叠 + 左侧改 1px 竖线分隔 |
| 信息出场顺序 | 概览数字 → 进行中 → 需处理 | 完全相同 |

改动集中在：圆角（15px→7px）、描边色、字号微调、状态色三级化、节点形状。**这些都是「皮肤层」参数。**

人眼判断「一个界面变没变」，依据的是**版式重量的分布**——什么大、什么小、什么在上、什么留白、视线从哪走到哪。这些一个都没动，所以：

> 无论皮肤层改多少参数，第一眼的印象都不会变。这是感知差最主要的来源，**权重超过其余三条之和**。

真正能让你「一眼看出变了」的动作只有三类：改版式骨架、改字形、改动效节奏。本轮三类都没有实质推进（字形见主因 2，动效见主因 4）。

### 主因 2：中文字形基本没变，而中文占 59.6% 的可视宽度

**先给占比证据。** 对 `pages/*.tsx` + `design-system/*.tsx` + `App.tsx` 的 JSX 可见文本节点做字符统计：

```
中文字符 1857，拉丁字符 2522
按字面宽度折算（中文 ≈ 2 倍拉丁宽度）：中文占可视宽度 59.6%
```

（近似口径：只统计 JSX 文本节点与文案字面量，不含 className、不含运行时数据。）

**再看字体栈的实际变化。**

改造前（`git show HEAD:frontend/src/styles.css` 第 1 行）：

```css
:root{font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;...}
```

Inter 从未加载 → 中文实际落到 **微软雅黑 / PingFang SC**。

改造后（`tokens.css:3-5`）：

```css
--font-sans: "IBM Plex Sans", "Noto Sans SC", sans-serif;
--font-cn:   "Noto Sans SC", "IBM Plex Sans", sans-serif;
--font-mono: "IBM Plex Mono", "Noto Sans SC", ui-monospace, monospace;
```

中文实际落到 **Noto Sans SC（＝思源黑体）**。

**问题在这里 —— `base.css:33`：**

```css
h1, h2, h3, h4 { font-family: var(--font-cn); letter-spacing: 0; }
```

全站标题被**主动指定**为中文字体优先。所以：

- **正文中文**：微软雅黑 → 思源黑体。同属现代几何黑体，x-height、字重轴、字面宽度高度接近，在 12–15px 下**肉眼几乎不可分辨**
- **标题中文**：被 `base.css:33` 明确锁死在思源黑体，**IBM Plex Sans 完全无法参与**
- **IBM Plex 的全部辨识度**（方肩、单层 a、斜杠零、窄字腔）只作用在拉丁字符上——而界面里的拉丁字符主要是 **10px 的 mono 工单号和数字**

一句话概括：

> 花力气引入的字体性格，只作用在最小号、最不显眼的那 40% 上；而标题——最该有性格的那一层——被 CSS 明确指向了中文字体。

`08-dashboard-dark.png` 里能看到 Plex Mono 的斜杠零和 `redmine-main #48217` 的字形确实变好了，但这两处加起来占不到画面 5% 的面积。

**附带发现的三个字体工程问题**（会直接影响你看到的效果，一并列出）：

1. **路径走 `node_modules`**：`fonts.css` 全部 8 条 `src: url("../../node_modules/@fontsource/...")`，`public/fonts/` 目录不存在。Vite 能构建（产物已确认打包成功），但这是不该依赖的路径形态

2. **中文字体整包加载、无分片**。构建产物核验：

   ```
   dist/assets/index-*.css 中 unicode-range 出现次数：0

   noto-sans-sc-chinese-simplified-400  1115.8 KB
   noto-sans-sc-chinese-simplified-500  1132.0 KB
   noto-sans-sc-chinese-simplified-600  1135.1 KB
                                      ───────────
                                        3.4 MB
   对比：IBM Plex 全家（Sans 3 档 + Mono 2 档）共 99 KB
   ```

   `@fontsource/noto-sans-sc` 本身提供了 100+ 个 unicode-range 分片文件，当前引法绕过了分片机制，把整本字库拉了下来。

3. **无 `preload`**。`index.html` 与 `dist/index.html` 都只有一条 CSS `<link>`，没有任何字体预载。配合 `font-display: swap`，实际首屏时序是：

   > 先用系统字体画完整页中文 → 1MB 字体到位 → **整页中文跳变一次**

   网络稍慢或首次访问时，**你看到的中文根本就是系统字体**。这可能是「感觉没变」的直接体感来源之一。

### 主因 3：改得最出彩的东西，日常界面上看不到

§1.4 列的四个新 pattern，全部藏在深层：

| Pattern | 触发条件 | 需要几步才能看到 |
|---|---|---|
| `NoChangeSurface` | 任务 `result === 'no_change'` | 进任务页 → 找到一个无需修改的任务 → 点开抽屉 |
| `FrozenChange` | run 存在 `change_manifest` artifact | 进任务页 → 点开抽屉 → 该任务已冻结 |
| `FailureSurface` | 任务 `failure` 非空 | 进任务页 → 点开一个失败任务 |
| `RepairLoopBand` | **repair 重试次数 > 1** | 需要一个真实重试过的任务 |

四个 pattern **零个出现在首页**，最有巧思的 `3px double` 封存线要点开三层才能看到，`RepairLoopBand` 甚至需要特定运行历史。

> 三小时里最有设计含量的产出，全部落在长尾路径上。**你在日常浏览时的确看不到它们。**

### 主因 4：没有动效编排，primitives 零产出

**动效**——全站只有 4 个 keyframes：

```
heartbeat   3s   侧栏健康点（shell.css:142）
railPulse   1.8s StageRail 运行态呼吸环
standby     3s   空态待机信号
reconcile   2.2s 对账态虚线旋转
+ veilIn / overlayIn / toastIn 三个 220ms 的遮罩淡入
```

都是几像素范围内的呼吸点。**没有页面进入的 staggered reveal，没有列表项的错峰出场，没有状态切换的形变过渡。** 页面依然是「啪」地一下瞬间出现——这一点在感知上和改造前完全一致。

`frontend-design` 的原话是「one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions」——本轮做的恰好是后者。

**Primitives**——第一轮路线图 S2 要求的 14 个 design primitives：

```
frontend/src/components/     ← 仍是空目录
frontend/src/design-system/  ← 仍只有 ModeController.tsx + StageRail.tsx
```

**零产出。** 所以每个页面仍在用裸 `<button className="ghost framed">`、裸 `<select>` 拼装，一致性继续靠 CSS 选择器碰运气。

---

## 三、量化对照：第一轮 vs 本轮

| 维度 | 第一轮实测 | 本轮实测 | 判定 |
|---|---|---|---|
| CSS 文件层数 | 4 层覆盖 + 3 死文件 | **单层 6 文件** | ✅ 解决 |
| CSS 是否可读 | 单行压缩 | **全部换行** | ✅ 解决 |
| Web 字体加载 | 0 个 | **8 个 @font-face** | ✅ 解决（但见主因 2） |
| 字体分片 | — | **无 unicode-range，中文 3.4 MB** | ❌ 新问题 |
| 字体 preload | — | **无** | ❌ 新问题 |
| 字号档位 | 17 种，主力 9/10/11px | **14 种，主力 10px×32 / 12px×23 / 11px×21** | ◐ 略好，仍失控 |
| 正文 14px 使用次数 | 1 | **2** | ❌ 未解决 |
| 圆角档位 | 16 种 px 值 | **令牌 4 档 + 裸值 5 处（4px×4、2px×1）+ 999px×2** | ◐ 大幅收敛，未清零 |
| `@keyframes` | 1 个 | **7 个** | ◐ 有进展，无编排 |
| `transition` 声明 | 2 处 | **多处（按钮/输入/导航全覆盖）** | ✅ 解决 |
| 暗色覆盖变量 | 11 / 20 | **全量 + 状态色重新取值** | ✅ 解决 |
| design primitives | 0 / 14 | **0 / 14** | ❌ 零进展 |
| product patterns | 2 / 9 | **6 / 9** | ✅ 显著进展 |
| checkbox 原生蓝 ✓ | 2 处 | **0 处** | ✅ 解决 |
| tabular numerals | 未启用 | **已启用** | ✅ 解决 |
| `:focus-visible` | 1 条 | **全站 `:where()` 兜底** | ✅ 解决 |
| StageRail 阶段覆盖 | 8 / 12 | **8 / 12** | ❌ 零进展 |
| 英文 kicker 数量 | 未统计 | **19 处** | ⚠️ 见 13 册 |
| skeleton loading | 0 处 | **0 处** | ❌ 零进展 |
| visual baseline | 未冻结 | **10 张多态快照 + fixtures** | ✅ 解决 |

**汇总**：✅ 11 项 / ◐ 3 项 / ❌ 6 项 / ⚠️ 1 项。

**解决的 11 项里，有 9 项属于「工程质量」与「可访问性」，只有 2 项（product patterns、StageRail 形状编码）产生了可见的视觉变化。** 这个分布本身就解释了感知差。

---

## 四、残留硬伤（第一轮点名、本轮未修）

以下四条第一轮明确列出，本轮未处理，且在截图中可直接验证：

### 4.1 xs 断点下 tabbar 遮挡最后一行 —— 🔴 明确违反规范 §5.1

截图 `_shots2/21-tasks-xs.png`（420px 宽）：底部固定 tabbar 压住任务表最后一行。

`shell.css:184` 已经写了补偿：

```css
main { padding: 30px 18px calc(92px + env(safe-area-inset-bottom)); }
```

但 `.task-table` 在 `pages.css` 里没有对应的 `margin-bottom`，最后一行仍被 68px 高的 `.navrail` 覆盖。**padding 加在了 `main` 上，而表格的最后一行溢出到了 padding 区之外。**

### 4.2 StageRail 仍只画 8 / 12 个阶段

`DashboardPage.tsx:9` 与 `TasksPage.tsx:11` 的 `order` 数组都是：

```js
['prepare','scope_discovery','discovery','assess','repair','verify','review','deliver']
```

而 `stageLabels` 定义了 12 个。**永远不在轨道上的四个阶段**：

```
workspace_prepare    工作区
no_change_verify     确认      ← TasksPage 借 verify 位显示，Dashboard 完全不显示
pre_delivery_check   检查
freeze_change        冻结      ← 本轮新做的 FrozenChange pattern 对应的阶段，轨道上没有它
```

讽刺的是，本轮新增的 `FrozenChange` 视觉件所对应的 `freeze_change` 阶段，在进度轨道上根本不存在。

### 4.3 首页空态缺「上次检查 N 秒前」

规范 §19 原文要求空态要给出「系统仍在工作」的证据。当前空态（`DashboardPage.tsx:21`）文案是：

```
当前没有进行中的任务
工单轮询正常 · CodeFixer 正在等待下一条修复信号
```

「轮询正常」是一句断言，没有时间戳支撑。加一个每 3 秒更新的「上次检查 2 秒前」，可信度完全不同——而且这是**唯一能让空态页面产生「活着」感的元素**。

### 4.4 组件层仍直接写业务色值（违反规范 §3）

```css
.provider-monogram        { color: #9c2e3d }   /* Redmine */
.provider-monogram.tapd   { color: #2f66bd }   /* TAPD */
.runtime-claudeCode       { color: #b85f42 }
```

比改造前少（原来 4 处硬编码品牌色），但仍未收进令牌层。`#2f66bd` 那块纯蓝在整页暖调里依然突兀。

另：`.segmented button.selected { box-shadow: 0 2px 7px rgba(0,0,0,.07) }` —— 固定黑色阴影，**暗色主题下完全失效**（黑底上的黑阴影不可见），选中态在暗色下失去浮起感。

### 4.5 抽屉展开态未被快照覆盖

```
md5(_shots2/11-task-drawer.png) == md5(_shots2/12-task-drawer-expanded.png)
= 81805a9329381c533e5526aae96b3acf
```

两张截图**像素级完全相同**——说明 `<details className="detail-disclosure">`（`TasksPage.tsx:39`）的展开态从未被采集到。视觉回归设施虽然搭好了，但这一态是盲区。

---

## 五、本册结论

> **codex 这轮改造是一次合格的「工程债清偿」，不是一次视觉改版。**

它把第一轮评审里所有「地基类」问题（CSS 架构、令牌体系、可访问性、暗色、回归设施）解决得相当好，这些是真实且必要的进步，也是后续视觉改版能否顺利的前提。

但它没有触碰任何一个决定「第一眼观感」的变量——版式骨架、中文字形、动效节奏。所以从用户视角看，**投入三小时，感知变化约等于把圆角改小了一点**。这个落差是真实的，不是错觉。

下一轮改动如果只能做三件事，应该是：

1. **改版式骨架**（首页与任务页重新分工，见 [13 册](13-round2-redundancy.md)）
2. **降噪**（删掉 19 处英文 kicker、砍掉三重状态编码，见 [14 册](14-round2-noise-cut.md)）
3. **让中文也有性格**（标题层换字或做字距/字重编排，见 [14 册 §7](14-round2-noise-cut.md)）

这三件事的感知收益，会比本轮已完成的 11 项加起来还大。

---

**下一册** → [13 · 视觉信息重复与页面职责重叠](13-round2-redundancy.md)
