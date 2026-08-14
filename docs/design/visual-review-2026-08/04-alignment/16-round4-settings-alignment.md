# 16 · 第四轮：设置页的方感、对齐与信息噪音

> 本册回答两批精准反馈。
>
> **第一批（形态）**
> 1. **「除了设置界面，好像其他地方都是圆角，设置页有点突兀的方感」** —— 属实，但**不是圆角的问题**。
> 2. **「里面的卡片也不对齐，参差不齐，这个设计好吗」** —— 不好。已改为等高 + 主控件贴底。
> 3. 顺带修正上一册留下的**页面标题不一致**：kicker 三有一无。
>
> **第二批（这个界面到底在说什么）** —— 见 §6
> 4. 切到设置页时，「设置」标题先闪一下。
> 5. 改并发数量时，「全自动 / 待我开始」跟着闪。
> 6. 「环境正常 · 4/4 项核心正常」—— **四项是啥？**
> 7. Claude Code CLI 为什么重复两次？这张卡到底想展示什么？
>
> 第 6、7 两条是本轮唯二**违反 SPEC 明文**的问题（第 1168 行、第 1495 行），不是审美偏好。
>
> 施工过程中另外撞出两件事：**第三处同屏复读**（§5），以及**视觉回归线本身是坏的**（§7）——默认阈值能放过「整块文字区消失」，导致基线漏更两轮。
>
> 本册**修正 [15 册 §8](../03-single-ledger/15-round3-single-list.md) 验收项**「任务页 h1 上方无英文 kicker」——该项按四页反向统一处理，见 §3。

---

## 一、方感的真凶不是圆角

先证伪最直观的猜测。全站圆角令牌四档：

```css
--r-sharp: 3px    /* 徽标、状态点、微型标签 */
--r-sm:    7px    /* 卡片、输入框、按钮 */
--r-md:    11px   /* 大面板、表格容器 */
--r-overlay: 16px /* 模态、抽屉 */
```

用计算样式实测设置页四张卡：

```
cardRadius: "7px"
```

**和全站 `--r-sm` 完全一致。** 卡片本身一点都不方。所以「方」的来源必须在卡片内部。逐个量下来，三个元素在别处不存在：

### 1.1 `.card-index` —— 四个纯直角方块，戳在最显眼的位置

```css
/* 改前 */
.card-index { display: grid; place-items: center; width: 36px; height: 36px;
              border: 1px solid var(--line-strong); /* ← 没有 border-radius */ }
```

36×36 的实心描边方块，四张卡各一个，全部落在卡片**左上角**——视线进入卡片的第一落点。对照来源页的同类元素：

| 元素 | 尺寸 | 圆角 |
|---|---|---|
| `.provider-monogram`（来源页） | 46×46 | `--r-sm` |
| `.card-index`（设置页） | 36×36 | **无** |

同一种「方形标识块」，一个有一个没有。这不是设计意图，是遗漏。

### 1.2 `.mode-callout` —— 只有上下两条边线的横条

```css
/* 改前 */
.mode-callout { border-block: 1px solid var(--line); }
```

`border-block` 只画上下、不画左右，自然也谈不上圆角。结果是 01 卡中间横着一条**四角全直、左右开口**的带子。全站再无第二处这种形状——别的地方要么是完整描边卡，要么是纯背景块。

### 1.3 `.control-card::before` —— 四条 4px 彩色左边线

```css
/* 改前 */
.control-card::before { position: absolute; inset: -1px auto -1px -1px; width: 4px;
                        border-radius: var(--r-sm) 0 0 var(--r-sm); background: var(--line-strong); }
.settings-mode::before        { background: var(--signal); }
.settings-agents::before      { background: var(--reconcile); }
.concurrency-card::before     { background: var(--nochange); }
.settings-environment::before { background: var(--success); }
```

这条色带有两重问题：

- **形状孤例**：全站没有第二处「卡片左侧竖色带」。任务表格靠行内状态标签，流水线靠卡内字段，来源页靠字母徽标——都不用边线做分类。
- **暗色下变成硬边框**：亮色里这是四条淡色装饰；深底上 `--signal`/`--success` 这类饱和色变成四道高对比亮条，等于给每张卡额外加了一层轮廓。**暗色截图里的「方」比亮色重得多，就是这么来的。**

更关键的是它在**表达一个不存在的语义**。四种颜色分别是信号色、复核色、无变更色、成功色——这套颜色在别处都有确定含义（任务状态）。在设置页它们只是「第 1/2/3/4 张卡」，纯装饰性借用，会稀释状态色的可信度。

**处置：全部删除。** 卡片编号已经由 `01–04` 表达，不需要第二套编码。

### 1.4 不动的一处

`.no-change-mark` 也是直角，但它是 no_change 的**印章语义**（配 `=` 符号，模拟盖章），是刻意的形式构件，不在本轮改动范围。

---

## 二、参差不齐：量化与修法

### 2.1 先量，再判断

四张卡的实测高度：

| | 左列 | 右列 | 差值 |
|---|---|---|---|
| 第 1 行 | 271 | 225 | **46px** |
| 第 2 行 | 253 | 269 | **16px** |

但同时量到三件事：

- 四张卡的 `header` 底边**都在 72**
- 四张卡的说明文字 `p` 底边**都在 108**
- 四张卡从主控件底到卡片底的留白**都是 23px**

也就是说，**上半部对齐良好，下半部各自为政**。参差不是随机的——它是「每张卡内容多少不同，但都紧跟着上一块往下排」的必然结果。

这决定了修法不是「强行等高」（那只会在短卡底部留一段无意义空白），而是**给下半部也建立一条对齐轴**。

### 2.2 改法：`stretch` + 主控件贴底

```css
/* 改后 */
.control-grid { align-items: stretch; }            /* start → stretch，同行等高 */
.control-card { display: flex; flex-direction: column; min-height: 0;
                padding: 21px 22px 22px; }          /* 左 25px → 22px，色带删了不用留位 */
.control-card > p + * { margin-top: auto; }         /* 说明文字之后的一整组，压到底部 */
```

第三行是关键，也是唯一容易写错的地方。

**为什么不是 `:last-child`？** 因为四张卡的「主控件」结构不同：

| 卡 | 结构（`header` → `p` → 之后） |
|---|---|
| 01 运行方式 | `.mode-callout` + `.segmented` |
| 02 当前模型 | `.current-model-control` |
| 03 AI 并发池 | `.concurrency-control` + `.capacity-meter` + `.capacity-scale` |
| 04 运行环境 | `.readiness-summary` + `.dependency-grid` |

> 04 卡的 `.readiness-summary` 随后在 §6.3 被整块删除，此处保留改造当时的结构以说明选择器为何这样写。

03 卡的主控件是三块、04 卡是两块。`margin-top:auto` 只推最后一块，会把加减器和刻度尺**拉裂**——中间凭空插进一段空白。

`p + *` 推的是「说明文字之后的第一块」，`auto` 把它连同其后所有兄弟一起顶到底部，**整组保持原有间距下沉**。这是唯一能同时满足「组内不裂」和「组底对齐」的选择器。

### 2.3 改后复测

```
第 1 行 271 = 271   主控件底部  248 / 248
第 2 行 269 = 269   主控件底部  246 / 246
gridAlign: "stretch"
idxRadius: "7px"   calloutRadius: "7px"   cardRadius: "7px"
```

两条对齐轴成立：上轴是标题与说明文字，下轴是主控件底边。开关、下拉、加减器现在落在同一条水平线上。

**代价**：内容最少的 02 卡（当前模型）中部会出现一段留白。这是等高布局的必然成本，已确认接受——比起「四张卡的操作控件散落在四个不同高度」，一段可预期的留白是更小的代价。

---

## 三、页面 kicker：反向统一

15 册的验收项写的是「任务页 h1 上方无英文 kicker」，当时的判断是 kicker 属于可削的噪音。但实际状态是：

| 页面 | kicker |
|---|---|
| 流水线 | `REPAIR PIPELINES` |
| 反馈源 | `INTAKE CHANNELS` |
| 设置 | `CONTROL PARAMETERS` |
| 任务 | **无** |

三有一无，这比「四个都有」或「四个都没有」都糟——落地页缺了一层，四页标题区结构对不上。

**处置：反向统一，任务页补 `REPAIR RECORD`。** 四页标题区结构一致：kicker → h1 → 说明/摘要。

这一项**修正 15 册 §8 的对应验收行**。

---

## 四、连带修掉的重复入口

改 kicker 时顺手核对了标题区的按钮，发现反馈源页在零来源时有两个入口做同一件事：

- 右上角「添加反馈源」
- 空态卡片里「连接反馈源」

外加任务页首屏引导的「去配置」，同一个动作在同一条路径上出现三次。

**处置**：右上角按钮改为 `providers.length > 0 &&` 条件渲染。零来源时只保留空态里那一个——空态卡片本来就是为「引导下一步」存在的，标题区再摆一个是纯重复。

同时把页面标题从「工单反馈来源」统一为「反馈源」（与导航一致），`ProjectsPage` 里引用旧名的提示文案（`还没有可选反馈源。请先到"工单反馈来源"…`）同步跟改。

---

## 五、施工中撞出来的第三处同屏复读

改完上述三项后跑组件测试，`tests/stage-rail.test.tsx` 报严格模式冲突：

```
strict mode violation: getByText('PARTIAL DELIVERY') resolved to 2 elements
```

这不是测试写法问题——**界面真的把同一句话说了两遍**。`git stash` 后在 HEAD 上复现，来自 `c64ec42`，不是本轮引入，但性质和前三轮一直在清的重复完全一致，就地修掉。

### 5.1 复读来自 `TaskConclusion` 的兜底分支

后端没返回 `run.conclusion` 时，`TaskConclusion` 会用任务字段拼一段兜底文案。问题是这段兜底和同屏已有的专属版面**逐字撞车**：

| 兜底字段 | 取值 | 同屏已有 |
|---|---|---|
| `headline` | `任务未能完成` | `FailureSurface` 的 `<b>远程交付失败</b>` |
| `cause` | `failure.summary` | `FailureSurface` 的 `<p>` —— **同一个字符串** |
| `resolution` | `failureHint[code]` | `FailureSurface` 的 `<small>` —— **同一个字符串** |

`no_change` 分支同理：「当前代码无需修改 / 当前基线已经满足工单描述」紧挨着 `NoChangeSurface` 的「代码已经满足工单描述 / 定位、验证与独立复核均未发现需要交付的代码差异」。视觉上是两块并排的大面板在互相复述。

### 5.2 改法：没有真实结论时不兜底

```tsx
// 没有真实结论时，失败和 no_change 都已经有专属版面在说同一件事，
// 这里再兜一遍就是同屏复读。只有「已完成且有改动」没有别的版面兜底，才保留通用结论。
if (!value && (task.failure || task.result === 'no_change')) return null
```

保留了两条路径：

- 后端返回真实 `conclusion` → 照常渲染（失败任务也一样，fixture 里的 `task-failed` 有真结论，抽屉不变）。
- 已完成且有改动、又没有 `conclusion` → 保留通用兜底，因为这一支确实没有别的版面接手。

no_change 抽屉因此少了一整块面板，基线 `task-no-change-drawer-dark.png` 相应更新。

---

## 六、设置页的四处闪烁与噪音（追加）

上述三项改完后，用户在真机上给出四条新反馈。它们和前五节不同——前五节是「排版对不对」，这四条是**「这个界面到底在说什么」**。逐条取证。

### 6.1 切到设置页时，「设置」标题先闪一下

不是动画，是 **DOM 结构在两帧之间变了**。改前的加载态：

```tsx
if (!settings) return <section className="page-stack">
  <div className="page-heading"><div><h1>设置</h1><p>{error || '正在读取配置…'}</p></div></div>
</section>
```

对比就绪态：`kicker → h1 → 说明`。加载态**没有 kicker**。于是 `/api/settings` 一回来，标题区从两行变三行，`h1` 位置下移，整页内容跟着往下跳。视觉上就是「设置」两个字闪一下再落位。

**改法：加载态与就绪态共用同一个 `heading` 常量。**

```tsx
// 加载态与就绪态共用同一套标题区结构（kicker → h1 → 说明），
// 否则接口回来时标题区从两行变三行，整页内容跟着往下跳。
const heading = <div className="page-heading"><div>
  <span className="page-kicker">CONTROL PARAMETERS</span><h1>设置</h1>
  <p>控制平台运行节奏、当前模型和并发容量。</p>
</div></div>
```

顺带把加载态的四张卡改成骨架屏（`.card-skeleton`），而不是空白——否则标题不跳了，下面的网格还是会从「无」到「有」撑开一次。骨架**不做闪烁动画**：这四张卡的形状本来就是稳定的，闪一下再变形比静静等一下更糟。

实测三个阶段的几何：

```
骨架态      headTop 116  headH 88  gridTop 232
settings 到  headTop 116  headH 88  gridTop 232
readiness 到 headTop 116  headH 88  gridTop 232
```

三个阶段完全一致，零位移。

### 6.2 改并发数量时，「全自动 / 待我开始」跟着闪

一个 `busy` 布尔值被三张卡共用：

```tsx
const [busy,setBusy] = useState(false)   // 改前
```

改并发触发 `PUT /api/settings`，`busy` 置 true，于是 01 卡的模式按钮、02 卡的模型下拉**同时被 disable**。disabled 态有自己的配色，视觉上就是「我明明在点加号，旁边两个按钮灰了一下」。

这在语义上也是错的：**改并发数量和「要不要自动执行」没有任何关系**，没有理由锁住后者。

**改法：忙碌态按卡切分。**

```tsx
// 按卡区分忙碌态：改并发不该把运行方式和模型选择一起灰掉。
const [busy,setBusy] = useState<'mode'|'model'|'concurrency'|''>('')
```

`put()` 增加 `scope` 参数，三处 `disabled` 改为精确比较（`busy === 'mode'` / `'model'` / `'concurrency'`）。实测保存并发期间：

```
模式按钮  disabled: false, false   opacity 1
并发按钮  disabled: true,  true
模型下拉  disabled: false
```

只有正在操作的那一组被锁。

### 6.3 「环境正常 · 4/4 项核心正常」—— 四项是啥？

这是本轮**唯一一条违反 SPEC 明文**的问题。四项来自后端 `readiness()`：

| check id | 含义 |
|---|---|
| `config.loaded` | 配置文件能读 |
| `storage.data_root` | 数据目录可写 |
| `sqlite.wal` | SQLite WAL 模式已开 |
| `frontend.dist` | 前端构建产物存在 |

问题在于：**这四项全部正常，是「你能看到这个页面」的前提。** 配置读不到、数据目录不可写、前端产物不存在——任何一项挂了，用户根本打不开设置页，更看不到这行字。所以它恒等于 `4/4`，是一个永远为真的数字。

而且它**不可点开、无从核对**。用户问「四项是啥」，界面给不出任何答案。

对照 [SPEC 第 1168 行](../../design-spec.md)：

> 健康检查正常时只显示能力可用，失败时才在诊断详情展示命令、探测结果和修复方式。

「4/4 项核心正常」既不是「能力可用」，也不是「诊断详情」，是介于两者之间的一个内部计数。

**处置：整块 `.readiness-summary` 删除。** 平台自检项改为**只在 failed 时列出**：

```tsx
// 平台自身的四项自检（配置、数据目录、SQLite、构建产物）不列出：它们正常是打开这个页面的前提，
// 报一句「4/4 正常」既不可点开也无从核对。只有真的挂了才需要占位置。
{blockedChecks.filter(item => !item.id.startsWith('dependency.')).map(...)}
```

### 6.4 Claude Code CLI 为什么重复两次

改前一行依赖渲染出四段文字，实测 innerText：

```
Claude Code CLI            ← 前端 dependencyLabel 映射的显示名
claude-code-cli 2.1.220 可用  ← 后端 summary，原样透出
claude-code-cli            ← 后端 suggestion 里的裸 id
可用                        ← 前端右侧状态标签
```

**同一个工具的名字出现三次，「可用」出现两次。** 后端那句 summary 本来就不是给界面看的：

```python
base.update(
    status="ready",
    summary=f"{binding_id} {version} 可用",
    suggestion=f"为 executableBindings.{binding_id} 配置 versionConstraint",
)
```

`binding_id` 是内部标识，`suggestion` 是给运维看的配置提示——把 `executableBindings.claude-code-cli` 这种实现引用摆到日常设置页，也和 README「日常项目 UI 不暴露这些实现引用」相抵触。

**处置：ready 时只显示版本号，实现细节只在异常时露出。**

```tsx
<small>{item.status === 'ready'
  ? (item.version ? `版本 ${item.version}` : '已就绪')
  : item.summary}
  {item.status !== 'ready' && (item.suggestion || item.command) && <code>{item.suggestion ?? item.command}</code>}
</small>
```

改后整张卡的全部文字：

```
04  HEALTH  运行环境                    [重新检查]
这里只列出当前配置真正会用到的命令行工具；未启用的工具不参与判定。
● Claude Code CLI
  版本 2.1.220                                可用
```

**六句话压到一句真信息**：当前模型用的 CLI 是 Claude Code 2.1.220，可用。

### 6.5 顺带补上的高度稳定性

`refreshReadiness` 改前会先把结果清空再填。依赖检查要跑 subprocess 取版本，比 `settings` 慢一个数量级，这中间卡片会塌一次。这违反 [SPEC 第 1495 行](../../design-spec.md)：

> 异步健康检查必须预留稳定高度，刷新期间保留上一份结果并标记检查中，避免卡片动态跳动。

补 `checking` state：重查期间保留上一份结果、整块 `.is-checking` 半透明、按钮文案变「检查中…」；首次检查未回时渲染一行骨架占位。

---

## 七、视觉回归线本身是坏的

改完 6.3 后跑 `npm run test:e2e`，**6 条全绿**。这不合理——我刚删掉运行环境卡整整一行文字（「环境正常 · 4/4 项核心正常」），设置页基线不可能不变。

用零容差配置重跑，量到真相：

```
settings-light.png: 5299 pixels (ratio 0.01) are different
```

差异真实存在，是默认配置放过了它：

```ts
expect: { toHaveScreenshot: { threshold: 0.25, maxDiffPixelRatio: 0.006 } }
```

`0.006 × 1440 × 900 ≈ 7776 px`。**任何小于 7776 像素的视觉改动都测不出来**——包括删掉一整行文字、挪动一个控件、改掉一段文案。

更糟的是连带效应：因为「通过」了，`--update-snapshots` **不会重写基线**（它只重写失败项）。于是基线一直停在两轮之前的旧图，后续每一轮都在和一张过期参照物比对。`task-failed-drawer-dark.png` 就这样漏更了整整两轮。

### 7.1 先验证渲染是否确定

收紧阈值的前提是渲染稳定，否则只会换来一堆假失败。零容差连跑三次：

```
--- 第 1 次   3 passed
--- 第 2 次   3 passed
--- 第 3 次   3 passed
```

同一台机器、同一份 `dist`，**零像素差异**。既然如此，7776 px 的容差就不是在吸收抖动，而是纯粹的空头额度。

### 7.2 收紧

```ts
// 0.006 的容差约等于 1440×900 里的 7776 px，实测能放过「整块文字区消失」这种改动
// （删掉运行环境卡的摘要行只有 5299 px 差异，旧配置全绿）。同一台机器上连跑三次是
// 零像素差异，所以这里按确定性渲染收紧：只留抗锯齿的单像素色差容忍。
expect: { toHaveScreenshot: { animations: 'disabled', threshold: 0.2, maxDiffPixelRatio: 0.0005 } },
```

新额度约 648 px，仍足以吸收字体抗锯齿的边缘抖动，但删一行文字必然报红。

**注意跨机器风险**：这个数值建立在「同机同产物零差异」的实测上。若将来接 CI 或换机，字体栅格化差异可能需要重新标定。这属于已知代价——宁可换机时调一次数，也好过让回归线长期形同虚设。

### 7.3 附带的常驻纪律

`npm run test:e2e` 打的是 `127.0.0.1:9522` 上**已运行实例的 `frontend/dist`**，不是 dev server。**改完前端必须先 `npm run build` 再跑 e2e**，否则验的是旧产物。本轮已在此栽过一次：`TaskConclusion` 的改动第一次跑时全绿，build 后重跑才暴露基线失效。

---

## 八、改动清单

| 文件 | 改动 |
|---|---|
| `src/styles/pages.css` | 删 5 条色带规则；`align-items` 改 `stretch`；`.control-card` 转 flex 列 + `p + *` 贴底；padding 左 25→22；`.card-index` 补 `--r-sm`；`.mode-callout` 由 `border-block` 改完整描边 + 圆角；删 5 条 `.readiness-summary` 规则；`.dependency-grid` 补顶边线与 `.is-checking`；新增骨架屏样式段 |
| `src/pages/SettingsPage.tsx` | 提取 `heading` 常量供加载态复用 + 四张骨架卡；`busy` 由 `boolean` 改为按卡枚举；`put()` 加 `scope`；删 `.readiness-summary` 与 `coreChecks`；平台自检只在 failed 时列出；依赖行 ready 时只显示版本号；补 `checking` state |
| `src/pages/TasksPage.tsx` | 补 `REPAIR RECORD` kicker；`TaskConclusion` 去掉与专属版面重复的兜底分支 |
| `src/pages/ProvidersPage.tsx` | h1 改「反馈源」；右上按钮条件渲染 |
| `src/pages/ProjectsPage.tsx` | 同步提示文案中的页面名 |
| `playwright.config.ts` | `maxDiffPixelRatio` 0.006 → 0.0005，`threshold` 0.25 → 0.2 |
| `e2e/phase0.spec.ts` | 修 4 处过期文案断言（「工单反馈来源」→「反馈源」、「接入工单反馈来源」→「接入反馈源」） |
| `e2e/phase0.spec.ts-snapshots/` | 全部 7 张基线在新阈值下重新生成 |

---

## 九、本轮验收清单

```
□ 设置页四张卡无左侧彩色竖带
□ .card-index 圆角为 --r-sm（7px），与 .provider-monogram 同族
□ .mode-callout 是完整描边 + 圆角，不是 border-block 横条
□ .control-grid 的 align-items 是 stretch
□ 同一行两张卡等高，主控件底边落在同一条水平线上
□ 03 卡的加减器 / 刻度条 / 容量尺三块之间无被拉开的空隙
□ 暗色下设置页四张卡与其他页面卡片是同一种形状语言
□ 四个页面的标题区都是 kicker → h1，无一缺失
□ 零来源时，反馈源页标题区不渲染「添加反馈源」按钮
□ 反馈源页 h1 与导航项同名（「反馈源」）
□ no_change 抽屉只有一块结论面板，不与 NoChangeSurface 复读
□ 失败任务有真实 conclusion 时，AI 结论面板照常渲染
□ 切到设置页，标题区在骨架态 / settings 到达 / readiness 到达三个阶段几何一致
□ 改并发数量时，模式按钮与模型下拉的 disabled 保持 false
□ 运行环境卡不出现「N/N 项核心正常」这类不可核对的计数
□ 依赖行 ready 时只显示「版本 x.y.z」，不出现裸 binding id 或 executableBindings 引用
□ 「重新检查」期间保留上一份结果，卡片高度不塌
□ playwright 的 maxDiffPixelRatio 不高于 0.0005
□ .no-change-mark 仍为直角（印章语义，不受本轮影响）
□ .secret-boundary-note 仍然零明文占位
□ failureTitle / failureHint 文案一字未改
□ npm run typecheck / test:browser / test:e2e 全绿（e2e 6 条）
```

---

**上一册** ← [15 · 第三轮：合并为单一账本](../03-single-ledger/15-round3-single-list.md)
**返回** → [README](../README.md)
