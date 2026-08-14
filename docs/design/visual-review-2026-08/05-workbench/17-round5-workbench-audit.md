# 第五轮 · 上册：流水线弹窗的整体诊断

本轮只审「新增 / 编辑流水线」这一个四步弹窗。用户的三条精准反馈都落在这里：

1. 「表单和下面的 3 个单选贴这么近吗」
2. 「这里的方感也还在，你刚刚查的方感只有设置界面不够全面」
3. 「展开【修改与检查规则】我去乱七八糟，大字小字混在一起，这真的是设计排版过的吗」

三条全部属实，且都能量化。取证方式是 Playwright 打开 `127.0.0.1:9522` 上的真实产物，注入 `e2e/fixtures/visual-control-tower.json`，走「编辑配置」入口逐步截图并读取 computed style。

下册（[18 册](18-round5-workbench-fixes.md)）是具体改动与验收。

---

## 1 · 用户反馈一：0px 组间距

### 1.1 量化

第 4 步「最终交付」的纵向节奏，改前实测：

| 从 | 到 | 间隙 |
|---|---|---|
| `step-intro` | `delivery-log-config` | 26px |
| `delivery-log-config` | `action-choice-grid` | **0px** |
| `action-choice-grid` | `action-config-stack` | 17px |
| `action-config-stack` | `project-policy` | 30px |

`.action-choice-grid` 根本没写 `margin-top`。这不是「间距调得太小」，是漏了一条声明。

### 1.2 为什么 0px 是语义错误而不只是难看

`.delivery-log-config` 当时的样式是：

```css
border: 1px solid var(--line-strong);          /* 比周围重的实心描边 */
background: color-mix(... var(--signal-soft) ...);  /* 有底色 */
border-left: 3px solid var(--signal);          /* 还有一条彩色左边线 */
```

一块「实心描边 + 有底色 + 带强调左边线」的区域，正下方零间隙贴着三张卡片 —— 这在任何视觉语法里都读作**父子关系**：这三张卡是这个日志块的三个子选项。

实际语义完全相反：交付日志是三个出口**共用**的配置，三张出口卡是并列的独立选择。间距把语义讲反了。

修法不是「加点间距」，是让组间距明显大于组内间距：三张卡之间是 `gap: 10px`，那么组与组之间给 26px（2.6 倍），才能读作两块并列内容而非一块。

---

## 2 · 用户反馈二：方感不止设置页

用户这句「你刚刚查的方感只有设置界面不够全面」是对的，第四轮的判断偏窄了。

### 2.1 普查结果

对弹窗内所有 `width>40 && height>12` 的元素读 `borderWidth` 四边，筛出「有边但不足四边」的：

| 元素 | 四边（上/右/下/左） | 圆角 |
|---|---|---|
| `project-grid` | 1/0/1/0 | 0 |
| `action-config-stack` | 1/0/1/0 | 0 |
| `source-separation` | 1/0/1/0 | 0 |
| `detection-report` | 1/0/1/0 | 0 |
| `project-policy` | 1/0/0/0 | 0 |
| `workbench-actions` | 1/0/0/0 | 0 |
| ...（弹窗内共 13 处） | | |

`border-block`（只画上下边线）不是设置页的个例，是这个代码库的**系统性习惯**。第四轮把它当成局部问题处理，所以「改完了方感还在」。

### 2.2 更严重的一层：彩色左边线在这里原样存活

第四轮刚在设置页废止了「3px 彩色左边线做分类」这个模式，理由写在 16 册：状态色只服务真实状态语义，不做装饰性借用。

但弹窗里有四处同款，一处没动：

| 元素 | 左边线 | 是否真实状态 |
|---|---|---|
| `.delivery-log-config` | `3px solid var(--signal)` | ❌ 装饰 |
| `.source-separation div` | `3px solid var(--line-strong)` | ❌ 装饰 |
| `.detection-report.ready` | `3px solid var(--success)` | ✅ 是状态，但表达方式不对 |
| `.detection-report.failed` | `3px solid var(--failed)` | ✅ 同上 |
| `.soft-warning` | `3px solid var(--warning)` | ✅ 同上 |

后三者虽然承载真实状态，但都叠在「只有上下边线」的盒子上：一块内容左边一条粗色线、右边完全敞开，读起来是「被切了一半的卡」，不是「一张有状态的卡」。

### 2.3 判定标准

不是「所有 `border-block` 都要改」。分界线是**这块内容是不是一个独立对象**：

- 是独立对象（一张卡、一个可折叠区、一组配置）→ 必须四边收口，否则它在版面上没有边界。
- 是同一张卡内部的分隔（`remote-line` 的上边线、`action-config` 之间的下边线、`workbench-head` 的下边线）→ `border-block` 正确，它画的是「分隔」不是「边界」。

按这条线，本轮该改的是 `delivery-log-config` / `action-config-stack` / `source-separation` / `detection-report` / `project-policy` / `soft-warning` 六处；`remote-line` / `detection-checks > div` / `workbench-head` / `workbench-actions` / `project-stepper` 保持不动。

**本轮范围仅限弹窗内。** 全站其余页面的同类问题（`task-table` 等）已记录，未获授权，不在本轮改动。

---

## 3 · 用户反馈三：折叠区没有排版

### 3.1 量化：只有两级，且差距不足

展开「修改与检查规则」后，内部所有文本的字号层级实测：

| 角色 | 字号 | 字重 | 字族 |
|---|---|---|---|
| 分组标题（`h4`：允许修改哪些文件 / 完成后自动检查 / 工单接收规则） | 14px | 600 | IBM Plex Sans |
| 字段标签（可修改目录 / 禁止修改目录 / 匹配优先级…） | 12px | 500 | IBM Plex Sans |

两级之间只差 **2px 字号 + 一档字重**，同字族。在 12px 起步的密集表单里，这个差距扫过去几乎读不出「这是标题」。

于是视觉上就成了用户说的样子：一堆 12px 里混着几个 14px，大字小字轮流出现，看不出分组，也看不出层级 —— 「乱七八糟」是准确的描述。

### 3.2 为什么不能靠「把 h4 调大」解决

把 `h4` 调到 16px/18px 能拉开差距，但会引入新问题：折叠区是**附加规则**，是这一步的补充内容，它内部的标题不应该比第 3 步主标题（`step-intro h3`，18px）还抢眼，也不该跟它同级。

正确解法是换维度：不靠字号大小，靠**字族与字距**。全站已有现成的眉标语汇 —— `font: 600 10px/1 var(--font-mono)` + `letter-spacing: .1em~.16em` + `--tertiary` 色，用在 `task-table-head`、`remote-line`、`detect-placeholder`、`control-card > header small` 等 20 余处。

10px mono 大写间距眉标 与 12px sans 字段标签，字族不同、字距不同、颜色不同，**是两个物种**，一眼能断句。字号反而更小 —— 层级靠的是对比维度的数量，不是尺寸。

### 3.3 附带问题：分组之间没有分隔

眉标降到 10px 之后，单靠 `margin` 撑不出三组的边界（原本 `h4` 的 `margin: 22px 0 12px` 是为 14px 标题配的）。需要给每组补一条虚线上边线，首组不画。

### 3.4 「添加检查」按钮的重心问题

`.advanced-heading` 是「完成后自动检查」眉标 + 「添加检查」按钮的一行。按钮走全局 `.ghost.framed`，`min-height: 40px`。眉标降到 10px 后，这一行的视觉重心整个压在按钮上，眉标反倒像是按钮的附属说明。按钮需要缩到眉标量级（28px 高、11px 字）。

---

## 4 · 用户没提但同样是缺陷的两处

### 4.1 弹窗高度写死，第 1 步半屏空白、第 4 步装不下

```css
.project-workbench { height: min(800px, calc(100vh - 36px)); }
```

固定 800px。实测各步内容高度：

| 步骤 | 内容高 | 结果 |
|---|---|---|
| 01 工单反馈 | 253px | 下方 500+px 空白 |
| 02 定位资料 | 341px | 大量空白 |
| 03 修改工程 | 440px | 尚可 |
| 04 最终交付 | 686px（GitHub 工程 716px） | 需要滚动 |

一个四步向导，第 1 步空掉大半屏，第 4 步却装不下，两头都不对。

**注**：修法先按自适应实现，实测体验后由用户判定改回定高（取值 912px，覆盖第 4 步最坏情况）。定高不是问题，**取值取错**才是。完整取舍见 [18 册 §1](18-round5-workbench-fixes.md)。

### 4.2 折叠区展开后内容被切断，且没有任何提示

在 1440×1100 视口下展开「修改与检查规则」：`.workbench-body` 的 `scrollHeight` 961 vs `clientHeight` 605，**超出 244px**。

后果：
- 「完成后自动检查」只露出半个标题
- 「工单接收规则」整块不可见

技术上能滚动，但滚动条是浏览器细条，在这个浅色底上几乎看不见 —— 用户不知道下面还有东西。这不是「需要滚动」的问题，是「没有告知需要滚动」的问题。

### 4.3 附带发现：折叠区挂在四步之外

`<details className="project-policy">` 写在 `step === 1/2/3/4` 四个判断的**外面**，所以四步全程常驻。用户在第 4 步选交付出口时，下方仍挂着「修改与检查规则」。

这块内容的语义是「在这个工程里能改什么、改完怎么验」，明确属于第 3 步「修改工程」。已核实 `stepComplete` 与 `canSave` 都不依赖折叠区内的字段，移动是安全的。

---

## 5 · 本轮不触碰的边界

评审与改动均未涉及以下内容，与 `README.md`「配置原则」一致：

- `localizationSource.path`、`modificationWorkspace.path` 与 Patch 输出目录属于 CodeFixer 服务主机路径，只存在于本机 `.local/config.json`。
- 共享默认配置与 SPEC 不写死任何开发机路径。
- 内部命令的 `executableRef`、工单登录信息的 `SecretRef` 不在日常项目 UI 暴露。
- Secret 明文独立存储，Web API 只返回 `configured` 状态；`.secret-boundary-note` 文案未改动。

本轮改动全部是 CSS 形态与一处 JSX 位置调整，不涉及任何字段、接口或存储。
