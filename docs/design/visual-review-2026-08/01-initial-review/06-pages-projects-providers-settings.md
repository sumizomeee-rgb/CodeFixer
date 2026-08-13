# 06 · 项目页 · 项目工作台 · 来源页 · 设置页

---

## 1. 项目页 ProjectsPage（列表）

源码：`frontend/src/pages/ProjectsPage.tsx`（235 行）
截图：`03-projects-light-full` / `-light-empty` / `-dark-full` / `22-projects-md|sm|xs`

### 1.1 左侧竖栏是灰的 —— 浪费了最好的位置

```css
.project-ledger-card:before{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:var(--line)}
```

结构完全正确（这正是 [01-direction.md](01-direction.md) 主张的"账本页边栏"），但**填的是 `--line` 灰色**，三张卡的竖栏一模一样，等于没有。

**改法**——用项目的**就绪状态**着色，这是列表页唯一需要一眼扫到的信息：

```css
.project-ledger-card::before{
  content:'';position:absolute;inset:0 auto 0 0;width:3px;
  border-radius:var(--r-md) 0 0 var(--r-md);
  background:var(--st-queued)
}
.project-ledger-card[data-health="ready"]::before  {background:var(--st-success)}
.project-ledger-card[data-health="warning"]::before{background:var(--st-warning)}
.project-ledger-card[data-health="blocked"]::before{background:var(--st-failed)}
.project-ledger-card[data-enabled="0"]::before     {background:repeating-linear-gradient(180deg,var(--line-strong) 0 4px,transparent 4px 8px)}
```

停用项目用虚线竖栏——**形状而非仅颜色**区分（无障碍）。

### 1.2 按钮主次颠倒 【实现硬伤】

```css
.project-ledger-card .action-link{padding:0}
```

`.action-link` 是橙红色纯文字（`.ghost.action-link` → `color:var(--signal)` 推断自截图），「运行体检」是 `.ghost.framed` 描边按钮。

`03-projects-light-full` 里视觉权重：**「编辑配置」（橙字）> 「运行体检」（灰描边）**。

但真实使用频率与重要性相反——项目配置好之后基本不动，「运行体检」是每次改完配置、换机器、换分支后都要点的。

**改法**：

```css
/* 主动作：运行体检 —— 描边 + 主色 */
.project-ledger-card footer .primary{
  background:none;border:1px solid var(--signal-line);color:var(--signal-text);
  padding:7px 13px;border-radius:var(--r-sm);font:var(--t-micro);font-weight:600;width:auto
}
.project-ledger-card footer .primary:hover{background:var(--signal-soft);border-color:var(--signal)}
/* 次动作：编辑配置 —— 中性文字 */
.project-ledger-card .action-link{color:var(--text-secondary);font:var(--t-micro);font-weight:500;padding:0;background:none;border:0}
.project-ledger-card .action-link:hover{color:var(--text);text-decoration:underline;text-underline-offset:3px}
```

### 1.3 卡片信息组织

`03-projects-light-full` 每张卡显示：kicker + 项目名 + 一些配置摘要 + footer 两个按钮。

问题：

| # | 问题 | 改法 |
|---|---|---|
| 1 | 配置摘要是平铺的 label:value，没有分组，看不出「定位资料 / 修改工程 / 验证 / 交付」四段结构 | 改 4 段 `<dl>`，段间 1px 分隔 |
| 2 | 路径直出完整字符串（`E:\WorkProject\ClientTrunk`），长路径会撑破卡片 | `direction:rtl;text-align:left` 从中间省略，保留尾部（尾部才是有信息量的部分）；完整值放 `title` |
| 3 | `vcsKind` / `hostingKind`（git+gitlab、svn+none）没有可视化 | 加小徽章 |
| 4 | `finalActions` 数量（Patch / MR / PR）没显示 | 加交付动作 chip 行 |
| 5 | 无路由规则摘要——项目页最该回答的问题是"哪些工单会进这个项目" | 顶部加一行 `redmine-main · 全部工单` |

**路径省略的具体写法**（这个细节值得单独说，因为本产品到处是长路径）：

```css
.path-value{
  display:block;font:var(--t-mono-sm);color:var(--text-secondary);
  direction:rtl;text-align:left;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  unicode-bidi:plaintext          /* 防止 rtl 把 E:\ 的顺序搞乱 */
}
```

效果：`E:\WorkProject\ClientTrunk` 太长时显示 `…\WorkProject\ClientTrunk` 而不是 `E:\WorkProje…`。

> ⚠️ **边界注意**：这些路径按 `README.md`「配置原则」是**本机路径**，只应在本机 UI 显示，不进共享配置。视觉上建议加一个小的"本机"标记（同 [07 §3](07-controls-overlays.md) 的 secret 边界模式），提醒用户这个值换机器要重配。

### 1.4 空态

`03-projects-light-empty` 与任务页空态用同一个 `.empty-state`：

```css
.empty-state{border:1px dashed var(--lineStrong);border-radius:18px;background:color-mix(in srgb,var(--surface) 65%,transparent);padding:70px 30px;text-align:center}
```

70px 上下 padding 在 1600×1000 屏幕上撑出一个巨大空盒。而且**项目页空态是新用户的第一站**，它应该是引导，不是"这里没东西"。

**改法**：项目页空态用**三步引导**替代通用空态：

```tsx
<div className="onboard-state">
  <span className="kicker">开始使用</span>
  <h2>还没有配置项目</h2>
  <ol className="onboard-steps">
    <li className={hasProvider ? 'done' : ''}><b>连接工单来源</b><small>Redmine 或 TAPD</small></li>
    <li><b>建立项目</b><small>指定定位资料与修改工程</small></li>
    <li><b>运行体检</b><small>确认环境与权限就绪</small></li>
  </ol>
  <button className="primary compact" onClick={openNew}>新建项目</button>
</div>
```

### 1.5 xs 遮挡

`22-projects-xs`：第二张卡的 footer 被底部 tabbar 完全遮住 → 见 [04 §6.1](04-shell.md)。

---

## 2. 项目工作台（4 步向导）

截图：`13-project-workbench-step1` / `14-…step2` / `15-…step3` / `16-…step4` / `17-…policy`

### 2.1 stepper 缺状态

`.project-stepper` 四个按钮，当前步高亮，但：

- 已填完的步骤与未填的步骤**外观相同** → 用户不知道哪步还缺东西
- 无法看出哪步有校验错误
- 步骤间无连接线，不像流程

**改法**（复用 StageRail 的形态语言，保持全站一致）：

```css
.project-stepper{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:0;position:relative;margin-bottom:var(--s-6)}
.project-stepper::before{content:'';position:absolute;top:9px;left:12%;right:12%;height:2px;background:var(--line)}
.project-stepper button{
  position:relative;background:none;border:0;padding:0;display:grid;justify-items:center;gap:var(--s-2);
  font:var(--t-micro);color:var(--text-tertiary);z-index:1
}
.project-stepper button::before{
  content:'';width:18px;height:18px;border-radius:var(--r-dot);
  border:2px solid var(--line-strong);background:var(--canvas)
}
.project-stepper .step-done::before{background:var(--text);border-color:var(--text)}
.project-stepper .step-done{color:var(--text-secondary)}
.project-stepper .step-current::before{border-color:var(--signal);background:var(--signal);box-shadow:0 0 0 4px var(--signal-soft)}
.project-stepper .step-current{color:var(--signal-text);font-weight:650}
.project-stepper .step-error::before{border-color:var(--st-failed);background:var(--st-failed-soft)}
.project-stepper .step-error{color:var(--st-failed)}
```

### 2.2 原生 checkbox 未样式化 【缺陷 H · 高优先级实现硬伤】

`ProjectsPage.tsx:225`：

```tsx
<label className="check-row"><input type="checkbox" checked={!!editor.verification?.allowNoAutomatedTests} .../><span>这个工程暂时没有自动验证</span></label>
```

`ProjectsPage.tsx:227`：

```tsx
<label className="check-row"><input type="checkbox" checked={!!route.catchAll} .../><span>接收该来源的全部工单</span></label>
```

全量搜索三个 CSS：`input[type="checkbox"]` → **0 匹配**。

结果：渲染为**浏览器默认蓝色 ✓**（Windows Chrome 是 `#0078d4` 系）。在一个主色为 `#f4603c` 橙红、底色为暖灰的界面里，这是**最刺眼的一处**，一眼就能看出"这里没做设计"。

同样问题的还有 `<select>`（`SettingsPage.tsx:91` 当前模型、`ProvidersPage.tsx:93` 登录方式）——原生下拉箭头是系统样式。

**改法**——新建 `frontend/src/components/controls.css`（这也是 §27 primitives 的起点）：

```css
/* ---- Checkbox ---- */
.check-row{display:flex;align-items:flex-start;gap:var(--s-3);cursor:pointer;padding:var(--s-2) 0}
.check-row input[type="checkbox"]{
  appearance:none;-webkit-appearance:none;
  width:16px;height:16px;flex:none;margin:2px 0 0;
  border:1.5px solid var(--line-strong);border-radius:var(--r-xs);
  background:var(--surface);cursor:pointer;position:relative;
  transition:background-color var(--d-fast) var(--e-standard),border-color var(--d-fast) var(--e-standard)
}
.check-row input[type="checkbox"]:hover{border-color:var(--text-tertiary)}
.check-row input[type="checkbox"]:checked{background:var(--signal);border-color:var(--signal)}
.check-row input[type="checkbox"]:checked::after{
  content:'';position:absolute;left:4.5px;top:1.5px;width:4px;height:8px;
  border:solid #fff;border-width:0 2px 2px 0;transform:rotate(42deg)
}
.check-row input[type="checkbox"]:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
.check-row input[type="checkbox"]:indeterminate{background:var(--signal);border-color:var(--signal)}
.check-row input[type="checkbox"]:indeterminate::after{
  content:'';position:absolute;left:3px;top:6px;width:8px;height:2px;background:#fff;border:0;transform:none
}
.check-row>span{font:var(--t-body-sm);color:var(--text);line-height:1.5}
.check-row small{display:block;font:var(--t-caption);color:var(--text-tertiary);margin-top:2px}

/* ---- Radio ---- */
.radio-row input[type="radio"]{
  appearance:none;-webkit-appearance:none;width:16px;height:16px;flex:none;
  border:1.5px solid var(--line-strong);border-radius:var(--r-dot);background:var(--surface);position:relative
}
.radio-row input[type="radio"]:checked{border-color:var(--signal);border-width:5px}

/* ---- Select ---- */
select{
  appearance:none;-webkit-appearance:none;
  padding:8px 32px 8px 11px;
  border:1px solid var(--line);border-radius:var(--r-sm);
  background-color:var(--surface);color:var(--text);
  font:var(--t-body-sm);cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,var(--text-tertiary) 50%),
                   linear-gradient(135deg,var(--text-tertiary) 50%,transparent 50%);
  background-position:calc(100% - 16px) 52%,calc(100% - 11px) 52%;
  background-size:5px 5px,5px 5px;
  background-repeat:no-repeat
}
select:hover{border-color:var(--line-strong)}
select:focus-visible{outline:2px solid var(--signal);outline-offset:1px;border-color:var(--signal)}
select:disabled{opacity:.55;cursor:not-allowed}

/* ---- Input ---- */
input[type="text"],input[type="password"],input:not([type]),textarea{
  width:100%;padding:8px 11px;
  border:1px solid var(--line);border-radius:var(--r-sm);
  background:var(--surface);color:var(--text);font:var(--t-body-sm)
}
input::placeholder,textarea::placeholder{color:var(--text-tertiary)}
input:hover,textarea:hover{border-color:var(--line-strong)}
input:focus-visible,textarea:focus-visible{outline:2px solid var(--signal);outline-offset:1px;border-color:var(--signal)}
input:disabled{background:var(--surface-2);color:var(--text-tertiary);cursor:not-allowed}
/* 路径 / 密钥类输入用 mono */
input.mono,input[type="password"]{font-family:var(--font-mono);letter-spacing:.02em}
```

> `.current-model-control select` 现在是 `border:0;background:transparent`（`ai-picker.css`）——那是刻意的"无框内联选择"设计，可以保留，但要**补 focus-visible**，否则键盘不可用。

### 2.3 「范围与验证策略」折叠区

`17-project-workbench-policy`：`allowedRoots` / `deniedRoots` / `allowedExtensions` 三组列表，视觉上完全相同，只靠标题文字区分。

`allowedRoots` 是**放行**、`deniedRoots` 是**阻止**——语义相反，视觉必须相反：

```css
.policy-list[data-kind="allow"] .policy-item{border-left:2px solid var(--st-success);background:var(--st-success-soft)}
.policy-list[data-kind="deny"]  .policy-item{border-left:2px solid var(--st-failed); background:var(--st-failed-soft)}
.policy-item{display:flex;align-items:center;gap:var(--s-2);padding:5px 9px;font:var(--t-mono-sm);border-radius:0 var(--r-xs) var(--r-xs) 0}
```

这也直接改善 `workspace_policy_blocked` 失败码的可理解性——用户点进项目就能看到"哦，这个目录在红名单里"。

### 2.4 向导底部动作条

`.workbench-actions .primary{min-width:104px}`。问题：

- 「上一步 / 下一步 / 保存」三个按钮在 step1 和 step4 显示逻辑不同，但按钮位置会跳
- 无"未保存更改"提示——切走会丢

**改法**：固定三栏 `[上一步] [进度文字] [下一步/保存]`，位置永不跳；有未保存修改时在中间显示 `● 有未保存的更改`（用 `--st-warning`）。

---

## 3. 来源页 ProvidersPage

源码：`frontend/src/pages/ProvidersPage.tsx`（95 行）
截图：`04-providers-light-full` / `-light-empty` / `-dark-full` / `18-provider-editor`

### 3.1 provider-actions 竖排错位 【实现硬伤】

```css
/* product.css */
.provider-actions{display:flex;flex-direction:column;gap:7px;align-items:stretch}
/* simplify.css —— 想改回横排，但没重置 flex-direction */
.provider-channel .provider-actions{display:flex;align-items:center;gap:8px}
```

`flex-direction:column` 未被重置 → 三个按钮（编辑 / 测试连接 / 立即收单）**竖着堆在卡片右侧**，把卡片撑成 ~150px 高，且 `align-items:center` 让它们宽度不一致，右边缘参差不齐（`04-providers-light-full` 明显可见）。

**修复**：

```css
.provider-channel .provider-actions{display:flex;flex-direction:row;align-items:center;gap:var(--s-2);flex-wrap:wrap}
```

一行代码。这是全站最容易修、视觉收益最直接的一处。

### 3.2 品牌色方块

```css
.provider-monogram{width:52px;height:52px;border-radius:15px;display:grid;place-items:center;background:#aa1f2e;color:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18)}
.provider-monogram.tapd{background:#2868d8}
.provider-monogram span{font:750 19px ui-monospace,monospace}
```

`#aa1f2e`（Redmine 红）与 `#2868d8`（TAPD 蓝）见 [02 §3.5](02-foundation.md)——第三方品牌色与产品色系无关，`#2868d8` 那块纯蓝在暖灰界面里像贴纸。

**改法**：

```css
.provider-monogram{
  width:44px;height:44px;display:grid;place-items:center;flex:none;
  background:var(--surface-3);color:var(--text);
  border:1px solid var(--line-strong);
  border-radius:var(--r-sm);      /* Redmine：方 */
  box-shadow:none
}
.provider-monogram.tapd{border-radius:var(--r-lg)}   /* TAPD：圆 —— 形状区分而非颜色 */
.provider-monogram span{font:600 17px var(--font-mono);letter-spacing:.02em}
```

**颜色改用于连接状态**（这才是用户扫这一列时要看的）：

```css
.provider-card{position:relative}
.provider-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:var(--r-md) 0 0 var(--r-md);background:var(--st-warning)}
.provider-card[data-state="verified"]::before{background:var(--st-success)}
.provider-card[data-state="disabled"]::before{background:repeating-linear-gradient(180deg,var(--line-strong) 0 4px,transparent 4px 8px)}
.provider-card[data-state="failed"]::before{background:var(--st-failed)}
```

### 3.3 连接状态语义不完整

```tsx
<span><i className={isTested ? 'ready-dot' : ''}/>{isTested ? '连接已验证' : provider.enabled === false ? '已停用' : '已配置 · 待验证'}</span>
```

`tested` 是**组件本地 state**（`useState<Record<string,boolean>>`），刷新页面就丢。用户每次打开页面看到的都是"已配置 · 待验证"，即使昨天验证过。

而 `action()` 里失败时会 `setTested(v => ({...v,[id]:false}))`——但 `false` 和"从未测过"渲染结果完全一样，**测试失败在界面上没有任何痕迹**（只有一个会消失的 notice）。

**改法**：

- 三态改四态：`未验证` / `验证中` / `已验证 · {时间}` / `验证失败 · {原因}`
- 失败态持久显示在卡片上（红色左栏 + 失败文字），直到下次测试成功
- 若能拿到后端的 `lastPolledAt` / `lastTestedAt`，优先用后端值；否则至少存 `localStorage`（这只是 UI 提示，不涉及 secret，不违反配置原则）

### 3.4 Secret 边界提示 —— 做得好，建议推广

`ProvidersPage.tsx:93`：

```tsx
<div className="secret-boundary-note">
  <svg viewBox="0 0 24 24"><path d="M7 10V8a5 5 0 0 1 10 0v2M5 10h14v10H5z"/></svg>
  <div><b>本机私密存储</b><span>保存后界面只知道"已配置"，无法读回真实值。</span></div>
</div>
```

这是把 `README.md`「Secret 明文独立存储，Web API 只返回 configured 状态」翻译成用户语言的正确做法。

**建议**：抽成通用组件 `<BoundaryNote kind="secret|localpath|readonly">`，用在三处：

| kind | 用在哪 | 文案 |
|---|---|---|
| `secret` | 来源编辑器（已有） | 保存后界面只知道"已配置"，无法读回真实值。 |
| `localpath` | 项目工作台的 `localizationSource.path` / `modificationWorkspace.path` / Patch 输出目录 | 这是 CodeFixer 服务主机上的路径，只保存在本机，换机器需要重新配置。 |
| `readonly` | `localizationSource`（`readOnly:true`） | 定位资料只读，平台不会修改这里的任何文件。 |

```css
.boundary-note{
  display:flex;gap:var(--s-3);align-items:flex-start;
  padding:var(--s-3) var(--s-4);margin-top:var(--s-4);
  border:1px dashed var(--line-strong);border-radius:var(--r-sm);
  background:var(--surface-2)
}
.boundary-note svg{width:16px;height:16px;flex:none;margin-top:1px;stroke:var(--text-tertiary);fill:none;stroke-width:1.6}
.boundary-note b{display:block;font:var(--t-micro);color:var(--text)}
.boundary-note span{display:block;font:var(--t-caption);color:var(--text-secondary);margin-top:2px;max-width:60ch}
```

虚线边框 = "这是一条规则，不是一条数据"。**这三处提示是产品可信度的一部分**，值得视觉上统一。

### 3.5 来源编辑器模态

`18-provider-editor`：

| # | 问题 | 改法 |
|---|---|---|
| 1 | `.provider-type-switch` 两个大按钮（R / T）在**编辑模式下 `disabled`**，但外观与可用时几乎相同 | disabled 时降透明度 + 移除 hover + 加"类型创建后不可更改"说明 |
| 2 | 表单字段 label 与 input 间距过小，label 是 11px 灰字，扫不到 | label 用 `--t-micro` + `--text-secondary`，间距 `--s-2` |
| 3 | 密码字段用默认 sans 字体，圆点大小不一 | `input[type="password"]{font-family:var(--font-mono)}`（已在 §2.2 CSS 里） |
| 4 | 编辑模式下 placeholder「已保存；留空表示不更换」是唯一提示，容易误以为字段空=会清空 | 字段上方加 `<span class="field-state">已配置</span>` 小徽章（绿点 + "已配置"），与 secret 边界呼应 |
| 5 | 「保存来源」按钮 disabled 条件复杂（`!id || !baseUrl || secretRequired`），但**不告诉用户缺什么** | disabled 时在按钮旁显示缺失项：「还需填写：服务地址」 |

---

## 4. 设置页 SettingsPage

源码：`frontend/src/pages/SettingsPage.tsx`（98 行）
截图：`05-settings-light-full` / `-light-empty` / `-dark-full` / `23-settings-md|sm|xs`

### 4.1 卡片空洞 —— 最明显的排版问题 【实现硬伤】

```css
/* simplify.css */
.control-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(310px,auto);gap:18px}
.control-card{padding:23px;display:flex;flex-direction:column;min-height:310px;...}
.control-card .segmented{margin-top:auto}
.control-card .current-model-control{margin-top:auto}
.settings-environment .readiness-summary{margin-top:auto}
.control-card>p{min-height:40px;margin:16px 0 20px!important}
```

`min-height:310px` 强制四张卡等高，`margin-top:auto` 把唯一的控件推到底部。

`05-settings-light-full` 实测：

| 卡片 | 内容高度 | 卡片高度 | 空洞 |
|---|---|---|---|
| 01 运行方式 | ~140px | 310px | **~170px** |
| 02 当前模型 | ~150px | 310px | ~160px |
| 03 AI 并发池 | ~180px | 310px | ~130px |
| 04 运行环境 | ~290px | 310px | ~20px |

三张卡中间挂着大片空白，控件孤零零贴在底边。这是"死板"最直观的一处——**用固定高度强行对齐，然后用 `margin-top:auto` 填空**。

**改法**：

```css
.control-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
  grid-auto-rows:auto;               /* 删掉 minmax(310px,auto) */
  gap:var(--s-5);
  align-items:start                   /* 关键：不拉伸等高 */
}
.control-card{padding:var(--s-5);display:flex;flex-direction:column;gap:var(--s-4);min-height:0}
.control-card .segmented,
.control-card .current-model-control,
.settings-environment .readiness-summary{margin-top:0}   /* 删掉 auto */
.control-card>p{min-height:0;margin:0!important;font:var(--t-body-sm);color:var(--text-secondary);max-width:52ch}
```

`align-items:start` + `auto-fit` = 每张卡只占它需要的高度，且窄屏自动降为一列。

**运行环境卡（04）内容最多，让它跨两列**：

```css
.settings-environment{grid-column:span 2}
@media (max-width:900px){.settings-environment{grid-column:auto}}
```

### 4.2 卡片竖条规则不明 【实现硬伤】

`05-settings-light-full`：**02 卡有橙色竖条、04 卡有绿色竖条，01 和 03 卡没有**。

从 CSS 推断这不是刻意设计，而是 `.mode-callout` / `.readiness-summary` 内部元素的边框漏出来。用户看到的是"这两张卡不一样，但不知道为什么"。

**改法**：统一规则——**竖条只表示"这项配置当前是否需要注意"**：

```css
.control-card{position:relative;overflow:hidden}
.control-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent}
.control-card[data-attention="warn"]::before{background:var(--st-warning)}
.control-card[data-attention="block"]::before{background:var(--st-failed)}
```

- 01 运行方式：全自动时橙（`--signal`，表示"正在自动运行"），待我开始时无
- 02 当前模型：模型 CLI 不可用时红
- 03 并发池：无（这不是会出问题的配置）
- 04 运行环境：`not_ready` 红、`warning` 黄、`ready` 无

**"无问题时不亮"是关键**——现在四张卡的竖条是随机的，改完之后竖条出现就意味着有事。

### 4.3 卡片角标 01–04

```css
.control-card .card-index{width:35px;height:35px;border-radius:10px;display:grid;place-items:center;background:var(--text);color:var(--surface);font:700 9px ui-monospace,monospace}
```

35×35 的近黑实心方块 + 9px 数字，四张卡各一个 —— 视觉重量很大，但序号本身**没有信息价值**（这四项配置没有顺序关系）。

**改法**：去掉实心方块，改成低调的角标：

```css
.control-card>header{display:flex;align-items:baseline;gap:var(--s-3)}
.control-card .card-index{
  width:auto;height:auto;background:none;color:var(--text-tertiary);
  font:var(--t-kicker);letter-spacing:.14em;border-radius:0
}
.control-card>header h2{font:var(--t-section);margin:0}
.control-card>header small{font:var(--t-kicker);letter-spacing:.16em;text-transform:uppercase;color:var(--text-tertiary);display:block;margin-bottom:3px}
```

省下的视觉预算给真正重要的东西（并发数字、环境状态）。

### 4.4 并发控制器

```tsx
<div className="concurrency-control">
  <button aria-label="减少并发" ...>−</button>
  <div><strong>{llmConcurrency}</strong><span>个并行调用</span></div>
  <button aria-label="增加并发" ...>+</button>
</div>
<div className="capacity-scale">
  <span className={llmConcurrency<=2?'active':''}>保守</span><i/>
  <span className={llmConcurrency>2&&llmConcurrency<=6?'active':''}>均衡</span><i/>
  <span className={llmConcurrency>6?'active':''}>高吞吐</span>
</div>
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | `−` / `+` 是 ASCII 字符按钮，1–64 范围内只能一次一次点 | 保留 ± 但加**可拖动刻度条**；或长按加速 |
| 2 | `capacity-scale` 三档标签与实际数字关系靠猜（2/6 的分界没标出来） | 刻度条上标出 1 / 2 / 6 / 16 / 64 分档位置 |
| 3 | 数字 `{llmConcurrency}` 没用 mono + tabular，4→16 时布局跳 | `font:600 40px var(--font-mono);font-variant-numeric:tabular-nums` |
| 4 | 没告诉用户**当前实际用了多少**——这是并发池最该显示的信息 | 加 `4 / 8 使用中` 的占用条 |

**建议的并发控件**（刻度 + 占用可视化）：

```tsx
<div className="capacity-meter">
  <div className="cm-value"><strong>{llmConcurrency}</strong><small>上限</small></div>
  <div className="cm-bar" role="img" aria-label={`当前使用 ${inUse} / ${llmConcurrency}`}>
    {Array.from({length: Math.min(llmConcurrency, 16)}, (_, i) =>
      <i key={i} className={i < inUse ? 'used' : ''}/>)}
    {llmConcurrency > 16 && <em>+{llmConcurrency - 16}</em>}
  </div>
  <div className="cm-ctrl"><button>−</button><button>+</button></div>
</div>
```

```css
.cm-bar{display:flex;gap:2px;align-items:center;flex:1}
.cm-bar i{flex:1;height:22px;min-width:3px;background:var(--surface-3);border-radius:1px}
.cm-bar i.used{background:var(--signal)}
.cm-bar em{font:var(--t-mono-sm);color:var(--text-tertiary);font-style:normal;margin-left:4px}
```

一排小竖格，亮起来的是正在跑的。这是机床面板的语汇，也比"保守/均衡/高吞吐"三个抽象词有用得多。

> **数据前提**：`inUse` 需要后端返回当前 LLM 并发占用数。若暂无，先只渲染上限格（全灰），保留结构。

### 4.5 当前模型控件

```css
.current-model-control{display:grid;grid-template-columns:36px minmax(0,1fr) auto;align-items:center;gap:12px;margin-top:16px;padding:12px 0 2px;border-top:1px solid var(--line)}
.current-model-control select{...border:0;background:transparent;font-size:13px;font-weight:700}
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 无框 select 看不出可点击（`05-settings-light-full` 里像一行加粗文字） | 加 hover 底色 + 下拉箭头（§2.2 的 select 样式，但保留无框：`border:0` + hover `background:var(--surface-2)`） |
| 2 | `.profile-health` 是一个 `<span>` 纯色小点，无文字无 title 之外的说明 | 改为 `<StatusDot>` + 文字（"CLI 可用" / "未检测到"） |
| 3 | `AgentMark` 三个 runtime 图标用硬编码品牌色 | 见 [02 §3.5](02-foundation.md)，统一 `currentColor` |
| 4 | 六个模型选项的 `note`（"更快、更省，适合高频任务"）只在选中后显示一条 | 下拉展开时每项都显示 note（原生 `<select>` 做不到 → 这正是需要 `Select` primitive 的地方） |

> **边界注意**：`executableRef`（`claude-code-cli` / `codex-cli`）按 `README.md`「日常项目 UI 不暴露这些实现引用」，但设置页的**运行环境卡当前直接显示 `{item.dependencyId}`**（即 `claude-code-cli`）。设置页属于运维视角，显示是合理的；但建议加中文名：`Claude Code CLI`（主）+ `claude-code-cli`（mono 小字）双行，既可读又保留可排查性。

### 4.6 运行环境卡

```tsx
<div className="readiness-summary"><strong className={readiness?.status ?? 'checking'}>…</strong><span>{`${ok}/${total} 项核心正常`}</span></div>
<div className="dependency-grid relevant-dependencies">{relevantChecks.map(item =>
  <div className={`dependency-row ${item.status}`} key={item.id}><i/><div><b>{item.dependencyId}</b><small>{item.summary}</small></div>
  <span>{item.status==='ready'?'可用':item.status==='failed'?'阻断':'注意'}</span></div>)}
</div>
```

| # | 问题 | 改法 |
|---|---|---|
| 1 | 每个 dependency-row 是独立盒子（违反 §16） | 共享容器 + 分隔线 |
| 2 | 状态只在最右侧一个词（可用/阻断/注意），左侧 `<i/>` 圆点颜色是唯一的快速信号 | 行左侧加 3px 状态栏 + 保留圆点，failed 行加浅红底 |
| 3 | `relevantChecks` 过滤逻辑（`required || 当前模型 || failed`）很聪明——"未启用的工具不会制造黄灯"，但**用户不知道被过滤掉了什么** | 底部加一行「另有 3 项未启用的依赖未检查」+ 可展开 |
| 4 | 「重新检查」按钮在 `readiness` 为 null 时显示"检查中…"并 disabled，但**首次加载和手动刷新的视觉相同** | 手动刷新时按钮内显示 spinner，列表加 skeleton（见 [07 §6](07-controls-overlays.md)） |
| 5 | `item.summary` 是后端返回的英文/中文混合摘要，字号 10px | 提到 `--t-caption`(12px) |

### 4.7 notice / error 条是 `<button>`

```tsx
{notice && <button className="notice-strip success-note" onClick={()=>setNotice('')}>{notice}</button>}
{error && <button className="notice-strip error-note" onClick={()=>setError('')}>{error}</button>}
```

整条通知是一个按钮，点任意位置关闭——功能上可以，但：

- 没有可见的关闭图标，用户不知道能点
- `<button>` 语义上应该是"执行动作"，这里是"消息" → 无障碍上应该是 `role="status"` / `role="alert"`

**改法**：

```tsx
<div className={`notice-strip ${kind}`} role={kind==='error-note'?'alert':'status'}>
  <i aria-hidden="true"/>
  <span>{text}</span>
  <button className="icon-btn ghost" onClick={dismiss} aria-label="关闭提示">×</button>
</div>
```

---

## 5. 四页共同的两个问题

### 5.1 页面标题体系不统一

- 首页：`.hero > h1`（34px + 右侧 slots）
- 任务页：`.page-heading > h1` + 右侧「刷新」按钮
- 项目页：`.page-heading > h1` + 右侧「新建项目」
- 来源页：`.page-heading > h1` + 右侧「添加来源」
- 设置页：`.page-heading > h1`，**无右侧动作**

→ 统一为 `.page-heading`（见 [02 §5](02-foundation.md) 的样式），首页只是右侧插槽内容不同。

### 5.2 加载态全是纯文字

- `SettingsPage.tsx:44`：`<p>{error || '正在读取配置…'}</p>`
- `ProvidersPage`：无加载态，直接从空数组渲染成"还没有工单来源"——**首次加载时会闪一下错误的空态**
- `ProjectsPage` / `TasksPage` 同样问题

规范 §20 要求优先 skeleton。→ 见 [07 §6](07-controls-overlays.md)。

`ProvidersPage` 的空态闪烁是**功能性 bug 级**的视觉问题：用户打开来源页，先看到"还没有工单来源 / 连接 Redmine 或 TAPD 后…"，200ms 后才变成两个已配置的来源。必须加 `loading` 状态区分"没加载完"和"真的没有"。

---

## 6. 验收 checklist

**项目页**
- [ ] 卡片左侧竖栏按就绪状态着色，停用用虚线
- [ ] 「运行体检」权重 > 「编辑配置」
- [ ] 长路径从中间省略，保留尾部，`title` 有完整值
- [ ] 本机路径处有 `localpath` 边界提示
- [ ] 空态是三步引导，不是通用空盒

**工作台**
- [ ] stepper 能区分 已完成 / 当前 / 未填 / 有错
- [ ] 两个 checkbox 不再是浏览器默认蓝色
- [ ] allowedRoots 绿 / deniedRoots 红，语义相反视觉相反
- [ ] 有未保存更改时有提示

**来源页**
- [ ] 三个动作按钮**横排**
- [ ] monogram 无第三方品牌色，靠形状区分
- [ ] 卡片左栏表示连接状态
- [ ] 测试失败在卡片上持久可见
- [ ] 编辑器 disabled 的类型切换外观明显不同
- [ ] 保存按钮 disabled 时说明缺什么

**设置页**
- [ ] 四张卡不再等高，无 `margin-top:auto` 空洞
- [ ] 竖条只在需要注意时出现，规则一致
- [ ] 并发数字 mono + tabular，有占用可视化
- [ ] 依赖列表是共享容器 + 分隔线
- [ ] 被过滤掉的依赖有说明
- [ ] notice 条有可见关闭按钮 + 正确 role

**全部四页**
- [ ] 标题区结构一致
- [ ] 首次加载显示 skeleton，不闪错误空态
