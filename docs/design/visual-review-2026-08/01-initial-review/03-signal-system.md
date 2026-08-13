# 03 · Repair Signal System 与 StageRail

> `design-system.md` §6 原文把 StageRail 定义为**"本产品最重要的产品视觉组件……不是普通 Stepper"**。
> 当前实现（`frontend/src/design-system/StageRail.tsx`，20 行）是一个带数字 1–8 的等宽圆点条。
> **这是全站视觉改造中收益最高的单点。**

---

## 1. 现状取证

### 1.1 组件全文

`frontend/src/design-system/StageRail.tsx`：

```tsx
export function StageRail({ stages = defaultStages }: { stages?: StageItem[] }) {
  return <div className="stage-rail" style={{gridTemplateColumns:`repeat(${stages.length},1fr)`}} aria-label="任务阶段">
    {stages.map((stage, index) => <div className={`stage stage-${stage.state}`} key={`${stage.label}-${index}`}>
      <div className="rail-line" aria-hidden="true" />
      <div className="rail-node"><span>{index + 1}</span></div>
      <strong>{stage.label}</strong><small>{stage.meta}</small>
    </div>)}
  </div>
}
```

对应 CSS（散在 `styles.css` + `product.css`）：

```css
.stage-rail{display:grid;grid-template-columns:repeat(6,1fr);margin:0 2px}
.rail-line{height:2px;background:var(--line);position:absolute;top:10px;left:0;right:0}
.rail-node{position:absolute;top:3px;left:0;width:16px;height:16px;border:2px solid var(--lineStrong);border-radius:50%;background:var(--surface);display:grid;place-items:center;z-index:2}
.stage-done .rail-node{background:var(--text);border-color:var(--text);color:var(--surface)}
.stage-running .rail-node{border-color:var(--signal);box-shadow:0 0 0 5px color-mix(in srgb,var(--signal) 12%,transparent)}
.stage-reconciling .rail-node{border-color:var(--reconcile)}
.stage-failed .rail-node{border-color:var(--failed)}
.stage strong,.stage small{display:block;font-size:10px}
```

### 1.2 六个具体问题

| # | 问题 | 影响 |
|---|---|---|
| 1 | **节点里印数字 1–8** | 暗示"固定八步流程"，但真实流水线是**变长且带循环**的（Repair↔Verify 可循环）。数字是错误信息。 |
| 2 | **failed 只改描边色** | 规范要求"节点断开 + 断点处 error notch"。现在失败节点和运行节点长得几乎一样（都是彩色描边圆），扫视时区分不出来。 |
| 3 | **skipped 无任何表达** | `state(value)` 把 `canceled` 映射成 `skipped`，但 CSS 里没有 `.stage-skipped` 规则。跳过的阶段显示为普通 queued。 |
| 4 | **reconciling 只改描边色** | 规范要求"沿节点边缘慢速 traveling signal"。现在紫色静止圆，看不出"正在对账"。 |
| 5 | **done 节点是纯黑实心** | `background:var(--text)`。在"橙色=信号"的体系里，已完成用近黑是对的方向，但**连接线没跟着变实**（`.stage-done .rail-line` 只在 `product.css` 里给了 `background:var(--signal)`，与节点的黑不一致）。 |
| 6 | **`grid-template-columns:repeat(6,1fr)` 与 inline style 冲突** | CSS 写死 6 列，组件 inline 写 `repeat(${stages.length},1fr)`（实际 8）。inline 胜出，但 CSS 里那行是死代码，误导后续维护。 |

### 1.3 一个更严重的问题：四个阶段被丢弃 【实现硬伤】

`TasksPage.tsx:7` 的 `stageLabel` 映射定义了 **12 个阶段**：

```
prepare, scope_discovery, discovery, assess, workspace_prepare, no_change_verify,
repair, verify, review, pre_delivery_check, freeze_change, deliver
```

但 `TasksPage.tsx:11` 与 `DashboardPage.tsx:9` 的 `order` 数组只有 **8 个**：

```ts
const order=['prepare','scope_discovery','discovery','assess','repair','verify','review','deliver']
```

**被丢掉的四个**：`workspace_prepare`、`no_change_verify`、`pre_delivery_check`、**`freeze_change`**。

其中 `freeze_change` 是整个产品语义上最重要的一步——`README.md` 把它列为核心能力：

> Freeze Change：不可变 patch、文件内容快照、hash、verification、review。

而 `design-system.md` §11 专门用一节要求它必须有"视觉转折"。**现在它在进度条上根本不存在。** 用户看到 `review` 直接跳到 `deliver`，无法知道修改是什么时候被封存的。

同理 `no_change_verify` 是 `no_change` 终态的证据来源，`workspace_prepare` 失败时有专门的失败码 `workspace_prepare_failed`（`TasksPage.tsx:14`）——**用户会看到一个失败码指向一个进度条上不存在的阶段。**

### 1.4 代码重复

`DashboardPage.tsx:6-9` 与 `TasksPage.tsx:7-11` 各自定义了一份 `stageLabels`、`state()`、`duration()/meta()`、`rail()/stageRail()`，内容近乎相同但**不完全相同**（`DashboardPage.duration` 支持"分"单位，`TasksPage.meta` 不支持，超过 60 秒会显示"421 秒"）。

---

## 2. 目标形态

规范 §6 给出的示意：

```
●━━━━●━━━━◉────○────○
完成   完成   当前  排队  排队
```

加上失败与跳过：

```
●━━━━●━━━━╳    ○────○           失败：轨道断开 + notch
●━━━━●╌╌╌╌●━━━━◉────○           跳过：短虚线 + 节点带斜杠
```

**核心原则：轨道是连续的，节点是轨道上的事件，不是一串独立的小圆。**

---

## 3. 替换实现

### 3.1 抽出共享逻辑

新建 `frontend/src/design-system/stages.ts`，消除 `DashboardPage` / `TasksPage` 的重复：

```ts
import type { StageRun, TaskRun } from '../entities/task'
import type { StageItem, StageState } from './StageRail'

export const STAGE_LABEL: Record<string,string> = {
  prepare:'准备', scope_discovery:'范围', discovery:'定位', assess:'评估',
  workspace_prepare:'工作区', no_change_verify:'确认', repair:'修复', verify:'验证',
  review:'复核', pre_delivery_check:'检查', freeze_change:'冻结', deliver:'交付',
}

/** 完整顺序。可选阶段只在 run 里真实出现时才渲染。 */
const FULL_ORDER = [
  'prepare','scope_discovery','discovery','assess','workspace_prepare',
  'no_change_verify','repair','verify','review','pre_delivery_check',
  'freeze_change','deliver',
] as const
/** 无论是否出现都要占位的骨架阶段（让排队中的任务也能看到全貌） */
const SKELETON = new Set(['prepare','scope_discovery','discovery','assess','repair','verify','review','deliver'])

export const toStageState = (v:string):StageState =>
  v==='completed' ? 'done' : v==='running' ? 'running' : v==='failed' ? 'failed'
  : v==='reconciling' ? 'reconciling' : v==='canceled' || v==='skipped' ? 'skipped'
  : v==='superseded' ? 'superseded' : 'queued'

export function formatDuration(stage:StageRun):string{
  if(!stage.started_at) return ''
  if(!stage.finished_at) return stage.status==='running' ? '进行中' : ''
  const ms = new Date(stage.finished_at).getTime() - new Date(stage.started_at).getTime()
  if (ms < 1000) return '<1s'
  if (ms < 60_000) return `${Math.round(ms/1000)}s`
  const m = Math.floor(ms/60_000), s = Math.round((ms%60_000)/1000)
  return s ? `${m}m ${s}s` : `${m}m`
}

export function buildRail(run:TaskRun):StageItem[]{
  const latest = new Map<string,StageRun>()
  const attempts = new Map<string,number>()
  for (const s of run.stages ?? []) {
    latest.set(s.stage_id, s)
    attempts.set(s.stage_id, (attempts.get(s.stage_id) ?? 0) + 1)
  }
  return FULL_ORDER
    .filter(id => SKELETON.has(id) || latest.has(id))
    .map(id => {
      const item = latest.get(id)
      return {
        id,
        label: STAGE_LABEL[id] ?? id,
        meta: item ? formatDuration(item) : '',
        state: item ? toStageState(item.status) : 'queued',
        attempt: attempts.get(id) ?? 0,
      }
    })
}

/** Repair↔Verify 循环次数，用于 §6.3 的 loop band */
export const repairLoopCount = (run:TaskRun) =>
  (run.stages ?? []).filter(s => s.stage_id === 'repair').length
```

**关键改动**：`freeze_change` / `workspace_prepare` / `no_change_verify` / `pre_delivery_check` **只要在这次 run 里真实出现过就渲染**，不出现则不占位。这样 `changed` 路径会看到"冻结"，`no_change` 路径会看到"确认"，两条路径的进度条自然不同——**这正是它们语义上的差别**。

### 3.2 新 StageRail 组件

```tsx
// frontend/src/design-system/StageRail.tsx
export type StageState = 'done' | 'running' | 'queued' | 'failed' | 'reconciling' | 'skipped' | 'superseded'
export type StageItem = { id?:string; label:string; meta:string; state:StageState; attempt?:number }

export function StageRail({ stages, loops = 0, dense = false }:{ stages:StageItem[]; loops?:number; dense?:boolean }) {
  const failedAt = stages.findIndex(s => s.state === 'failed')
  return (
    <div className={`stage-rail${dense ? ' stage-rail-dense' : ''}`} role="list" aria-label="处理进度">
      <div className="rail-track" aria-hidden="true">
        {stages.slice(0, -1).map((s, i) => (
          <span key={i} className={`rail-seg rail-seg-${segState(s, stages[i + 1])}`} />
        ))}
      </div>
      {stages.map((s, i) => (
        <div className={`stage stage-${s.state}${i === failedAt ? ' stage-breakpoint' : ''}`} key={s.id ?? i} role="listitem">
          <span className="rail-node" aria-hidden="true">
            {s.state === 'running' && <span className="node-pulse" />}
            {s.state === 'reconciling' && <span className="node-orbit" />}
            {s.state === 'failed' && <span className="node-notch" />}
            {s.state === 'skipped' && <span className="node-slash" />}
          </span>
          <strong>{s.label}</strong>
          <small>{s.meta}{(s.attempt ?? 0) > 1 && <em>×{s.attempt}</em>}</small>
        </div>
      ))}
      {loops > 1 && (
        <div className="rail-loop" aria-label={`修复循环 ${loops} 次`}>
          <span className="loop-arc" aria-hidden="true" />
          <span className="loop-label">修复循环 ×{loops}</span>
        </div>
      )}
    </div>
  )
}

/** 段的状态取两端较弱的一侧：只有两端都 done 才是实线 */
function segState(a:StageItem, b:StageItem){
  if (a.state === 'failed') return 'broken'
  if (a.state === 'skipped' || b.state === 'skipped') return 'skipped'
  if (a.state === 'done' && (b.state === 'done' || b.state === 'running' || b.state === 'reconciling')) return 'done'
  if (a.state === 'done') return 'half'
  return 'queued'
}
```

**改动要点**：
- **节点里不再印数字**，改为纯几何形态（实心 / 双层 / 空心 / notch / slash）。
- **轨道段独立成 `.rail-track > .rail-seg`**，段的状态由两端节点决定——这样才能做出"实线 / 半实线 / 虚线 / 断开"四种连接语义，而不是每个 stage 自带一截线。
- `attempt > 1` 时在耗时后加 `×2`——**这是 Repair Loop 在 rail 上的轻量提示**，配合下方 loop band。
- `dense` 变体给首页 `LiveTask` 用（首页卡片宽度只有 ~500px，8–12 个阶段需要更紧的呈现）。

### 3.3 CSS

新建 `frontend/src/design-system/stage-rail.css`（**不要再写进那三个压缩文件**）：

```css
.stage-rail{
  --node:11px;
  --track-y:5px;
  position:relative;
  display:grid;
  grid-auto-flow:column;
  grid-auto-columns:1fr;
  gap:0;
  padding-top:2px;
  margin-top:var(--s-4);
}

/* ---- 连续轨道 ---- */
.rail-track{
  position:absolute; top:var(--track-y); left:0; right:0; height:2px;
  display:grid; grid-auto-flow:column; grid-auto-columns:1fr;
  /* 轨道整体左右各内缩半个节点，让端点落在节点圆心 */
  margin-inline:calc(100% / var(--n, 8) / 2);
}
.rail-seg{height:2px;border-radius:1px}
.rail-seg-done   {background:var(--text)}
.rail-seg-half   {background:linear-gradient(90deg,var(--text) 0 55%,var(--line) 55% 100%)}
.rail-seg-queued {background:var(--line)}
.rail-seg-skipped{background:repeating-linear-gradient(90deg,var(--line-strong) 0 3px,transparent 3px 7px)}
.rail-seg-broken {background:linear-gradient(90deg,var(--st-failed) 0 32%,transparent 32% 100%)}

/* ---- 节点 ---- */
.stage{position:relative;display:flex;flex-direction:column;align-items:flex-start;padding-right:var(--s-3);min-width:0}
.rail-node{
  position:relative;width:var(--node);height:var(--node);border-radius:var(--r-dot);
  border:2px solid var(--line-strong);background:var(--canvas);
  margin-bottom:var(--s-3);flex:none;
  transition:border-color var(--d-standard) var(--e-standard),background-color var(--d-standard) var(--e-standard)
}
.stage-queued  .rail-node{border-color:var(--line-strong);background:var(--canvas)}
.stage-done    .rail-node{border-color:var(--text);background:var(--text)}
.stage-running .rail-node{border-color:var(--signal);background:var(--signal)}
.stage-reconciling .rail-node{border-color:var(--st-reconcile);background:var(--canvas)}
.stage-failed  .rail-node{border-color:var(--st-failed);background:var(--st-failed)}
.stage-skipped .rail-node{border-color:var(--line-strong);background:var(--canvas);opacity:.7}
.stage-superseded{opacity:.42}
.stage-superseded .rail-node{border-style:dashed}

/* running：双层缓慢脉冲（规范 §15 signal token） */
.node-pulse{
  position:absolute;inset:-6px;border-radius:var(--r-dot);
  border:1.5px solid var(--signal);
  animation:railPulse var(--d-signal) var(--e-signal) infinite
}
@keyframes railPulse{
  0%,100%{transform:scale(.72);opacity:.85}
  50%    {transform:scale(1.12);opacity:.15}
}

/* reconciling：沿节点边缘行进的信号点（规范 §6 traveling signal） */
.node-orbit{
  position:absolute;inset:-5px;border-radius:var(--r-dot);
  background:conic-gradient(from 0deg,transparent 0 72%,var(--st-reconcile) 84%,transparent 92% 100%);
  -webkit-mask:radial-gradient(circle,transparent 0 56%,#000 58%);
          mask:radial-gradient(circle,transparent 0 56%,#000 58%);
  animation:railOrbit 2.4s linear infinite
}
@keyframes railOrbit{to{transform:rotate(360deg)}}

/* failed：断点处的 error notch（规范 §6 明确要求） */
.node-notch{
  position:absolute;left:calc(100% + 5px);top:50%;transform:translateY(-50%);
  width:9px;height:9px;
  background:
    linear-gradient(45deg,transparent 44%,var(--st-failed) 44% 56%,transparent 56%),
    linear-gradient(-45deg,transparent 44%,var(--st-failed) 44% 56%,transparent 56%)
}
/* skipped：节点内斜杠 */
.node-slash{
  position:absolute;inset:1px;border-radius:var(--r-dot);
  background:linear-gradient(-45deg,transparent 42%,var(--line-strong) 42% 58%,transparent 58%)
}

/* ---- 文字 ---- */
.stage strong{font:var(--t-micro);color:var(--text-secondary);letter-spacing:.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.stage small{font:var(--t-mono-sm);color:var(--text-tertiary);font-variant-numeric:tabular-nums;display:flex;gap:4px;align-items:baseline}
.stage small em{font-style:normal;color:var(--st-reconcile);font-weight:600}
.stage-done strong{color:var(--text)}
.stage-running strong{color:var(--signal-text);font-weight:650}
.stage-running small{color:var(--signal-text)}
.stage-failed strong{color:var(--st-failed)}
.stage-queued strong,.stage-queued small{color:var(--text-tertiary)}

/* ---- Repair Loop band（规范 §6.3） ---- */
.rail-loop{
  grid-column:1/-1;margin-top:var(--s-3);padding-top:var(--s-2);
  display:flex;align-items:center;gap:var(--s-2);
  border-top:1px dashed var(--line)
}
.loop-arc{width:22px;height:9px;border:1.5px solid var(--st-reconcile);border-top:0;border-radius:0 0 11px 11px}
.loop-label{font:var(--t-mono-sm);color:var(--st-reconcile);letter-spacing:.04em}

/* ---- dense 变体（首页卡片） ---- */
.stage-rail-dense{--node:9px;--track-y:4px;margin-top:var(--s-3)}
.stage-rail-dense .stage small{display:none}
.stage-rail-dense .stage-running small,
.stage-rail-dense .stage-failed small{display:flex}

@media (prefers-reduced-motion:reduce){
  .node-pulse{animation:none;opacity:.5;transform:scale(1)}
  .node-orbit{animation:none}
}
```

> `.rail-track` 的 `margin-inline` 用了 `--n` 变量，组件需要传：`style={{'--n':stages.length}}`。或者更简单——给 `.stage` 加 `padding-left:calc(var(--node)/2)` 并让轨道从第一个节点圆心起算。施工时二选一，**务必目视确认轨道两端精确落在首末节点圆心**，这是这个组件成败的细节。

### 3.4 调用点改造

`TasksPage.tsx:34`：

```tsx
<StageRail stages={buildRail(run)} loops={repairLoopCount(run)} />
```

`DashboardPage.tsx:11`（`LiveTask`）：

```tsx
{run ? <StageRail stages={buildRail(run)} loops={repairLoopCount(run)} dense /> : null}
```

同时**删除**两个文件里各自的 `stageLabels` / `state` / `duration` / `meta` / `rail` / `stageRail` 定义，改为从 `stages.ts` import。

---

## 4. Repair Loop 的完整表达 【规范欠账 §6.3】

规范原文：

> Repair Loop 必须呈现为主轨道下方的 loop band，不得在 Rail 上假装成一次线性通过。

§3.2–3.3 里的 `.rail-loop` 是**轻量版**（一条弧 + `修复循环 ×N`）。抽屉里应该有**完整版**——因为循环意味着"机器试了几次才过"，这是评估修复质量的关键信息。

抽屉内在 StageRail 下方追加：

```tsx
{loops > 1 && (
  <div className="loop-detail">
    {Array.from({length: loops}, (_, i) => {
      const round = i + 1
      const v = verifyAttempts[i]   // 从 run.stages 里按 attempt 分组
      return (
        <div className={`loop-round loop-${v?.status ?? 'unknown'}`} key={round}>
          <span className="loop-index">R{round}</span>
          <span className="loop-bar" />
          <span className="loop-outcome">{v?.status === 'completed' ? '验证通过' : '验证未通过'}</span>
          <span className="loop-time">{v ? formatDuration(v) : ''}</span>
        </div>
      )
    })}
  </div>
)}
```

```css
.loop-detail{margin-top:var(--s-3);border-left:2px solid var(--st-reconcile);padding-left:var(--s-3);display:grid;gap:var(--s-2)}
.loop-round{display:grid;grid-template-columns:26px 1fr auto auto;align-items:center;gap:var(--s-3);font:var(--t-mono-sm)}
.loop-index{color:var(--st-reconcile);font-weight:650}
.loop-bar{height:2px;background:var(--line)}
.loop-completed .loop-bar{background:var(--st-success)}
.loop-failed .loop-bar{background:var(--st-failed)}
.loop-outcome{color:var(--text-secondary)}
.loop-time{color:var(--text-tertiary);font-variant-numeric:tabular-nums}
```

> **数据前提**：需要后端在 `stages` 里保留每次 attempt 的记录（`StageRun.attempt` 字段已存在，`shots.mjs` mock 里也有 `attempt:1`）。当前 `buildRail` 用 `latest.set()` 只留最后一次——loop detail 需要单独遍历全量。这是纯前端可做的，不需要后端改动。

---

## 5. 局部扫描脉冲 【规范欠账 §2】

规范 §2 Repair Signal System 提到"局部扫描脉冲"——当某个阶段正在做长时间扫描（scope_discovery / discovery 经常跑 40–120 秒）时，轨道上应该有一段光在扫。

现在 `discovery` 跑 78 秒，界面上完全静止，用户不知道它是在跑还是卡了。

**实现**（加在 `.rail-seg` 上，只在当前 running 段的前一段）：

```css
.rail-seg-scanning{
  background:var(--line);
  position:relative;overflow:hidden
}
.rail-seg-scanning::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent 0,var(--signal) 40%,var(--signal) 60%,transparent 100%);
  width:38%;
  animation:railScan 2.2s var(--e-signal) infinite
}
@keyframes railScan{from{transform:translateX(-100%)}to{transform:translateX(300%)}}
```

`segState()` 增加一条：若 `b.state === 'running'` 且 `a.state === 'done'`，返回 `'scanning'` 而非 `'half'`。

这样"正在跑的那一段轨道有光在流"，加上节点的呼吸——**两层动效叠加，界面就活了**，而且只在真的有任务运行时出现，不构成噪音。

---

## 6. 验收 checklist

改完后逐项目视：

- [ ] 节点上没有任何数字
- [ ] 已完成段是**连续实线**，不是一截截的
- [ ] 轨道两端精确落在首末节点圆心（放大 400% 检查）
- [ ] running 节点在缓慢呼吸，且**整页只有它在动**
- [ ] failed 节点右侧有 ✕ 形 notch，轨道在该处**断掉**（不是变色，是消失）
- [ ] skipped 节点内有斜杠，前后段是短虚线
- [ ] reconciling 节点边缘有点在绕圈
- [ ] `changed` 任务的 rail 上能看到「冻结」
- [ ] `no_change` 任务的 rail 上能看到「确认」，且**没有**「冻结」
- [ ] Repair 跑了两轮的任务，耗时后面有 `×2`，下方有 loop band
- [ ] 首页 dense 变体在 500px 宽度下不换行、不挤压
- [ ] `prefers-reduced-motion: reduce` 下所有 loop 动画停止，running 节点仍可辨识
- [ ] 暗色下 5 种节点状态都能区分（尤其 done 的黑节点在 `#0d100f` 上——需要改用 `--text` 即近白）
