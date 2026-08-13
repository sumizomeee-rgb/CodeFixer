# 14 · 降噪执行单与下一轮优先级

> 本册是可直接交给 codex（或人）执行的清单。
> 每条包含：**改什么 / 改哪里 / 改成什么 / 为什么 / 验收方式**。
> 排序依据是「感知收益 ÷ 改动成本」，不是严重度。

---

## 一、总原则：这一轮只做三件事

第二轮改造已经把工程债清得差不多了（[12 册 §1](12-round2-verdict.md)）。下一轮**不要再碰架构**，只做三类改动：

| 类别 | 目标 | 为什么是这三类 |
|---|---|---|
| **A · 降噪** | 删掉不承载信息的视觉元素 | 成本最低、感知收益最高，且零风险 |
| **B · 改骨架** | 首页与任务页重新分工 | 唯一能改变「第一眼印象」的结构性动作 |
| **C · 给字形性格** | 让占 59.6% 宽度的中文也有设计感 | [12 册主因 2](12-round2-verdict.md) 的正面解法 |

明确**不做**的（留给下一阶段）：
- ❌ 14 个 design primitives（工程量大、感知收益低，且当前 CSS 已可控）
- ❌ 完整动效编排（需要先定版式）
- ❌ 新增任何功能性 UI

---

## 二、A 类 · 降噪（建议全做，约 2 小时）

### A1 — 删除英文 kicker 🔴 最高优先

**改什么**：全站 20 处 `page-kicker` / `section-index` / `modal-kicker` / `failure-flag` / `<small>` 英文标签（完整清单见 [13 册 §2 重复 4](13-round2-redundancy.md)）。

**改成什么**——三选一，建议**方案 B**：

**方案 A · 全删**
```diff
- <span className="page-kicker">REPAIR CONTROL / LIVE</span>
  <h1>维修控制台</h1>
```
最干净，但会失去一部分「工业仪表」调性。

**方案 B · 只保留页面级 h1 的 kicker，且改为承载真实信息** ✅ 推荐
```diff
- <span className="page-kicker">REPAIR CONTROL / LIVE</span>
+ <span className="page-kicker">LIVE · 每 3 秒同步</span>
  <h1>维修控制台</h1>
```
全站从 20 处降到 5 处（每页 1 处），且剩下的 5 处**说的是中文标题没说过的事**（同步频率、任务总数、最后更新时间）。调性保住，噪音去掉 75%。

**方案 C · 保留但降权**
```diff
  .page-kicker {
-   color: var(--signal);
-   font: 600 10px/1.2 var(--font-mono);
+   color: var(--tertiary);
+   font: 500 10px/1.2 var(--font-mono);
  }
```
成本最低，但没有解决「重复」这个根本问题——只是让重复变得不那么显眼。

**为什么**：20 行橙色主色小字，每行占 `10px 行高 + 8px margin`，全部只是下一行中文标题的英译。这是全站视觉噪音**总量**最大的单一来源。

**验收**：`grep -c 'page-kicker\|section-index\|modal-kicker'` 从 20 降到 ≤ 5，且剩余每处的文本不能是紧邻中文标题的直译。

---

### A2 — 消灭 8 个「等待中」🔴

**改哪里**：`DashboardPage.tsx:9` 的 `rail()`，以及 `TasksPage.tsx:11` 的 `stageRail()`（去重后是同一个函数，见 A9）。

**改成什么**：`queued` 态的 `meta` 强制返回空串。

```diff
  return order.map(id => {
    const item = grouped.get(id)
-   return { label: stageLabels[id]??id, meta: item?duration(item):'', state: item?state(item.status):'queued' }
+   const st = item ? state(item.status) : 'queued'
+   return { label: stageLabels[id]??id, meta: st==='queued' ? '' : (item?duration(item):''), state: st }
  })
```

**为什么**：8 个一模一样的灰色小词横排一行，信息量为零，是全站噪音**密度**最高的单点。眼睛会不自觉逐个扫过去，然后发现什么也没读到。

**验收**：一个 `queued` 状态的任务，其 StageRail 下方无任何文字。

---

### A3 — 状态三重编码砍到两重 🟡

**改哪里**：`DashboardPage.tsx:12` 的 `LiveTask`。

**改成什么**：删掉右上角 `.status-pill`。

```diff
- <span className={`status-pill ${task.status==='running'?'running':''}`}>
-   {task.status==='running'?'处理中':task.status==='queued'?'等待中':'处理中'}
- </span>
```

**为什么**：保留左侧 4px 竖条（成本最低）+ StageRail 阶段色（唯一能指明「跑到哪一步」的手段）。胶囊占用右上角高价值位置，只重复了一个词。

> 顺带修掉一个逻辑瑕疵：当前三元表达式里 `queued → '等待中'`，其余全部 fallback 到 `'处理中'`——`cancel_requested` 状态会被错误显示为「处理中」。删掉胶囊后此问题自然消失。

**验收**：首页任务卡右上角为空，状态仍可从左侧竖条 + 轨道读出。

---

### A4 — 设置页三层标签砍成一层 🟡

**改哪里**：`SettingsPage.tsx:103 / 105 / 107 / 109`，四张卡的 `<header>`。

**改成什么**：

```diff
  <header>
-   <span className="card-index">01</span>
-   <div>
-     <small>AUTOMATION</small>
-     <h2>运行方式</h2>
-   </div>
+   <h2>运行方式</h2>
  </header>
```

**为什么**：标题区占三行，卡片本体（一个二选一控件）只占一行——标题比内容还重。`01 02 03 04` 不表示步骤（四张卡无先后依赖），编号不承载信息。

**如果想保留编号感**：把 `01` 移到卡片右下角作为极淡的水印（`color: var(--line)`、`font-size: 23px`），变成装饰而非标签。这符合「机床铭牌」的意象锚点，且不占标题区。

**验收**：设置页四张卡的标题区各为一行。

---

### A5 — 失败态隐藏冗余状态格 🟢

**改哪里**：`TasksPage.tsx:35` 的 `.fact-grid`。

**改成什么**：当 `selected.failure` 非空时，不渲染「状态」那一格（`FailureSurface` 已经把失败讲透了）。

**验收**：打开失败任务，抽屉顶部 fact-grid 只剩「结果」「项目」两格。

---

### A6 — 项目页状态并入动作 🟢

**改哪里**：`ProjectsPage.tsx` 项目卡。

**改成什么**：删除 `.readiness-badge` 的「待体检」态（`ready` / `failed` 两态保留，它们承载真实结果），按钮文案由状态驱动：

```
未体检 → 按钮「运行体检」（无 badge）
已通过 → badge「就绪」+ 按钮「重新体检」
有阻断 → badge「阻断」+ 按钮「重新体检」
```

**验收**：未体检的项目卡上不出现「待体检」胶囊。

---

### A7 — 字号从 14 档收到 5 档 🔴 高收益

**现状实测**（`styles/*.css` 全量）：

| 字号 | 次数 | | 字号 | 次数 |
|---|---|---|---|---|
| **10px** | **32** | | 23px | 4 |
| **12px** | **23** | | 15px | 4 |
| **11px** | **21** | | 18px | 2 |
| 13px | 5 | | 14px | 2 |

另有 `clamp(28px,3vw,36px)` / `30px` / `21px` / `19px` / `16px` / `10px !important` 各 1 次，以及 `font:` 简写里的 `17px` / `28px` / `35px`。

**14+ 个档位，10 / 11 / 12px 三档合计 76 处**，而 body 级 14px 只有 2 处。

**这是「信息很多但都又小又灰又挤」的直接来源。** 不是密度高——是层级塌了。真正的高密度工业界面（Linear、Datadog）主力正文在 13–14px，靠行高、分隔线、留白做密度，不靠缩字号。

**改成什么**——五档制，写进 `tokens.css`：

```css
:root {
  --t-micro:  11px;   /* mono 元数据、时间戳、字节数 —— 仅此一档最小 */
  --t-caption:13px;   /* 辅助说明、表格次要列 */
  --t-body:   15px;   /* 正文、按钮、输入框 —— 主力 */
  --t-title:  19px;   /* section 标题、卡片标题 */
  --t-page:   30px;   /* 页面 h1 */
}
```

映射规则：

| 现有 | 迁移到 | 说明 |
|---|---|---|
| 10px（32 处） | `--t-micro` 11px | **全部上调 1px**，且只允许 mono 元数据使用 |
| 11px（21 处） | `--t-micro` 或 `--t-caption` | 若是说明文字 → 13px；若是元数据 → 11px |
| 12px（23 处） | `--t-caption` 13px | |
| 13 / 14 / 15px | `--t-body` 15px | |
| 16 / 18 / 19 / 21px | `--t-title` 19px | |
| 23 / 28 / 30 / clamp | `--t-page` 30px | h1 统一 30px，去掉 clamp |

**注意**：字号整体上调后，密度会下降。**用减少元素（A1–A6）来补回来，不要用缩字号补。** 这两件事必须成对做——只做 A7 会让页面显得空，只做 A1–A6 会让页面显得稀。

**验收**：`grep -o "font-size: *[0-9]*px" styles/*.css | sort -u` 只剩 5 个值（或全部走 `var(--t-*)`）。

---

### A8 — 清掉残留裸值 🟢

```css
/* 圆角：5 处裸像素 + 2 处 999px */
components.css:93   border-radius: 4px          → var(--r-sharp)
components.css:148  border-radius: 2px          → var(--r-sharp)
components.css:224  border-radius: 4px          → var(--r-sharp)
shell.css:58        border-radius: 999px        → var(--r-pill)（新增令牌）
shell.css:72        border-radius: 999px        → var(--r-pill)

/* 组件层直写业务色（违反规范 §3） */
pages.css  .provider-monogram      { color:#9c2e3d }  → var(--brand-redmine)
pages.css  .provider-monogram.tapd { color:#2f66bd }  → var(--brand-tapd)
pages.css  .runtime-claudeCode     { color:#b85f42 }  → var(--brand-claude)

/* 暗色下失效的固定阴影 */
pages.css  .segmented button.selected { box-shadow: 0 2px 7px rgba(0,0,0,.07) }
           → box-shadow: var(--shadow-raise)   （亮/暗各定义一次）
```

`#2f66bd` 那块纯蓝在整页暖调里依然突兀，建议收进令牌后统一降饱和（如 `#4a6ea8`）。

---

### A9 — 抽出 `entities/stage.ts` 🔴 含正确性修复

**改什么**：`DashboardPage.tsx:6-10` 与 `TasksPage.tsx:7-12` 的五个重复定义。

**为什么不只是洁癖**——两处已经分叉，产生了**真实的视觉不一致**：

1. 跑了 5 分钟的阶段：首页显示「5 分」，任务页显示「300 秒」
2. 「无需修改」任务：任务页把 repair / deliver 画成跳过态（虚线 + 斜杠），首页画成普通等待态——**本轮新做的 `stage-skipped` 样式在首页永远不会触发**

**改成什么**：新建 `frontend/src/entities/stage.ts`

```ts
export const STAGE_LABELS: Record<string,string> = { /* 12 项，两处已相同 */ }

// 补齐 12 项（当前两处都只有 8 项）
export const STAGE_ORDER = [
  'prepare','scope_discovery','discovery','assess','workspace_prepare',
  'no_change_verify','repair','verify','review','pre_delivery_check',
  'freeze_change','deliver',
]

export function stageState(value: string): StageState        // 两处逐字符相同，直接搬
export function stageDuration(stage: StageRun): string       // 以 Dashboard 版为准（有「分」档）
export function buildRail(run: TaskRun): StageItem[]         // 以 Tasks 版为准（含 no_change 分支）
export function repairAttempts(run: TaskRun): number         // 两处逐字符相同，直接搬
```

**取舍说明**：`stageDuration` 取 Dashboard 版（有分钟档），`buildRail` 取 Tasks 版（有分支处理）——**各取正确的那一半，不是简单二选一**。

**注意 `STAGE_ORDER` 补齐到 12 项的连带影响**：12 个节点在首页卡片宽度（约 560px）下会明显过密。这是**首页不该渲染完整轨道**的又一个理由——B1 做完后此问题自然消失。若 B1 暂不做，`STAGE_ORDER` 需先保持 8 项。

**验收**：两个页面文件内不再有 `stageLabels` / `state` / `duration` / `rail` / `repairAttempts` 的本地定义。

---

## 三、B 类 · 改骨架（约 3 小时，感知收益最大）

### B1 — 首页去掉完整 StageRail，改单行紧凑态 🔴 最高

**为什么**：这是**唯一一个能让你「一眼看出变了」的改动**。

首页 hero 自称「只看正在处理的任务和需要你关注的问题」，而每张卡塞了 24 个信息单元（8 节点 × 标签+时长+状态），三张卡 = 72 个。**「只看」与「塞满」直接矛盾。**

**改成什么**：

```
┌─────────────────────────────────────────────────────────────┐
│ ● 修复 · 2 分   redmine-main #48217  订单导出金额精度错误   → │
│ ◐ 定位 · 34 秒  tapd-core #9921      登录态偶发丢失         → │
│ ○ 等待          redmine-main #48250  报表分页越界           → │
└─────────────────────────────────────────────────────────────┘
```

每行保留：状态点（形状 + 色，沿用 StageRail 的形状编码）、**当前阶段名 + 该阶段已耗时**、工单号（mono）、标题、进入箭头。

> 「当前跑到哪一步、跑了多久」是首页真正需要的进度信息。
> 「整体走到哪」需要完整轨道，那是打开任务之后才需要回答的问题。

**验收**：首页主区高度显著下降；`grep -c StageRail DashboardPage.tsx` = 0。

---

### B2 — 首页主次对调 🔴

**现状**：`.content-grid { grid-template-columns: minmax(0,1fr) minmax(270px,340px) }`——「正在处理」占主区，「需要处理」被挤到 270–340px 的窄栏。

**问题**：首页存在的唯一理由是「有什么需要我做」。**需要人介入的失败任务，视觉权重却低于自动跑着不用管的任务。**

**改成什么**：

- **「需要处理」上移到主区**，失败任务用 `FailureSurface` 的完整形态展示（这个 pattern 做得好，值得给它更大舞台）
- **「正在处理」收成 B1 的单行列表**，放在下方或右侧窄栏
- 当没有失败任务时，「需要处理」区收缩为一行状态条（`运行平稳 · 3 个任务处理中`），把空间还给任务列表

**验收**：有失败任务时，失败内容出现在首屏视觉中心。

---

### B3 — 首页空态补时间戳 🟡

**改哪里**：`DashboardPage.tsx:21` 的 `.standby-panel`。

```diff
  <b>当前没有进行中的任务</b>
- <p>工单轮询正常 · CodeFixer 正在等待下一条修复信号</p>
+ <p>上次检查 <time>{secondsAgo}</time> 秒前 · 工单轮询正常</p>
```

**为什么**：规范 §19 要求空态给出「系统仍在工作」的证据。「轮询正常」是一句断言，没有证据。一个每秒递增的时间戳，是**空态页面上唯一能产生「活着」感的元素**——配合已有的 `standby-signal` 呼吸点，效果会明显。

**实现**：`load()` 成功时记 `lastCheckedAt`，用 1 秒 interval 渲染差值。

---

### B4 — 修 xs 断点 tabbar 遮挡 🔴 明确违反规范 §5.1

**现状**：`_shots2/21-tasks-xs.png`（420px）底部 tabbar 压住任务表最后一行。

`shell.css:184` 已有补偿，但加在 `main` 的 padding 上，`.task-table` 最后一行溢出到 padding 区之外。

**改成什么**：给滚动容器内的最后一个块加 margin，而不是只靠父级 padding：

```css
@media (max-width: 720px) {
  .task-table,
  .page-stack > :last-child { margin-bottom: calc(24px + env(safe-area-inset-bottom)); }
}
```

**验收**：420px 宽下滚到底，最后一行任务完整可见且可点击。

---

## 四、C 类 · 给中文字形性格（约 1.5 小时）

这是 [12 册主因 2](12-round2-verdict.md) 的正面解法。中文占 59.6% 可视宽度，**不解决这个，视觉改造的天花板就锁死了**。

### C1 — 先修字体工程三个问题 🔴 前置

```
1. 路径：fonts.css 全部 8 条走 ../../node_modules/  → 改为 public/fonts/ 或 @fontsource 包导入
2. 分片：Noto Sans SC 整包 3.4 MB（对比 Plex 全家 99 KB）
        dist CSS 中 unicode-range 出现 0 次
        → 改用 @fontsource/noto-sans-sc 的分片入口，或自建 subset
3. preload：index.html 无任何字体预载
        → <link rel="preload" as="font" type="font/woff2" crossorigin>
           至少预载 Plex Sans 400/600 与中文 400 的首屏分片
```

**为什么是前置**：当前时序是「先用系统字体画完整页中文 → 1MB 字体到位 → 整页跳变」。网络稍慢时**你看到的中文根本就是系统字体**——在修好这个之前，任何字形层面的设计都不会稳定呈现。

**验收**：dist CSS 中 `unicode-range` 出现次数 > 0；中文字体首包 < 100 KB；DevTools Network 中中文字体在 CSS 之后立即开始下载。

---

### C2 — 解开 `base.css:33` 的中文锁定 🔴

**现状**：

```css
h1, h2, h3, h4 { font-family: var(--font-cn); letter-spacing: 0; }
```

全站标题被主动指定为中文字体优先，**IBM Plex Sans 完全无法参与标题渲染**。

**问题**：标题里的拉丁字符（`CodeFixer`、`GitLab MR`、`#48217`、`Redmine`）也被迫用思源黑体的拉丁部分画——那是一套设计上从属于中文的拉丁字形，单独看质量平平。

**改成什么**：

```css
h1, h2, h3, h4 { font-family: var(--font-sans); }   /* Plex Sans 在前，中文自动 fallback 到 Noto */
```

`--font-sans: "IBM Plex Sans", "Noto Sans SC", sans-serif` 已经是正确的栈——**拉丁走 Plex，中文自动落到 Noto**，这正是想要的效果。当前的 `--font-cn` 覆盖是多余且有害的。

> `letter-spacing: 0` 可以保留（中文标题不该有负字距），但应该只作用于中文——见 C3。

---

### C3 — 给中文标题做字重与字距编排 🟡 这是「性格」的真正来源

思源黑体本身没有太多性格空间（这是它作为通用字库的设计目标）。但**排版编排可以创造性格**：

```css
/* 页面 h1：加大字重差 + 微收字距 + 大幅提升与副标题的对比 */
h1 {
  font-size: var(--t-page);      /* 30px */
  font-weight: 600;
  letter-spacing: -0.01em;        /* 中文轻微收紧，30px 下不会粘连 */
  line-height: 1.2;
}
h1 + p {
  font-size: var(--t-caption);    /* 13px —— 与 h1 拉开 2.3 倍 */
  color: var(--tertiary);         /* 比现在的 --muted 更淡 */
}

/* section 标题：反向操作，用字距张开做「铭牌感」 */
h2 {
  font-size: var(--t-title);      /* 19px */
  font-weight: 500;               /* 降一档，靠字距而非字重建立存在感 */
  letter-spacing: 0.04em;         /* 中文张开 —— 这是工业铭牌的经典手法 */
}
```

**为什么有效**：中文张开字距（`letter-spacing: 0.04em`）会立刻产生「刻在金属牌上」的观感，这与「工业修复账本」的方向锚点（机床铭牌 / 设备面板）直接对应。**这是不换字体也能拿到性格的最有效手法**，且成本只有几行 CSS。

**注意**：字距张开只用于 **h2 级 section 标题**（短、少、位置固定）。正文和 h1 不要张开——中文正文加字距会严重降低阅读速度。

---

### C4 — （可选）换掉中文字体 🟢 收益高但成本也高

如果 C2 + C3 之后仍觉得中文缺性格，可以考虑换字库。候选：

| 字体 | 性格 | 适配度 | 成本 |
|---|---|---|---|
| **霞鹜文楷 / LXGW WenKai** | 楷体骨架、手写感 | ❌ 与工业调性冲突 | — |
| **HarmonyOS Sans SC** | 比思源更方、字腔更窄、有工业感 | ✅ **最贴合** | 中（需自建 subset） |
| **思源宋体 Noto Serif SC** | 衬线、账本/印刷台账感 | ◐ 仅适合标题层 | 中 |
| **得意黑 Smiley Sans** | 强倾斜、极窄、张力大 | ◐ 只适合 h1，正文不可用 | 低（有 CDN） |

**推荐组合**：正文继续 Noto Sans SC，**h1 单独用得意黑或思源宋体**。只换一个层级，成本最低，但因为 h1 是视线第一落点，感知收益极高。

这一条留作可选——C2 + C3 已经能拿到大部分收益。

---

## 五、执行顺序与工时

| 阶段 | 内容 | 工时 | 感知收益 |
|---|---|---|---|
| **第 1 步** | A1（删 kicker）+ A2（8 个等待中）+ A3（状态胶囊） | 45 min | 🔴🔴🔴 |
| **第 2 步** | A9（抽 stage.ts，含分叉修复） | 40 min | 🟡（含正确性） |
| **第 3 步** | B1（首页去 StageRail 改单行）+ B2（主次对调） | 2.5 h | 🔴🔴🔴 |
| **第 4 步** | A7（字号五档）+ A8（清裸值） | 1 h | 🔴🔴 |
| **第 5 步** | C1（字体工程）+ C2（解锁标题字体）+ C3（字距编排） | 1.5 h | 🔴🔴🔴 |
| **第 6 步** | A4 A5 A6 + B3（空态时间戳）+ B4（xs 遮挡） | 1 h | 🟡 |
| | | **≈ 7.5 h** | |

**如果只有 2 小时**：做第 1 步 + 第 5 步。这两步覆盖了「降噪」和「字形」两个最大的感知变量，且互不依赖。

**如果只能做一件事**：**B1**。首页从「三张塞满进度轨道的大卡」变成「三行紧凑列表」，是全部建议里视觉冲击最大的单一改动。

---

## 六、验收清单

改完后逐项核对：

```
□ grep -c 'page-kicker\|section-index\|modal-kicker' → ≤ 5，且无中文直译
□ queued 任务的 StageRail 下方无任何文字
□ 首页任务卡右上角无状态胶囊
□ grep -c StageRail DashboardPage.tsx → 0
□ 有失败任务时，失败内容在首屏视觉中心
□ 设置页四张卡标题区各一行
□ font-size 只剩 5 个值（或全部 var(--t-*)）
□ border-radius 无裸像素值、无 999px
□ DashboardPage/TasksPage 内无 stageLabels/state/duration/rail/repairAttempts 本地定义
□ 5 分钟的阶段在两个页面显示一致
□ no_change 任务在两个页面的轨道显示一致
□ dist CSS 中 unicode-range 出现次数 > 0
□ 中文字体首包 < 100 KB
□ base.css 中 h1-h4 不再指向 --font-cn
□ 首页空态显示「上次检查 N 秒前」且数字在跳
□ 420px 宽下任务表最后一行不被 tabbar 遮挡
□ 暗色下 segmented 选中态仍有浮起感
```

---

## 七、遗留事项（不在本轮范围）

以下三项本轮不做，但需要记录：

1. **`.detail-disclosure` 展开态无快照覆盖**——`_shots2/11-task-drawer.png` 与 `12-task-drawer-expanded.png` md5 完全相同（`81805a93…`），说明展开态从未被采集。修 Playwright fixture 时补一次 `page.click('summary')`。

2. **`--side` 令牌全站零使用**——`tokens.css:33` 定义了 `--side: #a74182`（规范 §3.3 的 `status-side-effect`），但 `FailureSurface` 的 `.failure-effects`（外部副作用分区）用的是普通灰。这个语义色应该用上——「已经发生的外部结果」正是它的设计用途。

3. **14 个 design primitives 仍是 0**——`frontend/src/components/` 空目录。本轮刻意不做（感知收益低于工程成本），但如果之后要做第三轮改造，这会成为瓶颈。

---

## 八、临时产物清理

复评过程中产生 / 遗留的文件：

```
frontend/_audit2.mjs        本轮截图脚本
frontend/_shots2/           改造后 41 张截图
.local/ui-audit/shots/      改造前 41 张截图（建议保留，是唯一的 before 基线）
```

`_audit2.mjs` 与 `_shots2/` 可删；`.local/ui-audit/shots/` **建议保留**——它是改造前唯一完整的视觉基线，第三轮复评时还要用。

---

**上一册** ← [13 · 视觉信息重复与页面职责重叠](13-round2-redundancy.md)
**返回** → [README](../README.md)
