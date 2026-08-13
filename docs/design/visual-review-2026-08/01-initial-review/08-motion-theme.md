# 08 · 动效落地与暗色态重做

---

## 1. 动效现状：全站一个 【缺陷 F · 规范欠账 §15】

### 1.1 取证

`grep '@keyframes'` 三个 CSS 文件 → **1 个**。`grep 'animation:'` → **1 处**。`grep 'transition:'` → **2 条规则**。

唯一的动画：

```css
@media(prefers-reduced-motion:no-preference){
  .stage-running .rail-node:after{animation:pulse 1.8s ease-in-out infinite}
  @keyframes pulse{50%{transform:scale(.55);opacity:.55}}
}
```

它作用在 `.stage-running .rail-node:after`——一个 **5px 的实心小点**：

```css
.stage-running .rail-node:after{content:'';width:5px;height:5px;border-radius:50%;background:var(--signal)}
```

5px 的点在 `scale(.55)` 与 `scale(1)` 之间缩放 = 在 **2.75px 与 5px 之间**变化。在 1600px 宽的屏幕上，这个动效**肉眼几乎不可察觉**。

唯一的两条 transition：

```css
/* product.css */ transition:background-color .18s ease,color .18s ease,border-color .18s ease   /* → .navrail button */
/* simplify.css */ transition:border-color .15s,transform .15s,box-shadow .15s                    /* → .action-choice */
```

**结论**：这是一个**几乎完全静止**的界面。所有状态变化（任务从 running 到 done、筛选切换、抽屉打开、主题切换）都是瞬间跳变。

这是"死板"最核心的技术成因——比配色和字体更根本。**一个不动的界面无法表达"机器正在工作"**，而这恰恰是这个产品要表达的全部。

### 1.2 值得肯定的一点

用 `@media(prefers-reduced-motion:no-preference)` **包裹**动画（而不是事后 override）是正确写法——前庭障碍用户默认不会看到任何动画。这个思路要保留并推广。

但**只有这一处**用了。改造后新增的动效必须同样处理，见 §5。

---

## 2. 动效原则

> 见 [01 §3.3](01-direction.md)。核心：**动效只服务两件事——信号在流动、状态在转折。** 其余一切静止。

反过来说，明确**不做**的清单（写下来是为了防止施工时越界）：

| 不做 | 理由 |
|---|---|
| 页面切换过渡 | 五个页面是并列的工作台，不是叙事流程 |
| 卡片入场逐个飞入 | 首屏就 20+ 卡片，飞入 = 每次刷新等半秒 |
| 数字 count-up | 3 秒轮询一次，数字会一直在爬，永远读不准 |
| hover 放大 / 3D 倾斜 | 与工业冷静气质冲突 |
| 视差滚动 | 这是数据界面，不是落地页 |
| 装饰性粒子 / 渐变流动背景 | 噪音 |

---

## 3. 应该做的动效（共 9 个，按优先级）

### P0 · 三个持续信号

这三个是"界面活着"的最低配置，加完之后整体感受会有质变。

#### 3.1 StageRail running 节点呼吸

见 [03 §3.3](03-signal-system.md) 的 `railPulse`。**关键差异**：现在动的是 5px 的实心点，改为动**节点外的一圈 12px 光环**——尺寸变化从 2.75px→5px 变成 8px→17px，才看得见。

```css
.node-pulse{
  position:absolute;inset:-6px;border-radius:var(--r-dot);
  border:1.5px solid var(--signal);
  animation:railPulse var(--d-signal) var(--e-signal) infinite
}
@keyframes railPulse{
  0%,100%{transform:scale(.72);opacity:.85}
  50%    {transform:scale(1.12);opacity:.15}
}
```

`--d-signal:1600ms`（规范 §15 给的 1200–1800 区间）。**慢是刻意的**——快速闪烁是"警报"，慢速呼吸是"运转中"。

#### 3.2 轨道扫描光

见 [03 §5](03-signal-system.md) 的 `railScan`。当前 running 阶段前的那一段轨道有一道光在流。

`discovery` 这类阶段经常跑 40–120 秒，界面上必须有东西在动，否则用户不知道它是在跑还是卡死。

```css
.rail-seg-scanning::after{
  content:'';position:absolute;inset:0;width:38%;
  background:linear-gradient(90deg,transparent,var(--signal) 40% 60%,transparent);
  animation:railScan 2.2s var(--e-signal) infinite
}
@keyframes railScan{from{transform:translateX(-100%)}to{transform:translateX(300%)}}
```

#### 3.3 轮询心跳

见 [04 §5.2](04-shell.md) 的 `pollBeat`。侧栏底部一个 6px 绿点，每 3 秒跳一次。

```css
@keyframes pollBeat{0%,88%,100%{opacity:.35;transform:scale(1)}92%{opacity:1;transform:scale(1.5)}}
```

**这个动效的作用是心理性的**：它把"什么都没发生"从"系统坏了"变成"系统在待命"。88% 的时间它是暗的——不构成视觉噪音。

同样的心跳用在首页空态（`.standby-pulse`）。

---

### P1 · 三个状态转折

#### 3.4 任务状态变化的高亮闪

任务列表 3 秒轮询，某一行从 `处理中` 变成 `已完成` 时，现在是**瞬间跳变**——用户如果没盯着那一行，完全不会注意到。

```css
@keyframes rowSettle{
  0%  {background:var(--signal-soft)}
  100%{background:transparent}
}
.task-row[data-just-changed="1"]{animation:rowSettle 1.4s var(--e-standard)}
/* 终态各自的颜色 */
.task-row[data-just-changed="1"][data-status="succeeded"]{animation-name:rowSettleOk}
@keyframes rowSettleOk{0%{background:var(--st-success-soft)}100%{background:transparent}}
.task-row[data-just-changed="1"][data-status="failed"]{animation-name:rowSettleErr}
@keyframes rowSettleErr{0%{background:var(--st-failed-soft)}100%{background:transparent}}
```

React 侧：轮询回来时对比上一次的 `status`，变了就给这一行打 1.4 秒的 `data-just-changed`：

```tsx
const prevStatus = useRef<Record<string,string>>({})
const [flash, setFlash] = useState<Set<string>>(new Set())
useEffect(() => {
  const changed = rows.filter(r => prevStatus.current[r.id] && prevStatus.current[r.id] !== r.status).map(r => r.id)
  rows.forEach(r => { prevStatus.current[r.id] = r.status })
  if (!changed.length) return
  setFlash(new Set(changed))
  const t = setTimeout(() => setFlash(new Set()), 1500)
  return () => clearTimeout(t)
}, [rows])
```

> 注意条件是 `prevStatus.current[r.id] &&`——首次加载时不闪（否则整页会一起闪一下）。

#### 3.5 Frozen Change 封存

见 [05](05-pages-dashboard-tasks.md)。`freeze_change` 完成时，Frozen Change 区块的双线框从外向内收一下：

```css
@keyframes freezeSet{
  0%  {box-shadow:0 0 0 6px var(--signal-soft);border-color:var(--signal)}
  100%{box-shadow:0 0 0 0 transparent;border-color:var(--line-heavy)}
}
.frozen-change[data-just-frozen="1"]{animation:freezeSet 900ms var(--e-standard)}
```

**这是全站唯一一个"仪式性"动效**，因为 freeze 是产品语义上唯一一次不可逆的转折。规范 §11 明确要求这里有"视觉转折"。

#### 3.6 模态 / 抽屉进入

见 [07 §4.3 / §5.1](07-controls-overlays.md)。`modalRise`（10px 上浮 + 0.985 缩放）、`drawerIn`（24px 右移）。

位移量刻意小——**大位移读起来是"炫技"，小位移读起来是"物理"**。

---

### P2 · 三个微交互

#### 3.7 全局交互态基线

见 [02 §7](02-foundation.md)。所有 button / input / row 加 140ms 的颜色+边框过渡。

这一条**改动最小、覆盖面最大**——一条 CSS 规则，让全站所有 hover 从跳变变成过渡。

#### 3.8 按钮按下位移

```css
.primary:active:not(:disabled){transform:translateY(1px);box-shadow:none}
```

1px。配合 `box-shadow:0 1px 0 var(--signal-press)` 的硬边，按下去时硬边消失 = 按钮真的被按扁了。这是纯 CSS 的物理反馈，成本近乎为零。

#### 3.9 筛选切换的下划线滑动

`.filter-strip` 五个状态按钮，切换时选中标记直接跳。改为滑动：

```css
.filter-strip{position:relative}
.filter-strip::after{
  content:'';position:absolute;bottom:0;height:2px;background:var(--signal);
  left:var(--fx,0);width:var(--fw,0);
  transition:left var(--d-standard) var(--e-standard),width var(--d-standard) var(--e-standard)
}
```

React 侧测量选中按钮的 `offsetLeft` / `offsetWidth` 写到 `--fx` / `--fw`。

> 若不想加测量逻辑，退而求其次：给按钮本身的 `border-bottom-color` 加 transition，虽然没有滑动感，但至少不跳。

---

## 4. Motion Token 落地位置

[02 §7](02-foundation.md) 已给出 token。使用对照：

| Token | 值 | 用在 |
|---|---|---|
| `--d-instant` | 80ms | 按钮 active 位移 |
| `--d-fast` | 140ms | hover / focus / 颜色变化 |
| `--d-standard` | 220ms | 模态背景淡入、筛选滑动、skeleton 行浮现 |
| `--d-emphasis` | 360ms | 模态面板上浮、抽屉滑入 |
| `--d-signal` | 1600ms | rail 节点呼吸 |
| `--e-standard` | `cubic-bezier(.2,.8,.2,1)` | 进入、位移（快出慢收） |
| `--e-exit` | `cubic-bezier(.4,0,1,1)` | 退出（慢出快收） |
| `--e-signal` | `cubic-bezier(.45,0,.55,1)` | 循环动画（对称，无起止感） |

**规则：任何新写的 `transition` / `animation` 都不许出现字面时长。** 现有两条硬编码的 `.18s` / `.15s` 一并替换。

---

## 5. prefers-reduced-motion

现有写法（`@media(no-preference)` 包裹）是正确的，但对 9 个动效逐个包裹太啰嗦。**推荐组合写法**：

```css
/* 1) 全局兜底：把所有动画压到近零 */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{
    animation-duration:.001ms!important;
    animation-iteration-count:1!important;
    transition-duration:.001ms!important;
    scroll-behavior:auto!important
  }
}

/* 2) 但三个"状态指示"动效不能完全停 —— 它们承载信息 */
@media (prefers-reduced-motion:reduce){
  /* running 节点：不缩放，改静态双环 */
  .node-pulse{animation:none!important;opacity:.5;transform:scale(1)}
  /* 扫描光：不流动，改静态半段 */
  .rail-seg-scanning::after{animation:none!important;width:100%;opacity:.4}
  /* 轮询心跳：不跳，改常亮 */
  .poll-dot,.standby-pulse{animation:none!important;opacity:1}
  /* spinner：放慢而非停止 —— 停止的 spinner 意味着"卡住了" */
  .spinner{animation-duration:1.8s!important;animation-iteration-count:infinite!important}
}
```

> **原则**：reduce motion 是"减少运动"，不是"删除信息"。凡是**唯一**表达某个状态的动效，都要提供静态替代，而不是直接关掉。这一条建议写进规范（见 [10](10-spec-upgrade.md)）。

---

## 6. 暗色态重做 【缺陷 C · 高优先级】

### 6.1 现状：只覆盖 11 个变量

`styles.css` 里暗色块全文（这是**唯一**一处暗色规则）：

```css
:root[data-theme="dark"]{
  color-scheme:dark;
  --canvas:#0e1110; --surface:#141817; --surface2:#1b201e;
  --line:#2b322f; --lineStrong:#3a4440;
  --text:#edf1ed; --muted:#aab3ad; --tertiary:#77817b;
  --signalSoft:#2b1914;
  --shadow:0 20px 50px rgba(0,0,0,.3)
}
```

**11 个变量。** 亮色一共定义了 20+ 个变量，也就是说：

| 未覆盖的变量 | 亮色值 | 在 `#0e1110` 深底上的后果 |
|---|---|---|
| `--signal` | `#f4603c` | 饱和度过高，在深底上"发光"、边缘出现红色溢出 |
| `--success` | `#2f8f5e` | 太暗，对比度 ~2.8:1，**不合格** |
| `--nochange` | `#357f84` | 太暗，~2.6:1，**不合格** |
| `--warning` | `#c98a24` | 勉强 3.6:1 |
| `--failed` | `#d0424d` | ~3.4:1，红色在深底上尤其难读 |
| `--reconcile` | `#6f5cbe` | ~2.4:1，**严重不合格**，紫色几乎融进背景 |
| `--side` | `#c258a0` | 未使用，但同样问题 |

`08-task-drawer-failed-dark` / `07-tasks-dark-full` 里直接可见：失败红字在深底上灰暗发闷，`reconciling` 紫色状态几乎看不见。

### 6.2 其它暗色问题

| # | 问题 | 位置 |
|---|---|---|
| 1 | `.mode-controller{box-shadow:inset 0 1px 0 rgba(255,255,255,.4)}` | 拟物高光在暗色下变成一道明显白边（`01-dashboard-dark-full` 顶栏右侧） |
| 2 | `.provider-monogram{background:#aa1f2e}` / `#2868d8` | 硬编码品牌色不随主题变，深底上更突兀 |
| 3 | `.modal-backdrop{background:rgba(10,15,12,.42)}` | 暗色下遮罩太浅，模态与背景分不开 |
| 4 | `.segmented .selected{box-shadow:0 2px 8px rgba(0,0,0,.06)}` | 黑色阴影在黑底上完全不可见，选中态失去立体感 |
| 5 | `.stage-done .rail-node{background:var(--text)}` | `--text` 在暗色是 `#edf1ed` 近白 —— 恰好正确，但纯属巧合，不是设计 |
| 6 | `.toast{background:var(--text);color:var(--surface)}` | 暗色下变成白底黑字，与整体反差过大 |
| 7 | 15 处 `rgba(30,40,33,...)` 字面量 | 全是亮色调的绿灰，在暗色下方向错误 |
| 8 | `--canvas:#0e1110` 与 `--surface:#141817` 差 6 个亮度级 | 卡片与背景几乎分不开，全靠 1px 边框 |

### 6.3 改法

**Step 1** — 用 [02 §3.2](02-foundation.md) 给出的完整暗色令牌表替换现有 11 行。要点：

- 状态色**单独调值**（提亮 + 降饱和）：`--st-success:#4fb583`、`--st-failed:#f0656f`、`--st-reconcile:#9b8ae0`
- 信号色提亮：`--signal:#ff7350`（不是直接用亮色的 `#f4603c`）
- 六个 `*-soft` 底色改为**深色调**（`#122320` 而非 `#e8f4ed`）
- 表面层级拉开：`--canvas:#0d100f` / `--surface:#141817` / `--surface-2:#1b201e` / `--surface-3:#232927`

**Step 2** — 修复上表 8 个问题：

```css
:root[data-theme="dark"]{
  /* 遮罩加深 */
  --scrim:rgba(0,0,0,.62);
}
.modal-backdrop{background:var(--scrim,color-mix(in srgb,var(--canvas) 18%,rgba(8,11,10,.5)))}

/* 阴影在暗色下改用"亮边"表达抬升 */
:root[data-theme="dark"] .segmented .selected{
  box-shadow:none;
  background:var(--surface-3);
  border:1px solid var(--line-strong)
}
/* 删除拟物高光 */
.mode-controller{box-shadow:var(--shadow-raise)}   /* 去掉 inset white */
```

**Step 3** — Toast 改白底/深底 + 左侧状态条（[07 §8.2](07-controls-overlays.md)），暗色下自然跟随 `--surface`，不再是反色块。

**Step 4** — 15 处 `rgba(30,40,33,.xx)` 全部替换为 `--shadow-*` token。

### 6.4 暗色不是"亮色反转"

现在的暗色本质是把 6 个中性色换掉。要做出**有质感的暗色**，还需要三件事：

**① 深色下降低边框对比、提高表面对比。**

亮色靠边框分层（`1px solid var(--line)`），暗色应该更多靠**表面明度差**分层：

```css
:root[data-theme="dark"] .control-card,
:root[data-theme="dark"] .project-ledger-card,
:root[data-theme="dark"] .provider-card{
  background:var(--surface);
  border-color:var(--line);        /* #2b322f，比亮色的边框相对更弱 */
}
:root[data-theme="dark"] .task-list,
:root[data-theme="dark"] .metrics{
  background:var(--surface)        /* 与 canvas #0d100f 差 ~4% 明度，够了 */
}
```

**② 图纸格线与噪点参数不同。**

```css
:root[data-theme="dark"] main::before{opacity:.18}    /* 亮色 .28 */
:root[data-theme="dark"] body::after{opacity:.035;mix-blend-mode:soft-light}   /* 亮色 .022 / overlay */
```

深底上噪点需要更强才看得出，但混合模式要换（overlay 在深底上会过曝）。

**③ 橙色信号在深底上需要 halo。**

亮色下 `--signal` 实心块已经足够醒目；深底上纯色块会显得"平"。给主 CTA 和 running 节点加一层极淡外发光：

```css
:root[data-theme="dark"] .primary{box-shadow:0 0 0 1px var(--signal-press),0 0 16px -6px var(--signal)}
:root[data-theme="dark"] .stage-running .rail-node{box-shadow:0 0 12px -3px var(--signal)}
```

**只给这两处**——发光是稀缺资源，用多了就变成霓虹灯。

### 6.5 暗色验证清单

改完后逐张对照截图检查（截图矩阵里有 8 张 dark）：

| 截图 | 检查点 |
|---|---|
| `01-dashboard-dark-full` | 三个指标数字可读；顶栏无白边；卡片与背景可区分 |
| `06-tasks-dark-full` | 五种状态 chip 都能区分；橙色不发红溢出 |
| `08-task-drawer-failed-dark` | 失败红字对比度 ≥4.5:1；`side_effects` 粉紫可见 |
| `09-task-drawer-nochange-dark` | `nochange` 青色可读 |
| `03-projects-dark-full` | 竖栏状态色可区分 |
| `04-providers-dark-full` | monogram 不再是品牌色块 |
| `05-settings-dark-full` | 依赖行三态可区分 |
| `19-provider-editor-dark` | 遮罩足够深，模态边界清晰 |

---

## 7. 主题切换的三个问题 【实现硬伤】

`App.tsx:36-38`：

```tsx
const [dark, setDark] = useState(false)
useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light' }, [dark])
```

### 7.1 不持久化

刷新页面回到亮色。用户每次打开都要重新点一次。

```tsx
const [theme, setTheme] = useState<'light'|'dark'|'system'>(
  () => (localStorage.getItem('cf.theme') as any) ?? 'system'
)
useEffect(() => { localStorage.setItem('cf.theme', theme) }, [theme])
```

> 这是纯前端偏好，存 `localStorage` 不涉及后端配置，不违反 `README.md` 的配置边界。

### 7.2 不读系统偏好

`matchMedia('(prefers-color-scheme: dark)')` 全站零使用。**默认应该跟随系统**——这个产品可能在夜间值班时打开。

```tsx
useEffect(() => {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const apply = () => {
    const resolved = theme === 'system' ? (mq.matches ? 'dark' : 'light') : theme
    document.documentElement.dataset.theme = resolved
  }
  apply()
  mq.addEventListener('change', apply)
  return () => mq.removeEventListener('change', apply)
}, [theme])
```

### 7.3 切换是瞬间跳变

整页颜色瞬间反转，很刺眼（尤其从亮切暗）。

```css
:root{
  transition:background-color var(--d-emphasis) var(--e-standard),
             color var(--d-emphasis) var(--e-standard)
}
/* 只给大面积表面加过渡，不给全部元素 —— 否则会有 300ms 的"渐变泥"效果 */
body,.app-shell,.topbar,.navrail,main,
.control-card,.project-ledger-card,.provider-card,.task-list,.task-drawer{
  transition:background-color var(--d-emphasis) var(--e-standard),
             border-color var(--d-emphasis) var(--e-standard)
}
/* 切换瞬间禁用过渡（避免首次加载时闪一下） */
:root[data-theme-switching] *{transition:none!important}
```

### 7.4 切换按钮应该是三态

现在是 `<button className="icon-btn" onClick={() => setDark(!dark)}>` 二态。改为三态循环 `system → light → dark → system`，图标随之变化（显示器 / 太阳 / 月亮）：

```tsx
const NEXT = {system:'light', light:'dark', dark:'system'} as const
<button className="icon-btn" onClick={() => setTheme(NEXT[theme])}
        aria-label={`外观：${{system:'跟随系统',light:'浅色',dark:'深色'}[theme]}，点击切换`}
        title={{system:'跟随系统',light:'浅色',dark:'深色'}[theme]}>
  {theme === 'system' ? <IconMonitor/> : theme === 'light' ? <IconSun/> : <IconMoon/>}
</button>
```

---

## 8. 验收 checklist

**动效**
- [ ] running 节点的呼吸**看得见**（外圈 12px 光环，不是 5px 点）
- [ ] 有任务在跑时，扫描光在轨道上流动
- [ ] 侧栏底部轮询心跳每 3 秒跳一次
- [ ] 任务状态变化时对应行有 1.4 秒高亮
- [ ] freeze 完成时 Frozen Change 区块有一次收束
- [ ] 模态 / 抽屉有进入动画
- [ ] 全站 hover 是过渡不是跳变
- [ ] 按钮按下有 1px 位移
- [ ] 无任何字面时长，全部用 `--d-*` / `--e-*`
- [ ] 空闲时**整页只有心跳在动**（打开首页盯 10 秒确认）

**reduced-motion**
- [ ] 开启系统"减少动态效果"后，所有循环动画停止
- [ ] 但 running 节点、扫描段、心跳点仍有**静态**可辨识形态
- [ ] spinner 放慢而非停止

**暗色**
- [ ] 7 个状态色在暗色下单独调值，对比度全部 ≥4.5:1（文字）/ 3:1（图形）
- [ ] 无白色 inset 高光
- [ ] 遮罩足够深
- [ ] 无 `rgba(30,40,33,...)` 残留
- [ ] 卡片与背景可区分（不靠边框也能分出层）
- [ ] 8 张 dark 截图逐张目视通过

**主题切换**
- [ ] 刷新后保持上次选择
- [ ] 默认跟随系统，系统切换时实时响应
- [ ] 切换有过渡，不刺眼
- [ ] 按钮三态，图标与 aria-label 正确
