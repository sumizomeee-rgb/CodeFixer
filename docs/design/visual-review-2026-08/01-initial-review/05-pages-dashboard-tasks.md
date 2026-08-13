# 05 · 首页 · 任务页 · 任务抽屉

---

## 1. 首页 DashboardPage

源码：`frontend/src/pages/DashboardPage.tsx`（22 行）
截图：`01-dashboard-light-full` / `-light-empty` / `-dark-full` / `-dark-empty` / `20-dashboard-md|sm|xs`

### 1.1 Hero 区

```tsx
<section className="hero">
  <div><h1>维修控制台</h1><p>只看正在处理的任务和需要你关注的问题。</p></div>
  <div className="slots"><span>活跃</span><b>{metrics.active}</b></div>
</section>
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 「维修控制台」34px + `letter-spacing:-.045em`，中文粘连 | 见 [02 §2.2](02-foundation.md)：改 mono 32px，字距 `.02em` |
| 2 | 右侧 `.slots`（"活跃 4"）与下方 metrics 条的「处理中 2」信息重叠且样式完全不同——两个数字条上下堆着，用户不知道该看哪个 | **删掉 `.slots`**，活跃数并入 metrics 条 |
| 3 | Hero 与下方 metrics 之间 `margin-bottom:28px`，与 metrics 到 content-grid 的间距不成比例 | 统一用 `--s-8`（32px）作为区块间距 |
| 4 | 页面标题与其他四页的 `.page-heading` 结构不一致（首页用 `.hero`，其余用 `.page-heading`），导致四页标题的字号、留白、有无下划线都不同 | **统一为 `.page-heading`**，首页只是多一个右侧插槽 |

**改后结构**：

```tsx
<section className="page-heading">
  <div><h1>维修控制台</h1><p>只看正在处理的任务和需要你关注的问题。</p></div>
  <div className="heading-slot"><ModeHint mode={mode}/></div>
</section>
```

右侧插槽放**当前执行模式的一句话说明**（而不是重复的数字）：全自动时"新工单自动进入队列"，待我开始时"3 个任务等待你授权"。这才是首页顶部真正该回答的问题。

### 1.2 指标条 metrics 【做得基本对，需增强】

```tsx
<section className="metrics metrics-compact">
  <Metric value={metrics.running} label="处理中" tone="running"/>
  <Metric value={completed} label="已完成" tone="success"/>
  <Metric value={metrics.failed} label="需要处理" tone="failed"/>
</section>
```

```css
.metric{padding:20px 22px;border-right:1px solid var(--line);position:relative;min-height:82px}
```

**做对的地方**：共享容器 + `border-right` 分栏，没有做成三张独立卡片。这是全站少数符合规范 §16 的地方，**保留**。

**问题**：

| # | 问题 | 改法 |
|---|---|---|
| 1 | 三个指标视觉权重完全相同，但「需要处理」= 3 是唯一需要行动的 | failed > 0 时该格加左侧 3px `--st-failed` 信号栏 + `--st-failed-soft` 底 |
| 2 | `completedChanged` 与 `completedNoChange` 被 `metrics.completedChanged + metrics.completedNoChange` 合并成一个"已完成" | **拆开**。`changed`（真的改了代码）和 `no_change`（证明不用改）是产品的两种健康终态，语义完全不同，规范 §10 专门为 NoChange 设计了 surface。合并等于抹掉了产品最有价值的区分 |
| 3 | 数字用什么字体没定义，实际是 sans | 改 `--font-mono` + `tabular-nums`，48px |
| 4 | `metrics.queued` / `metrics.active` 完全没展示 | 见下方新结构 |

**改后**：四格（可点击跳转到对应筛选）

```tsx
<section className="metrics">
  <Metric value={metrics.running}  label="处理中"   sub={`${metrics.queued} 等待`} tone="running" onClick={()=>onOpenTasks('active')}/>
  <Metric value={metrics.completedChanged}  label="已修复" tone="success"  onClick={()=>onOpenTasks('completed')}/>
  <Metric value={metrics.completedNoChange} label="无需修改" tone="nochange" onClick={()=>onOpenTasks('completed')}/>
  <Metric value={metrics.failed}   label="需要处理" tone="failed" onClick={()=>onOpenTasks('failed')}/>
</section>
```

```css
.metrics{
  display:grid;grid-template-columns:repeat(4,1fr);
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);
  overflow:hidden;box-shadow:var(--shadow-raise)
}
.metric{
  position:relative;padding:var(--s-5) var(--s-5) var(--s-4);
  border-right:1px solid var(--line);text-align:left;background:none;border-top:0;border-bottom:0;border-left:0;
  cursor:pointer;transition:background-color var(--d-fast) var(--e-standard)
}
.metric:last-child{border-right:0}
.metric:hover{background:var(--surface-2)}
.metric span{display:block;font:600 42px/1 var(--font-mono);font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.metric small{display:block;margin-top:var(--s-2);font:var(--t-micro);color:var(--text-secondary)}
.metric em{display:block;margin-top:2px;font:var(--t-mono-sm);color:var(--text-tertiary);font-style:normal}

/* 左侧信号栏：只有需要行动的格子才亮 */
.metric::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent}
.metric-running span{color:var(--signal)}
.metric-running::before{background:var(--signal)}
.metric-failed span{color:var(--st-failed)}
.metric-failed::before{background:var(--st-failed)}
.metric-failed{background:var(--st-failed-soft)}
.metric-success span{color:var(--text)}
.metric-nochange span{color:var(--st-nochange)}
/* 数字为 0 时不喊叫 */
.metric[data-zero="1"] span{color:var(--text-tertiary)}
.metric[data-zero="1"]::before{background:transparent}
.metric[data-zero="1"].metric-failed{background:none}
```

> 最后三条很重要：**0 个失败时，这一格必须安静下来**。现在的实现无论 0 还是 3 都是同样的红色 tone，"需要处理 0" 顶着红字是错误信号。

### 1.3 内容双栏

```css
.content-grid{grid-template-columns:1fr 350px}  /* 推断自截图与源码 */
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 规整的左右两栏，主栏与侧栏视觉重量接近，缺乏节奏 | 见下 |
| 2 | 侧栏「需要处理」在无异常时显示 `.evidence-card.calm-card`「一切正常 / 暂无需要你处理的问题」——占据整个 350px×~140px 说一句废话 | 无异常时**整个侧栏收起**，主栏占满宽；异常出现时侧栏才展开（配 `--d-emphasis` 过渡） |
| 3 | 有异常时，异常卡在右侧下方，视觉位置比左侧的运行任务弱 | 有异常时侧栏**上移与 metrics 齐平**，并加 `--st-failed` 左栏 |
| 4 | `.attention` 只显示 `.slice(0,2)`，多于 2 个时没有"还有 N 个"的出口 | 加尾部链接 |

```css
.content-grid{display:grid;grid-template-columns:minmax(0,1fr) 0;gap:0;transition:grid-template-columns var(--d-emphasis) var(--e-standard)}
.content-grid[data-attention="1"]{grid-template-columns:minmax(0,1fr) 380px;gap:var(--s-8)}
.attention{overflow:hidden}
```

### 1.4 LiveTask 卡片

```tsx
<article className="task-card">
  <div className="task-top">
    <div><span className="ticket">{task.provider_instance_id} #{task.external_ticket_id}</span><h3>{task.title}</h3></div>
    <span className={`status-pill ${task.status==='running'?'running':''}`}>{...}</span>
  </div>
  {task.project_id&&<div className="task-meta"><span>{task.project_id}</span></div>}
  {run?<StageRail stages={rail(run)}/>:null}
</article>
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 状态胶囊三态映射有 bug：`task.status==='running'?'处理中':task.status==='queued'?'等待中':'处理中'` —— `cancel_requested` 会显示"处理中" | 用统一的 `labels` 映射（`TasksPage.tsx:6` 已有，抽到共享文件） |
| 2 | `.task-meta` 只放一个 `project_id`，用了一整行 | 并进 `.ticket` 行：`redmine-main #48217 · client-lua` |
| 3 | 卡片无左侧信号栏，三张卡视觉完全平行，看不出哪个更紧急 | 加 3px 状态栏 |
| 4 | 卡片间距与 StageRail 的下边距不成比例，卡片底部拥挤 | `padding:var(--s-5) var(--s-5) var(--s-5)` |
| 5 | 卡片不可点击进入详情（要先去任务页再点） | **整卡改 `<button>`**，点击直接开抽屉。首页的价值就是快速下钻 |

```css
.task-card{
  position:relative;width:100%;text-align:left;
  padding:var(--s-5);
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);
  box-shadow:var(--shadow-raise);cursor:pointer
}
.task-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:var(--r-md) 0 0 var(--r-md);background:var(--st-queued)}
.task-card[data-status="running"]::before{background:var(--signal)}
.task-card:hover{border-color:var(--line-strong);box-shadow:var(--shadow-float)}
.task-card .ticket{font:var(--t-mono-sm);color:var(--text-tertiary);letter-spacing:.04em}
.task-card h3{font:var(--t-subhead);margin:var(--s-2) 0 0;color:var(--text)}
```

### 1.5 空态 【规范欠账 §19】

现状（`01-dashboard-light-empty`）：主栏 `.quiet-panel` 只有一句加粗「现在没有进行中的任务」，侧栏「一切正常」。整页 3 个 0 + 两句话，看起来像**系统没启动**。

规范 §19 的范式：

> 暂无 Bug 任务 / 工单轮询正常 · 上次检查 18 秒前

**改法**：

```tsx
<div className="quiet-panel">
  <span className="poll-pulse" aria-hidden="true"/>
  <b>暂无进行中的任务</b>
  <small>工单轮询正常 · 上次检查 {agoText}</small>
  <div className="quiet-sources">
    {providers.map(p => <span key={p.id}><i className={`dot dot-${p.health}`}/>{p.id}</span>)}
  </div>
</div>
```

```css
.quiet-panel{
  display:grid;justify-items:center;gap:var(--s-2);
  padding:var(--s-16) var(--s-6);
  border:1px dashed var(--line-strong);border-radius:var(--r-lg);
  background:
    repeating-linear-gradient(45deg,transparent 0 9px,color-mix(in srgb,var(--line) 40%,transparent) 9px 10px)
}
.quiet-panel b{font:var(--t-section)}
.quiet-panel small{font:var(--t-mono-sm);color:var(--text-tertiary);font-variant-numeric:tabular-nums}
.poll-pulse{width:8px;height:8px;border-radius:var(--r-dot);background:var(--st-success);animation:pollBeat 3s var(--e-signal) infinite;margin-bottom:var(--s-3)}
.quiet-sources{display:flex;gap:var(--s-4);margin-top:var(--s-4);font:var(--t-mono-sm);color:var(--text-tertiary)}
```

45° 细斜纹背景 = "此区域待命"，这是工业面板的标准语汇（比大片空白或插画都更贴切）。

> **数据前提**：`agoText` 需要后端在 `/api/dashboard` 返回 `lastPollAt`（或各 provider 的 `lastPolledAt`）。若暂不可得，退一步显示"工单轮询运行中"，不带时间——**但不要省略这句话**，它是空态的全部意义。

---

## 2. 任务页 TasksPage

源码：`frontend/src/pages/TasksPage.tsx`（38 行）
截图：`02-tasks-light-full` / `-light-empty` / `-dark-full` / `21-tasks-md|sm|xs`

### 2.1 双套行布局并存 【实现硬伤】

```css
/* product.css */
.task-row{width:100%;display:grid;grid-template-columns:92px minmax(280px,1fr) 150px 100px 28px;...}
/* simplify.css —— 覆盖成 3 列 */
.simple-row{grid-template-columns:92px minmax(0,1fr) 28px}
```

`TasksPage.tsx:30` 同时挂两个 class：`className="task-row simple-row"`。5 列版的 `150px`（项目）和 `100px`（时间）两列**在 DOM 里没有对应元素**，属于历史遗留。

**后果**：任何人尝试给任务行加一列（例如"项目"），改 `.task-row` 不生效，会以为是 CSS 没编译。

**改法**：删掉 `.task-row` 的 5 列定义，只保留一套，并**把项目和时间加回来**（下节）。

### 2.2 信息密度太低 【设计问题】

现在每行只有三个东西：状态胶囊 | 工单号+标题 | 箭头。

`02-tasks-light-full` 里 8 行任务占满整屏，但用户想知道的三个问题一个都答不了：

- 这个任务属于哪个项目？（`task.project_id` 有数据，没显示）
- 什么时候进来的 / 多久没动了？（`created_at` / `updated_at` 有数据，没显示）
- 完成的那两个，是"改了"还是"没改"？（`task.result` 有数据，只在抽屉里显示）

`result` 尤其关键——`no_change` 是本产品的核心卖点之一（"证明不用改"），列表里完全看不出来。

**改后行结构**（5 列，都有真实数据支撑）：

```tsx
<button key={task.id} className="task-row" data-status={task.status} onClick={()=>void open(task.id)}>
  <span className="cell-status">
    <i className={`st-dot st-${task.status}`} aria-hidden="true"/>
    {labels[task.status] ?? task.status}
  </span>
  <span className="cell-main">
    <small>{task.provider_instance_id} #{task.external_ticket_id}</small>
    <b>{task.title}</b>
  </span>
  <span className="cell-project">{task.project_id ?? '未分配'}</span>
  <span className="cell-result">{resultBadge(task.status, task.result)}</span>
  <span className="cell-time">{relTime(task.updated_at)}</span>
  <span className="row-arrow" aria-hidden="true">→</span>
</button>
```

```css
.task-table{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);
  overflow:hidden;box-shadow:var(--shadow-raise)
}
.task-row{
  position:relative;width:100%;
  display:grid;
  grid-template-columns:104px minmax(240px,1fr) 132px 92px 76px 22px;
  align-items:center;gap:var(--s-4);
  padding:var(--s-4) var(--s-5) var(--s-4) var(--s-5);
  border:0;border-bottom:1px solid var(--line);border-radius:0;   /* 去胶囊，规范 §16 */
  background:none;text-align:left;cursor:pointer;
  transition:background-color var(--d-fast) var(--e-standard)
}
.task-row:last-child{border-bottom:0}
.task-row:hover{background:var(--surface-2)}
/* 左侧状态信号栏 */
.task-row::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent}
.task-row[data-status="running"]::before{background:var(--signal)}
.task-row[data-status="failed"]::before{background:var(--st-failed)}
.task-row[data-status="awaiting_start"]::before{background:var(--st-warning)}
.task-row[data-status="cancel_requested"]::before{background:var(--st-reconcile)}

.cell-status{display:flex;align-items:center;gap:6px;font:var(--t-micro);color:var(--text-secondary);white-space:nowrap}
.st-dot{width:7px;height:7px;border-radius:var(--r-dot);flex:none;background:var(--st-queued)}
.st-running{background:var(--signal);animation:railPulse 1.8s var(--e-signal) infinite}
.st-failed{background:var(--st-failed)}
.st-completed{background:var(--st-success)}
.st-awaiting_start{background:var(--st-warning)}
.st-canceled{background:var(--line-strong)}

.cell-main{min-width:0}
.cell-main small{display:block;font:var(--t-mono-sm);color:var(--text-tertiary);letter-spacing:.04em}
.cell-main b{display:block;font:var(--t-body);font-weight:500;color:var(--text);margin-top:2px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cell-project{font:var(--t-mono-sm);color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cell-time{font:var(--t-mono-sm);color:var(--text-tertiary);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.row-arrow{color:var(--text-tertiary);transition:transform var(--d-fast) var(--e-standard)}
.task-row:hover .row-arrow{transform:translateX(3px);color:var(--signal)}
```

`resultBadge`——**这是把 `no_change` 从抽屉里解放出来的关键**：

```tsx
const resultBadge = (status:string, result:string|null|undefined) => {
  if (status !== 'completed') return null
  if (result === 'changed')  return <span className="rb rb-changed">已修复</span>
  if (result === 'no_change') return <span className="rb rb-nochange">无需修改</span>
  return null
}
```

```css
.rb{font:var(--t-micro);padding:2px 7px;border-radius:var(--r-xs);border:1px solid;white-space:nowrap}
.rb-changed {color:var(--st-success); border-color:color-mix(in srgb,var(--st-success) 45%,transparent); background:var(--st-success-soft)}
.rb-nochange{color:var(--st-nochange);border-color:color-mix(in srgb,var(--st-nochange) 45%,transparent);background:var(--st-nochange-soft)}
```

窄屏逐列隐藏：

```css
@media (max-width:1200px){ .task-row{grid-template-columns:104px minmax(200px,1fr) 92px 76px 22px} .cell-project{display:none} }
@media (max-width:860px){  .task-row{grid-template-columns:96px minmax(0,1fr) 22px} .cell-result,.cell-time{display:none} }
@media (max-width:560px){
  .task-row{grid-template-columns:minmax(0,1fr) 22px;row-gap:var(--s-2)}
  .cell-status{grid-column:1/-1;order:-1}
}
```

### 2.3 筛选条

```css
.filter-strip{display:flex;gap:6px;padding:4px;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:auto}
.filter-strip button{...font-size:11px}
.filter-strip button.active{background:var(--text);color:var(--surface)}
.filter-strip em{font:700 9px ui-monospace,monospace;margin-left:6px;opacity:.7}
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | `.filter-strip em`（计数）的样式写了，但 `TasksPage.tsx:29` **根本没渲染 `<em>`** —— 死 CSS | 补上计数：`filters` 数组里带上每个状态的数量 |
| 2 | active 态用近黑实心，与主 CTA 同色，视觉上像"这是个按钮"而非"这是当前筛选" | active 改为 `background:var(--signal-soft);color:var(--signal-text);border:1px solid var(--signal-line)` |
| 3 | 9px 字号 | 提到 `--t-micro`(11px)，计数用 `--t-mono-sm` |
| 4 | 筛选条与列表之间无关联，看起来是两个独立控件 | 筛选条**贴在列表容器顶部**（共享边框，中间一条 `border-bottom`），变成"表头" |

```tsx
const counts = useMemo(() => ({
  all: items.length,
  active: items.filter(x=>['queued','running','cancel_requested'].includes(x.status)).length,
  awaiting_start: items.filter(x=>x.status==='awaiting_start').length,
  failed: items.filter(x=>x.status==='failed').length,
  completed: items.filter(x=>x.status==='completed').length,
}), [items])
...
<button key={value} className={filter===value?'active':''} onClick={()=>setFilter(value)}>
  {label}<em>{counts[value]}</em>
</button>
```

```css
.task-panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;box-shadow:var(--shadow-raise)}
.filter-strip{display:flex;gap:0;padding:0 var(--s-3);background:var(--surface-2);border:0;border-bottom:1px solid var(--line);border-radius:0;overflow-x:auto}
.filter-strip button{position:relative;border:0;background:none;color:var(--text-secondary);padding:var(--s-3) var(--s-4);font:var(--t-micro);white-space:nowrap;border-radius:0}
.filter-strip button.active{color:var(--text);font-weight:650}
.filter-strip button.active::after{content:'';position:absolute;left:var(--s-3);right:var(--s-3);bottom:-1px;height:2px;background:var(--signal)}
.filter-strip em{font:var(--t-mono-sm);font-style:normal;margin-left:6px;color:var(--text-tertiary);font-variant-numeric:tabular-nums}
.filter-strip button.active em{color:var(--signal)}
```

### 2.4 「刷新」按钮的存在本身是个问题

`TasksPage.tsx:28` 有一个 `<button className="ghost framed" onClick={()=>void load()}>刷新</button>`，但页面已经 3 秒自动轮询。

**改法**：换成**轮询状态指示器**，让用户知道数据是活的：

```tsx
<span className="live-indicator" aria-live="polite">
  <i/><span>实时更新中</span>
</span>
```

```css
.live-indicator{display:flex;align-items:center;gap:6px;font:var(--t-mono-sm);color:var(--text-tertiary)}
.live-indicator i{width:6px;height:6px;border-radius:var(--r-dot);background:var(--st-success);animation:pollBeat 3s var(--e-signal) infinite}
```

这也是 [01](01-direction.md) "信号进来"叙事的一部分——**产品是活的，界面要表现出来**。

---

## 3. 任务抽屉 TaskDrawer

截图：`11-task-drawer` / `12-task-drawer-expanded`

```css
.task-drawer{width:min(760px,92vw);height:100vh;overflow:auto;background:var(--surface);border-left:1px solid var(--line);padding:28px;box-shadow:-30px 0 100px rgba(0,0,0,.18)}
```

### 3.1 抽屉未贴右 【实现硬伤】

`.modal-backdrop{...display:grid;place-items:center;padding:24px}` —— backdrop 是**居中布局**，抽屉继承了这个居中，导致 `12-task-drawer-expanded` 里抽屉两侧都有 24px 间隙，`height:100vh` 又比可用高度大 48px，**底部被裁切**。

```css
.drawer-backdrop{place-items:stretch;justify-content:end;padding:0}
.task-drawer{height:100dvh}   /* 用 dvh 避免移动端地址栏问题 */
```

### 3.2 事实网格信息量不足

```tsx
<div className="fact-grid fact-grid-simple">
  <div><small>状态</small><b>{labels[selected.status]}</b></div>
  <div><small>结果</small><b>{resultLabel(selected.result)}</b></div>
  <div><small>项目</small><b>{selected.project_id??'未分配'}</b></div>
</div>
```

三格里「状态」和标题旁的 ticket 已经重复，「结果」在未完成时显示 `—`。

**改为**：状态 | 结果 | 项目 | 用时 | 执行模式（`run.execution_mode_snapshot` 有数据，从未展示——但它很重要：这个任务是自动跑的还是人授权的）

### 3.3 NoChangeSurface 完全缺失 【规范欠账 §10 · 高优先级】

`TasksPage.tsx:9`：

```ts
const resultLabel=(value)=>value==='no_change'?'无需修改':value==='changed'?'已修复':'—'
```

一个 `no_change` 任务，界面上给用户的全部信息是**「无需修改」四个字**。

规范 §10 要求 NoChangeSurface 展示：baseline / evidence 数 / verification / review / Why / Related fix。

**为什么这是最严重的功能性视觉缺陷**：`README.md` 把 `no_change` 列为与 `changed` 并列的健康终态，并强调是「严格证据化 no_change」。后端做了大量工作去证明"确实不用改"，前端一个字都没呈现。用户看到"无需修改"只会想"它是不是偷懒了"。

**改法**——新增 `NoChangeSurface` 组件（`frontend/src/design-system/NoChangeSurface.tsx`）：

```tsx
export function NoChangeSurface({ run, task }:{ run:TaskRun; task:TaskRecord }) {
  const evidence = (run.artifacts ?? []).filter(a => a.artifact_type === 'discovery_report' || a.artifact_type === 'evidence')
  const verify = (run.stages ?? []).find(s => s.stage_id === 'no_change_verify' || s.stage_id === 'verify')
  const review = (run.stages ?? []).find(s => s.stage_id === 'review')
  return (
    <div className="nochange-surface">
      <div className="nc-head">
        <span className="nc-mark" aria-hidden="true"/>
        <div><b>已确认无需修改代码</b><small>这不是跳过；平台完成了完整调查并留下证据。</small></div>
      </div>
      <dl className="nc-grid">
        <div><dt>基线</dt><dd>{run.baseline_ref ?? '—'}</dd></div>
        <div><dt>证据</dt><dd>{evidence.length} 项</dd></div>
        <div><dt>验证</dt><dd className={verify?.status}>{verify ? '已执行' : '未执行'}</dd></div>
        <div><dt>独立复核</dt><dd className={review?.status}>{review?.status === 'completed' ? '通过' : '—'}</dd></div>
      </dl>
      <div className="nc-why">
        <span className="kicker">为什么不用改</span>
        <p>{String(task.no_change_reason ?? run.no_change_reason ?? '见调查报告。')}</p>
      </div>
      {relatedFix && <a className="nc-related" href="#">相关已修复任务 · {relatedFix}</a>}
    </div>
  )
}
```

```css
.nochange-surface{
  border:1px solid color-mix(in srgb,var(--st-nochange) 32%,var(--line));
  border-left:3px solid var(--st-nochange);
  background:var(--st-nochange-soft);
  border-radius:0 var(--r-md) var(--r-md) 0;
  padding:var(--s-4) var(--s-5);margin:var(--s-5) 0
}
.nc-head{display:flex;gap:var(--s-3);align-items:flex-start}
.nc-mark{width:16px;height:16px;flex:none;margin-top:2px;border-radius:var(--r-dot);border:2px solid var(--st-nochange);
  background:radial-gradient(circle,var(--st-nochange) 0 34%,transparent 36%)}
.nc-head b{font:var(--t-subhead);color:var(--text);display:block}
.nc-head small{font:var(--t-caption);color:var(--text-secondary);display:block;margin-top:3px}
.nc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--s-4);margin:var(--s-4) 0 0;padding-top:var(--s-4);border-top:1px solid color-mix(in srgb,var(--st-nochange) 22%,transparent)}
.nc-grid dt{font:var(--t-kicker);letter-spacing:.14em;text-transform:uppercase;color:var(--text-tertiary)}
.nc-grid dd{margin:4px 0 0;font:var(--t-mono);color:var(--text)}
.nc-why{margin-top:var(--s-4)}
.nc-why p{margin:var(--s-2) 0 0;font:var(--t-body);color:var(--text-secondary);max-width:68ch}
```

> **数据前提**：`baseline_ref`、`no_change_reason` 需要后端在任务详情里返回。若字段暂缺，**先按"未提供"渲染并保留结构**——结构本身就是产品承诺，后端补字段时前端零改动。这一点建议同步进 `docs/design-spec.md`。

### 3.4 FailureSurface 缺三段 【规范欠账 §9】

规范 §9 要求 7 段固定顺序，现状（`TasksPage.tsx:16`）有 4 段：阶段+code / 标题 / summary / hint / side_effects。

**缺失**：

| 缺失段 | 为什么必须有 |
|---|---|
| **retryable 标识** | 用户现在无法知道"重试有没有用"。`delivery_failed` 可重试，`unsupported_artifact_change` 重试无意义。现在按钮只在 `status==='failed' && 有 change_manifest` 时出现，逻辑藏在代码里 |
| **evidence links** | 失败时最该做的事是看证据。`run.artifacts` 里有 `verification_log`（91 KB pytest 日志），但被埋在「技术详情」折叠面板里 |
| **原始 stderr 折叠** | 规范明确要求。现在完全没有 |

**改后结构**：

```tsx
<div className="failure-surface" data-retryable={retryable ? '1':'0'}>
  <div className="fs-head">
    <span className="fs-stage">{stageLabel[stage] ?? '任务'}</span>
    <code className="fs-code">{code}</code>
    <span className={`fs-retry ${retryable?'yes':'no'}`}>{retryable ? '可重试' : '不可自动重试'}</span>
  </div>
  <b className="fs-title">{failureTitle[code] ?? summary}</b>
  <p className="fs-summary">{summary}</p>
  {failureHint[code] && <div className="fs-hint"><span className="kicker">下一步</span><small>{failureHint[code]}</small></div>}
  {effects.length > 0 && <div className="failure-effects">…</div>}
  {evidenceLinks.length > 0 && (
    <div className="fs-evidence">
      <span className="kicker">证据</span>
      {evidenceLinks.map(a => <EvidenceChip key={a.id} artifact={a}/>)}
    </div>
  )}
  {stderr && <details className="fs-raw"><summary>原始输出</summary><pre>{stderr}</pre></details>}
</div>
```

```css
.failure-surface{
  border:1px solid color-mix(in srgb,var(--st-failed) 26%,var(--line));
  border-left:3px solid var(--st-failed);
  background:var(--st-failed-soft);
  border-radius:0 var(--r-md) var(--r-md) 0;
  padding:var(--s-4) var(--s-5);margin:var(--s-5) 0
}
.fs-head{display:flex;align-items:center;gap:var(--s-2);flex-wrap:wrap}
.fs-stage{font:var(--t-micro);padding:2px 7px;border-radius:var(--r-xs);background:var(--st-failed);color:#fff}
.fs-code{font:var(--t-mono-sm);color:var(--st-failed);background:none;padding:0;letter-spacing:.03em}
.fs-retry{margin-left:auto;font:var(--t-micro);padding:2px 7px;border-radius:var(--r-xs);border:1px solid}
.fs-retry.yes{color:var(--st-warning);border-color:color-mix(in srgb,var(--st-warning) 45%,transparent)}
.fs-retry.no{color:var(--text-tertiary);border-color:var(--line)}
.fs-title{display:block;font:var(--t-subhead);margin:var(--s-3) 0 var(--s-2);color:var(--text)}
.fs-summary{margin:0;font:var(--t-body);color:var(--text-secondary);max-width:68ch}
.fs-hint{margin-top:var(--s-3);padding-left:var(--s-3);border-left:2px solid color-mix(in srgb,var(--st-failed) 30%,transparent)}
.fs-hint small{display:block;margin-top:4px;font:var(--t-body-sm);color:var(--text-secondary);max-width:68ch}
.fs-raw{margin-top:var(--s-3)}
.fs-raw summary{font:var(--t-mono-sm);color:var(--text-secondary);cursor:pointer}
.fs-raw pre{margin-top:var(--s-2);padding:var(--s-3);background:var(--surface-3);border-radius:var(--r-sm);
  font:var(--t-mono-sm);max-height:280px;overflow:auto;white-space:pre-wrap}
```

**文案一个字都不要动**——`failureTitle` / `failureHint` 是全站质量最高的资产（见 [00 §3](00-verdict.md)）。这里只是给它更好的容器。

### 3.5 EvidenceChip / EvidenceRow 【规范欠账 §13】

规范要求稳定 ID 格式 `EV-003 · source`，完全未实现。现状 artifact 列表：

```tsx
<div className="artifact-list">{(run.artifacts??[]).map(a=>
  <div key={a.id}><span>{a.artifact_type}</span><code>{a.relative_path}</code>
  <small>{Math.max(1,Math.round(a.size_bytes/1024))} KB · {a.sha256.slice(0,10)}</small></div>)}
</div>
```

问题：`artifact_type` 是原始英文标识符（`change_manifest` / `verification_log` / `discovery_report`）直出，路径是完整相对路径，用户读不懂也用不上。

**新组件** `frontend/src/design-system/EvidenceChip.tsx`：

```tsx
const EV_LABEL:Record<string,string> = {
  change_manifest:'修改清单', verification_log:'验证日志', discovery_report:'调查报告',
  review_report:'复核意见', patch:'补丁文件', scope_report:'范围报告',
}
export function EvidenceChip({ artifact, index }:{ artifact:Artifact; index:number }) {
  const id = `EV-${String(index + 1).padStart(3,'0')}`
  return (
    <a className="ev-chip" href={artifactUrl(artifact)} target="_blank" rel="noreferrer"
       title={`${artifact.relative_path}\nsha256 ${artifact.sha256}`}>
      <span className="ev-id">{id}</span>
      <span className="ev-name">{EV_LABEL[artifact.artifact_type] ?? artifact.artifact_type}</span>
      <span className="ev-meta">{fmtSize(artifact.size_bytes)}</span>
    </a>
  )
}
```

```css
.ev-chip{
  display:inline-grid;grid-auto-flow:column;align-items:center;gap:var(--s-2);
  padding:4px 9px;border:1px solid var(--line);border-radius:var(--r-xs);
  background:var(--surface);text-decoration:none;
  font:var(--t-mono-sm);color:var(--text-secondary)
}
.ev-chip:hover{border-color:var(--signal-line);background:var(--signal-soft);color:var(--signal-text)}
.ev-id{font-weight:650;color:var(--text-tertiary);letter-spacing:.06em}
.ev-chip:hover .ev-id{color:var(--signal)}
.ev-name{font-family:var(--font-sans);font-size:11px;color:var(--text)}
.ev-meta{color:var(--text-tertiary);font-variant-numeric:tabular-nums}
```

**EvidenceRow**（技术详情里的完整行式）加上 sha 前 8 位 + 复制按钮 + 阶段归属。

### 3.6 交付结果 【规范欠账 §12.2】

```tsx
function Delivery({action}){return <div className={`delivery-card delivery-${action.status}`}>
  <div><b>{deliveryType(action.action_type)}</b></div>
  <span className="delivery-status">{deliveryStatus(action.status)}</span>
  {action.targets?.map(t=><div className="delivery-target" key={t.id}>
    <span>{t.target_key}</span><span>{deliveryStatus(t.status)}</span>
    {t.external_url?<a href={t.external_url} target="_blank" rel="noreferrer">打开</a>:null}
  </div>)}
</div>}
```

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| 1 | target 的「失败」是普通文字，**没有失败色** | `12-task-drawer-expanded`：`release/1.0 失败` 与 `main 已完成` 灰度完全相同 | 每个 target 加状态点 + 语义色 |
| 2 | `partial_success` 整卡状态显示「部分完成」，但看不出**哪个成功、哪个失败** | 同上 | 见下方树状结构 |
| 3 | 规范 §12.2 要求「成功对象保持可点击，不因为父任务失败而降成灰色不可见」 | 现在成功的 `main` 有「打开」链接，但整卡因为 `delivery-partial_success` 而降了透明度（推断） | 明确禁止父状态影响子项可见度 |
| 4 | 多 target 是平铺列表，看不出层级 | — | 改树状：父 action 一行，targets 缩进 + 连接线 |

```css
.delivery-list{display:grid;gap:var(--s-3)}
.delivery-card{
  border:1px solid var(--line);border-radius:var(--r-md);
  background:var(--surface);overflow:hidden;opacity:1        /* 明确：父状态不降透明度 */
}
.delivery-head{display:flex;align-items:center;gap:var(--s-3);padding:var(--s-3) var(--s-4);background:var(--surface-2);border-bottom:1px solid var(--line)}
.delivery-head b{font:var(--t-body-sm);font-weight:600}
.delivery-status{margin-left:auto;font:var(--t-micro);padding:2px 8px;border-radius:var(--r-xs);border:1px solid}
.delivery-completed .delivery-status{color:var(--st-success);border-color:color-mix(in srgb,var(--st-success) 45%,transparent);background:var(--st-success-soft)}
.delivery-partial_success .delivery-status{color:var(--st-warning);border-color:color-mix(in srgb,var(--st-warning) 45%,transparent);background:var(--st-warning-soft)}
.delivery-failed .delivery-status{color:var(--st-failed);border-color:color-mix(in srgb,var(--st-failed) 45%,transparent);background:var(--st-failed-soft)}

/* 树状 targets */
.delivery-target{
  position:relative;display:grid;grid-template-columns:14px minmax(0,1fr) auto auto;
  align-items:center;gap:var(--s-3);
  padding:var(--s-3) var(--s-4) var(--s-3) var(--s-6);
  border-bottom:1px solid var(--line)
}
.delivery-target:last-child{border-bottom:0}
.delivery-target::before{         /* 连接线 └─ */
  content:'';position:absolute;left:calc(var(--s-4) + 4px);top:0;bottom:50%;width:1px;background:var(--line)
}
.delivery-target::after{
  content:'';position:absolute;left:calc(var(--s-4) + 4px);top:50%;width:8px;height:1px;background:var(--line)
}
.delivery-target>i{width:7px;height:7px;border-radius:var(--r-dot);grid-column:1}
.dt-completed{background:var(--st-success)}
.dt-failed{background:var(--st-failed)}
.dt-running{background:var(--signal);animation:railPulse 1.8s infinite}
.delivery-target>span:nth-child(2){font:var(--t-mono);color:var(--text);overflow:hidden;text-overflow:ellipsis}
.delivery-target .dt-status{font:var(--t-micro)}
.delivery-target.is-failed .dt-status{color:var(--st-failed)}
.delivery-target a{font:var(--t-micro);color:var(--signal-text);text-decoration:none;padding:3px 8px;border:1px solid var(--signal-line);border-radius:var(--r-xs)}
.delivery-target a:hover{background:var(--signal-soft)}
```

### 3.7 Freeze Change 视觉转折 【规范欠账 §11】

规范要求：Candidate → **Frozen Change** → Delivery 三段，Frozen 用**双线框**表达不可变。

现在抽屉里完全没有这个概念——用户看不出"这份修改已经被封存了、不会再变了"。

**改法**：在 StageRail 与交付结果之间插入 Frozen Change 卡：

```tsx
{frozen && (
  <section className="drawer-section">
    <div className="frozen-change">
      <div className="fz-band"><span className="kicker">FROZEN CHANGE</span><span className="fz-time">{fmtTime(frozen.created_at)}</span></div>
      <div className="fz-body">
        <div className="fz-row"><span>补丁</span><code>{frozen.patch_path}</code></div>
        <div className="fz-row"><span>指纹</span><code className="fz-hash">{frozen.hash}</code><CopyBtn value={frozen.hash}/></div>
        <div className="fz-row"><span>文件</span><b>{frozen.file_count} 个</b><em>+{frozen.added} / −{frozen.removed}</em></div>
        <div className="fz-row"><span>验证</span><b className="ok">通过</b></div>
        <div className="fz-row"><span>复核</span><b className="ok">通过</b></div>
      </div>
      <p className="fz-note">这份修改已封存，后续交付只搬运它，不会再改动内容。</p>
    </div>
  </section>
)}
```

```css
.frozen-change{
  position:relative;
  border:1px solid var(--line-heavy);
  border-radius:var(--r-md);
  background:var(--surface);
  box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--line);   /* 双线框 = 不可变 */
  overflow:hidden
}
.fz-band{display:flex;align-items:center;gap:var(--s-3);padding:var(--s-3) var(--s-4);
  background:var(--text);color:var(--text-inverse)}
.fz-band .kicker{color:var(--text-inverse);opacity:.9}
.fz-time{margin-left:auto;font:var(--t-mono-sm);opacity:.7;font-variant-numeric:tabular-nums}
.fz-body{padding:var(--s-4);display:grid;gap:var(--s-3)}
.fz-row{display:grid;grid-template-columns:64px minmax(0,1fr) auto;align-items:center;gap:var(--s-3);font:var(--t-mono)}
.fz-row>span:first-child{font-family:var(--font-sans);font-size:11px;color:var(--text-tertiary)}
.fz-hash{overflow:hidden;text-overflow:ellipsis}
.fz-row em{font-style:normal;color:var(--text-tertiary)}
.fz-row .ok{color:var(--st-success)}
.fz-note{margin:0;padding:var(--s-3) var(--s-4);border-top:1px dashed var(--line);
  font:var(--t-caption);color:var(--text-secondary);background:var(--surface-2)}

/* 出现时的一次性硬化动效（规范 §11 视觉转折） */
@keyframes freezeSet{
  from{box-shadow:0 0 0 1px var(--surface),0 0 0 12px transparent;border-color:var(--line)}
  to  {box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--line);border-color:var(--line-heavy)}
}
.frozen-change{animation:freezeSet var(--d-emphasis) var(--e-standard)}
```

双线框（`box-shadow` 双层 ring）+ 近黑标题带 + 一次性收紧动画——**这是全站唯一使用 `--d-emphasis` 的地方**，因为它对应产品里唯一不可撤销的一步。

### 3.8 「重试交付」按钮是紫色 【实现硬伤】

```css
/* product.css */
.retry-delivery{margin-left:8px;background:var(--reconcile)}
```

`--reconcile:#7d68c7` 是规范 §3.3 定义的 **reconciling 状态色**（对账中），把它当成按钮背景色属于语义误用。而且这是全站唯一一个紫色按钮，与整体暖调完全脱节（见 `11-task-drawer`）。

**改法**：

```css
.retry-delivery{background:var(--signal);color:#fff;border:0}
.retry-delivery:hover{background:var(--signal-hover)}
```

重试交付是主动作，就用主色。紫色留给真正的 reconciling 状态显示。

### 3.9 「技术详情」/「执行记录」折叠面板

```tsx
<details className="detail-disclosure"><summary>技术详情</summary>…</details>
<details className="detail-disclosure"><summary>执行记录</summary>…</details>
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 两个 `<details>` 视觉上和普通文字一样，看不出可展开 | summary 加三角标 + hover 态 + 边框 |
| 2 | 「执行记录」timeline 里 `event_type` 直出英文（`stage_completed:discovery`、`verification_failed`） | 加中文映射表 |
| 3 | `created_at` 直出 ISO 字符串 `2026-08-13T06:10:55.000Z` | 格式化为 `08-13 14:10:55`（本地时区）+ 相对时间 |
| 4 | timeline 每条包一个盒子（违反 §16） | 竖线 + 节点，去盒子 |

```css
.detail-disclosure{border:1px solid var(--line);border-radius:var(--r-md);margin-top:var(--s-4);overflow:hidden}
.detail-disclosure>summary{
  list-style:none;cursor:pointer;padding:var(--s-3) var(--s-4);
  font:var(--t-body-sm);font-weight:600;color:var(--text-secondary);
  background:var(--surface-2);display:flex;align-items:center;gap:var(--s-2)
}
.detail-disclosure>summary::-webkit-details-marker{display:none}
.detail-disclosure>summary::before{
  content:'';width:0;height:0;border:4px solid transparent;border-left-color:var(--text-tertiary);
  transition:transform var(--d-fast) var(--e-standard)
}
.detail-disclosure[open]>summary::before{transform:rotate(90deg) translateX(-1px)}
.detail-disclosure[open]>summary{border-bottom:1px solid var(--line)}
.detail-disclosure>summary:hover{color:var(--text);background:var(--surface-3)}

.timeline{padding:var(--s-4);display:grid;gap:0}
.timeline .event{position:relative;display:grid;grid-template-columns:auto minmax(0,1fr) auto;
  gap:var(--s-3);align-items:baseline;padding:var(--s-2) 0 var(--s-2) var(--s-5)}
.timeline .event::before{content:'';position:absolute;left:3px;top:0;bottom:0;width:1px;background:var(--line)}
.timeline .event:first-child::before{top:50%}
.timeline .event:last-child::before{bottom:50%}
.timeline .event>i{position:absolute;left:0;top:calc(50% - 3px);width:7px;height:7px;border-radius:var(--r-dot);
  background:var(--surface);border:1.5px solid var(--line-strong)}
.timeline .event b{font:var(--t-body-sm);font-weight:500;color:var(--text)}
.timeline .event small{font:var(--t-mono-sm);color:var(--text-tertiary);font-variant-numeric:tabular-nums}
```

事件中文映射（新增到 `stages.ts`）：

```ts
export const EVENT_LABEL:Record<string,string> = {
  task_ingested:'工单收录', run_started:'开始运行', run_completed:'运行完成', run_failed:'运行失败',
  verification_failed:'验证未通过', review_rejected:'复核拒绝', change_frozen:'修改已封存',
  delivery_completed:'交付完成', delivery_failed:'交付失败', task_canceled:'任务取消',
}
export const eventLabel = (t:string) => {
  if (t.startsWith('stage_completed:')) return `${STAGE_LABEL[t.slice(16)] ?? t.slice(16)} 阶段完成`
  if (t.startsWith('stage_failed:'))    return `${STAGE_LABEL[t.slice(13)] ?? t.slice(13)} 阶段失败`
  return EVENT_LABEL[t] ?? t
}
```

原始 `event_type` 保留为 `title` 属性（工程师排查时仍需要）。

---

## 4. 首页 / 任务页验收 checklist

- [ ] 首页与其他四页共用 `.page-heading`，标题体系一致
- [ ] metrics 拆成四格，`changed` 与 `no_change` 分开
- [ ] failed = 0 时该格不显红
- [ ] 首页任务卡可点击直接开抽屉
- [ ] 空态显示轮询心跳与上次检查时间
- [ ] 任务列表是**共享容器 + 分隔线**，不是 8 个胶囊
- [ ] 任务列表能看到项目、结果（已修复/无需修改）、更新时间
- [ ] 筛选条带计数，且贴在列表容器顶部
- [ ] 抽屉贴右满高，底部不被裁切
- [ ] `no_change` 任务有完整的 NoChangeSurface
- [ ] 失败任务能看到 retryable 标识与证据链接
- [ ] 交付 target 的「失败」是红色且带状态点
- [ ] 交付成功的 target 在父任务 partial_success 时**仍然完全可见可点**
- [ ] 已冻结任务能看到双线框 Frozen Change 卡
- [ ] 「重试交付」按钮不是紫色
- [ ] 执行记录里没有裸英文 `event_type` 和 ISO 时间戳
