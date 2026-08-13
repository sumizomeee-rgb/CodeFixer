# 02 · 基础层重写（令牌 / 字体 / 色彩 / 形状 / 间距 / 动效）

> 本册的 CSS 可以直接落地。建议新建 `frontend/src/tokens.css`，作为 `main.tsx` 的**第一个** import，然后逐步把 `styles.css` 里的令牌段删掉。

---

## 1. 字体 【实现硬伤 + 规范升级】

### 1.1 问题

`frontend/src/styles.css:1`：

```css
:root{font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;...}
```

`frontend/index.html` **没有任何字体加载**（无 `<link>`、无 `@font-face`）。Inter 从未生效，Windows 中文环境实际渲染为 **Segoe UI + 微软雅黑混排**。

证据：所有截图里拉丁字符（`redmine-main #48217`、`verification_failed`）与中文的基线、灰度、字面宽度都不匹配；9–11px 的中文笔画糊成灰块。

### 1.2 改法

**Step 1** — `frontend/index.html` `<head>` 内加入（在 `<title>` 之后）：

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;450;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap">
```

> ⚠️ **离线部署注意**：CodeFixer 部署在公司内网（`10.101.0.8`），Google Fonts 很可能不可达。**推荐做法**：把三个字体的 woff2 子集下载到 `frontend/public/fonts/`，用 `@font-face` 本地引入，`font-display:swap`。中文用 `unicode-range` 切子集，只保留常用 3500 字，体积可控在 ~400 KB。这也符合 `README.md` 里"不依赖外部托管平台"的整体取向。

本地方案示例（放在 `tokens.css` 顶部）：

```css
@font-face{font-family:"Plex Mono";src:url("/fonts/IBMPlexMono-Regular.woff2") format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"Plex Mono";src:url("/fonts/IBMPlexMono-Medium.woff2") format("woff2");font-weight:500;font-display:swap}
@font-face{font-family:"Plex Mono";src:url("/fonts/IBMPlexMono-SemiBold.woff2") format("woff2");font-weight:600;font-display:swap}
@font-face{font-family:"Plex Sans";src:url("/fonts/IBMPlexSans-Regular.woff2") format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"Plex Sans";src:url("/fonts/IBMPlexSans-Text.woff2") format("woff2");font-weight:450;font-display:swap}
@font-face{font-family:"Plex Sans";src:url("/fonts/IBMPlexSans-Medium.woff2") format("woff2");font-weight:500;font-display:swap}
@font-face{font-family:"Plex Sans";src:url("/fonts/IBMPlexSans-SemiBold.woff2") format("woff2");font-weight:600;font-display:swap}
@font-face{font-family:"Noto SC";src:url("/fonts/NotoSansSC-Regular.woff2") format("woff2");font-weight:400;font-display:swap;unicode-range:U+4E00-9FFF,U+3000-303F,U+FF00-FFEF}
@font-face{font-family:"Noto SC";src:url("/fonts/NotoSansSC-Medium.woff2") format("woff2");font-weight:500;font-display:swap;unicode-range:U+4E00-9FFF,U+3000-303F,U+FF00-FFEF}
@font-face{font-family:"Noto SC";src:url("/fonts/NotoSansSC-Bold.woff2") format("woff2");font-weight:700;font-display:swap;unicode-range:U+4E00-9FFF,U+3000-303F,U+FF00-FFEF}
```

**Step 2** — 字体栈令牌：

```css
:root{
  --font-sans:"Plex Sans","Noto SC","PingFang SC",sans-serif;
  --font-mono:"Plex Mono","Noto SC",ui-monospace,SFMono-Regular,monospace;
}
```

**Step 3** — 使用界线（**这条是设计决策，不只是技术配置**）：

| 用 `--font-mono` | 用 `--font-sans` |
|---|---|
| 任务 ID / 运行 ID / hash | 工单标题 |
| 工单号 `#48217` | 失败说明与建议文案 |
| 阶段耗时 `43 秒` | 页面标题与小节标题 |
| 指标数字 `27` | 按钮文字 |
| 失败码 `verification_failed` | 表单 label 与说明 |
| 文件路径 / 分支名 | 空态文案 |
| 卡片角标 `01`–`04` | 导航 label |
| 大写 kicker（`AUTOMATION`） | — |
| **h1 页面主标题** | — |

> h1 用 mono 是本方案最有态度的一处。`维修控制台` / `任务` / `设置` 用 IBM Plex Mono 600，配 `.08em` 字距——立刻从"后台管理系统"变成"设备控制面板"。这一处改动的视觉收益最大。

**Step 4** — 删除 `styles.css:1` 里的 `font-family:Inter,...`，改为：

```css
:root{font-family:var(--font-sans);font-feature-settings:"cv05" 1,"ss01" 1;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
```

---

## 2. 字号与排版 Scale 【规范欠账】

### 2.1 问题

规范 §4.2 定义了七档 Type Scale，实现完全没有采用。实测：9px 26 处、10px 33 处、11px 27 处，而 body 级 14px 只有 **1 处**；`h1{font-size:34px}` 超出规范 32px。

### 2.2 改法

**严格采用规范 §4.2 的七档（字重逐位对齐），并补四档**（标注为规范升级）：

```css
:root{
  /* ---- 规范 §4.2 原有七档，weight/size/line-height 完全照搬 ---- */
  --t-display:      650 32px/38px var(--font-mono);   /* display */
  --t-title:        650 24px/30px var(--font-mono);   /* page-title */
  --t-section:      650 16px/22px var(--font-sans);   /* section-title */
  --t-body:         450 14px/20px var(--font-sans);   /* body —— 主力 */
  --t-body-strong:  600 14px/20px var(--font-sans);   /* body-strong */
  --t-caption:      500 12px/17px var(--font-sans);   /* caption */
  --t-micro:        550 11px/15px var(--font-sans);   /* micro —— 最小可读 */
  --t-mono:         500 12px/18px var(--font-mono);   /* mono */

  /* ---- 本评审新增四档【规范升级】 ---- */
  --t-subhead:      550 15px/21px var(--font-sans);   /* 卡片内小标题：section 与 body 之间缺一档 */
  --t-body-sm:      450 13px/19px var(--font-sans);   /* 密集列表正文：任务行 14px 太挤、12px 太小 */
  --t-mono-sm:      500 11px/16px var(--font-mono);   /* 密集 mono：rail 耗时、行内 ID */
  --t-kicker:       600 10px/12px var(--font-mono);   /* 大写铭牌标签，配 .16em 字距，仅限拉丁 */
}
```

> **为什么 display / page-title 用 mono**：规范 §4.1 只说"数据/代码/SHA/耗时用等宽"，没规定标题字体。把 display 和 page-title 也交给 mono 是本评审的主张——见 §1.3 的理由。字号字重不动，只换 family，风险很低、收益最大。
>
> **`--t-kicker` 是新增的第八档**，规范里没有，但实现里已经到处在用 8–9px 大写小标签（`.control-card>header small`、`.modal-kicker`、`.project-ledger-card header small`）。与其放任它们各写各的，不如正式立一档 10px，并**限定只用于大写拉丁**（中文 10px 不可读）。

**硬性规则**：

1. **9px 全站禁用**。当前 26 处 9px 全部提到 11px（`--t-micro`）或 10px kicker（仅限大写拉丁）。
   - 需要改的典型：`.filter-strip em{font:700 9px ...}`、`.control-card .card-index{font:700 9px ...}`、`.control-card>header small{font:700 8px ...}`、`.project-ledger-card header small{font:700 9px/1 ...}`。
   - 8px 的两处（`.control-card>header small` 等）**必须**改，8px 中文完全不可读。

2. **`.stage strong,.stage small{font-size:10px}`（`styles.css`）→ 分离**：`strong` 用 `--t-micro`(11px)，`small` 用 `--t-mono-sm`(11px mono)。见 [03](03-signal-system.md)。

3. **h1 改造**：

```css
h1{font:var(--t-display);letter-spacing:.06em;text-transform:none;margin:0 0 6px}
h1:lang(zh),h1{letter-spacing:.02em}   /* 中文不用负字距，也不用大字距 */
```

> 现状 `letter-spacing:-.045em` 在 34px 中文标题上导致字面粘连（见 `01-dashboard-light-full` 的"维修控制台"）。mono 字体本身字面就宽，不需要负字距。

4. **tabular numerals 全站启用**【规范 §4.3 欠账】：

```css
:root{font-variant-numeric:tabular-nums}
.metric span,.stage small,.concurrency-control strong,.slots b,.mode-controller em{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
```

必要性：任务列表 3 秒轮询、抽屉 2 秒轮询，比例数字会让"43 秒 → 44 秒"整行左右跳动。

5. **kicker 统一**：

```css
.kicker,.control-card>header small,.project-ledger-card header small,.modal-kicker,.provider-body>small{
  font:var(--t-kicker);letter-spacing:.16em;text-transform:uppercase;color:var(--text-tertiary)
}
```

---

## 3. 色彩 【规范欠账 + 实现硬伤】

### 3.1 问题

**先说做对的**：7 个状态色与规范 §3.3 **逐位相同**（`--success:#36a26b`、`--nochange:#3c8c91`、`--warning:#d69a32`、`--failed:#d94a55`、`--reconcile:#7d68c7`、`--side:#c258a0`），`--signal:#f4603c` 与 `--signalSoft:#fff1ec` 也精确对应 `signal-500` / `signal-50`。**色值本身不用改**，问题在其它五处：

1. **两个中性色偏离规范**：规范 §3.1 定义 light `text-secondary #5D655F` / `text-tertiary #858D87`，实现是 `--muted:#657068` / `--tertiary:#8b948e`。命名也不一致（`muted`/`tertiary` vs `text-secondary`/`text-tertiary`）。
2. **`--side:#c258a0` 定义了但全站零使用**——`side_effects` 是本产品最需要被看到的信息（见 §3.4）。
3. **暗色只覆盖 11 个变量，7 个状态色沿用亮色**——见 [08 §6](08-motion-theme.md)。
4. **硬编码第三方品牌色 4 组、rgba 字面量 15 处**——违反规范 §3 首句"组件禁止直接写业务色值"。
5. **色阶不足**：`--signal` 只有 2 级，规范 §3.2 给了 6 级（`signal-50/100/300/500/600/700`）却只实现了 2 级；状态色一级都没有，导致代码里到处写 `color-mix(in srgb,var(--failed) 12%,transparent)`（实测 20+ 处）。

### 3.1b 一个必须处理的对比度问题 【规范升级】

规范 §3.3 的状态色是按**图形色**（状态点、边框、进度条）选的，在白底上约 **3.2:1**（`#36A26B` 实测 3.21:1），满足 WCAG 非文字元素的 3:1。

但实现把它们直接**当文字色**用：

```css
.readiness-badge.ready{background:color-mix(in srgb,var(--success) 12%,transparent);color:var(--success)}
.error-note{color:var(--failed)}
.preflight-mini .ready i{background:var(--success)}
```

文字要求 4.5:1，`#36A26B` 不够。规范 §3.4 写了"正文和关键状态文本必须满足可读对比"、§23 写了"不用低对比灰字展示重要失败原因"——**这两条现在是不满足的**。

**改法：状态色分两级，不改规范给的图形色。**

| 用途 | 令牌 | 值 |
|---|---|---|
| 图形（点 / 边框 / 竖条 / 进度） | `--st-success` 等 | **保持规范值不变** |
| 文字（badge 文字 / 失败说明） | `--st-success-text` 等 | 同色相压暗至 ≥4.5:1 |
| 底色（softly tinted 背景） | `--st-success-soft` 等 | 同色相提亮 |

### 3.2 改法：完整令牌表

```css
:root{
  color-scheme:light;

  /* — 表面（严格采用规范 §3.1 Light 值） — */
  --canvas:#f5f6f4;
  --surface:#ffffff;
  --surface-2:#f0f2ef;
  --surface-3:#e6e9e4;      /* 新增：三级底，用于 inset 区域 */
  --surface-raised:#ffffff; /* 规范 §3.1 有此项，实现缺失 */
  --line:#d8dcd6;
  --line-strong:#b7bdb5;
  --line-heavy:#8d968b;     /* 新增：Frozen Change 的硬边 */

  /* — 文字（对齐规范 §3.1，修正现有两处偏差） — */
  --text:#171a17;
  --text-secondary:#5d655f;  /* 规范值，替换 --muted:#657068 */
  --text-tertiary:#858d87;   /* 规范值，替换 --tertiary:#8b948e */
  --text-inverse:#f7f9f6;

  /* — 信号色阶（补全规范 §3.2 的 6 级） — */
  --signal-50:#fff1ec;       /* = 现 --signalSoft */
  --signal-100:#ffd8cc;
  --signal-300:#ff9a7a;
  --signal:#f4603c;          /* = signal-500，规范值 */
  --signal-hover:#da4c2c;    /* = signal-600，规范值 */
  --signal-press:#b83b20;    /* = signal-700，规范值 */
  --signal-soft:var(--signal-50);
  --signal-line:var(--signal-300);
  --signal-text:#b83b20;     /* = signal-700，白底 5.9:1 ✓ */

  /* — 状态色：图形级，全部保持规范 §3.3 原值 — */
  --st-success:#36a26b;
  --st-nochange:#3c8c91;
  --st-warning:#d69a32;
  --st-failed:#d94a55;
  --st-reconcile:#7d68c7;
  --st-side:#c258a0;
  --st-queued:#858d87;       /* 新增：排队/未开始，= text-tertiary，明确是灰而非无色 */

  /* — 状态色：文字级（新增，同色相压暗至白底 ≥4.5:1） — */
  --st-success-text:#1f7048;
  --st-nochange-text:#2a6367;
  --st-warning-text:#8a5c12;
  --st-failed-text:#a92b36;
  --st-reconcile-text:#584399;
  --st-side-text:#8f3771;

  /* — 状态底色（新增，替代到处写 color-mix） — */
  --st-success-soft:#e9f5ef;
  --st-nochange-soft:#e8f2f3;
  --st-warning-soft:#fbf3e3;
  --st-failed-soft:#fbecee;
  --st-reconcile-soft:#efecf9;
  --st-side-soft:#f9ecf5;

  /* — 阴影（改为短硬阴影，见 §6） — */
  --shadow-raise:0 1px 0 rgba(23,26,23,.04),0 2px 6px rgba(23,26,23,.05);
  --shadow-float:0 2px 0 rgba(23,26,23,.05),0 12px 28px rgba(23,26,23,.10);
  --shadow-overlay:0 4px 0 rgba(23,26,23,.06),0 32px 64px rgba(23,26,23,.18);
}

:root[data-theme="dark"]{
  color-scheme:dark;

  /* 表面：规范 §3.1 Dark 值 + 补两级 */
  --canvas:#0e1110;
  --surface:#141817;
  --surface-2:#1b201e;
  --surface-raised:#202624;   /* 规范值，实现缺失 */
  --surface-3:#232927;        /* 新增 */
  --line:#2b322f;
  --line-strong:#3a4440;
  --line-heavy:#5a6661;       /* 新增 */

  --text:#edf1ed;
  --text-secondary:#aab3ad;
  --text-tertiary:#77817b;
  --text-inverse:#0e1110;

  /* 信号色在深底上需提亮 + 降饱和（规范 §3.4「不允许简单反色」） */
  --signal-50:#2b1914;
  --signal-100:#4a251b;
  --signal-300:#a34a30;
  --signal:#ff7350;
  --signal-hover:#ff8a6c;
  --signal-press:#e35c3a;
  --signal-soft:var(--signal-50);
  --signal-line:#6b3526;
  --signal-text:#ff8f73;

  /* 状态色：深底上重新取值 —— 这是当前最大的暗色缺口 */
  --st-success:#4fb583;
  --st-nochange:#4fa5aa;
  --st-warning:#e0a94a;
  --st-failed:#f0656f;
  --st-reconcile:#9b8ae0;
  --st-side:#dc72bb;
  --st-queued:#77817b;

  /* 暗色下图形色本身已 ≥4.5:1，文字级可直接复用 */
  --st-success-text:var(--st-success);
  --st-nochange-text:var(--st-nochange);
  --st-warning-text:var(--st-warning);
  --st-failed-text:var(--st-failed);
  --st-reconcile-text:var(--st-reconcile);
  --st-side-text:var(--st-side);

  --st-success-soft:#122320;
  --st-nochange-soft:#0f2224;
  --st-warning-soft:#241d10;
  --st-failed-soft:#291416;
  --st-reconcile-soft:#1c1830;
  --st-side-soft:#2a1526;

  --scrim:rgba(0,0,0,.62);
  --shadow-raise:0 1px 0 rgba(0,0,0,.3),0 2px 6px rgba(0,0,0,.35);
  --shadow-float:0 2px 0 rgba(0,0,0,.35),0 12px 28px rgba(0,0,0,.45);
  --shadow-overlay:0 4px 0 rgba(0,0,0,.4),0 32px 64px rgba(0,0,0,.6);
}
```

**使用界线**（这条比色值本身更重要）：

| 场景 | 用哪个 |
|---|---|
| 状态点 / 竖条 / 边框 / 进度条 / rail 节点 | `--st-*`（规范原值） |
| badge 文字 / 失败说明 / 链接 | `--st-*-text` |
| badge 底 / 行高亮 / 区块底 | `--st-*-soft` |

亮色下 `--st-*` 与 `--st-*-text` 是两个值；暗色下后者别名到前者。组件里一律写 `--st-*-text` 表示文字，主题切换自动正确。

### 3.3 迁移 alias（避免一次性改 60 KB CSS）

在 `tokens.css` 末尾加：

```css
:root{
  --muted:var(--text-secondary); --tertiary:var(--text-tertiary);
  --lineStrong:var(--line-strong); --surface2:var(--surface-2);
  --signalSoft:var(--signal-soft);
  --success:var(--st-success); --nochange:var(--st-nochange);
  --warning:var(--st-warning); --failed:var(--st-failed);
  --reconcile:var(--st-reconcile); --side:var(--st-side);
  --shadow:var(--shadow-float)
}
```

这样现有 CSS 不改也能立刻吃到**暗色状态色修正**和**两个中性色对齐规范**，后续再逐步换名。

> ⚠️ alias 只解决色值，**不解决文字对比度**——`.error-note{color:var(--failed)}` 通过 alias 拿到的还是图形级 `#d94a55`。§3.1b 的 20+ 处状态文字必须逐个手动改成 `--st-*-text`，这一步无法用 alias 偷懒。

### 3.4 启用 `--st-side`（side-effect）【规范欠账】

规范 §3.3 定义了它，`TasksPage.tsx:16` 的 `FailureSurface` 已经在渲染 `side_effects` 数组，但用的是普通 code 样式：

```tsx
{effects.length>0&&<div className="failure-effects"><span>已发生的外部结果</span>{effects.map(...=><code key={...}>{effect}</code>)}</div>}
```

**改**：`.failure-effects` 整块改用 side-effect 语义色：

```css
.failure-effects{margin-top:12px;padding:10px 12px;border-left:3px solid var(--st-side);background:var(--st-side-soft);border-radius:0 var(--r-md) var(--r-md) 0}
.failure-effects>span{font:var(--t-kicker);letter-spacing:.16em;text-transform:uppercase;color:var(--st-side);display:block;margin-bottom:6px}
.failure-effects code{font:var(--t-mono-sm);color:var(--text);background:none;padding:0;display:block}
```

**为什么重要**：`side_effects` 里装的是"任务失败了，但外部世界已经被改动了"——`worktree codefixer/tsk_01HQ8A 已保留`、`MR !812 已创建`。这是全站**最需要人立刻看到**的信息，现在它是灰色小字。

### 3.5 移除第三方品牌色 【实现硬伤】

| 位置 | 现状 | 改法 |
|---|---|---|
| `simplify.css` `.provider-monogram{background:#aa1f2e}` | Redmine 红 | 统一 `background:var(--surface-3);color:var(--text);border:1px solid var(--line-strong)`，靠字母 `R`/`T` 区分 |
| `simplify.css` `.provider-monogram.tapd{background:#2868d8}` | TAPD 蓝 | 同上；如需区分，改用**形状**：Redmine 方角 `--r-sm`，TAPD 圆角 `--r-lg` |
| `product.css` `#d97757` ×2 | Claude 橙 | `.runtime-mark` 统一 `currentColor`，靠图形区分 |
| `product.css` `#4f8b73` ×2 | OpenCode 绿 | 同上 |

**唯一保留颜色的场景**：来源卡片左侧的 3px 信号栏，用**连接状态**着色（`--st-success` 已验证 / `--st-warning` 待验证 / `--st-queued` 已停用），而不是品牌色。这才是用户真正要扫的信息。

---

## 4. 圆角 【规范欠账】

### 4.1 问题

规范 §16 只允许四档 `4 / 7 / 10 / 14`。实测 **16 种像素值**：9px×15、10px×15、12px×7、8px×6、11px×6、15px×5、6px×4、16px×4、18px×3、14px×2、13px×2、7px×1、4px×1、3px×1、22px×1、17px×1，外加 `50%`×14、`999px`×7。

9px 与 10px 各 15 处、11px 与 12px 各 6–7 处——人眼分不清 1px 差异，但整体轮廓会显得"没对齐"。

### 4.2 改法

```css
:root{
  --r-xs:4px;    /* 小徽章、status dot 容器、inline code */
  --r-sm:7px;    /* 按钮、输入框、小控件 */
  --r-md:10px;   /* 卡片、面板、模态 */
  --r-lg:14px;   /* 抽屉、大容器、空态 */
  --r-pill:999px;/* 仅 ModeController、filter chip */
  --r-dot:50%;   /* 仅 status dot / rail node */
}
```

**批量映射表**（可用一次 `sed`）：

| 现值 | → | 现值 | → |
|---|---|---|---|
| 3px, 4px, 6px | `--r-xs` | 12px, 13px | `--r-md` |
| 7px, 8px, 9px | `--r-sm` | 14px, 15px, 16px, 17px, 18px | `--r-lg` |
| 10px, 11px | `--r-md` | 22px | `--r-lg` |

```bash
# 参考命令（施工时逐文件确认）
sed -i -E 's/border-radius:(3|4|6)px/border-radius:var(--r-xs)/g;
           s/border-radius:(7|8|9)px/border-radius:var(--r-sm)/g;
           s/border-radius:(10|11|12|13)px/border-radius:var(--r-md)/g;
           s/border-radius:(14|15|16|17|18|22)px/border-radius:var(--r-lg)/g' \
  frontend/src/styles.css frontend/src/product.css frontend/src/simplify.css
```

### 4.3 更重要的一条：减少需要圆角的东西 【规范欠账】

规范 §16 原文：

> 避免满屏圆角卡片；列表中的连续信息优先通过线、分组和间距组织，不把每一行包进独立胶囊。

违反处清单：

| 位置 | 现状 | 改法 |
|---|---|---|
| `.task-row.simple-row`（任务列表 8 行） | 8 个独立圆角块 | 共享容器 `--r-md`，行之间 `border-bottom:1px solid var(--line)`，行本身无圆角无边框 |
| `.dependency-row`（设置页依赖列表） | 每行独立盒 | 同上 |
| `.delivery-target`（交付目标） | 每个 target 独立盒 | 同上，缩进 + 左侧连接线 |
| `.artifact-list > div` | 每条独立盒 | 同上 |
| `.timeline .event` | 每条独立盒 | 保留竖线 + 节点，去掉盒子 |
| `.metric`（首页 3 指标） | 已经是共享容器 + `border-right` ✅ | 保留，这个做对了 |

→ 具体见 [05](05-pages-dashboard-tasks.md) §2。

---

## 5. 间距与栅格 【规范升级】

规范里没有明确的 spacing scale，这是需要补的。现状是 `18px / 22px / 23px / 13px / 42px / 46px / 70px` 这类任意值散布。

```css
:root{
  --s-1:4px;  --s-2:8px;   --s-3:12px;  --s-4:16px;
  --s-5:20px; --s-6:24px;  --s-8:32px;  --s-10:40px;
  --s-12:48px;--s-16:64px; --s-20:80px;
}
```

**页面容器规则**（替换现有 `main{padding:42px 46px 70px;max-width:1580px}`）：

```css
main{padding:var(--s-10) var(--s-12) var(--s-20);width:100%;margin:0 auto}
/* 内容宽度按类型分档，而不是全站一个 max-width */
.page-stack,.content-grid{max-width:1440px;margin-inline:auto}
.prose,.failure-surface p,.empty-state p,.wizard-step p{max-width:68ch}
```

> 现状全站 `max-width:1580px`，导致失败说明这类阅读性文本在宽屏被拉成一整行，眼睛找不到下一行的起点。

**page heading 留白**（现状标题几乎贴着内容）：

```css
.page-heading{padding-bottom:var(--s-6);margin-bottom:var(--s-8);border-bottom:1px solid var(--line);align-items:flex-end}
.page-heading p{margin-top:var(--s-2);font:var(--t-body);color:var(--text-secondary)}
```

加一条底部实线——这是"台账页眉"的直接体现，也顺便解决了标题与内容黏连。

---

## 6. 阴影 【规范升级】

现状 `--shadow:0 16px 45px rgba(30,40,33,.08)` 是典型的 SaaS 柔和大投影，加上 `.control-card{box-shadow:0 10px 34px rgba(30,40,33,.04)}`、`.project-ledger-card{box-shadow:0 10px 34px rgba(30,40,33,.045)}` 这类 4% 透明度的投影——**几乎看不见，但会让边缘发灰、发脏**。

改成"纸叠纸"：1px 实边 + 极短硬阴影（token 已在 §3.2 给出）。

```css
/* 卡片：靠边框立体，不靠模糊 */
.control-card,.project-ledger-card,.provider-card,.task-card{
  border:1px solid var(--line);box-shadow:var(--shadow-raise)
}
/* 浮层：短硬 + 长柔 双层 */
.task-drawer{box-shadow:var(--shadow-overlay)}
.confirm-modal,.config-modal{box-shadow:var(--shadow-overlay)}
```

删除所有 `rgba(30,40,33,.04)` / `.045` 这类不可见投影（共 3 处）。

同时删掉 `.mode-controller{box-shadow:inset 0 1px 0 rgba(255,255,255,.4)}` 这类拟物高光——它在暗色下变成一道白边（见 `01-dashboard-dark-full`）。

---

## 7. Motion Token 【规范欠账，§15】

规范已定义，实现只有 1 个 keyframes + 2 个 transition。落地：

```css
:root{
  --d-instant:80ms;
  --d-fast:140ms;
  --d-standard:220ms;
  --d-emphasis:360ms;
  --d-signal:1600ms;              /* 规范给 1200–1800 区间 */
  --e-standard:cubic-bezier(.2,.8,.2,1);
  --e-exit:cubic-bezier(.4,0,1,1);
  --e-signal:cubic-bezier(.45,0,.55,1);
}

@media (prefers-reduced-motion:reduce){
  :root{--d-instant:0ms;--d-fast:0ms;--d-standard:0ms;--d-emphasis:0ms}
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}
}
```

**全站交互态基线**（现在只有 `.navrail button` 和一处卡片有 transition）：

```css
button,a,input,select,textarea,.task-row,.project-ledger-card,.provider-card,.metric{
  transition:background-color var(--d-fast) var(--e-standard),
             border-color var(--d-fast) var(--e-standard),
             color var(--d-fast) var(--e-standard),
             box-shadow var(--d-fast) var(--e-standard),
             transform var(--d-fast) var(--e-standard)
}
```

→ 四个具体动效的实现见 [08-motion-theme.md §1](08-motion-theme.md)。

---

## 8. 焦点态 【实现硬伤 · 无障碍】

### 8.1 现状

`simplify.css:12` 有**一条**焦点规则：

```css
.primary:focus-visible,.ghost:focus-visible,.icon-btn:focus-visible,.project-step:focus-visible,
.action-choice:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{
  outline:3px solid color-mix(in srgb,var(--signal) 24%,transparent);
  outline-offset:2px
}
```

方向是对的（用 `:focus-visible` 而非 `:focus`，不干扰鼠标点击），但有两个问题：

**问题一：对比度不足。** `24%` 透明度的橙色在白底上算出来约 `#fcd8cf`，与 `--surface:#fff` 的对比度 **1.3:1**。WCAG 2.2 要求非文字焦点指示器对相邻色至少 **3:1**。实测在 `01-dashboard-light-full` 上把焦点打到「新建项目」按钮，焦点环几乎看不出来。

**问题二：覆盖不全。** 全站 90+ 个 className 中，只有 8 类被覆盖。**未覆盖且可聚焦**的清单：

| 选择器 | 是什么 | 后果 |
|---|---|---|
| `.task-row` | 任务列表整行（`TasksPage.tsx:30` 是 `<button>`） | 键盘用户不知道 Tab 落在哪一行 —— **这是任务页的主要交互** |
| `.navrail button` | 五个导航项 | Tab 过导航时无反馈 |
| `.filter-strip button` | 状态筛选 | 同上 |
| `.segmented button` | 运行方式二选一 | 同上 |
| `.action-link` | 「编辑配置」文字按钮 | 同上 |
| `.danger-button` | 「删除项目」 | **危险操作无焦点提示** |
| `.mode-controller` | 全局模式开关 | 同上 |
| `.toast` | 可点击关闭的通知 | 同上 |
| `.framed`（无 `.ghost` 前缀时） | 部分描边按钮 | 同上 |
| `summary` / `details` | 折叠区 | 同上 |

### 8.2 改法

用 `:where()` 兜底 + 对比度合格的实色环，替换 `simplify.css:12` 那条规则：

```css
:where(button,a[href],input,select,textarea,summary,[tabindex]:not([tabindex="-1"])):focus-visible{
  outline:2px solid var(--signal);
  outline-offset:2px;
  border-radius:var(--r-sm)
}
/* 深底/彩底元素上换白环，保证 3:1 */
.primary:focus-visible,.mode-automatic:focus-visible,.toast:focus-visible{
  outline-color:var(--text-inverse);
  outline-offset:-4px
}
/* 整行按钮：环画在内侧，不撑破容器 */
.task-row:focus-visible,.dependency-row:focus-visible{outline-offset:-2px;border-radius:0}
```

`:where()` 的特异性为 0，任何后续规则都能覆盖，不会引入新的覆盖链。

> `2px` 实色 + `offset:2px` 是通用安全值；不要用 `3px`，在 40px 高的按钮上会显得笨重。

---

## 9. 背景质感 【规范升级】

两层纯 CSS 质感，无外部资源：

```css
/* 图纸格线：几乎不可见，但消除"空" */
main::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:
    repeating-linear-gradient(to right,color-mix(in srgb,var(--line) 55%,transparent) 0 1px,transparent 1px 32px),
    repeating-linear-gradient(to bottom,color-mix(in srgb,var(--line) 55%,transparent) 0 1px,transparent 1px 32px);
  opacity:.28;
  mask-image:radial-gradient(120% 90% at 50% 0%,#000 20%,transparent 78%)
}
main>*{position:relative;z-index:1}

/* 噪点：消除数字塑料感 */
body::after{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:9999;opacity:.022;
  mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E")
}
:root[data-theme="dark"] body::after{opacity:.035;mix-blend-mode:soft-light}
```

> 两者都必须 `pointer-events:none`。噪点的 `z-index:9999` 要低于 toast（现在 toast 是 70，需提到 10000）或者把噪点降到 `z-index:0` 放在 `body::before`——**施工时确认层级，不要挡住交互**。
