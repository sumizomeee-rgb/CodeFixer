# 第六轮 · 上册：反馈源页的形态诊断

用户这一轮的问题很短：「还有反馈源设置这边的，是不是也是方的，这个页签下面的界面你有看过吗」

两问都成立，且反馈源页的方感比之前任何一处都彻底。取证方式与前几轮一致：Playwright 打开 `127.0.0.1:9522` 的真实产物，注入 `e2e/fixtures/visual-control-tower.json`，读 computed style 并逐态截图。

下册（[20 册](20-round6-sources-fixes.md)）是改动与验收。

---

## 1 · 「是不是也是方的」——三层全方

实测三层结构：

| 层 | 边框（上/右/下/左） | 圆角 | 底色 |
|---|---|---|---|
| `.provider-grid` 列表壳 | **1/0/1/0** | **0px** | `--surface` |
| `.provider-channel` 单条 | **0/0/1/0** | **0px** | 透明 |
| `.provider-channel::before` | — | — | **4px 实色左边条** |

三层没有一层是收口的。列表左右两端直接切在版面上；每条记录没有自己的边界，靠 1px 分隔线断开。

### 1.1 根因：类名是卡，实现是表格行

```tsx
<article className="provider-card provider-channel" data-health={health}>
```

类名写 `card`，内容密度也是卡的规格 —— 46px 徽标 + 4 行文字（眉标 / 名称 / 描述 / 状态）+ 2 个动作按钮，单条实测高 **129px**。

但样式是表格行的语汇：无边框、无圆角、无底色、靠分隔线。

两边都不彻底。从任务页、设置页那些圆角卡切过来，到这里突然变成一张表 —— 用户感受到的「方」就是这个断裂。

### 1.2 4px 色带：前两轮废止模式的最后据点

```css
.provider-channel::before { position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--warning); }
.provider-channel[data-health="ready"]::before { background: var(--success); }
.provider-channel[data-health="failed"]::before { background: var(--failed); }
.provider-channel[data-health="inactive"]::before { background: var(--line-strong); }
```

第四轮在设置页废止「彩色左边条做分类」，第五轮在弹窗内收掉六处同款，这里不但活着，还比那些地方粗（4px vs 3px）。

更糟的是它的位置效应：因为列表壳**没有左边框**，这条色带事实上成了整个列表的左边线。它既是唯一的左侧收口，又是彩色的 —— 所以视觉上格外扎眼，也是这一页方感最重的单一来源。

### 1.3 同一个 health 讲了三遍

实测一张 `ready` 卡上表达连接状态的载体：

| 载体 | 值 |
|---|---|
| `::before` 4px 色带 | `rgb(39, 130, 90)` |
| `.provider-meta i` 圆点 | `rgb(39, 130, 90)` |
| `.provider-meta span` 文字 | 「连接正常」 |
| `data-health` 属性 | `ready` |

色带和圆点是**同一个色值**。加上文字，一个布尔量占了三个视觉载体。这与用户此前反复提的噪音、与第四轮删掉的彩色竖带是同一类问题。

---

## 2 · 「这个页签下面的界面」——弹窗三态

弹窗整体比列表干净：圆角 7px 齐整，`border-block` 一处都没有。问题集中在栅格和状态表达。

### 2.1 表单栅格有洞

`.form-grid` 是 `repeat(2, minmax(0,1fr))`，实测三态的 x/y 坐标：

| 形态 | 布局 | 空洞 |
|---|---|---|
| Redmine | 名称 \| 服务地址 → API Key 跨列 | 无 |
| TAPD 账密 | 名称 \| 工作区 → 登录方式 \| 账号 → 密码 \| **空** | 右下角 325px |
| TAPD Token | 名称 \| 工作区 → 登录方式 \| **空** → Token 跨列 | 中部 325px |

Token 态最明显：「登录方式」右边一个洞，下面 Token 又拉通两列，栅格节奏断成两截。

账密态的问题是语义而非空洞本身 ——「账号」和「密码」是一对凭据，却被拆成「登录方式 | 账号」「密码 | 空」的对角布局，一对字段跨了两行且不对齐。

### 2.2 编辑态整个类型区 46% 透明

编辑时类型不可改，实现是给两个按钮加 `disabled`：

```tsx
<button className={...} disabled={!!editingId} onClick={() => setType('redmine')}>
```

于是吃到全局 `base.css:22` 的 `button:disabled { opacity: .46 }`。实测两个按钮 `opacity: 0.46`。

问题在于此时这两张卡的**唯一作用是告诉你「这是个 TAPD 源」** —— 纯信息展示，不是被禁用的操作。把信息压到 46% 透明等于说「这条不重要」，而且对比度不达标。

体量也对不上：一个不可操作的身份标识，不该继续占 66px 高 × 双列的按钮规格。

### 2.3 `.secret-boundary-note` 是全站最后一处加粗左边线

```css
border: 1px solid color-mix(in srgb, var(--nochange) 32%, var(--line));
border-left-width: 3px;
```

实测边框 `1/1/1/3`。第五轮收完弹窗内六处后，这是「加粗左边线」模式在代码库里的最后一处。

它已经有底色 + 整圈同色系描边，与周围表单区分得很清楚，那条 3px 是多余的强调。

（**文案与语义不动** —— 它讲的是 Secret 存储边界，属于安全约束。）

### 2.4 高度三态 541 / 624 / 624

Redmine ↔ TAPD 差 83px。与第五轮刚修完的流水线弹窗同类，但只有两档、且是主动切换类型而非连点下一步，程度轻很多。

---

## 3 · 用户没提但是真 bug：测试连接的忙碌态串扰

`busy` 是单一字符串 state，两张卡的按钮都写 `disabled={!!busy}`：

```tsx
<button className="ghost framed" disabled={!!busy} onClick={() => void testConnection(provider.id)}>
  {busy === `test:${provider.id}` ? '测试中…' : '测试连接'}
</button>
```

文案判断用了 `busy === \`test:${id}\``（精确到这一条），但 `disabled` 用了 `!!busy`（任意忙碌）。实测点第一张的「测试连接」（mock 延迟 4s）：

| 卡 | 按钮文案 | disabled |
|---|---|---|
| 0 | 测试中… | `true` ← 对 |
| 1 | 测试连接 | `true` ← 错，它没在忙 |

第四轮刚在设置页修过同款（README 第 18 条：忙碌态按控件分组，一次保存只锁住正在操作的那一组），这里原样存在。

---

## 4 · 其余两处

### 4.1 品牌色硬编码在页面样式里

```css
.provider-monogram { color: #9c2e3d; }
.provider-monogram.tapd { color: #2f66bd; }
```

README「已明确废止或修正的建议」里有一条：「将所有第三方品牌色视为违规：修正为**收敛到令牌层并限制使用范围**」。这两个值既没进令牌层，也没有暗色主题对应值 —— 暗色下 `#2f66bd` 在 `#141817` 底上偏暗。

一屏内的色相计数：TAPD 蓝徽标 + 绿状态带 + 绿圆点 + 橙主按钮 = 四个色相，其中两个表达同一件事。

### 4.2 两个动作按钮的权重反了

「编辑」是 `.ghost`（纯文字），「测试连接」是 `.ghost.framed`（描边），`gap: 8px` 紧挨。

两个后果：
- 视觉上「编辑」像是描边按钮的标签，而不是独立动作
- 已显示「连接正常」时，测试按钮反倒是整张卡上最重的控件 —— 它是验证动作，不该常态压过编辑

（本轮只调整了间距关系，未改按钮语汇，见下册 §6 遗留。）

---

## 5 · 本轮不触碰的边界

与 `README.md`「配置原则」一致，评审与改动均未涉及：

- `localizationSource.path`、`modificationWorkspace.path` 与 Patch 输出目录属于 CodeFixer 服务主机路径，只存在于本机 `.local/config.json`。
- 共享默认配置与 SPEC 不写死任何开发机路径。
- 内部命令的 `executableRef`、工单登录信息的 `SecretRef` 不在日常项目 UI 暴露。
- Secret 明文独立存储，Web API 只返回 `configured` 状态。

反馈源页是 `SecretRef` 的主战场（`api.setSecret`、`apiKeySecretRef` / `usernameSecretRef` / `passwordSecretRef` / `tokenSecretRef`），本轮尤其关键。已核实：

- `.secret-boundary-note` 零明文占位，文案「保存后界面只知道『已配置』，无法读回真实值。」**未改动**。
- `secretPrefix` 生成逻辑、`api.setSecret` 调用顺序、`secretRequired` 校验条件均未改动。
- 改动全部是 CSS 形态、JSX 结构位置与一处 `disabled` 条件收窄，不涉及任何字段、接口或存储。
