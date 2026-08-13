# 04 · Shell：顶栏 / 导航 / 模式控制器 / 响应式

---

## 1. 布局骨架的三重覆盖 【实现硬伤】

### 1.1 现状

```css
/* styles.css */
.app-shell{min-height:100vh;display:grid;grid-template:72px 1fr/74px 1fr}
/* product.css —— 覆盖 */
.app-shell{grid-template:72px 1fr/176px minmax(0,1fr)}
/* product.css 窄屏 —— 再覆盖 */
@media(...){.app-shell{grid-template:64px 1fr 66px/minmax(0,1fr)}}
```

`styles.css` 的 74px 是"图标导轨"设计，配套的 tooltip 逻辑还在：

```css
/* styles.css：hover 才浮出的 tooltip */
.navrail button span{position:absolute;left:58px;top:11px;background:var(--text);color:var(--surface);padding:5px 9px;border-radius:6px;font-size:11px;opacity:0;pointer-events:none;white-space:nowrap}
.navrail button:hover span{opacity:1}
/* product.css：把它变成常显 label，上面整段成为死代码 */
.navrail button span{position:static;opacity:1;pointer-events:auto;background:none;color:inherit;padding:0;border-radius:0;font-size:12px;font-weight:700;letter-spacing:.02em}
```

**后果**：读代码的人无法判断哪套生效；改 `styles.css` 里的 navrail 完全不起作用；`.navrail button{font-size:18px}`（图标时代的遗留）被 `product.css` 的 `13px` 覆盖，但 18px 那行还在。

### 1.2 改法

删除 `styles.css` 里全部 navrail 规则与 `.app-shell` grid 定义，把 shell 收进新文件 `frontend/src/shell.css`：

```css
.app-shell{
  min-height:100vh;
  display:grid;
  grid-template-columns:var(--rail-w,208px) minmax(0,1fr);
  grid-template-rows:var(--top-h,64px) 1fr;
  background:var(--canvas)
}
```

用 CSS 变量承载断点差异（见 §5），不再靠多条 `grid-template` 互相盖。

---

## 2. 品牌 mark 不一致 【缺陷 J】

### 2.1 现状

存在**两个互不相干的品牌图形**：

`App.tsx:27` 的 `RepairMark`——双半圆 + 中间锯齿缝：

```tsx
<path className="repair-plate" d="M20 4A16 16 0 0 0 20 36V27a7 7 0 0 1 0-14V4Z"/>
<path className="repair-plate repair-plate-right" d="M20 4A16 16 0 0 1 20 36V27a7 7 0 0 0 0-14V4Z"/>
<path className="repair-seam" d="m17 7 6 4-6 4 6 4-6 4 6 4-6 4"/>
```

`frontend/public/favicon.svg`——黑方块 + 橙色心电图折线：

```svg
<rect x="3" y="3" width="26" height="26" rx="8" fill="#171A17"/>
<path d="M8 16h5l2.2-4.2 2.3 8.4 2.1-4.2H24" fill="none" stroke="#F4603C" stroke-width="2.6" .../>
```

**favicon 的语义明显更好**——它就是 `design-system.md` §2 "Repair Signal System" 的图形化：一条平静的基线，中间一次波动，然后恢复平静。这正是这个产品做的事。

`RepairMark` 的"双半圆 + 锯齿缝"读起来像"裂开的东西"或"拉链"，与"修复信号"无关，而且在 40×40 的小尺寸下锯齿缝糊成一团（见 `01-dashboard-light-full` 左上角）。

### 2.2 改法

**以 favicon 为准，统一为信号线 mark**，替换 `App.tsx:27-31`：

```tsx
const RepairMark = () => (
  <svg className="repair-mark" viewBox="0 0 32 32" aria-hidden="true">
    <rect className="mark-plate" x="1" y="1" width="30" height="30" rx="9"/>
    <path className="mark-signal" d="M6 16h4.4l2.1-5.4 2.6 10.8 2.2-5.4H26"
          fill="none" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
```

```css
.repair-mark{width:30px;height:30px;flex:none}
.mark-plate{fill:var(--text)}
.mark-signal{stroke:var(--signal)}
:root[data-theme="dark"] .mark-plate{fill:var(--surface-3)}
```

**加分项**：让 mark 的信号线在**有任务运行时**缓慢描边（`stroke-dasharray` + `stroke-dashoffset` 动画）。这样浏览器标签旁的品牌标本身就是一个状态指示器。约 8 行 CSS，收益很高：

```css
.app-shell[data-live="1"] .mark-signal{
  stroke-dasharray:34;
  animation:markTrace 3.2s var(--e-signal) infinite
}
@keyframes markTrace{
  0%{stroke-dashoffset:34}
  55%,100%{stroke-dashoffset:0}
}
```

`App.tsx` 里给 `.app-shell` 加 `data-live={runningCount > 0 ? '1' : '0'}`（`api.dashboard()` 已经返回 `metrics.running`）。

**同时统一 favicon**：把 favicon 的圆角从 `rx="8"`（26px 方块上）改成与 `--r-md` 一致的比例，并把折线路径与组件保持完全相同。

---

## 3. 顶栏 【缺陷 D】

### 3.1 现状问题

```css
.topbar{grid-column:1/3;background:color-mix(in srgb,var(--surface) 92%,transparent);border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 28px;position:sticky;top:0;z-index:10;backdrop-filter:blur(18px)}
.brand{...min-width:280px}
.top-actions{min-width:280px;...}
.mode-controller{margin:auto}          /* styles.css：居中 */
.mode-controller{margin-left:auto}     /* product.css：贴右 —— 生效 */
```

| # | 问题 | 证据 |
|---|---|---|
| 1 | **ModeController 被推到右侧**，与健康指示器和主题按钮挤在一起 | `01-dashboard-light-full`：右上角三个元素连成一片，视觉权重全在右上，左侧品牌区大片空白 |
| 2 | `.brand` 与 `.top-actions` 都写 `min-width:280px`——这是为居中方案准备的对称留白，现在 ModeController 不居中了，280px 变成纯浪费 | 顶栏中段 ~700px 完全空白 |
| 3 | `backdrop-filter:blur(18px)` + `92%` 半透明背景——但顶栏下方就是纯色 canvas，没有内容穿过，模糊完全看不出效果，白白付出合成层开销 | — |
| 4 | 顶栏高度 72px 偏高，内部只有 30px 的品牌 mark 和 34px 的按钮，上下各 ~19px 空白 | — |
| 5 | 健康指示器 `.health` 是纯文字 + 小圆点，与旁边的 icon-btn 视觉重量不匹配，且"系统正常/有依赖提醒/需要检查"三态**只靠圆点颜色区分**，色盲不可用 | `01-*` 全系列 |

### 3.2 改法

**结构**：三段式，但权重是「品牌（弱）| 模式控制器（**强，居中**）| 状态 + 主题（弱）」。

```css
.topbar{
  grid-column:1/-1;
  display:grid;
  grid-template-columns:1fr auto 1fr;
  align-items:center;
  gap:var(--s-4);
  height:var(--top-h,64px);
  padding-inline:var(--s-5) var(--s-5);
  background:var(--surface);
  border-bottom:1px solid var(--line);
  position:sticky;top:0;z-index:30
}
.brand{display:flex;align-items:center;gap:var(--s-3);min-width:0}
.brand b{font:var(--t-subhead);font-family:var(--font-mono);letter-spacing:.04em}
.brand small{font:var(--t-kicker);letter-spacing:.14em;text-transform:uppercase;color:var(--text-tertiary);display:block;margin-top:1px}
.mode-controller{justify-self:center;margin:0}   /* 覆盖两处 margin */
.top-actions{justify-self:end;display:flex;align-items:center;gap:var(--s-3)}
```

删掉 `min-width:280px` 两处、`backdrop-filter`、`color-mix` 半透明底。

**顶栏底边变成数据**（[01-direction.md §3.5](01-direction.md) 提到的手法）：

```css
.topbar{position:relative;border-bottom:0}
.topbar::after{
  content:'';position:absolute;left:0;right:0;bottom:0;height:1px;
  background:linear-gradient(90deg,
    var(--signal) 0 var(--live-ratio,0%),
    var(--line) var(--live-ratio,0%) 100%);
  transition:background var(--d-emphasis) var(--e-standard)
}
```

`App.tsx` 里算 `--live-ratio`（`running / max(active,1) * 100%`）写到 `.topbar` 的 inline style。一条本来就有的分隔线，顺便告诉你"现在有多满"。

**健康指示器加形状区分**（无障碍）：

```css
.health{display:flex;align-items:center;gap:6px;font:var(--t-micro);color:var(--text-secondary);padding:5px 9px;border:1px solid var(--line);border-radius:var(--r-sm)}
.health i{width:7px;height:7px;flex:none}
.health-ready    i{background:var(--st-success);border-radius:var(--r-dot)}
.health-warning  i{background:var(--st-warning);clip-path:polygon(50% 0,100% 100%,0 100%)}  /* 三角 */
.health-not_ready i{background:var(--st-failed);clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)} /* 菱形 */
.health-checking i{background:var(--line-strong);border-radius:var(--r-dot);animation:railPulse 1.6s infinite}
.health-not_ready{border-color:var(--st-failed);color:var(--st-failed);background:var(--st-failed-soft)}
```

圆 = 正常、三角 = 警告、菱形 = 阻断。这是仪表面板的标准语汇，也顺手解决色盲问题。

---

## 4. ModeController 【规范欠账 §7】

### 4.1 现状

`frontend/src/design-system/ModeController.tsx` 全文 10 行：

```tsx
export function ModeController({ mode, pending, onClick }) {
  const automatic = mode === 'automatic'
  return <button className={`mode-controller ${automatic ? 'mode-automatic' : 'mode-awaiting'}`} onClick={onClick} aria-label="切换执行模式">
    <span className="mode-dot" />
    <span>{automatic ? '全自动' : '待我开始'}</span>
    {pending ? <em>{pending}</em> : null}
  </button>
}
```

`App.tsx:64` 调用时**没有传 `pending`**：

```tsx
<ModeController mode={mode} onClick={() => setConfirmMode(true)}/>
```

规范 §7 的三条要求，落地情况：

| 规范要求 | 现状 |
|---|---|
| 「待我开始」模式下**沉静态显示待开始数量** | ❌ 组件支持 `pending`，但调用方不传，永远不显示 |
| 切到全自动前的确认 sheet 必须展示**队列数 + ready 项目数 + 并发上限** | ❌ 模态只有标题 + 一句话（见 [07](07-controls-overlays.md) §4） |
| 切回「待我开始」时显示「新任务将等待开始 · 3 个已授权任务继续运行」 | ❌ toast 只说"已切换为待我开始" |

### 4.2 改法

**Step 1** — `App.tsx` 补数据。已有 `api.dashboard()` 返回 `metrics.queued`，只需在 App 层拉一次（或提到 context）：

```tsx
const [pending, setPending] = useState(0)
useEffect(() => {
  const tick = () => api.dashboard()
    .then(d => setPending(d.metrics.queued + (d.metrics.active - d.metrics.running)))
    .catch(() => {})
  tick(); const t = setInterval(tick, 5000); return () => clearInterval(t)
}, [])
...
<ModeController mode={mode} pending={mode === 'awaitingStart' ? pending : 0} onClick={() => setConfirmMode(true)}/>
```

**Step 2** — 组件升级为「物理开关」形态。现在它是一个圆角胶囊按钮，和普通按钮没有区别；它应该是全站**唯一一个看起来像硬件开关**的东西，因为它是唯一一个改变系统行为的全局控制。

```tsx
export function ModeController({ mode, pending = 0, onClick }: { mode: ExecutionMode; pending?: number; onClick: () => void }) {
  const automatic = mode === 'automatic'
  return (
    <button className={`mode-controller ${automatic ? 'mode-automatic' : 'mode-awaiting'}`}
            onClick={onClick} aria-label="切换执行模式"
            aria-description={automatic ? '当前全自动执行' : `当前待我开始，${pending} 个任务等待授权`}>
      <span className="mode-track" aria-hidden="true"><span className="mode-knob" /></span>
      <span className="mode-text">
        <em className="mode-kicker">EXECUTION</em>
        <b>{automatic ? '全自动' : '待我开始'}</b>
      </span>
      {!automatic && pending > 0 && <span className="mode-pending">{pending}</span>}
    </button>
  )
}
```

```css
.mode-controller{
  display:inline-grid;grid-auto-flow:column;align-items:center;gap:var(--s-3);
  padding:6px 10px 6px 8px;
  background:var(--surface-2);
  border:1px solid var(--line-strong);
  border-radius:var(--r-sm);        /* 从 999px 改为方一点 —— 开关是方的 */
  box-shadow:var(--shadow-raise);
  cursor:pointer
}
.mode-controller:hover{border-color:var(--text-tertiary)}

/* 物理拨杆 */
.mode-track{position:relative;width:32px;height:16px;border-radius:var(--r-xs);background:var(--surface-3);border:1px solid var(--line-strong);flex:none}
.mode-knob{position:absolute;top:1px;left:1px;width:14px;height:12px;border-radius:2px;background:var(--text-tertiary);transition:transform var(--d-standard) var(--e-standard),background-color var(--d-standard) var(--e-standard)}
.mode-automatic .mode-track{background:var(--signal-soft);border-color:var(--signal-line)}
.mode-automatic .mode-knob{transform:translateX(16px);background:var(--signal)}

.mode-text{display:grid;text-align:left;line-height:1}
.mode-kicker{font:var(--t-kicker);letter-spacing:.16em;color:var(--text-tertiary);font-style:normal}
.mode-text b{font:var(--t-caption);font-weight:650;margin-top:3px}

/* 待开始计数：沉静，不是红点 */
.mode-pending{
  font:var(--t-mono-sm);font-weight:650;font-variant-numeric:tabular-nums;
  min-width:20px;padding:2px 5px;text-align:center;
  background:var(--surface-3);color:var(--text-secondary);
  border:1px solid var(--line);border-radius:var(--r-xs)
}
```

> 规范用词是「**沉静态**显示待开始数量」——所以不用红色 badge，用灰底方框计数器。这是"有东西在等你"而不是"出事了"。

**Step 3** — 切回「待我开始」的 toast 文案（规范 §7 明确给了句式）：

`App.tsx:54` 现在是：

```tsx
setToast(next === 'automatic' ? '已切换为全自动' : '已切换为待我开始')
```

改为：

```tsx
setToast(next === 'automatic'
  ? `已切换为全自动 · ${pending} 个等待任务将进入队列`
  : `新任务将等待开始 · ${runningCount} 个已授权任务继续运行`)
```

---

## 5. 导航 navrail

### 5.1 现状

```css
.navrail{background:var(--surface);border-right:1px solid var(--line);padding:18px 12px;display:flex;flex-direction:column;gap:7px}
.navrail button{height:46px;padding:0 13px;display:flex;align-items:center;gap:12px;border:1px solid transparent;border-radius:10px;font-size:13px;text-align:left;transition:...}
.navrail .nav-active{color:var(--signal);background:var(--signalSoft)}
```

| # | 问题 |
|---|---|
| 1 | 176px 固定宽 + 5 个圆角胶囊按钮 = 标准 Bootstrap 侧栏，最"死板"的一处 |
| 2 | active 态只有淡橙底 + 橙字，**没有位置锚点**——扫视时找不到"我在哪一层" |
| 3 | 5 个导航项之间没有分组，`首页/任务` 是运行时视角，`项目/来源/设置` 是配置视角，混在一起 |
| 4 | 底部大片空白（900px 高的屏幕，5×46px + gap ≈ 270px，剩下 600px 全空） |
| 5 | 规范 §5.2 建议「常态 72px / hover 显 label / 可固定展开 216px」，实现直接固定 176px 常显 —— 这一条**建议不照搬**（见 §5.3） |

### 5.2 改法

**保留常显 label**（规范 §5.2 的 72px 图标轨对中文不友好——"首页/任务/项目/来源/设置"这些两字标签在 72px 下要么省略要么挤），但改掉胶囊：

```css
.navrail{
  grid-row:2;
  background:var(--surface);
  border-right:1px solid var(--line);
  padding:var(--s-5) 0 var(--s-5);
  display:flex;flex-direction:column;gap:2px;
  position:sticky;top:var(--top-h);height:calc(100vh - var(--top-h));
  overflow:auto
}
.navrail button{
  position:relative;
  height:40px;padding:0 var(--s-5) 0 var(--s-5);
  display:flex;align-items:center;gap:var(--s-3);
  border:0;background:none;border-radius:0;          /* 去胶囊 */
  font:var(--t-body-sm);font-weight:500;color:var(--text-secondary);
  text-align:left;width:100%;
  transition:color var(--d-fast) var(--e-standard),background-color var(--d-fast) var(--e-standard)
}
.navrail button:hover{background:var(--surface-2);color:var(--text)}

/* active：左侧信号栏 + 加重，不是圆角色块 */
.navrail .nav-active{color:var(--text);font-weight:650;background:var(--signal-soft)}
.navrail .nav-active::before{
  content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--signal)
}
.navrail .nav-active .ui-icon{color:var(--signal)}
.navrail .ui-icon{width:17px;height:17px;flex:none;opacity:.85}

/* 分组 */
.nav-group{font:var(--t-kicker);letter-spacing:.16em;text-transform:uppercase;color:var(--text-tertiary);padding:var(--s-5) var(--s-5) var(--s-2)}
.nav-group:first-child{padding-top:0}
```

`App.tsx:67` 加分组：

```tsx
<aside className="navrail" aria-label="主导航">
  <div className="nav-group">运行</div>
  {nav('dashboard','首页')}{nav('tasks','任务')}
  <div className="nav-group">配置</div>
  {nav('projects','项目')}{nav('sources','来源')}{nav('settings','设置')}
</aside>
```

**填补底部空白**——放一个常驻的轮询心跳条（这也解决了 [01](01-direction.md) 提的"空态要有心跳"）：

```tsx
<div className="nav-foot">
  <span className="poll-dot" aria-hidden="true" />
  <div><b>工单轮询正常</b><small>上次检查 {lastPollAgo}</small></div>
</div>
```

```css
.nav-foot{margin-top:auto;padding:var(--s-4) var(--s-5);border-top:1px solid var(--line);display:flex;gap:var(--s-3);align-items:center}
.nav-foot b{display:block;font:var(--t-micro);color:var(--text-secondary)}
.nav-foot small{display:block;font:var(--t-mono-sm);color:var(--text-tertiary);font-variant-numeric:tabular-nums}
.poll-dot{width:6px;height:6px;border-radius:var(--r-dot);background:var(--st-success);flex:none;animation:pollBeat 3s var(--e-signal) infinite}
@keyframes pollBeat{0%,88%,100%{opacity:.35;transform:scale(1)}92%{opacity:1;transform:scale(1.5)}}
```

一个 3 秒跳一下的绿点，在整个空白区域最下方。**这是全站第二个持续动效**，它的作用是让"没有任务"看起来像"待命"而不是"坏了"。

### 5.3 关于规范 §5.2 的分歧 【规范升级】

规范建议 nav rail 常态 72px 图标轨、hover 显 label。**本评审建议改掉这一条**：

- 中文两字标签在 72px 轨道下无处安放，hover tooltip 对键盘和触摸用户不友好。
- 本产品只有 5 个一级导航，208px 侧栏的空间成本可以接受（1600px 宽屏下占 13%）。
- 折叠 rail 适合导航项 >10 的产品，这里是过度设计。

**替代方案**：保持 208px 常显，在 `md`（≤1280）断点降到 **56px 图标轨 + 常显 label 移到图标下方**（两行式），`sm`（≤1024）改为顶部横向 tab，`xs`（≤560）改为底部 tabbar。见 §6。

---

## 6. 响应式硬伤 【缺陷 G · 高优先级】

### 6.1 xs（420px）：底部 tabbar 遮挡内容 —— 三处确认

`product.css` 窄屏规则：

```css
@media(...){
  .app-shell{grid-template:64px 1fr 66px/minmax(0,1fr)}
  main{grid-row:2;padding:24px 16px 42px}
}
```

tabbar 是 `position:fixed` 的第三行，但 `main` 的 `padding-bottom` 只有 42px，**小于 tabbar 的 66px**。

截图确认的遮挡：

| 截图 | 被遮住的内容 |
|---|---|
| `20-dashboard-xs` | 第三张任务卡的标题被切掉一半 |
| `22-projects-xs` | 第二张项目卡底部（"编辑配置 / 运行体检"按钮行）完全不可见 |
| `23-settings-xs` | 并发数字 `4` 与"个并行调用"被盖住 |

**修复**：

```css
@media (max-width:560px){
  main{padding-bottom:calc(66px + env(safe-area-inset-bottom,0px) + var(--s-8))}
  .tabbar{padding-bottom:env(safe-area-inset-bottom,0px)}
}
```

`env(safe-area-inset-bottom)` 是必须的——iPhone / 全面屏 Android 的手势条会再吃掉 34px。

### 6.2 xs：中文标签被拦腰断行 —— 四处确认

| 截图 | 现象 |
|---|---|
| `22-projects-xs` | 「新建项目」→「新建项/目」 |
| `21-tasks-xs` | 「处理中」→「处理/中」 |
| `04-providers-*` | 「检查中…」→「检查/中…」 |
| `23-settings-xs` | 「运行环境」竖排成两行 |

中文没有连字符，浏览器默认在任意字之间断行。**全局修复**（加到 `tokens.css`）：

```css
button,.chip,.task-status,.status-pill,.filter-strip button,.segmented button,
.badge,.delivery-status,.health,.mode-text b,h1,h2,h3{
  white-space:nowrap
}
/* 允许换行但按词断 */
h1,h2,h3,p,.task-row b{ word-break:keep-all; overflow-wrap:break-word; line-break:strict }
/* 确实放不下时优先缩小容器而不是断词 */
.task-status,.status-pill,.delivery-status{min-width:0;text-overflow:ellipsis;overflow:hidden}
```

`word-break:keep-all` 是关键——它让中文按语义单元断，不在词中间切。

### 6.3 xs：StageRail 8 阶段挤在 375px

`21-tasks-xs` 里 StageRail 每列只有 ~40px，label「scope_discovery→范围」勉强、耗时数字完全叠在一起。

**改法**（加到 `stage-rail.css`）：

```css
@media (max-width:720px){
  .stage-rail{
    grid-auto-flow:row;
    grid-auto-columns:auto;
    grid-template-columns:14px 1fr auto;   /* 节点 | 名称 | 耗时 */
    gap:0
  }
  .rail-track{display:none}                 /* 横轨道换成竖轨道 */
  .stage{
    display:grid;grid-template-columns:subgrid;grid-column:1/-1;
    align-items:center;padding:7px 0;position:relative
  }
  /* 竖向连接线 */
  .stage:not(:last-child)::after{
    content:'';position:absolute;left:6px;top:22px;bottom:-7px;width:2px;background:var(--line)
  }
  .stage-done:not(:last-child)::after{background:var(--text)}
  .rail-node{margin:0}
  .stage strong{font:var(--t-body-sm)}
  .stage small{justify-self:end}
}
```

横轨在窄屏转成竖轨——这是标准做法，而且**竖排更适合展示 12 个阶段**（现在为了塞进横排才砍到 8 个）。

### 6.4 sm（900px）：导航未降级

`21-tasks-sm` / `22-projects-sm` / `23-settings-sm` 显示 176px 侧栏仍然常开，内容区只剩 724px，任务标题严重截断。

**断点体系**（写进 `shell.css`，替换现有零散 media query）：

```css
:root{--rail-w:208px;--top-h:64px}

/* lg ≥1440：默认 */

/* md 1080–1439：侧栏收窄为图标 + 下置 label */
@media (max-width:1439px){
  :root{--rail-w:76px}
  .navrail button{flex-direction:column;gap:3px;height:56px;padding:0 4px;justify-content:center;text-align:center}
  .navrail button span{font:var(--t-kicker);letter-spacing:.06em}
  .nav-group{text-align:center;padding-inline:4px;font-size:9px}
  .nav-foot{flex-direction:column;text-align:center;gap:4px;padding-inline:6px}
  .nav-foot small{display:none}
}

/* sm 561–1079：侧栏变顶部横向 tab */
@media (max-width:1079px){
  .app-shell{grid-template-columns:minmax(0,1fr);grid-template-rows:var(--top-h) auto 1fr}
  .navrail{
    grid-row:2;position:sticky;top:var(--top-h);height:auto;
    flex-direction:row;overflow-x:auto;border-right:0;border-bottom:1px solid var(--line);
    padding:0 var(--s-4);gap:0
  }
  .navrail button{flex-direction:row;height:44px;width:auto;padding:0 var(--s-4);white-space:nowrap}
  .navrail .nav-active::before{left:0;right:0;top:auto;bottom:0;width:auto;height:2px}
  .nav-group,.nav-foot{display:none}
  main{grid-row:3;padding:var(--s-6) var(--s-5) var(--s-12)}
}

/* xs ≤560：底部 tabbar */
@media (max-width:560px){
  .app-shell{grid-template-rows:56px 1fr}
  :root{--top-h:56px}
  .navrail{
    grid-row:auto;position:fixed;left:0;right:0;bottom:0;top:auto;z-index:40;
    border-top:1px solid var(--line);border-bottom:0;
    padding:0;justify-content:space-around;
    background:var(--surface);box-shadow:0 -1px 0 var(--line),0 -8px 24px rgba(0,0,0,.06)
  }
  .navrail button{flex-direction:column;gap:2px;height:56px;padding:0;flex:1}
  .navrail button span{font-size:10px}
  .navrail .nav-active::before{top:0;bottom:auto;height:2px}
  main{grid-row:2;padding:var(--s-5) var(--s-4) calc(66px + env(safe-area-inset-bottom,0px) + var(--s-8))}
  .brand small{display:none}
  .mode-kicker{display:none}
}
```

### 6.5 xs：顶栏三段式在 420px 下放不下

`1fr auto 1fr` 在 420px 下，品牌（~140px）+ ModeController（~150px）+ 状态（~120px）= 410px，刚好挤爆。

```css
@media (max-width:560px){
  .topbar{grid-template-columns:auto 1fr auto;gap:var(--s-2);padding-inline:var(--s-4)}
  .brand small{display:none}
  .brand b{display:none}                 /* 只留 mark */
  .health span{display:none}             /* 只留状态点 */
  .health{padding:5px;border:0}
  .mode-controller{justify-self:end}
}
```

---

## 7. Shell 验收 checklist

- [ ] `styles.css` 里的 `.app-shell` / `.navrail*` 规则已全部删除，只剩 `shell.css` 一处定义
- [ ] `RepairMark` 与 `favicon.svg` 图形完全一致
- [ ] ModeController 在顶栏**正中**，是全站唯一一个"看起来像开关"的控件
- [ ] 「待我开始」模式下能看到待授权计数
- [ ] 顶栏底边橙色段长度随活跃任务变化
- [ ] 健康三态用**形状 + 颜色**双编码
- [ ] 导航 active 有左侧橙色信号栏，非圆角胶囊
- [ ] 侧栏底部有轮询心跳
- [ ] 420px 下：底部 tabbar 不遮挡任何内容（三个页面逐一滚到底确认）
- [ ] 420px 下：所有中文标签不断行
- [ ] 720px 以下 StageRail 转为竖排
- [ ] 900px 下侧栏已变成顶部 tab，内容区宽度 ≥ 860px
