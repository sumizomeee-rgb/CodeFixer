# 第五轮 · 下册：流水线弹窗的改动与验收

诊断见 [17 册](17-round5-workbench-audit.md)。本册记录实际落地的改动、取舍理由与验收结果。

三项范围决定由用户拍板：

| 议题 | 决定 |
|---|---|
| 弹窗高度 | 先做自适应 + 上限，实测体验后改回**定高**，见 §1 |
| 「修改与检查规则」折叠区归属 | 并入第 3 步「修改工程」，不拆成第 5 步，不保持常驻 |
| 方感收口范围 | **只改流水线弹窗内的**，不做全站统一 |

---

## 1 · 弹窗高度：自适应 → 定高

### 1.1 自适应方案与它的问题

第一版按「自适应 + 上限」实现：

```css
min-height: min(480px, calc(100vh - 36px));
max-height: calc(100vh - 36px);
```

技术指标全部达成 —— 四步都不需要滚动，短步骤不留半屏空白。但用户实测后的反馈是「切换 1234 不固定高度还是太难受了」。

原因在于数据：四步自然高 **515 / 534 / 633 / 909**，跨度 394px。点「继续」时弹窗四档跳动，底栏按钮跟着上下窜。**这种抽动比留白更难受** —— 留白是静态的，抽动每次点击都发生一次，而且底栏按钮位置不稳定会直接影响连续点「继续」的操作。

### 1.2 定高取值

```css
/* 定高。实测四步自然高 515 / 534 / 633 / 909，跟随内容会四档抽动，
   实际体验里这种跳动比空白更难受，所以宁可让短步骤留白。
   912 = 最坏步骤取整：第 4 步 GitHub 工程勾满 Patch + PR（两行配置都带输入框，
   比 GitLab 的单列 quiet 行高 31px），内容 716 + 头尾 193 = 909。
   视口不足时退到 calc(100vh - 36px)，此时才会滚，由 workbench-body 的渐隐提示。 */
.project-workbench { ...; height: min(912px, calc(100vh - 36px)); }
```

取值不能只看默认 fixture。第 4 步的高度随勾选的出口变化，实测两种极值：

| 场景 | 配置行高度 | 内容高 | 自然弹窗高 |
|---|---|---|---|
| GitLab 工程，勾 Patch + GitLab | 97 / 65 | 686 | 879 |
| **GitHub 工程，勾 Patch + PR** | 97 / 96 | **716** | **909** |

GitLab 那行是 `.action-config-quiet`（单列、无输入框），比带「目标分支」输入框的 PR 行矮 31px。按 GitLab 场景定 880 会让 GitHub 工程的第 4 步溢出 —— 这是只测一种 fixture 会漏掉的坑。

头尾（`workbench-head` + `workbench-actions`）恒为 193px，与视口宽度无关，四种视口下实测一致。

### 1.3 定高后实测

| 步骤 | 弹窗高 | 内容区 scroll/client | 需要滚动 |
|---|---|---|---|
| 01 工单反馈 | 912 | 717/717 | 否 |
| 02 定位资料 | 912 | 717/717 | 否 |
| 03 修改工程 | 912 | 717/717 | 否 |
| 04 最终交付 | 912 | 717/717 | 否 |
| 03 + 展开折叠区 | 912 | 1046/717 | 是，超出 329px |
| 1280×760 视口第 4 步 | 712（退化） | 686/517 | 是，超出 169px |

四步零抽动、零滚动。代价是第 1 步下方约 480px 留白 —— 这是定高必然的取舍，用户在知道两种方案实际观感后选择了留白。

溢出只在两种情况发生（主动展开折叠区、视口高度不足），两者都由 §2 的渐隐提示兜住。

---

## 2 · 溢出渐隐：两次尝试

### 2.1 第一版（背景渐变附着法）—— 有缺陷，已废弃

思路是给 `.workbench-body` 叠四层 `linear-gradient` 背景，两层 `local` 附着（随内容滚动）、两层 `scroll` 附着（钉在视口）。滚到底时 `local` 层被自身背景盖住，渐隐自动消失。

**实测失败。** 背景渐变画在容器的背景层，而卡片（`.project-policy`、`.detection-report`、`.delivery-log-config`）自己有底色，会把它整块盖住。折叠区展开时正好是卡片贴到边缘，渐隐完全不可见 —— 唯一需要它的场景恰好失效。

### 2.2 第二版（mask 附着法）—— 已采用

```css
.workbench-body {
  min-height: 0; padding: 27px 30px 42px; overflow-y: auto;
  mask:
    linear-gradient(#000 0 0) top / 100% 28px local no-repeat,
    linear-gradient(#000 0 0) bottom / 100% 32px local no-repeat,
    linear-gradient(transparent, #000 28px, #000 calc(100% - 32px), transparent) scroll;
}
```

`mask` 作用在**合成结果**上，卡片底色会一起淡出，绕开了 2.1 的问题。

三层按 mask 默认的 `add` 合成：

- 第 3 层 `scroll` 附着，钉在视口上，上下各一道渐隐，常驻；
- 第 1、2 层 `local` 附着，是两条实心带子，跟着内容走。

于是三种状态自动成立：

| 状态 | 实心带位置 | 效果 |
|---|---|---|
| 内容不溢出 | 两条带子都在视口内 | 渐隐被完全补满，整块不透明 |
| 滚到顶 | 顶部带子压在顶部 | 顶部实、底部渐隐 |
| 滚到中间 | 两条带子都滚出视口 | 上下都渐隐 |
| 滚到底 | 底部带子压在底部 | 顶部渐隐、底部实 |

全程零 JS，不监听 `scroll`，不用 `scroll-timeline`（兼容性不够）。三态均已截图核对。

---

## 3 · 折叠区并入第 3 步

```tsx
{/* frontend/src/pages/ProjectsPage.tsx */}
{/* 规则属于「在这个工程里能改什么、改完怎么验」，语义归第 3 步。
    放在 step 判断之外会让它在四步里全程常驻，用户在选交付出口时也看得到它。 */}
{step === 3 && <details className="project-policy">...</details>}
```

改前它写在四个 `step === n` 判断之外，四步常驻。

改动前已核实 `stepComplete`（`:154`）与 `canSave`（`:160`）都不读折叠区内字段，条件渲染不影响「继续」「保存并体检」的可用性判断。实测四步走查，`折叠区在场` 只在第 3 步为 `true`。

---

## 4 · 方感收口（六处）

### 4.1 `.delivery-log-config`

```css
/* 交付日志与三张出口卡是并列关系，不是父子。改前间隙 0px，两块焊在一起，
   看上去像日志块的三个子选项。完整描边替代「描边 + 彩色左边线」，与设置页同一处置。 */
.delivery-log-config { margin-top: 4px; padding: 18px; border: 1px solid var(--line-strong); border-radius: var(--r-sm); background: ...; }
```

删 `border-left: 3px solid var(--signal)`，补 `border-radius`。

### 4.2 `.action-choice-grid` —— 用户点名的 0px

```css
/* 组间距 26px：明显大于卡片之间的 10px，让「日志块 / 出口卡组」读作两块并列内容 */
.action-choice-grid { ...; gap: 10px; margin-top: 26px; }
```

### 4.3 `.action-config-stack`

```css
.action-config-stack { display: grid; margin-top: 17px; padding: 0 14px; border: 1px solid var(--line); border-radius: var(--r-sm); }
.action-config { ...; padding: 14px 0; border-bottom: 1px solid var(--line); }
```

`border-block` → 完整描边 + 圆角，容器接管左右内边距（`0 14px`），行内边距相应由 `13px 4px` 改 `14px 0`，避免两层内边距叠加。`.action-config` 之间的 `border-bottom` 保留 —— 那是卡内分隔，不是边界。

### 4.4 `.source-separation`

```css
.source-separation { ...; padding: 18px; border: 1px solid var(--line); border-radius: var(--r-sm); }
```

内部两个 `div` 的 `border-left: 3px solid var(--line-strong)` **保留**。它们是「定位源 ↔ 修改工程」两侧的对称标记，成对出现、语义是并列而非状态，属于图示的一部分，不是被切一半的卡。

### 4.5 `.detection-report`

```css
/* 识别结果是一张完整的卡，原来只有上下边线加一条彩色左边线，左右不收口。
   状态改由整圈描边表达：成功/失败各自染色，比 3px 左边线更容易一眼扫到。
   overflow 用来裁掉内部分隔行在圆角处露出的直角。 */
.detection-report { margin-top: 19px; border: 1px solid var(--line-strong); border-radius: var(--r-sm); background: var(--surface-2); overflow: hidden; }
.detection-report.ready  { border-color: color-mix(in srgb,var(--success) 55%,var(--line-strong)); }
.detection-report.failed { border-color: color-mix(in srgb,var(--failed) 55%,var(--line-strong)); }
```

状态色没有被删掉，是换了载体：从「左边一条 3px」变成「整圈染色」。`color-mix` 到 55% 是为了让描边仍读作描边而不是高亮块 —— 卡里已经有一枚彩色状态图标承担强调。

### 4.6 `.soft-warning`

```css
/* 原本是「3px 彩色左边线 + 底色」，右侧没有收口，一块底色悬在版面里。
   底色已经足够传达警示，边框补全成一圈同色系细线即可。 */
.soft-warning { ...; border: 1px solid color-mix(in srgb,var(--warning) 40%,transparent); border-radius: var(--r-sm); background: var(--warning-soft); ... }
```

### 4.7 收口后的残留

改后再普查，弹窗内剩下的非完整描边元素：

| 元素 | 四边 | 判定 |
|---|---|---|
| `workbench-head` | 0/0/1/0 | 保留 —— 头部与内容区的分隔线 |
| `project-stepper` | 0/1/0/0 | 保留 —— 侧栏与内容区的分隔线 |
| `workbench-actions` | 1/0/0/0 | 保留 —— 底栏与内容区的分隔线 |
| `remote-line` | 1/0/0/0 | 保留 —— `detection-report` 卡内分隔 |
| `action-config` | 0/0/1/0 | 保留 —— `action-config-stack` 卡内分隔 |
| `.policy-body > h4` / `.advanced-heading` | 1/0/0/0 | 新增 —— 折叠区分组虚线，见 §5 |
| `CODE`（日志预览） | 1/0/0/0 | 保留 —— `delivery-log-config` 卡内分隔 |

全部符合 17 册 §2.3 的判定标准：画的是分隔，不是边界。

---

## 5 · 折叠区排版重做

```css
.project-policy { margin-top: 30px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--surface); }
.project-policy > summary { padding: 15px 17px; ... }
.project-policy > summary:hover { color: var(--text); }
.project-policy[open] > summary { border-bottom: 1px solid var(--line); }
.policy-body { padding: 19px 17px 22px; }

/* 折叠区原来只有 h4(14px/600) 和 label(12px/500) 两级，差 2px 一档字重，
   分组标题和字段标签几乎同一视觉重量，扫下来就是一片大小字混排。
   这里不靠字号硬堆，改用全站已有的 mono 眉标：靠字族、字距、颜色区分「这是分组」，
   与 12px 无衬线字段标签完全是两个物种，一眼能断句。 */
.policy-body h4 { margin: 0; color: var(--tertiary); font: 600 10px/1 var(--font-mono); letter-spacing: .12em; }

/* 眉标降到 10px 后单靠间距断不开三组，补一条虚线分隔；首组不画。 */
.policy-body > h4,
.policy-body > .advanced-heading { margin: 24px 0 13px; padding-top: 19px; border-top: 1px dashed var(--line); }
.policy-body > :first-child { margin-top: 0; padding-top: 0; border-top: 0; }

/* 眉标只有 10px，旁边挂一枚 40px 的默认按钮会把整行重心压到按钮上，缩到眉标量级 */
.advanced-heading .ghost.framed { min-height: 28px; padding: 5px 10px; font-size: 11px; }
```

改后层级实测：

| 角色 | 字号 | 字重 | 字族 | 字距 |
|---|---|---|---|---|
| 分组眉标 ×3 | 10px | 600 | IBM Plex **Mono** | 1.2px |
| 字段标签 | 12px | 500 | IBM Plex **Sans** | normal |
| 勾选项文本 | 12px | 400 | IBM Plex Sans | normal |

三个维度同时不同（字族 / 字距 / 颜色），断句成立。折叠区自身也从「一条 `border-top`」变成一只完整的盒子，展开后不再是一片表单浮在版面上。

---

## 6 · 改动清单

**`frontend/src/styles/pages.css`**

| # | 选择器 | 改动 |
|---|---|---|
| 1 | `.project-workbench` | 定高 800 → 912（按第 4 步最坏情况实测取值） |
| 2 | `.workbench-body` | 新增三层 mask 溢出渐隐 |
| 3 | `.delivery-log-config` | 删彩色左边线，补圆角 |
| 4 | `.action-choice-grid` | 补 `margin-top: 26px` |
| 5 | `.action-config-stack` / `.action-config` | `border-block` → 完整描边 + 圆角，内边距移交容器 |
| 6 | `.source-separation` | `border-block` → 完整描边 + 圆角 |
| 7 | `.detection-report` | `border-block` + 彩色左边线 → 完整描边 + 状态染色 + `overflow: hidden` |
| 8 | `.soft-warning` | 彩色左边线 → 完整同色系描边 + 圆角 |
| 9 | `.project-policy` | `border-top` → 完整盒子；`summary` 加内边距、hover、展开分隔线 |
| 10 | `.policy-body h4` | 14px sans 标题 → 10px mono 眉标 + 虚线分组 |
| 11 | `.advanced-heading .ghost.framed` | 按钮缩到 28px / 11px |

**`frontend/src/pages/ProjectsPage.tsx`**

| # | 位置 | 改动 |
|---|---|---|
| 12 | `:228` | `<details className="project-policy">` 外包 `{step === 3 && ...}` |

**`frontend/e2e/phase0.spec.ts-snapshots/`**

| # | 文件 | 改动 |
|---|---|---|
| 13 | `project-workbench-compact-chromium.png` | 因弹窗高度改动重新生成 |

---

## 7 · 验收结果

| 项 | 结果 |
|---|---|
| 四步切换不抽动 | ✅ 恒为 912px |
| 四步都不需要滚动 | ✅ 717/717 ×4 |
| 定高覆盖第 4 步最坏情况 | ✅ GitHub 勾满 Patch + PR 需 909px < 912px |
| 折叠区展开后可滚 | ✅ 超出 329px |
| 小视口退化正常 | ✅ 1280×760 下弹窗 712px，第 4 步超出 169px |
| 溢出时有渐隐提示 | ✅ 顶/中/底三态均已截图核对 |
| 不溢出时 mask 不吃内容 | ✅ 第 4 步截图确认边缘不透明 |
| 折叠区只在第 3 步出现 | ✅ 四步走查，仅第 3 步 `折叠区在场: true` |
| 日志块与出口卡组间距 | ✅ 0px → 26px |
| 六处方感元素收口 | ✅ 残留 7 处全部是卡内分隔 |
| 折叠区层级可断句 | ✅ 10px mono / 12px sans，三维度不同 |
| `npm run build` | ✅ |
| `npm run typecheck` | ✅ |
| `npm run test:browser` | ✅ 1 passed |
| `npm run test:e2e` | ✅ 6 passed（1 张基线预期失效，已重新生成并复跑确认） |
| 其余 6 张基线零差异 | ✅ 证明改动确实只落在弹窗内 |
| 未触碰安全边界 | ✅ 仅 CSS 与一处 JSX 位置，不涉字段 / 接口 / 存储 |

`--update-snapshots` 只重写了 `project-workbench-compact-chromium.png` 一张，其余 6 张零差异 —— 这同时验证了第四轮收紧后的 `maxDiffPixelRatio: 0.0005` 仍然稳定，没有把无关基线误判成失败。

---

## 8 · 本轮已记录、未获授权的遗留

- **全站其余页面的 `border-block` 收口**：`task-table`、设置页与来源页仍有同类元素。用户本轮明确选择「只改流水线弹窗内的」，不在范围内。
- 15 册中标记「有效，未做」的 A4、A6、A7、A8、C1（`noto-sans-sc` 三个字重各 1.15MB，未分片）、C3。
- 主导航收敛为「任务 / 流水线 / 设置」—— SPEC 已写明，实现未跟进，需先与用户确认。
