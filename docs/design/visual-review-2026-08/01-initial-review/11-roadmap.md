# 11 · 施工路线图

> 前十册讲"改什么"和"为什么"。这一册讲**按什么顺序改、改完怎么验**。
>
> 面向的执行者可能是 codex，也可能是我。因此这一册的每一步都写到**文件级 + 可验证**，不依赖上下文记忆。

---

## 0. 施工前提

### 0.1 先改规范，再改实现

[10-spec-upgrade.md](10-spec-upgrade.md) 列的 15 项规范改动**必须先落到 `docs/design/design-system.md`**。

原因：如果先改实现，改完之后规范里还写着"72px icon rail"、"圆角四档"、"系统无衬线"，下一个人（或下一次评审）看到实现与规范不符，会把已经改对的东西再改回去。

**这一步大约 1 小时，是整个工程里投入产出比最高的一小时。**

### 0.2 CSS 现状必须先清理

当前 CSS 层的状态（本轮实测）：

```
styles.css          14,175 字符   ← main.tsx 引入
product.css         19,846        ← main.tsx 引入
simplify.css        26,107        ← main.tsx 引入
ai-picker.css          675        ← main.tsx 引入
─────────────────────────────
phase1.css           6,091        ← 死文件，未引入
phase2.css           2,458        ← 死文件，未引入
final-actions.css    1,867        ← 死文件，未引入
```

三个死文件共 10,416 字符，**未被 `main.tsx` 引入，对页面零影响**。

其中 `phase1.css` 有 **5,563 字符（91%）与 `styles.css` 尾部逐字重复**——它是 `styles.css` 的一个旧副本。`phase2.css` 和 `final-actions.css` 则是完全独立的内容（`.task-table` / `.timeline` / `.final-actions-editor` 等），从未生效过。

另外在**已加载**的四个文件里，扫描到 **51 个死类名**（定义了 CSS、TSX 中从不出现，已排除模板字符串动态拼接的类）：

```
action-type advanced-grid advanced-project-body agent-presets bad binding-list
card-title-row compact-action-form compact-check count-badge drawer-split
editor-section editor-section-title empty empty-mark evidence-row eyebrow
failure-code form-hint four inline-builder micro-facts mini-empty mono
muted-copy preflight-mini profile-grid profile-row project-advanced
project-card-head project-card-simple project-editor project-editor-simple
project-spec project-summary result-chip route-signature runtime-glyph
secret-form secret-list settings-advanced settings-secrets side-effects
signal-kicker slotbar span-2 sticky-actions success-banner teal three
```

> 注：`mark` 一词在 TSX 里有 4 次命中，但都来自 `RepairMark` 组件名而非 `className="mark"`，实际也是死的；`.stage-done` 等被 `stage-${state}` 动态拼接，**不是死类**，已排除。

**在动任何视觉之前先删掉这些**。理由很直接：改配色/字体时要全局替换令牌，多 10KB 死代码就多 10KB 的误伤面，而且会让你以为某个样式生效了其实没有。

---

## 1. 阶段划分总览

| 阶段 | 内容 | 预估 | 可独立交付 |
|---|---|---|---|
| **S0** | 规范修订 + CSS 清理 | 2h | ✅ |
| **S1** | 基础层：字体、令牌、圆角、焦点 | 4h | ✅ 全站立刻可见变化 |
| **S2** | Primitives：14 个组件 | 8h | ✅ |
| **S3** | 信号系统：StageRail 重做 + 动效 | 6h | ✅ |
| **S4** | 逐页对齐：5 个页面 | 10h | 可按页拆分 |
| **S5** | 暗色重做 | 3h | ✅ |
| **S6** | Baseline 冻结 + 验收 | 3h | ✅ |

**总计约 36 小时。** 但 S1 结束时"死板"这个观感就会有明显缓解——S1 是分水岭。

如果时间只够做一件事：**做 S1**。如果够做两件：**S1 + S3**。

---

## 2. S0 · 清理（先做，不涉及审美）

### 2.1 删死文件

```bash
git rm frontend/src/phase1.css frontend/src/phase2.css frontend/src/final-actions.css
```

**验证**：`grep -rn "phase1\|phase2\|final-actions" frontend/src/` 应零命中（`main.tsx` 本来就没引）。

### 2.2 删死类

上面 51 个类，逐个从 `styles.css` / `product.css` / `simplify.css` / `ai-picker.css` 里删除对应规则。

**注意**：`empty` / `bad` / `teal` / `three` / `four` / `span-2` 这几个是**修饰类**（`.slotbar .empty`、`.side-effects .bad`），删父类时会一起删掉，不要单独找。

**验证**：
```bash
# 删完后重新跑一遍死类扫描，应为 0
# 且四个页面截图与删除前逐像素一致
npx playwright test --grep @visual
```

### 2.3 合并三层 CSS 为一层

现在的 `styles.css → product.css → simplify.css` 是**三次覆盖**关系，同一个选择器在三个文件里各写一遍，靠加载顺序决定谁赢。这导致：

- 改一个值要在三处找
- `.provider-channel .provider-actions` 这类 bug（`product.css` 写了 `column`，`simplify.css` 忘了重置）
- 无法判断某条规则是否还在生效

**目标结构**（按 S1–S4 逐步迁移，不要求 S0 一次做完）：

```
frontend/src/styles/
  tokens.css        令牌：颜色、字体、间距、圆角、动效、阴影
  base.css          reset、body、排版基线、focus-visible 兜底
  shell.css         topbar / navrail / main / 响应式
  primitives.css    14 个 primitive 的样式
  patterns.css      9+4 个 product pattern 的样式
  pages.css         页面专属（应尽量薄）
```

`main.tsx` 按此顺序引入。**规则：同一个选择器只允许在一个文件里出现。**

> 迁移方式：S1 建 `tokens.css` + `base.css`，S2 建 `primitives.css`，S3–S4 逐步把 `product.css` / `simplify.css` 掏空，最后删掉这两个文件。不要试图一次性重排。

---

## 3. S1 · 基础层（分水岭）

### 3.1 字体（`frontend/public/fonts/` + `tokens.css`）

**① 下载并放置**（内网离线，必须自托管）：

```
frontend/public/fonts/
  ibm-plex-mono-400.woff2   ibm-plex-mono-500.woff2   ibm-plex-mono-600.woff2
  ibm-plex-sans-400.woff2   ibm-plex-sans-450.woff2   ibm-plex-sans-500.woff2   ibm-plex-sans-600.woff2
  noto-sans-sc-400.woff2    noto-sans-sc-500.woff2    noto-sans-sc-700.woff2
```

中文字体体积大（全量 Noto Sans SC 约 8MB/字重），**必须做子集**。两种做法：

- 用 `unicode-range` 按分片加载官方 CDN 切好的分片文件（把分片文件下载到本地）
- 或用 `fonttools pyftsubset` 按项目实际用字子集化（界面中文字数有限，子集后约 200–400KB/字重）

**② `@font-face`**（写在 `tokens.css` 顶部）：

```css
@font-face{font-family:'IBM Plex Mono';src:url('/fonts/ibm-plex-mono-500.woff2') format('woff2');font-weight:500;font-display:swap}
/* …其余 9 条同理 */
```

**③ 令牌**：

```css
--font-mono:'IBM Plex Mono',ui-monospace,'Cascadia Mono',Consolas,monospace;
--font-sans:'IBM Plex Sans','Noto Sans SC',system-ui,'Microsoft YaHei',sans-serif;
```

**④ 全局替换**：`styles.css:1` 的 `font-family:Inter,...` 改为 `font-family:var(--font-sans)`；全站 `ui-monospace,SFMono-Regular,Consolas,monospace` 字面量（约 20 处）改为 `var(--font-mono)`。

**验证**：DevTools → Network 过滤 font，应看到 woff2 请求且 200；Computed 面板里 `body` 的 font-family 首项为 `IBM Plex Sans`。

> **这一步单独做完就应该截图对比一次**。字体是本次改动里视觉冲击最大的单项。

### 3.2 令牌表（`tokens.css`）

照抄 [02 §3](02-foundation.md) 的完整令牌表。清单：

- 中性色 light/dark 各 9 值（含新增 `--surface-raised`）
- signal 六级
- 状态色 7×3 = 21 值（graphic / text / soft）
- 12 档 type scale（用 `font:` 简写，带 family）
- 间距 `--s-*` 八档
- 圆角 `--r-sharp/card/modal/dot` 四值
- 动效 `--d-*` 五档 + `--e-*` 三条
- 阴影 `--shadow-*` 三档（替换 15 处 `rgba(30,40,33,…)` 字面量）

**同时保留旧变量名作为 alias**，让改造可以分批：

```css
:root{
  --surface2:var(--surface-2);
  --lineStrong:var(--line-strong);
  --signalSoft:var(--signal-50);
  --success:var(--st-success); --nochange:var(--st-nochange);
  --warning:var(--st-warning); --failed:var(--st-failed);
  --reconcile:var(--st-reconcile); --side:var(--st-side);
}
```

> ⚠️ **alias 只解决色值映射，不解决文字对比度。** 全站 20+ 处 `color:var(--failed)` 之类必须**手动**改成 `color:var(--st-failed-text)`。alias 会让它们"看起来没坏"，但对比度问题依然存在。
>
> 检查方法：`grep -n "color:var(--st-[a-z]*)" *.css`，凡是 `color:` 后面跟非 `-text` 后缀的状态色，全部违规。

### 3.3 圆角收敛

全局替换 16 种像素值 → 四档：

| 原值 | 改为 |
|---|---|
| `4px` `5px` `6px` `7px` | `var(--r-sharp)` (2px) |
| `9px` `10px` `12px` | `var(--r-card)` (6px) — 卡片/面板；按钮和输入框改 `--r-sharp` |
| `15px` `16px` `18px` | `var(--r-modal)` (10px) — 仅 Dialog/抽屉/Toast；卡片降到 `--r-card` |
| `999px` | **删除**，改 `--r-sharp` |
| `50%` | `var(--r-dot)` — 仅状态点与 rail 节点 |

**同时删掉列表行的圆角**：`.task-row` / `.dependency-row` / `.delivery-target` / `.artifact-list > div` / `.timeline .event` 五处，`border-radius` 归零，改用 `border-bottom:1px solid var(--line)` 分隔（最后一行 `border-bottom:0`）。

**验证**：`grep -o 'border-radius:[^;}]*' *.css | sort -u` 应只剩四个 `var(--r-*)`。

### 3.4 焦点态

现有 `simplify.css:12` 那条覆盖 8 类、对比度 1.3:1。替换为：

```css
/* 兜底：所有可聚焦元素 */
:where(a,button,input,select,textarea,summary,[tabindex]):focus-visible{
  outline:2px solid var(--signal);
  outline-offset:2px;
  border-radius:var(--r-sharp)
}
/* 行/卡片这类大块，用内描边避免 outline 被裁切 */
.task-row:focus-visible,.project-ledger-card:focus-visible{
  outline:none;
  box-shadow:inset 0 0 0 2px var(--signal)
}
```

用 `:where()` 是为了让特异性为 0，任何组件都能覆盖它，但默认永远有。

**验证**：从地址栏按 Tab 走完首页所有可交互元素，**每一个都要有可见焦点环**，包括 `.task-row`、`.navrail button`、`.danger-button`、模态内的按钮。

### 3.5 交互基线

```css
button,a,input,select,textarea,.task-row,.project-ledger-card,.provider-card{
  transition:background-color var(--d-fast) var(--e-standard),
             color var(--d-fast) var(--e-standard),
             border-color var(--d-fast) var(--e-standard),
             box-shadow var(--d-fast) var(--e-standard)
}
```

一条规则，全站 hover 从跳变变过渡。同时补 `.primary` 缺失的 hover（现在**主按钮没有任何 hover 反馈**）。

### 3.6 tabular-nums

```css
.mono,code,kbd,[class*="metric"] span,.stage small,.slots b,
.capacity-meter,.task-meta time{
  font-variant-numeric:tabular-nums;
  font-feature-settings:'zero' 1   /* Plex Mono 的 slashed zero */
}
```

**验证**：任务页开着不动，看 3 秒轮询时耗时数字**宽度不跳**。

### S1 验收

- [ ] Network 里能看到 woff2 加载，页面用的是 Plex
- [ ] 全站无 `border-radius:999px`
- [ ] 列表行之间是细线，不是一行一个胶囊
- [ ] Tab 走一遍，每个元素都有清晰焦点环
- [ ] hover 有过渡，主按钮有 hover
- [ ] 数字不跳宽
- [ ] `grep 'color:var(--st-[a-z]*)'` 零命中（都改成了 `-text`）

---

## 4. S2 · Primitives（`frontend/src/components/`）

目录当前**存在但为空**。按此顺序建，前面的是后面的依赖：

| 序 | 文件 | 依赖 | 关键点 |
|---|---|---|---|
| 1 | `Button.tsx` | — | `.primary` 改 `--signal` 实心、`width:auto`；`.compact` 语义改为"小号" |
| 2 | `IconButton.tsx` | — | 强制 `aria-label` 必填（TS 类型上就要求） |
| 3 | `StatusChip.tsx` | — | 七状态 × 三密度，统一现在的 7 套 badge |
| 4 | `StatusDot.tsx` | — | **颜色 + 形状双编码**（done=实心 / running=环 / failed=方块 / queued=空心） |
| 5 | `Field.tsx` | — | `htmlFor` 自动关联、hint、error 三态 |
| 6 | `Input.tsx` `Select.tsx` `Checkbox.tsx` | Field | `appearance:none` 全套重写，含**当前完全没样式的原生 checkbox** |
| 7 | `Spinner.tsx` | — | 三尺寸，配 caption，1 秒后才出现 |
| 8 | `Skeleton.tsx` | — | 与最终布局同形，**当前全站 0 个** |
| 9 | `ModalShell.tsx` | — | 焦点陷阱 + Esc + 锁 body 滚动 + 焦点恢复 + `onMouseDown` 防误关 |
| 10 | `EmptyState.tsx` | — | 五个 kind |
| 11 | `Toast.tsx` | — | 四类生命周期，白底 + 左侧 3px 状态条 |
| 12 | `BoundaryNote.tsx` | — | 三 kind，虚线左边框 |
| 13 | `Divider.tsx` `Surface.tsx` `CodeText.tsx` | — | 简单，最后补 |
| 14 | `Tooltip.tsx` `Popover.tsx` | — | 优先级最低，当前没有真实需求 |

**关键约束**：每个组件的样式写在 `styles/primitives.css`，**不用 CSS-in-JS、不用 CSS Modules**——与现有工程保持一致，避免引入新的构建复杂度。

### 建组件后的替换顺序

不要写完 14 个再一起替换。**每写完一个立刻全局替换**，这样每一步都能截图验证：

```
Button → 替换 13 处 .primary + 13 处 .ghost
StatusChip → 替换 7 套 badge（这一步视觉变化最大）
ModalShell → 替换 4 个模态
Field/Input/Select/Checkbox → 替换设置页 + 三个编辑器
```

### S2 验收

- [ ] `frontend/src/components/` 下有 14 个文件
- [ ] 全站按钮只有 Button/IconButton 两种来源，`.primary` / `.ghost` 的裸 CSS 已删
- [ ] checkbox 是自绘的，有 hover/focus/checked/disabled 四态
- [ ] 模态：Esc 能关、Tab 不跑到背后、关闭后焦点回到触发按钮、背景不滚动
- [ ] 四个页面首次加载显示 skeleton，不闪错误空态
- [ ] 「取消任务」按钮弹确认框，主按钮文案是 `终止 Repair Agent`

---

## 5. S3 · 信号系统

这是让界面"活起来"的一步，也是与 §2/§6 规范差距最大的一步。

### 5.1 StageRail 重做（`design-system/StageRail.tsx` + `patterns.css`）

现在 20 行的实现要扩到约 120 行。按 [03](03-signal-system.md) 做，要点：

1. **连续轨道**：现在每个 stage 各自一截 `.rail-line`，改为一条贯穿的底轨 + 分段覆盖
2. **去掉节点数字**：改为形状编码（实心/双环/空心/斜杠/断口）
3. **补齐 4 个丢失的阶段**：`TasksPage.tsx:11` 的 `order` 数组只有 8 项，`stageLabel` 有 12 项。**`freeze_change` 必须回到轨道上**
4. **failed 断口**：轨道在失败节点处物理断开 + notch
5. **skipped**：短虚线 + 斜杠（当前 `.stage-skipped` CSS 完全不存在）
6. **reconciling**：沿边缘的 traveling signal
7. **呼吸环**：从 5px 内点改为 12px 外环（**当前的动画肉眼不可见**）
8. **ARIA**：每个 stage 补 `<span class="sr-only">已完成</span>`，屏幕阅读器现在读不出状态

### 5.2 RepairLoopBand（新组件）

规范 §6.3 明确写「不得在 Rail 上假装成一次线性通过」。主轨道下方加折返带，任务卡上显示 `Repair loop ×2`。

### 5.3 九个动效

按 [08 §3](08-motion-theme.md) 的 P0 → P1 → P2 顺序。

**P0 三个做完就够看了**：rail 呼吸环、轨道扫描光、侧栏轮询心跳。

心跳这个要特别说一下：它是**成本最低、心理效果最强**的一个。6px 的点每 3 秒亮一下，88% 的时间是暗的，不构成噪音，但它把"界面上什么都没发生"从"是不是坏了"变成"系统在待命"。

### 5.4 reduced-motion

按 [08 §5](08-motion-theme.md) 的两层写法：全局压零 + 三个信息性动效提供静态替代 + spinner 放慢不停止。

### S3 验收

- [ ] 轨道是连续的一条线，不是 8 截
- [ ] 节点上没有数字
- [ ] 12 个阶段全部在轨道上（含 `freeze_change`）
- [ ] failed 处轨道断开
- [ ] running 节点的呼吸**看得见**（离屏幕 60cm 能察觉）
- [ ] 侧栏底部心跳每 3 秒跳一次
- [ ] 开启系统"减少动态效果"后，动画停止但状态仍可辨识
- [ ] 空闲时整页只有心跳在动（盯 10 秒确认）

---

## 6. S4 · 逐页对齐

五个页面按此顺序（从改动小的开始，积累信心）：

| 序 | 页面 | 主要改动 | 参考 |
|---|---|---|---|
| 1 | 来源页 | `.provider-channel .provider-actions` 一行修 flex-direction；monogram 去硬编码品牌色；补 secret BoundaryNote | [06 §3](06-pages-projects-providers-settings.md) |
| 2 | 设置页 | 去掉 `min-height:310px` 三件套改 `align-items:start`；补 CapacityMeter；`dependencyId` 加中文名双行 | [06 §4](06-pages-projects-providers-settings.md) |
| 3 | 项目页 | 竖栏按 `data-health` 着色；按钮主次对调；长路径 rtl 省略；checkbox 换组件；补 localpath BoundaryNote | [06 §1–2](06-pages-projects-providers-settings.md) |
| 4 | 首页 | metrics 去投影改细线；空态改 standby（补"上次检查 N 秒前"）；attention 区改 FailureSurface | [05](05-pages-dashboard-tasks.md) |
| 5 | 任务页 | 行改细线分隔；补 NoChangeSurface；抽屉 `top:-28px` 负值 hack 修复；Evidence 加编号；timeline 事件中文化 | [05](05-pages-dashboard-tasks.md) |

任务页放最后是因为它牵扯最多（StageRail、抽屉、Failure、NoChange、Evidence、Timeline 六个东西）。

**Shell 的改动**（[04](04-shell.md)）穿插在第 1 步之前做：侧栏 176→200px、四档响应式、**修 420px 下内容被 tabbar 遮挡**、模式控制器移到侧栏顶部、侧栏底部加状态区。

### S4 验收（逐页）

- [ ] 来源页操作按钮横排
- [ ] 设置页卡片高度自适应，无大片留白
- [ ] 项目页停用项目一眼可辨（虚线竖栏）
- [ ] 首页空态读起来像"待命"不是"坏了"
- [ ] 任务页 `no_change` 与 `succeeded` 视觉可区分
- [ ] 420px 宽度下所有内容可见可点，无遮挡

---

## 7. S5 · 暗色

按 [08 §6](08-motion-theme.md) 做。现在只覆盖 11 个变量，7 个状态色直接沿用亮色。

四步：
1. 换完整暗色令牌（状态色单独调值、signal 提亮、soft 改深调、表面拉四层）
2. 修 8 个具体问题（inset 白高光、硬编码品牌色、遮罩太浅、黑投影失效、Toast 反色、15 处 rgba 字面量、canvas/surface 差距太小）
3. 图纸格线与噪点换参数（暗色下 `mix-blend-mode` 要从 overlay 改 soft-light）
4. 只给主 CTA 和 running 节点加 halo

### S5 验收

- [ ] 8 张 dark 截图逐张目视通过（清单见 [08 §6.5](08-motion-theme.md)）
- [ ] 所有状态文字对比度 ≥4.5:1
- [ ] 无 `rgba(30,40,33,` 残留
- [ ] 主题刷新后保持，默认跟随系统，三态循环

---

## 8. S6 · Baseline 与验收

### 8.1 现有设施可以直接用

好消息：`frontend/playwright.config.ts` 里这四项**已经配对了**——

```ts
viewport: {width:1440, height:900}     // 与规范 §5.1 baseline 一致
locale: 'zh-CN'
timezoneId: 'Asia/Singapore'
expect: {toHaveScreenshot:{animations:'disabled'}}
```

`animations:'disabled'` 尤其重要——S3 加完 9 个动效后，没有这一项 baseline 会随机失败。

需要补的是**数量**和**可复现性**。

### 8.2 补 fixtures

新建 `frontend/e2e/fixtures/`，为每个 baseline 准备一份 JSON：

```
dashboard-empty.json          dashboard-loaded.json
tasks-running.json            tasks-failed.json
task-detail-changed.json      task-detail-no-change.json
task-detail-repair-loop.json  task-detail-partial-delivery.json
project-preflight-ready.json  project-preflight-failed.json
```

用 `page.route('**/api/**', route => route.fulfill({json: fixture}))` 注入。

**这解决了两个问题**：一是 `task-detail-repair-loop` 这类状态不用等真实数据；二是现有 `phase0.spec.ts` 里写死的真实工单标题断言（`【4.7】【商城】购买礼包后偶现红点未刷新`）不再依赖数据库内容。

### 8.3 补 @visual 断言

11 个 baseline × light/dark = 22 张，加上 dashboard/tasks 两页的 1280/1024/420 三档响应式 = 28 张。

```ts
for (const theme of ['light','dark']) {
  test(`@visual dashboard-${theme}`, async ({page}) => {
    await mockApi(page, 'dashboard-loaded')
    await page.goto('/')
    await setTheme(page, theme)
    await expect(page).toHaveScreenshot(`dashboard-${theme}.png`, {fullPage:true})
  })
}
```

### 8.4 处理跨平台快照

现在 `e2e/phase0.spec.ts-snapshots/` 下同时有 linux 和 win32 两个版本的同一张图，**体积差 3 倍**（138KB vs 49KB）——这说明两个平台渲染出来的东西差异极大，主要来源是字体。

S1 换成自托管 woff2 后这个差距会大幅缩小，但**不会完全消失**（子像素抗锯齿策略仍不同）。建议：

- 在 CI 里固定一个平台跑 visual test（推荐 linux 容器）
- 本地开发用 `--update-snapshots` 时注意不要提交本机平台的快照
- 或者在 `playwright.config.ts` 里设 `snapshotPathTemplate` 去掉平台后缀，只保留一套

### 8.5 清理调试产物

`phase0.spec.ts` 里的 `proof()` 函数往 `test-results/proof/` 写全页截图——这些是**调试用的**，不是 baseline，不应该被误认为验收依据。建议保留但在文件头注释里写清楚两者区别。

另外本次评审用的临时脚本 `frontend/ui-audit-shots.mjs` 已完成使命，改造时删掉即可（它的 mock 逻辑可以搬进 `e2e/fixtures/`）。

---

## 9. 最小可行版本（如果时间很紧）

假设只有一天。按这个顺序做，做到哪算哪：

| 序 | 事项 | 耗时 | 收益 |
|---|---|---|---|
| 1 | 换字体（IBM Plex + Noto Sans SC） | 1h | ★★★★★ 单项视觉变化最大 |
| 2 | 圆角收敛 + 删列表行胶囊 | 1h | ★★★★★ 直接消除"死板" |
| 3 | 状态色 `-text` 变体 + 全局替换 | 1h | ★★★★ 可读性 |
| 4 | 焦点态 + 交互过渡基线 | 0.5h | ★★★★ 手感 |
| 5 | rail 呼吸环放大 + 侧栏心跳 | 1h | ★★★★ "活着" |
| 6 | 主按钮改橙色实心 | 0.5h | ★★★ 主次分明 |
| 7 | Toast 自动消失 + 白底状态条 | 0.5h | ★★★ |
| 8 | ModalShell（Esc/陷阱/锁滚） | 1h | ★★★ 可用性 |
| 9 | 修 420px 遮挡 + 来源页 flex 一行修 | 0.5h | ★★ 硬伤 |

**九项共 7 小时，覆盖了"死板"这个问题 70% 的成因。**

前四项是纯 CSS 改动，不碰任何 TSX 逻辑——**对一个"还没开始实测功能"的原型来说，这是风险最低的改法**。

---

## 10. 给执行者的注意事项

### 10.1 不要动的东西

- **配置边界**：`.local/config.json` 的本机路径、`executableRef`、`SecretRef`、Secret 只返回 `configured` 状态——这四条是 `README.md` 定的工程边界。本评审的全部建议都在这些边界内（[10 §11](10-spec-upgrade.md) 的 BoundaryNote 是**把边界可视化**，不是改变边界）
- **API 契约**：所有改动都是前端视觉层，不需要后端配合。唯一的例外是 [04 §4](04-shell.md) 建议模式确认框显示队列数/就绪项目数/并发上限——这三个数**已经在现有 API 响应里**（`dashboard.metrics.queued` / `readiness` / `execution.maxConcurrentTasks`），只是 UI 没取
- **`prefers-reduced-motion:no-preference` 的包裹写法**：现有唯一那个动画的写法是对的，新动效照抄这个模式

### 10.2 每一步都截图

每完成一个小节，跑一次：

```bash
cd frontend && npx playwright test --grep @visual --update-snapshots
git add -A && git commit -m "视觉: <这一步做了什么>"
```

**不要攒一大堆改动再看效果**。视觉改造最容易出的问题是"每一步都合理，合起来变难看"。

### 10.3 遇到分歧时的判据

按优先级：

1. **规范怎么写的**（改完 S0 之后，`design-system.md` 是唯一权威）
2. **§2.1 的六个关键词**：precise / kinetic / engineered / calm under load / traceable / slightly futuristic —— 拿不准就问"这个改动让哪个词更强了"
3. **[01 §1](01-direction.md) 的三个意象锚点**：示波器、账本、机床铭牌 —— 如果一个设计选择在这三个东西上都找不到依据，它大概率是从别的 SaaS 抄来的

### 10.4 什么时候停

规范 §28 写了四种**不接受**的完成标准。反过来，可以停的判据是：

- 11 个 baseline 全部截得出来且稳定
- 五个页面在 1440/1280/1024/420 四档下都可用
- light/dark 两套下所有文字对比度达标
- Tab 能走完所有交互，模态行为正确
- 空闲时整页只有心跳在动

这五条全过，就可以停了。

---

## 附：分册索引

| 册 | 内容 |
|---|---|
| [00-verdict](00-verdict.md) | 总体判断与十个核心缺陷 |
| [01-direction](01-direction.md) | 视觉方向：工业修复账本 |
| [02-foundation](02-foundation.md) | 令牌层：色彩、字体、间距、圆角、动效 |
| [03-signal-system](03-signal-system.md) | StageRail 与信号语言 |
| [04-shell](04-shell.md) | App Shell、导航、响应式 |
| [05-pages-dashboard-tasks](05-pages-dashboard-tasks.md) | 首页与任务页 |
| [06-pages-projects-providers-settings](06-pages-projects-providers-settings.md) | 项目页、来源页、设置页 |
| [07-controls-overlays](07-controls-overlays.md) | 按钮、表单、模态、抽屉、Toast、空态 |
| [08-motion-theme](08-motion-theme.md) | 动效落地与暗色重做 |
| [09-spec-debt](09-spec-debt.md) | 规范欠账对照表 |
| [10-spec-upgrade](10-spec-upgrade.md) | 规范本身的升级主张 |
| **11-roadmap** | **本册：施工顺序与验收** |
