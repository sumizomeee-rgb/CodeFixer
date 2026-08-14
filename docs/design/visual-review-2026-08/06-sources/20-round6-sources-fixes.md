# 第六轮 · 下册：反馈源页改动与验收

上册（[19 册](19-round6-sources-audit.md)）是诊断。本册记录改动、取舍与验收。

改动范围由用户在评审后指定：

1. 列表形态 → **收成独立卡片**（另一选项「收成紧凑表格行」未采纳）
2. 方感收口范围 → **只改反馈源页**（不顺带统一全站列表壳）
3. 弹窗高度 → **同流水线弹窗，定高**

---

## 1 · 列表：从「假卡真表格」收成真卡

```css
/* 改后 */
.provider-grid { display: grid; gap: 10px; }
.provider-channel {
  display: grid; grid-template-columns: 54px minmax(0,1fr) auto; align-items: center; gap: 16px;
  padding: 17px 19px;
  border: 1px solid var(--line); border-radius: var(--r-md); background: var(--surface);
  transition: border-color var(--fast), box-shadow var(--fast);
}
.provider-channel:hover { border-color: var(--line-strong); box-shadow: var(--shadow-float); }
```

三处判断：

- **列表壳退化为纯布局容器**。`border-block` 和 `background` 全部下放到卡片自己身上。壳不再是一个视觉对象，只负责 `gap: 10px`。
- **圆角取 `--r-md`（11px）不是 `--r-sm`（7px）**。这是页面级的主体对象，与设置页 `.control-card` 同级；7px 是弹窗内构件的量级。
- **hover 才升 `shadow-float`**。常态只有 1px 描边，避免两三张卡各自投影把版面搅碎。

### 1.1 为什么选卡片而不是紧凑表格行

反馈源常态只有 1–3 条（一个 Redmine + 一个 TAPD 就覆盖大部分团队）。表格行的优势在于**密度** —— 20 条以上时省纵向空间；在 2 条的场景下，密度不是问题，边界才是。

而且卡上真有 4 层信息（眉标 / 名称 / 描述 / 状态）+ 2 个动作，压成单行必须砍掉徽标和描述。砍完信息量还不如现在。

---

## 2 · 状态表达：删色带，失败态改底色承载

4px 彩色左边条整段删除。状态改由 `.provider-meta` 的圆点 + 文字表达（原本就有，且是同一个色值）。

失败态例外 —— 它需要在一屏里被一眼扫到：

```css
.provider-channel[data-health="failed"] {
  border-color: color-mix(in srgb,var(--failed) 42%,var(--line));
  background: color-mix(in srgb,var(--failed-soft) 55%,var(--surface));
}
.provider-channel[data-health="inactive"] { background: var(--surface-2); }
```

### 2.1 一次修正：整圈高对比描边在暗色下压垮版面

第一版按第五轮 `detection-report` 的处置写成 `color-mix(var(--failed) 55%, var(--line-strong))` —— 整圈高对比描边。

亮色下没问题，**暗色下两条全失败时整片版面被红框铺满**，反而失去了「一眼扫到异常」的作用：当所有东西都在报警时，没有东西在报警。

原因是原来的 4px 色带因为窄，多条失败也压不垮版面；换成整圈后周长增加约 20 倍，暗色底上对比度还更高。

改法不是退回色带，是**换承载者**：描边降到 42% 混 `--line`（回到环境层级），状态交给 `--failed-soft` 底色。底色是面、描边是线，面在低对比下依然可辨，且不会因为条数增加而线性叠加视觉重量。

**结论沉淀**：第五轮「状态色用整圈描边染色」这条对**单个对象**（弹窗里唯一的识别结果卡）成立；对**可能同时出现多个的列表项**，应由底色承载、描边保持环境层级。

---

## 3 · 品牌色收敛到令牌层

```css
/* tokens.css :root */
--brand-redmine: #9c2e3d;
--brand-tapd: #2f66bd;
/* :root[data-theme="dark"] */
--brand-redmine: #dd7784;
--brand-tapd: #7ba6e8;
```

补齐了原先缺失的暗色值（原硬编码在亮色下调过，暗色下 `#2f66bd` 在 `#141817` 底上偏暗）。

使用范围仍限制在 `.provider-monogram` 一处，注释写明「不参与状态语义，也不出现在其他构件上」。

---

## 4 · 弹窗

### 4.1 编辑态：disabled 按钮 → 只读身份条

```tsx
{editingId
  ? <div className="provider-type-static">
      <span className={`provider-monogram ${type}`}>{type === 'tapd' ? 'T' : 'R'}</span>
      <div><b>{...}</b><small>{...}</small></div>
      <em>类型创建后不可更改</em>
    </div>
  : <div className="provider-type-switch">{/* 两个按钮，disabled 属性已移除 */}</div>}
```

三点收益：

- 脱离 `button:disabled { opacity: .46 }`，信息以 100% 不透明度呈现
- 体量从 66px 双列降到 62px 单行，对得上「身份标识」的实际权重
- `<em>类型创建后不可更改</em>` 用 mono 眉标语汇（10px / .1em 字距 / `--tertiary`），把「为什么不能改」讲出来 —— 原先 disabled 按钮只表达「不能点」，没说原因

高度 62px 与原双列（66px）接近，两态切换不会大幅跳动。

### 4.2 表单栅格填平

**TAPD Token 态**：`Access Token` 去掉 `span-field`，补进「登录方式」右边的空格。3 行降到 2 行。

**TAPD 账密态**：账号密码包进整行子栅格：

```css
.credential-pair { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
```

与外层同宽同 gap，看不出是子栅格。改后三态布局：

| 形态 | 行结构 |
|---|---|
| Redmine | 名称 \| 服务地址 → API Key（跨列） |
| TAPD 账密 | 名称 \| 工作区 → 登录方式 \| — → 账号 \| 密码 |
| TAPD Token | 名称 \| 工作区 → 登录方式 \| Access Token |

账密态「登录方式」右边那格仍空，但这次是**有意的分组间隔** —— 三行读作身份 / 登录方式 / 凭据，而不是一对字段被拆到对角。

### 4.3 定高 624px

栅格填平后重新实测五态：

| 形态 | 填平前 | 填平后 |
|---|---|---|
| 新增 Redmine | 541 | 541 |
| 编辑 Redmine | 540 | 540 |
| 新增 TAPD Token | 624 | **541**（少一行） |
| 新增 TAPD 账密 | 624 | 624 |
| 编辑 TAPD 账密 | 624 | 624 |

按最大值定：

```css
.provider-editor { display: flex; flex-direction: column; height: min(624px, calc(100vh - 48px)); }
.provider-editor .modal-actions { margin-top: auto; padding-top: 24px; }
```

`margin-top: auto` 让短表单的多余空间落在 secret 提示与底栏之间，按钮位置恒定。定高后五态实测 **624 / 624 / 624 / 624 / 624**。

**为什么这里不需要 mask 渐隐**（流水线弹窗做了）：那个弹窗有可展开的折叠区，正常视口下就会溢出；这个弹窗内容固定，只有视口高度不足 624 + 48 时才滚，此时 `.config-modal` 自身的 `overflow: auto` 接管，属于极端窗口尺寸而非常规路径。

### 4.4 `.secret-boundary-note` 收口

`border-left-width: 3px` 删除，回到整圈 1px。全站「加粗左边线」模式至此清零。文案与语义未动。

---

## 5 · 忙碌态串扰修复

```tsx
- disabled={!!busy}
+ disabled={busy === `test:${provider.id}`}
```

一行。与文案判断统一到同一个条件，锁只落在正在测试的那一条上。

---

## 6 · 移动端

```css
@media (max-width: 720px) {
  .provider-editor { height: auto; }                                  /* 弹窗铺满全屏，定高会打架 */
  .provider-editor .modal-actions { margin-top: 24px; padding-top: 0; }
  .provider-type-static em { display: none; }                          /* 420px 下与身份文字挤在一行 */
  .credential-pair { grid-template-columns: 1fr; }                     /* 随 form-grid 一起降单列 */
}
```

`.provider-actions` 的 `border-top: 1px solid var(--line)` 保留 —— 按第五轮判定标准，它是**卡内分隔**（动作区与内容区），不是对象边界。

---

## 7 · 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `tokens.css` | 新增 `--brand-redmine` / `--brand-tapd`，亮暗各一套 |
| 2 | `pages.css` | `.provider-grid` 去 `border-block` / 底色，改 `gap: 10px` 纯容器 |
| 3 | `pages.css` | `.provider-channel` 四边收口 + `--r-md` 圆角 + 底色 + hover 升起 |
| 4 | `pages.css` | 删除 `::before` 4px 色带四条规则 |
| 5 | `pages.css` | 失败态 / 停用态改由底色承载 |
| 6 | `pages.css` | `.provider-monogram` 硬编码色 → 令牌 |
| 7 | `pages.css` | 新增 `.provider-type-static` 只读身份条 |
| 8 | `pages.css` | `.provider-editor` 定高 624px + 底栏 `margin-top: auto` |
| 9 | `pages.css` | 移动端断点：定高退让、`em` 隐藏 |
| 10 | `components.css` | `.secret-boundary-note` 删 `border-left-width: 3px` |
| 11 | `components.css` | 新增 `.credential-pair` 子栅格 + 移动端降单列 |
| 12 | `ProvidersPage.tsx` | 编辑态渲染只读身份条，新增态按钮移除 `disabled` |
| 13 | `ProvidersPage.tsx` | Token 去 `span-field`；账密包进 `.credential-pair` |
| 14 | `ProvidersPage.tsx` | `disabled={!!busy}` → `disabled={busy === \`test:${id}\`}` |

---

## 8 · 验收

| 项 | 结果 |
|---|---|
| `npm run build` | ✅ |
| `npx tsc --noEmit` | ✅ exit 0 |
| `npm run test:browser` | ✅ 1 passed |
| `npm run test:e2e` | ✅ 6 passed |
| 视觉基线变更 | 仅 `providers-light-chromium.png` 一张 |
| 弹窗五态高度 | 624 / 624 / 624 / 624 / 624，零抽动 |
| 忙碌态串扰 | 已消除，仅目标条禁用 |
| 暗色失败态 | 底色承载，描边不压版面 |
| 移动端 420px | 单列正常，弹窗不定高，`em` 隐藏 |
| Secret 边界 | `secret-boundary-note` 文案未改；`setSecret` 调用链未改 |

### 8.1 「只有一张基线失效」是双向证据

改动触及两处**公共**样式（`.secret-boundary-note`、`.credential-pair`），有外溢风险。e2e 六张基线里其余五张零差异，说明：

- `.secret-boundary-note` 目前只有反馈源弹窗在用（已 grep 核实）
- `.credential-pair` 是新增类名，不影响既有 `.form-grid` 布局

同时也再次验证了 `maxDiffPixelRatio: 0.0005` 这个阈值够灵敏 —— 它测得出反馈源页的改动，也没有误伤其他页面。

---

## 9 · 未做 / 遗留

- **两个动作按钮的权重倒置**（19 册 §4.2）：「测试连接」在已连通状态下仍是卡上最重的控件。本轮只做了形态收口，没动按钮语汇 —— 改它涉及「测试连接是否该常驻」的产品判断，超出视觉范围。
- **全站其余列表壳的 `border-block`**（任务页 `task-table` 等）：用户本轮明确选了「只改反馈源页」，继续挂账。
- 15 册中标记「有效，未做」的 A4 / A6 / A7 / A8 / C1 / C3 仍未动。
- 主导航收敛为「任务 / 流水线 / 设置」（SPEC 已写明，实现未跟进）仍待确认。
