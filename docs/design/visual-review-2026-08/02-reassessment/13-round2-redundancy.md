# 13 · 视觉信息重复与页面职责重叠

> 本册回答两个问题：
> ① 界面上是不是有视觉信息在重复？—— **是，七类。**
> ② 首页和任务页是不是重复了？—— **是，而且是信息层与代码层双重重复。**

---

## 一、判定标准

不是所有重复都是问题。区分标准只有一条：

> **同一条信息，在同一屏内，用两种以上视觉手段表达，且没有一种手段承担了别的手段做不到的事。**

冗余编码在两种情况下是**必要的**，本册不计入：

- **可访问性冗余**：颜色 + 形状同时编码状态（色盲用户需要形状）。StageRail 的「红色 + 旋转方块 ✕」属此类，**保留**。
- **跨屏一致性**：同一状态在列表与详情里都出现，帮助用户建立映射。

除此之外，本册列出的七类都是**纯噪音**：占了像素、占了扫视时间、没有增加任何信息。

---

## 二、七类视觉重复

### 重复 1：首页顶部同一份数据说两遍 —— 🔴 最刺眼

截图 `_shots2/01-dashboard-light-full.png`，首屏前 200px 内：

```
┌─ hero ──────────────────────────────────────────────┐
│  REPAIR CONTROL / LIVE                    ● 持续监听 │
│  维修控制台                                        4 │
│  只看正在处理的任务和需要你关注的问题。 活跃任务·每3秒同步│
└─────────────────────────────────────────────────────┘
                        ↕ 相隔约 40px
┌─ metrics ───────────────────────────────────────────┐
│   2         │      33       │       3               │
│  处理中      │    已完成      │   需要处理             │
└─────────────────────────────────────────────────────┘
```

代码位置：`DashboardPage.tsx:19`（slots）与 `DashboardPage.tsx:20`（metrics）。

- 右上 `.slots` 的 **`{metrics.active}` = 4**（活跃任务）
- 下方 `.metrics` 的 **处理中 2 + 需要处理 3**

`active` 与 `running + failed` 语义高度重叠，两组数字来自同一个 `metrics` 对象、渲染在同一屏、相隔 40px。而 `.slots b` 用了 `font: 600 30px/1 var(--font-mono)`——**全站第二大的字号，给了一个下面立刻会被拆解的汇总数**。

> **判定**：纯冗余。`.slots` 提供的「每 3 秒同步」是唯一独有信息，但它可以并入空态或页脚。

### 重复 2：每张任务卡状态编码三次

`DashboardPage.tsx:12` 的 `LiveTask` 组件，单张卡片内：

| # | 手段 | 位置 | 视觉重量 |
|---|---|---|---|
| 1 | 右上角「处理中」胶囊 | `.status-pill.running`，橙底橙字 | 高 |
| 2 | 卡片左缘 4px 橙色竖条 | `pages.css:41` `.task-card::before` | 中 |
| 3 | StageRail 上「修复 / 进行中」橙字 | `components.css:144` `.stage-running strong` | 中 |

三者全部用 `--signal` 橙色，全部表达「这个任务正在跑」。

其中 **③ 是必要的**（它同时指明了跑到哪一阶段，是别的手段做不到的），**② 成本最低**（4px 竖条，几乎不占空间），**① 是纯重复**（占据右上角高价值位置，只说了一个下面已经说过的词）。

### 重复 3：queued 任务卡下面 8 个「等待中」—— 🔴 信息量为零

截图 `_shots2/01-dashboard-light-full.png` 第三张任务卡：

```
准备    范围    定位    评估    修复    验证    复核    交付
 ○      ○      ○      ○      ○      ○      ○      ○
等待中  等待中  等待中  等待中  等待中  等待中  等待中  等待中
```

成因 —— `DashboardPage.tsx:8` 的 `duration()`：

```js
const duration=(stage:StageRun)=>{
  if(!stage.started_at) return '';
  if(!stage.finished_at) return stage.status==='running'?'进行中':'';
  ...
}
```

`duration()` 本身对未开始的阶段返回 `''`，是对的。问题在 `rail()`（`DashboardPage.tsx:9`）：当 `grouped.get(id)` 找不到该阶段时返回 `state: 'queued'`，而 StageRail 组件在 queued 态下渲染了 `labels[status]` 兜底文案。

**8 个一模一样的词横排一行，是全站视觉噪音密度最高的单点。** 灰色小字在 8 个位置重复，眼睛会不自觉逐个扫过去，然后发现什么也没读到。

### 重复 4：英文 kicker 与中文标题成对说同一件事 —— 全站 19 处

完整清单（`grep` 精确命中，含 className 与文本）：

| # | 文件 | 英文 kicker | 紧邻的中文 | 是否同义 |
|---|---|---|---|---|
| 1 | `App.tsx:85` | `EXECUTION AUTHORITY` | （模式确认框标题） | 部分 |
| 2 | `StageRail.tsx:21` | `REPAIR LOOP` | 重试次数 | 部分 |
| 3 | `DashboardPage.tsx:19` | `REPAIR CONTROL / LIVE` | **维修控制台** | **完全同义** |
| 4 | `DashboardPage.tsx:21` | `01 / ACTIVE` | **正在处理** | **完全同义** |
| 5 | `DashboardPage.tsx:22` | `02 / ATTENTION` | **需要处理** | **完全同义** |
| 6 | `DashboardPage.tsx:22` | `NEEDS ACTION` | （失败任务标题） | 同义于 ⑤ |
| 7 | `TasksPage.tsx:32` | `TASK LEDGER` | **任务** | **完全同义** |
| 8 | `TasksPage.tsx:38` | `REPAIR SIGNAL` | **处理进度** | **完全同义** |
| 9 | `TasksPage.tsx:38` | `OUTPUT` | **交付结果** | **完全同义** |
| 10 | `TasksPage.tsx:20` | `NO CHANGE / VERIFIED` | **代码已经满足工单描述** | **完全同义** |
| 11 | `TasksPage.tsx:21` | `FROZEN CHANGE` | **候选修改已封存** | **完全同义** |
| 12 | `ProjectsPage.tsx` | `REPAIR ROUTES` | **项目** | **完全同义** |
| 13 | `ProjectsPage.tsx` | `PROJECT WORKBENCH` | （工作台标题） | **完全同义** |
| 14 | `ProjectsPage.tsx` | `ORIGIN` | （来源字段） | **完全同义** |
| 15 | `ProvidersPage.tsx` | `INTAKE CHANNELS` | **工单来源** | **完全同义** |
| 16 | `ProvidersPage.tsx` | `TICKET PROVIDER` | （来源配置框标题） | **完全同义** |
| 17 | `SettingsPage.tsx:103` | `AUTOMATION` | **运行方式** | **完全同义** |
| 18 | `SettingsPage.tsx:105` | `MODEL` | **当前模型** | **完全同义** |
| 19 | `SettingsPage.tsx:107` | `CAPACITY` | **AI 并发池** | **完全同义** |
| 20 | `SettingsPage.tsx:109` | `HEALTH` | **运行环境** | **完全同义** |

（实测 20 处，其中 17 处为完全同义。上一轮口头汇报的「19 处」为 grep 未覆盖 `<small>` 变体时的计数。）

统一样式（`components.css:5-14`）：

```css
.page-kicker, .section-index, .modal-kicker, .failure-flag {
  display: block; margin-bottom: 8px;
  color: var(--signal);
  font: 600 10px/1.2 var(--font-mono);
  letter-spacing: .15em;
}
```

**每一处都占用一整行 + 8px margin，全部用橙色主色**——这是全站视觉噪音**总量**最大的一类：20 行橙色小字，说的全是下一行中文已经说过的话。

> 英文 kicker 作为一种装饰手法本身没问题（它确实能强化「工业仪表」的调性）。问题是**把它用成了标题的翻译**。如果它承载的是编号、状态码、时间戳这类中文标题不含的信息，就有价值；当它只是标题的英译，就是纯噪音。

### 重复 5：设置页每张卡三层标签

`SettingsPage.tsx:103 / 105 / 107 / 109`，四张卡结构完全一致：

```html
<header>
  <span className="card-index">01</span>      ← 第一层：方框编号
  <div>
    <small>AUTOMATION</small>                  ← 第二层：英文
    <h2>运行方式</h2>                          ← 第三层：中文
  </div>
</header>
```

单张卡片的标题区就占了三行视觉，而卡片本体（一个 segmented 二选一控件）只有一行。**标题比内容还重。**

`01 02 03 04` 编号在这里也不承载信息——四张卡没有先后依赖关系，编号不表示步骤。

### 重复 6：项目页状态胶囊与动作按钮互为同义反复

每张项目卡：

- 右上角 `.readiness-badge` 显示「待体检」
- 卡片底部按钮显示「运行体检」

「待体检」这个状态，完全可以由「运行体检」按钮的存在本身表达（体检过了就换成「重新体检」+ 结果摘要）。当前是**状态与动作各说一遍**。

配套的 `.project-card[data-health="inactive"]::before` 虚线竖条是第三重编码（这一条成本低，可保留）。

### 重复 7：任务抽屉失败信息三处

`TasksPage.tsx:35-38`，打开一个失败任务：

| # | 位置 | 内容 |
|---|---|---|
| 1 | `.fact-grid` | 「状态：**失败**」 |
| 2 | `FailureSurface` 红块 | 「验证失败」+ 失败码 + 摘要 + 提示 |
| 3 | StageRail | verify 节点渲染成红色旋转方块 ✕ |

③ 是必要的（指明失败发生在哪一阶段）。② 是本轮新做的、信息量最大的。① 是纯冗余——`.fact-grid` 的「状态」格在失败场景下只是把红块标题重说一遍。

---

## 三、首页 vs 任务页：双层重复

### 3.1 信息层 —— 同一批数据，两种画法

| 维度 | 首页「正在处理」 | 任务页 |
|---|---|---|
| 数据源 | `api.dashboard().recentTasks` 筛 `queued/running/cancel_requested`，`.slice(0,3)` | `api.tasks().items` 全量 |
| 交集 | **首页那 3 条，是任务页 8 行中的 3 行** | |
| 渲染形态 | `LiveTask` 卡片 + **完整 8 节点 StageRail** | `.task-table` 单行（状态 / 工单标题 / 结果 / →） |
| 筛选维度 | metrics：处理中 / 已完成 / 需要处理 | filter-strip：全部 / 处理中 / 待开始 / 失败 / 已完成 |
| 轮询周期 | 3 秒 | 3 秒 |

**两个页面每 3 秒各拉一次同一批数据，用两套完全不同的视觉语言画同一批任务。**

更关键的是 **StageRail 出现在首页**。它是本产品信息密度最高的组件（8 个节点 × 标签 + 时长 + 状态 = 24 个信息单元），`components.css:125` 给它设了 `min-width: 560px`。三张卡叠起来 = **72 个信息单元**，全部挤在首页主区。

而首页 hero 的自我定位是：

> 「只看正在处理的任务和需要你关注的问题。」

「只看」两个字与「每张卡塞 24 个信息单元」直接矛盾。

### 3.2 代码层 —— 五个定义逐字重复，且已经开始分叉

| 定义 | DashboardPage | TasksPage | 是否一致 |
|---|---|---|---|
| 阶段中文名表 | `:6` `stageLabels` | `:7` `stageLabel` | **内容逐字相同**，变量名差一个 s |
| 状态映射 | `:7` `state` | `:8` `state` | **逐字符相同** |
| 时长格式化 | `:8` `duration` | `:10` `meta` | **已分叉**（见下） |
| 轨道构建 | `:9` `rail` | `:11` `stageRail` | **已分叉**（见下） |
| 重试次数 | `:10` `repairAttempts` | `:12` `repairAttempts` | **逐字符相同** |

**分叉 1 — 时长格式化**：

```js
// DashboardPage.tsx:8
return ms<1000?'完成' : ms<60000?`${...} 秒` : `${...} 分`   // 有「分」档

// TasksPage.tsx:10
return ms<1000?'完成' : `${Math.max(1,Math.round(ms/1000))} 秒`  // 无「分」档
```

→ **一个跑了 5 分钟的阶段，首页显示「5 分」，任务页显示「300 秒」。**

**分叉 2 — 轨道构建（更严重）**：

```js
// TasksPage.tsx:11 —— 处理了 no_change 分支
const noChange = latest.get('no_change_verify');
const item = id==='verify' && noChange ? noChange : latest.get(id);
const branchSkipped = Boolean(noChange) && !item && (id==='repair'||id==='deliver');
return { ..., state: item?state(item.status) : branchSkipped?'skipped':'queued' }

// DashboardPage.tsx:9 —— 完全没有这段
return { ..., state: item?state(item.status):'queued' }
```

→ **同一个「无需修改」任务，任务页的轨道会把 repair / deliver 画成跳过态（虚线 + 斜杠节点），首页画成普通等待态（实心灰圈）。**

这不只是代码冗余，是**已经产生的视觉不一致**：本轮 codex 精心做的 `stage-skipped` 虚线样式，在首页永远不会触发。

**共同缺陷**：两处 `order` 数组都只有 8 项，`stageLabels` 有 12 项（详见 [12 册 §4.2](12-round2-verdict.md)）。

---

## 四、建议的页面分工

这是本轮**降噪收益最大的单一改动**。

### 4.1 定位重新划线

| 页面 | 该回答的问题 | 不该做的事 |
|---|---|---|
| **首页** | 「现在有什么需要**我**做？」 | 不做任务浏览、不做进度详情、不渲染完整 StageRail |
| **任务页** | 「所有任务的状态账」 | 不做单任务深挖（那是抽屉的事） |
| **任务抽屉** | 「这一个任务发生了什么」 | —— |

一句话：**首页是「收件箱」，任务页是「账本」，抽屉是「档案」。** 当前三者的边界是糊的。

### 4.2 首页具体改法

**移除**：
- `.slots` 整块（重复 1）
- `LiveTask` 里的 `<StageRail>`（信息层重复）
- 任务卡右上角 `.status-pill`（重复 2）

**保留并压缩**——进行中任务改为单行紧凑态：

```
● 修复 · 2 分  redmine-main #48217  订单导出金额精度错误        →
◐ 定位 · 34 秒 tapd-core #9921      登录态偶发丢失              →
○ 等待         redmine-main #48250  报表分页越界                →
```

每行只保留：状态点（形状+色）、**当前阶段名 + 该阶段已耗时**、工单号、标题、进入箭头。

> 「当前跑到哪一步、跑了多久」是首页真正需要的进度信息。**完整 8 节点轨道要回答的是「整体走到哪」，那是打开任务后才需要的。**

**强化**「需要处理」——这是首页存在的唯一理由。当前右侧 `.attention` 栏宽 270–340px，视觉权重低于左侧任务区。建议对调：失败任务占主区，进行中任务收成右侧窄栏或顶部一行摘要。

**空态补时间戳**（[12 册 §4.3](12-round2-verdict.md)）：

```
当前没有进行中的任务
上次检查 2 秒前 · 工单轮询正常
```

### 4.3 任务页具体改法

- 保持 `.task-table` 账本形态（本轮做得好）
- 列表行**不渲染 StageRail**（当前也没有，保持）
- 完整 StageRail **只活在抽屉里**
- filter-strip 与首页 metrics 的语义对齐（首页点「需要处理」→ 跳任务页并预选 `failed`）

### 4.4 代码层去重

新建 `frontend/src/entities/stage.ts`，抽出：

```ts
export const STAGE_LABELS: Record<string,string>   // 12 项
export const STAGE_ORDER: string[]                 // 补齐 12 项
export function stageState(value: string): StageState
export function stageDuration(stage: StageRun): string   // 统一到「秒 / 分」双档
export function buildRail(run: TaskRun): StageItem[]     // 以 TasksPage 版为准（含 no_change 分支）
export function repairAttempts(run: TaskRun): number
```

两个页面改为 import。**以 TasksPage 的版本为准**——它处理了 `no_change_verify` 分支和 `skipped` 态，是正确的那一份。

`STAGE_ORDER` 补齐 12 项后需注意：12 个节点在首页卡片宽度下会过密，这也是**首页不该渲染完整轨道**的又一个理由。

---

## 五、重复清单速查

| # | 重复项 | 位置 | 建议动作 | 降噪收益 |
|---|---|---|---|---|
| 1 | 首页 slots 与 metrics | `DashboardPage.tsx:19,20` | 删 slots | 🔴 高 |
| 2 | 任务卡状态三重编码 | `LiveTask` + `pages.css:41` | 删 status-pill | 🟡 中 |
| 3 | 8 个「等待中」 | `DashboardPage.tsx:9` | queued 态 meta 返回 `''` | 🔴 高 |
| 4 | 英文 kicker × 20 | 全站 | 删或改为承载编号/状态码 | 🔴 最高 |
| 5 | 设置页三层标签 | `SettingsPage.tsx:103-109` | 只留中文 h2 | 🟡 中 |
| 6 | 项目页状态 + 动作 | `ProjectsPage.tsx` | 状态并入按钮文案 | 🟢 低 |
| 7 | 抽屉失败三处 | `TasksPage.tsx:35-38` | 失败态隐藏 fact-grid 状态格 | 🟢 低 |
| 8 | 首页/任务页信息重复 | 两页 | 首页去 StageRail，改单行 | 🔴 最高 |
| 9 | 五个函数逐字重复 + 已分叉 | `:6-10` / `:7-12` | 抽 `entities/stage.ts` | 🔴 高（含正确性） |

---

**上一册** ← [12 · 第二轮复评总判](12-round2-verdict.md)
**下一册** → [14 · 降噪执行单与下一轮优先级](14-round2-noise-cut.md)
