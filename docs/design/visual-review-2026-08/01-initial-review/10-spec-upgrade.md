# 10 · 规范升级主张

> 前一册（[09](09-spec-debt.md)）列的是「规范写了、实现没做」。
> 这一册相反：**规范本身需要修改或补充的地方**。
>
> 每条给出：现状原文 → 问题 → 建议改成什么 → 写进 `docs/design/design-system.md` 的哪一节。
>
> 分两类：**【改】**（现有条款需要调整）/ **【补】**（规范缺失，需要新增条款）。
> 施工时的处理顺序是：**先改规范，再按规范改实现**——否则改完实现又与规范对不上，下一次评审还得再来一遍。

---

## 1. §4.1 字体 —— 从"系统字体"改为"指定字体" 【改】

### 现状

规范 §4.1 原文只规定了字体的**类别**：

> UI 正文使用系统无衬线，保证中英混排字宽稳定。数据、代码、SHA、耗时使用等宽。

实现照做了，`styles.css` 写的是：

```css
font-family:Inter,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
```

结果是**这台机器上永远走不到 Inter**（未引入任何 `@font-face`、未引入 Google Fonts），实际渲染 = Segoe UI（拉丁）+ 微软雅黑（中文）。

### 问题

"系统无衬线"这条规范在**跨机器时不可复现**：设计师的 Mac 上是 SF Pro + 苹方，运维的 Windows 上是 Segoe UI + 雅黑，两者的字重、x-height、中西文基线全部不同。§25 要求的 visual regression baseline 在这个前提下**根本无法成立**——换台机器截图就全红。

更重要的是：§2.1 定的六个关键词里有 `engineered`、`precise`、`slightly futuristic`。Segoe UI 是**中性办公字体**，它不表达这三个词里的任何一个。字体是"死板"这一观感里占比最大的单一变量。

### 建议改成

```markdown
### 4.1 字体（修订）

三个 family，全部**本地自托管**，不依赖任何 CDN（部署环境为内网）：

| 用途 | Family | 文件 |
|---|---|---|
| 标题 / 机器数据 / 代码 / SHA / 耗时 / 编号 | **IBM Plex Mono** | `plex-mono-{400,500,600}.woff2` |
| 拉丁正文 | **IBM Plex Sans** | `plex-sans-{400,450,500,600}.woff2` |
| 中文 | **Noto Sans SC** | `noto-sans-sc-{400,500,700}.woff2`（subset） |

CSS 变量：
--font-mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace;
--font-sans: 'IBM Plex Sans', 'Noto Sans SC', system-ui, 'Microsoft YaHei', sans-serif;

`@font-face` 一律 `font-display:swap`，中文子集按 `unicode-range` 分片。
禁止引用 Google Fonts / jsDelivr 等外部字体源。
```

### 为什么是 IBM Plex

1. **它就是为工业/工程语境画的**——IBM 的设计语言 Carbon 的字体，OpenType 里带 slashed zero，`0` 与 `O` 天然区分（SHA、工单号、路径场景刚需）。
2. **Mono 与 Sans 同源**，两者字宽和骨架一致，混排不会像 Consolas + 雅黑那样割裂。
3. Mono 的字形有轻微的**机械制图感**（`l` 的弯钩、`i` 的方点），这正是 §2.1 想要的 `engineered` + `slightly futuristic`，而不需要任何霓虹或渐变。
4. 开源（OFL），可自托管，不涉及授权。
5. 与 Noto Sans SC 的中文字面高度接近，中英混排基线稳定——这一点解决了原 §4.1 想要但没做到的"中英混排字宽稳定"。

> 备选：若嫌 Plex Mono 的字宽偏窄，可换 **JetBrains Mono**（更宽、更适合长 diff）。但标题用 JetBrains 略显软，建议只在 §14 Diff 视图里局部替换。

### 配套改动

规范 §4.1 还有一条：

> 标题不用过度粗黑，通过空间和层级建立权重。

实现是 `h1{font-weight:750;letter-spacing:-.045em}`——**两条都违反**。`-.045em` 的负字距在中文上会让相邻字粘连。建议在规范里把这条写死：

```markdown
- 中文文本一律 `letter-spacing:0`，负字距只允许用于纯拉丁的 display 级标题，且不超过 `-0.01em`。
- 字重上限 650。超过 650 的粗体在 CJK 上会糊。
```

---

## 2. §5.2 App Shell —— 放弃 icon rail，改为固定 200px 【改】

### 现状

规范 §5.2 原文：

> 常态 72px icon rail，hover/focus 显 label，可固定展开 216px。

实现做的是固定 176px 常显 label——**没有照规范做**。但本评审认为：**这里应该改规范，不是改实现。**

### 问题

72px icon rail 的前提是「导航项的图标语义足够自明」。这个产品的五个导航项是：

| 导航 | 图标能自明吗 |
|---|---|
| 首页 | ✅ 房子 |
| 任务 | ◐ 列表？清单？和"项目"容易混 |
| 项目 | ◐ 文件夹？和"任务"容易混 |
| 工单来源 | ❌ **没有任何通用图标表达"Redmine/TAPD 接入点"** |
| 设置 | ✅ 齿轮 |

五项里两项图标不自明、一项完全不可图标化。72px rail 会让用户每次都要 hover 试探——这与 §2.1 的 `precise` 相悖。

另外 72px rail 的常见收益是「省出内容宽度」。但这个产品的内容区已经是 `max-width:1580px` 且在 1440 屏上有留白，**省下来的 104px 没有去处**。收益为零，成本为二。

### 建议改成

```markdown
### 5.2 App Shell（修订）

侧栏固定 200px，常显中文 label，不折叠。理由：本产品导航项中「工单来源」等
概念无自明图标，icon-only 会造成反复 hover 试探。

栅格：
- ≥1440px：侧栏 200px + 内容 max 1440px，居中
- 1280–1439px：侧栏 200px + 内容流式
- 1024–1279px：侧栏收为 64px icon rail（此时用户已在小屏，接受 hover 成本）
- <1024px：侧栏抽屉化，顶部汉堡触发
- <720px：底部 tabbar，**内容区 padding-bottom 必须 ≥ tabbar 高 + 16px**

侧栏底部固定一条系统状态区（轮询心跳 + 上次检查时间 + 版本号），
它是「系统活着」的唯一常驻指示。
```

> 最后一条是新增的：现在的侧栏底部是空的，而首页空态又需要"上次检查 18 秒前"这个信息（§19）。把它放在侧栏底部，五个页面都能看到，比只放在首页空态更合理。

---

## 3. §3.3 状态色 —— 拆成"图形级 / 文字级"两级 【改】

### 现状

规范 §3.3 给了七个状态色，实现**逐位照抄**了（这是全站落地最好的一处）：

```
success #36a26b · no_change #3c8c91 · warning #d69a32 · failed #d94a55
reconcile #7d68c7 · side #c258a0 · queued（中性灰）
```

### 问题

这七个值是按**图形色**选的——它们在白底上的对比度约 3.0–3.4:1，正好满足 WCAG 对**非文字元素**的 3:1 要求。作为圆点、边框、进度条填充，完全合格。

但实现把它们**直接当文字色用**了，全站 20+ 处：

```css
.error-note{color:var(--failed)}
.readiness-badge.ready{color:var(--success)}
.delivery-status.partial{color:var(--warning)}
.stage-status{color:var(--nochange)}
...
```

文字要求 **4.5:1**。`#d94a55` 白底 3.4:1、`#36a26b` 白底 3.2:1、`#d69a32` 白底仅 **2.3:1**——橙黄色文字是全站最不可读的一处，而它恰好用在 `partial_delivery` 这种需要被看见的状态上。

规范 §3.4 已经写了「正文和关键状态文本必须满足可读对比」，但**没有给出满足它的色值**，导致实现只能拿图形色顶上。这是规范的缺口，不是实现的疏忽。

### 建议改成

在 §3.3 后面插入一节：

```markdown
### 3.3b 状态色的三层用法

每个状态色提供三个变体。**用途决定用哪个，不允许混用。**

| 层 | 变量 | 对比度要求 | 用在 |
|---|---|---|---|
| 图形 | `--st-{name}` | ≥3:1（白底/深底） | 圆点、边框、图标描边、进度填充、rail 节点 |
| 文字 | `--st-{name}-text` | ≥4.5:1 | 任何 `color:` 属性 |
| 底色 | `--st-{name}-soft` | — | chip 背景、行高亮、卡片左栏底 |

Light：
--st-success:#36a26b   --st-success-text:#1f7048   --st-success-soft:#e9f5ef
--st-nochange:#3c8c91  --st-nochange-text:#2a6367  --st-nochange-soft:#e8f2f3
--st-warning:#d69a32   --st-warning-text:#8a5c12   --st-warning-soft:#fbf3e3
--st-failed:#d94a55    --st-failed-text:#a92b36    --st-failed-soft:#fbecee
--st-reconcile:#7d68c7 --st-reconcile-text:#584399 --st-reconcile-soft:#efecf9
--st-side:#c258a0      --st-side-text:#8f3771      --st-side-soft:#f9ecf5
--st-queued:#858d87    --st-queued-text:#5b625d    --st-queued-soft:#f0f2ef

Dark：图形色整体提亮降饱和；`-text` 别名到图形色（深底上图形色已达 4.5:1）；
`-soft` 改为同色相深色调（如 `--st-success-soft:#122a20`）。
完整值见评审 [02 §3.2]。

**审查规则**：CSS 中出现 `color:var(--st-*)`（非 `-text` 后缀）即为违规。
```

### 为什么不直接把七个主色调暗

因为**图形场景会受损**。`#1f7048` 作为 rail 节点填充色在浅灰轨道上会显得脏、闷；`#36a26b` 才是对的。把两个需求塞进一个变量，必然牺牲其中一个。

---

## 4. §4.2 Type Scale —— 从 8 档补到 12 档 【改】

### 现状

规范 §4.2 给了八档：display / title / section / body / body-strong / caption / micro / mono。

实现用了 **17 种字号**，其中 `9px` 出现 26 次、`10px` 33 次、`11px` 27 次，而规范 body 级的 `14px` **只出现 1 次**。

### 问题

不是实现不守规矩，是**档位之间跳太大**：

- `caption 12px` 与 `micro 11px` 之间只差 1px，但从 `body 14px` 到 `caption 12px` 差 2px，遇到"比正文小一点但不到 caption"的场景（任务行副标题、卡片 meta）无档可用 → 于是写了 13px。
- mono 只有一档 `12px`。但 rail 节点上的耗时（需要 10–11px）、diff 里的代码（需要 12–13px）、卡片角标编号（需要 10px）都是 mono → 于是写了 9/10/11/13px 各一堆。
- 完全没有"kicker/eyebrow"档（那种全大写、宽字距的小标签），而这个界面上到处都是这种东西（`READINESS`、`DELIVERY`、卡片角标）→ 只能各自硬编码。

### 建议改成

保留原八档的**值不动**（避免推翻已对齐的部分），新增四档：

```markdown
### 4.2 Type Scale（修订：8 档 → 12 档）

原有八档保持不变：
--t-display     650 32px/38px  mono   页面主数字、大标题
--t-title       650 24px/30px  mono   页面标题
--t-section     650 16px/22px  sans   区块标题
--t-body        450 14px/20px  sans   正文
--t-body-strong 600 14px/20px  sans   正文强调
--t-caption     500 12px/17px  sans   辅助说明
--t-micro       550 11px/15px  sans   最小可用文字
--t-mono        500 12px/18px  mono   数据、SHA、路径

新增四档：
--t-subhead     550 15px/21px  sans   卡片标题、任务标题（介于 section 与 body）
--t-body-sm     450 13px/19px  sans   列表副行、表格单元
--t-mono-sm     500 11px/16px  mono   rail 耗时、chip 内数据、内联编号
--t-kicker      600 10px/12px  mono   全大写标签，配 letter-spacing:.08em

**下限**：`--t-kicker` 的 10px 是全站最小值。禁止出现 9px 及以下。
现有 26 处 9px、2 处 8px 全部上调到 `--t-kicker` 或 `--t-micro`。

**使用方式**：一律 `font:var(--t-body)` 简写，不允许单独写 `font-size`。
这样字号与字重、行高绑死，无法只改其一。
```

> `font:` 简写这一条是关键——它从机制上杜绝了"只改字号不改行高"导致的档位漂移。缺点是会重置 `font-family`，所以每档 token 里必须带 family（上表已带）。

### 关于标题用 mono

规范 §4.1 只规定了"数据、代码、SHA、耗时用等宽"，**没规定标题**。本评审主张 display / title 两档改用 mono，属于**新增主张**，理由：

- 页面标题用 mono 是"仪表/铭牌"语感的最低成本实现，比任何装饰元素都有效
- 只影响两档、约 6 个位置，风险可控
- 字号字重完全不动，只换 family，视觉回归可控

如果不认同，把这两档的 family 换回 sans 即可，其余 10 档不受影响。

---

## 5. §16 圆角 —— 四档改三档，并加禁令 【改】

### 现状

规范 §16 给四档 `4 / 7 / 10 / 14`，并写了「避免满屏圆角卡片」「不把每一行包进独立胶囊」。

实现有 **16 种像素值** + `50%` + `999px`，五处"每行一个胶囊"。

### 问题

四档里 `7px` 和 `10px` 差异太小，**肉眼无法分辨**，所以施工时的选择变成随机——9px、10px、12px 都"看起来差不多"，于是全都出现了。档位如果不能被眼睛区分，就不构成约束。

另外 `14px` 这一档在 1600px 宽的密集数据界面上偏大。规范说它只给 Dialog/浮层/模式控制器，但实现拿它去做了卡片（`.project-card{16px}`）——因为**没有"卡片该用哪档"的明确规定**。

### 建议改成

```markdown
### 16 圆角（修订：4 档 → 3 档）

--r-sharp:  2px   输入框、chip、表格单元、按钮 —— 默认档，绝大多数元素用它
--r-card:   6px   卡片、面板、代码块
--r-modal: 10px   Dialog、抽屉、Toast、Popover
--r-dot:   50%    仅状态圆点与 rail 节点

**禁令（硬性）**：
1. 禁止 `border-radius:999px` / `9999px` / `pill`。状态标识用 `--r-sharp` 的方形 chip。
2. 列表行禁止有 `border-radius`。行与行之间用 `border-bottom:1px solid var(--line)` 分隔。
3. 一个视图内，圆角档位不超过 2 种。

理由：本产品的视觉概念是「工业修复账本」。胶囊形是消费级 SaaS 的标记，
方形+细线是工程记录的标记。这不是审美偏好，是与 §2 视觉概念的一致性要求。
```

档位从 4 减到 3，是因为**能被眼睛分辨的圆角档位本来就只有三个量级**：几乎没有 / 明显有 / 很圆。

---

## 6. §19 空态 —— 从"文案示例"升级为"五类空态" 【改】

### 现状

规范 §19 给了三段文案示例，实现用**同一个** `.empty-state` 盒子承载了全部五种情况。

### 问题

规范只给了文案，没给分类。"没有数据"和"出错了"和"你还没配置"在产品语义上是三件完全不同的事，但都长一样，用户无法区分「系统正常但闲着」与「系统坏了」。

### 建议改成

```markdown
### 19 空态（修订：定义五类）

| 类 | 触发 | 视觉 | 是否带 CTA |
|---|---|---|---|
| `standby` | 有配置，但当前无数据 | 心跳点 + 「轮询正常 · 上次检查 N 秒前」 | 否 |
| `unconfigured` | 尚未配置来源/项目 | 45° 斜纹底 + 主 CTA | 是，主按钮 |
| `filtered` | 筛选后无结果 | 极简一行 + 「清除筛选」 | 是，文字按钮 |
| `error` | 请求失败 | 左侧 3px failed 竖条 + 错误码 + 「重试」 | 是，重试 |
| `forbidden` | 权限/边界不允许 | 虚线框 + 说明，无 CTA | 否 |

**`standby` 与 `error` 必须视觉可区分**——这是本条最重要的要求。
现在两者都是灰字居中，用户看到"暂无数据"无法判断系统是待命还是崩了。

`standby` 文案模板：`暂无{对象}` / `{来源}轮询正常 · 上次检查 {N} 秒前`
`error` 文案模板：`无法加载{对象}` / `{HTTP码} {简短原因}` / `[重试]`
```

---

## 7. §21 Toast —— 补"生命周期"规定 【改】

### 现状

规范 §21 只规定了 Toast 的**适用范围**（瞬时反馈；失败类不允许只靠 Toast），没规定它**怎么消失**。

实现的 Toast 不会自动消失，只能手动点掉——这与"瞬时"矛盾。

### 建议改成

```markdown
### 21 Toast（补充生命周期）

| 类型 | 停留 | 可手动关闭 | 视觉 |
|---|---|---|---|
| success | 3200ms 自动消失 | 是 | 左侧 3px `--st-success` 竖条 |
| info | 4000ms 自动消失 | 是 | 左侧 3px `--signal` 竖条 |
| warning | 6000ms 自动消失 | 是 | 左侧 3px `--st-warning` 竖条 |
| error | **不自动消失** | 是 | 左侧 3px `--st-failed` 竖条 |

- 底色一律 `--surface-raised`，不使用反色块（反色块在暗色下会变成刺眼白块）。
- 鼠标 hover 时暂停倒计时。
- 同时最多 3 条，超出时最早一条立即退出。
- 相同 message 在 2 秒内重复触发，合并为一条并显示 `×N`。
```

---

## 8. §22 Dialog —— 按钮文案规则 【改】

### 现状

规范写了「Dialog 必须说出结果，不写"确定吗？"」，并给了标题+描述的示例。实现的标题描述基本合格，但**按钮文字是"确认"**。

### 问题

规范管住了标题和正文，没管按钮。而用户在确认框里最常见的行为是**不读正文直接看按钮**。"确认 / 取消"这一组按钮不携带任何信息。

### 建议改成

```markdown
### 22 Dialog（补充按钮规则）

- 主按钮文案必须是**动词短语，说出即将发生的事**，禁止"确认"/"是"/"OK"。
  - ✅ `切换并排队 3 个任务` / `终止 Repair Agent` / `删除 2 个本地产物`
  - ❌ `确认` / `确定` / `是的，继续`
- 次按钮用 `取消`（这个可以是通用词，因为它的语义是"什么都不发生"）。
- 破坏性操作：主按钮用 `--st-failed` 描边（不用实心红——实心红会诱导点击）。
- 确认框必须列出**受影响的具体数量**，不能只说"部分任务"。
  数量为 0 时不弹确认框，直接执行。
```

最后一条尤其重要：现在切换到全自动会弹确认框，但如果队列是空的，这个确认框**没有任何意义**却仍然拦一次。

---

## 9. 【补】新增 §15b：Motion Token 表

### 缺口

规范 §15 只写了「定义 duration / easing token」和「signal 动效 1200–1800ms」，**没有给出具体的表**。结果实现里全是字面量 `.18s` / `.15s` / `1.8s`。

### 建议新增

```markdown
### 15b Motion Token（新增）

--d-instant:   80ms   按下位移、开关拨动
--d-fast:     140ms   hover / focus / 颜色变化
--d-standard: 220ms   遮罩淡入、下划线滑动、skeleton 浮现
--d-emphasis: 360ms   模态上浮、抽屉滑入、主题切换
--d-signal:  1600ms   循环信号（rail 呼吸）

--e-standard: cubic-bezier(.2,.8,.2,1)    进入、位移（快出慢收）
--e-exit:     cubic-bezier(.4,0,1,1)      退出（慢出快收）
--e-signal:   cubic-bezier(.45,0,.55,1)   循环（对称，无起止感）

**规则：CSS 中出现字面时长（如 `.18s`）即为违规。**
```

---

## 10. 【补】新增 §23b：reduced-motion 的"静态替代"原则

### 缺口

规范 §23 只写了一句「reduced motion」，§6.4 写了「`prefers-reduced-motion` 改静态强调」。这个措辞是对的，但太简略，容易被实现成"一刀切关掉全部动画"。

而有些动效是**唯一的状态载体**——比如 rail 上的呼吸环是"这个阶段正在跑"的唯一视觉线索，关掉之后 running 与 queued 就长得一样了。

### 建议新增

```markdown
### 23b reduced-motion（新增）

`prefers-reduced-motion:reduce` 的语义是"减少运动"，**不是"删除信息"**。

处理分两层：

1. **全局兜底**：所有 animation / transition 压到 0.001ms。
2. **信息性动效必须提供静态替代**——凡是某个状态的**唯一**视觉载体，
   不允许直接关闭，必须给出等效的静态形态：

| 动效 | reduce 时的静态替代 |
|---|---|
| rail running 呼吸环 | 保留环，固定在 `scale(1)`、`opacity:.5` |
| 轨道扫描光 | 改为该段整体半透明填充 |
| 轮询心跳点 | 改为常亮 |
| spinner | **放慢至 1.8s，不停止**（停止的 spinner 意味着"卡住了"） |

审查方法：开启系统的"减少动态效果"后，逐张对照 §25 的 baseline，
确认每个状态仍然可以**仅凭静态形态**区分。
```

---

## 11. 【补】新增 §12b：配置边界的视觉表达（BoundaryNote）

### 缺口

`README.md` 的「配置原则」定了四条硬边界：

- 本机路径存在 `.local/config.json`，共享配置与 SPEC 不写死开发机路径
- 内部命令用 `executableRef`
- 工单登录信息用 `SecretRef`
- Secret 明文独立存储，Web API 只返回 `configured` 状态

这些边界在**代码层**是清楚的，但在 **UI 层完全没有视觉表达**。用户看到设置页的路径输入框，不知道这个值只对本机有效；看到 Secret 字段显示"已配置"，不知道为什么看不到明文。

规范全篇 28 章**没有任何一节涉及这个**。这是规范最大的一处缺口——它是这个产品**区别于普通 CRUD 后台的核心约束**，却在设计语言里不存在。

### 建议新增

```markdown
### 12b 边界提示（BoundaryNote）（新增）

用于表达"这是系统的规则，不是你的数据"。视觉上必须与普通说明文字明确区分。

统一形态：**虚线左边框 + 无背景 + `--t-caption`**。
虚线是关键——它在整个设计语言里被保留为"这是约束，不是内容"的唯一标记。

三种 kind：

| kind | 图标 | 用在 | 文案模板 |
|---|---|---|---|
| `localpath` | 主机 | 所有本机路径字段 | 该路径保存在本机 `.local/config.json`，不随配置共享；换机后需重新设置。 |
| `secret` | 钥匙 | 所有凭据字段 | 凭据以 SecretRef 引用，明文独立存储，此处仅显示配置状态。 |
| `readonly` | 锁 | executableRef 等运维引用 | 由系统配置维护，日常操作无需修改。 |

**规则**：
- 凡是写入 `.local/config.json` 的字段，**必须**带 `localpath` 提示。
- 凡是 SecretRef 字段，**必须**带 `secret` 提示，且**禁止**渲染任何形式的明文占位
  （包括 `••••••`——圆点会让用户以为有值可取回）。状态只用 `已配置` / `未配置`。
- BoundaryNote 不占用主视觉权重，不使用状态色，只用 `--text-tertiary`。
```

> 这一条同时约束了实现和规范：它把 README 里的工程边界翻译成了设计语言，使得"边界"这件事在 UI 上**可被一眼识别**而不需要读文档。

---

## 12. 【补】§27 组件清单补 9 个

规范 §27 列了 14 primitives + 9 patterns。本评审在逐页审查中发现有 9 个反复出现、但清单里没有的组件——它们现在全部以"复制粘贴的 JSX + 一坨 CSS"形式散落在各页。

```markdown
### 27 Phase 0 组件清单（补充）

Design primitives 补 5 个：
| Field | label + control + hint + error 的组合，负责 htmlFor 关联与错误态 |
| ModalShell | 遮罩 + 焦点陷阱 + Esc + 锁 body 滚动 + 焦点恢复。所有 Dialog 必须基于它 |
| Spinner | 三尺寸（12/16/20），配 loading caption |
| EmptyState | 承载 §19 的五个 kind |
| StatusChip | 承载 §3.3b 的七个状态 × 三种密度 |

Product patterns 补 4 个：
| BoundaryNote | §12b 的三个 kind |
| CapacityMeter | 并发上限的格子指示（N 格，亮起的是运行中） |
| PollHeartbeat | 侧栏底部的轮询心跳 + 上次检查时间 |
| RepairLoopBand | §6.3 要求的 loop 表达，主轨道下方的折返带 |
```

---

## 13. 【补】§25 baseline 补 fixtures 要求

### 缺口

§25 列了 11 个 golden baseline，其中三个（`task-detail-repair-loop`、`task-detail-partial-delivery`、`project-preflight-failed`）**依赖真实运行时才可能出现的状态**。如果等真实数据，这三张永远截不到。

本次评审的截图矩阵用 Playwright `page.route()` 拦截 API 注入 mock，成功截到了 `no_change`、`failed`、`mode-confirm` 等状态。这个方法应该写进规范。

### 建议新增

```markdown
### 25b Baseline 采集方式（新增）

11 个 baseline 中，凡是依赖特定运行时状态的，一律通过 **API mock** 采集，
不等待真实数据：

- 在 `frontend/tests/fixtures/` 下为每个 baseline 准备一份 JSON 响应
- Playwright 用 `page.route('**/api/**', …)` 注入
- 每个 baseline 同时采集 light / dark 两张
- 分辨率固定 1440×900；另对 dashboard / tasks 两页额外采集 1280 / 1024 / 420 三档

**fixtures 是设计资产，与组件同期提交**——Phase 0 完成的判据之一是
「11 个 baseline 全部可截出」，而不是「组件写完了」。
```

---

## 14. 【补】新增 §4.4：中文排版规则

### 缺口

规范全篇是按英文界面的习惯写的（type scale、letter-spacing、tabular-nums），但这个产品**界面全中文**。中文排版有几条与拉丁完全不同的规则，规范一条都没写，导致实现出现了 `letter-spacing:-.045em` 这种在中文上明确有害的写法。

### 建议新增

```markdown
### 4.4 中文排版（新增）

1. **字距**：中文一律 `letter-spacing:0`。负字距禁止。
   `--t-kicker` 的正字距（`.08em`）只用于纯拉丁的全大写标签。
2. **字重**：不超过 650。CJK 字形笔画密集，700+ 在小字号下会糊成黑块。
   强调用颜色或底色，不用更粗的字重。
3. **行高**：中文行高比拉丁需要更大。正文 `20px/14px = 1.43` 偏紧，
   建议中文段落（连续 2 行以上）用 1.6。单行 label 保持 1.43。
4. **中英混排**：不手动插空格（增加维护成本且容易漏）。
   依赖 `--font-sans` 的 fallback 顺序保证字面高度一致即可。
5. **标点**：全角标点不加额外间距。**句尾禁止出现半角句号**（`.` vs `。`）。
6. **数字与单位**：数字用 mono + `tabular-nums`，单位用 sans。
   `43<span class="unit">秒</span>` 而不是整串都用 mono——
   mono 的中文会 fallback 到别的字体，字宽反而不齐。
```

第 6 条是实现里已经踩到的坑：`.stage-meta` 整段用 mono，里面的"秒"字实际 fallback 到雅黑，导致每个 stage 的 meta 宽度不一致。

---

## 15. 汇总：规范改动清单

给 codex 或后续施工者的 checklist——**这些是改 `docs/design/design-system.md` 本身**：

- [ ] §4.1 改：指定 IBM Plex Mono / Plex Sans / Noto Sans SC，本地自托管，禁 CDN
- [ ] §4.1 补：字重上限 650、中文禁负字距
- [ ] §4.2 改：8 档 → 12 档，新增 subhead / body-sm / mono-sm / kicker；下限 10px；强制 `font:` 简写
- [ ] §4.4 新增：中文排版六条
- [ ] §3.3b 新增：状态色三层（graphic / text / soft），给全部 21 个值
- [ ] §5.2 改：放弃 72px icon rail，固定 200px + 四档响应式 + 侧栏底部状态区
- [ ] §12b 新增：BoundaryNote 三 kind，及 secret 字段禁明文占位的硬性规则
- [ ] §15b 新增：Motion Token 表，禁字面时长
- [ ] §16 改：4 档 → 3 档（2/6/10 + dot），三条禁令
- [ ] §19 改：五类空态定义，standby 与 error 必须可区分
- [ ] §21 补：Toast 四类生命周期
- [ ] §22 补：按钮动词短语规则、数量为 0 不弹框
- [ ] §23b 新增：reduced-motion 静态替代原则 + 四条对照
- [ ] §25b 新增：baseline 用 API mock 采集，fixtures 与组件同期交付
- [ ] §27 补：primitives +5、patterns +4

改完规范后，实现侧的施工顺序见 [11-roadmap.md](11-roadmap.md)。
