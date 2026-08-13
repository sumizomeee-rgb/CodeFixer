# 07 · 控件体系与浮层

> 本册覆盖跨页面复用的东西：按钮 / 表单 / 模态 / 抽屉 / Toast / 空态 / 加载态 / 徽章。
> 这些是"死板感"的分母——单页改得再好，控件不改，整体气质不变。

---

## 1. 按钮体系 【缺陷 E · 结构性问题】

### 1.1 现状全貌

全站按钮 CSS 只有这些（跨三个文件）：

```css
/* styles.css */
.icon-btn,.navrail button,.ghost{border:0;background:none;color:var(--muted)}
.icon-btn{width:34px;height:34px;border:1px solid var(--line);border-radius:9px}
.ghost{font-weight:600;font-size:12px}
.primary{width:100%;border:0;background:var(--text);color:var(--surface);font-weight:700;border-radius:9px;padding:10px}
.primary.compact{width:auto;padding:9px 14px}
/* product.css */
.ghost.framed{border:1px solid var(--line);border-radius:9px;padding:8px 11px;background:var(--surface);color:var(--muted)}
.framed:hover{color:var(--text);border-color:var(--lineStrong)}
.danger-button{border:1px solid color-mix(in srgb,var(--failed) 40%,var(--line));background:transparent;color:var(--failed);border-radius:9px;padding:9px 12px;font-weight:700}
.icon-btn{display:grid;place-items:center}
/* simplify.css */
.primary,.ghost.framed,.icon-btn,.project-step,.action-choice{min-height:40px}
.workbench-actions .primary{min-width:104px}
```

使用频次（TSX 统计）：`primary` ×13、`ghost` ×13、`compact` ×12、`framed` ×6、`icon-btn` ×4、`action-link` ×2、`danger-button` ×1。

### 1.2 五个问题

**① `.primary` 默认 `width:100%`，靠 `.compact` 救回。**

13 处 `primary` 里 12 处都跟着 `compact`。也就是说**默认值是错的**，每次都要打补丁。而 `.compact` 又被用在非 primary 的地方（`.ghost.compact`），语义混乱。

**② hover 态几乎没有。** 全站只有 8 条 hover 规则，其中：

| 有 hover | 无 hover |
|---|---|
| `.ghost.framed` | **`.primary`（主按钮！）** |
| `.task-row` | `.ghost`（裸文字按钮） |
| `.navrail button` | `.icon-btn` |
| `.agent-presets button` | `.danger-button` |
| `.project-step` | `.action-link` |
| `.action-choice` | `.filter-strip button` |
| `.concurrency-control button` | `.segmented button` |
| — | `.mode-controller` |

**`.primary` 是全站被点最多的按钮，鼠标移上去毫无反应**——这一条比任何配色问题都更直接地造成"死板"。

**③ active / pressed 态：全站 0 处。** 点下去没有任何位移或加深，按钮感觉不像实体。

**④ loading 态：不存在。** 「保存项目」「测试连接」「立即收单」「运行体检」都是要等后端的操作，现在点下去按钮外观不变，只有事后弹一条 notice。用户会重复点击。

`ProvidersPage.tsx:47` 的 `busy` state 只用来 disable，没有视觉：

```tsx
<button className="ghost framed" disabled={busy} onClick={()=>action(...)}>测试连接</button>
```

**⑤ disabled 态只有 `cursor:not-allowed`。** 唯一的视觉是 `.action-choice:disabled{opacity:.42}` 一处。其余 disabled 按钮**看起来完全可点**。

### 1.3 改法：三层按钮体系

新建 `frontend/src/components/button.css`。**不改 className**（避免大改 TSX），只重定义样式：

```css
/* ============ 基类 ============ */
.primary,.ghost,.ghost.framed,.danger-button,.icon-btn{
  --btn-h:36px;
  display:inline-flex;align-items:center;justify-content:center;gap:var(--s-2);
  height:var(--btn-h);padding:0 var(--s-4);
  border-radius:var(--r-sm);
  font:var(--t-body-sm);font-weight:600;
  white-space:nowrap;cursor:pointer;
  border:1px solid transparent;background:none;
  transition:background-color var(--d-fast) var(--e-standard),
             border-color var(--d-fast) var(--e-standard),
             color var(--d-fast) var(--e-standard),
             transform var(--d-instant) var(--e-standard),
             box-shadow var(--d-fast) var(--e-standard)
}
.primary:active:not(:disabled),
.ghost.framed:active:not(:disabled),
.danger-button:active:not(:disabled),
.icon-btn:active:not(:disabled){transform:translateY(1px)}

/* ============ Primary：主色实心 ============ */
.primary{
  width:auto;                                  /* ← 删掉 100% */
  background:var(--signal);color:#fff;
  border-color:var(--signal);
  box-shadow:0 1px 0 var(--signal-press)       /* 1px 硬边 = 实体感 */
}
.primary:hover:not(:disabled){background:var(--signal-hover);border-color:var(--signal-hover)}
.primary:active:not(:disabled){background:var(--signal-press);box-shadow:none}

/* 需要满宽时显式声明 */
.primary.block,.modal-actions .primary.block{width:100%}
```

> **`--signal` 做主 CTA 是本方案的关键决定之一**（见 [01 §2](01-direction.md)）。现在 `.primary{background:var(--text)}` 是近黑，橙色只用在描边和文字上——结果是**页面上最亮的颜色不在主动作上**。橙色实心按钮 + 灰色界面，主动作立刻自己浮出来。

```css
/* ============ Secondary（.ghost.framed）：描边 ============ */
.ghost.framed{
  background:var(--surface);color:var(--text-secondary);
  border-color:var(--line)
}
.ghost.framed:hover:not(:disabled){color:var(--text);border-color:var(--line-strong);background:var(--surface-2)}
.ghost.framed:active:not(:disabled){background:var(--surface-3)}

/* ============ Tertiary（裸 .ghost）：纯文字 ============ */
.ghost{padding:0 var(--s-2);color:var(--text-secondary);font-weight:500}
.ghost:hover:not(:disabled){color:var(--text);background:var(--surface-2)}

/* ============ Danger ============ */
.danger-button{
  background:var(--surface);color:var(--st-failed);
  border-color:color-mix(in srgb,var(--st-failed) 32%,var(--line))
}
.danger-button:hover:not(:disabled){background:var(--st-failed-soft);border-color:var(--st-failed)}

/* ============ Icon ============ */
.icon-btn{width:36px;height:36px;padding:0;border-color:var(--line);background:var(--surface);color:var(--text-secondary)}
.icon-btn:hover:not(:disabled){color:var(--text);border-color:var(--line-strong);background:var(--surface-2)}
.icon-btn .ui-icon{width:17px;height:17px}

/* ============ 尺寸 ============ */
.compact{--btn-h:32px;padding:0 var(--s-3);font-size:12px}   /* 语义改为"小号"，不再是"取消满宽" */
.large{--btn-h:42px;padding:0 var(--s-5);font-size:14px}

/* ============ Disabled（统一） ============ */
button:disabled{opacity:.45;cursor:not-allowed;box-shadow:none;transform:none!important}
button:disabled:hover{background:inherit;border-color:inherit;color:inherit}
```

> ⚠️ **迁移注意**：`.compact` 的语义从"取消 100% 宽"变成"小号"。改完后需要**扫一遍 12 处 `.compact` 使用点**——大部分在 `modal-actions` 和 `page-heading` 里，改成小号是合适的；`.primary.compact` 若某处需要标准尺寸，去掉 `compact` 即可。

### 1.4 Loading 态（新增）

```tsx
// frontend/src/components/Spinner.tsx
export const Spinner = ({size = 14}: {size?: number}) => (
  <span className="spinner" style={{'--sp': `${size}px`} as React.CSSProperties} aria-hidden="true" />
)
```

```css
.spinner{
  width:var(--sp,14px);height:var(--sp,14px);flex:none;
  border:2px solid currentColor;border-right-color:transparent;
  border-radius:var(--r-dot);opacity:.75;
  animation:spin .72s linear infinite
}
@keyframes spin{to{transform:rotate(360deg)}}
button[data-busy="1"]{pointer-events:none;position:relative}
button[data-busy="1"] .btn-label{opacity:.55}
@media (prefers-reduced-motion:reduce){
  .spinner{animation-duration:1.6s}    /* 不完全停 —— 这是"正在进行"的唯一信号 */
}
```

用法（`ProvidersPage.tsx:47`）：

```tsx
<button className="ghost framed compact" data-busy={busy === id ? '1' : undefined} disabled={!!busy}
        onClick={() => action(id, 'test')}>
  {busy === id && <Spinner />}
  <span className="btn-label">测试连接</span>
</button>
```

需要加 loading 的按钮清单（共 8 处）：

| 页面 | 按钮 | 后端耗时 |
|---|---|---|
| 来源页 | 测试连接 / 立即收单 / 保存来源 | 秒级 |
| 项目页 | 运行体检 / 保存项目 / 探测路径 | 秒级 |
| 设置页 | 重新检查 | 秒级 |
| 抽屉 | 开始处理 / 重试交付 / 取消 | 秒级 |

### 1.5 按钮排列顺序

现状 `modal-actions{justify-content:flex-end}`，顺序是 `[取消][确认]`——正确（Windows 惯例）。但：

- `.workbench-actions`（工作台底部）与 `.modal-actions` 的按钮尺寸不一致（`min-width:104px` vs 无）
- `.page-heading` 右侧动作没有统一 gap

统一：

```css
.modal-actions,.workbench-actions,.drawer-actions,.page-heading>div:last-child{
  display:flex;align-items:center;gap:var(--s-3);justify-content:flex-end
}
.modal-actions .primary,.workbench-actions .primary{min-width:96px}
```

---

## 2. 表单

见 [06 §2.2](06-pages-projects-providers-settings.md) 的完整 `controls.css`（checkbox / radio / select / input）。本节补三点。

### 2.1 label 与字段的关系不成立

现状（`ProjectsPage` / `ProvidersPage` 表单）：

```html
<label>定位资料路径</label>
<input .../>
```

`<label>` 没有 `htmlFor`，`<input>` 没有 `id`——**点击 label 不会聚焦字段**，屏幕阅读器也读不出字段名。

**改法**：抽一个 `Field` 组件，一次解决 label 关联 + 说明文字 + 错误态：

```tsx
// frontend/src/components/Field.tsx
let seq = 0
export function Field({label, hint, error, mono, children}:{
  label:string; hint?:string; error?:string; mono?:boolean; children:(id:string)=>React.ReactNode
}){
  const id = useMemo(() => `fld-${++seq}`, [])
  return (
    <div className={`field${error ? ' field-error' : ''}${mono ? ' field-mono' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {error ? <p className="field-msg" role="alert">{error}</p>
             : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  )
}
```

```css
.field{display:grid;gap:var(--s-2)}
.field>label{font:var(--t-micro);color:var(--text-secondary);letter-spacing:.01em}
.field-hint{font:var(--t-caption);color:var(--text-tertiary);margin:0;max-width:60ch}
.field-msg{font:var(--t-caption);color:var(--st-failed);margin:0;display:flex;gap:5px;align-items:center}
.field-msg::before{content:'';width:3px;height:3px;border-radius:var(--r-dot);background:currentColor;flex:none}
.field-error input,.field-error select,.field-error textarea{border-color:var(--st-failed);background:var(--st-failed-soft)}
.field-mono input{font-family:var(--font-mono);font-size:12px;letter-spacing:.01em}
```

### 2.2 表单没有校验反馈

现在只有"保存按钮 disabled"这一种反馈。字段级错误（路径不存在、URL 格式不对、并发数超范围）全部靠保存后的 `error-note` 红条。

**最小改进**：至少给三类字段做失焦即时校验——路径（非空 + 绝对路径格式）、URL（`http(s)://`）、数字范围。用 `.field-error` 样式呈现。

### 2.3 表单栅格

`.form-grid` / `.polished-form` / `.fact-grid` / `.fact-grid-simple` / `.action-config-stack` 五套布局类，规则各自散落。统一为两种：

```css
/* 双列：短字段（并发数、开关、枚举） */
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--s-4) var(--s-5)}
/* 单列：长字段（路径、URL、说明） */
.form-stack{display:grid;gap:var(--s-4);max-width:640px}
.form-grid .span-2{grid-column:1/-1}
```

**路径字段一律用 `form-stack`**——它们长到 `minmax(220px,1fr)` 里必然溢出。

---

## 3. 边界提示组件 `<BoundaryNote>`

见 [06 §3.4](06-pages-projects-providers-settings.md)。这是本产品**特有**的一类 UI，应该成为设计系统的一等公民：

```tsx
export function BoundaryNote({kind, children}:{kind:'secret'|'localpath'|'readonly'; children:React.ReactNode}){
  return (
    <div className={`boundary-note bn-${kind}`}>
      <BoundaryIcon kind={kind}/>
      <div>{children}</div>
    </div>
  )
}
```

三种 kind 用三种图标（锁 / 定位针 / 只读眼），**共用虚线边框**——虚线是"规则/约束"的视觉编码，与实线的"数据/内容"区分开。这一条建议写进规范（见 [10](10-spec-upgrade.md)）。

---

## 4. 模态 Modal

### 4.1 现状

```css
.modal-backdrop{position:fixed;inset:0;background:rgba(10,15,12,.42);backdrop-filter:blur(6px);z-index:50;display:grid;place-items:center;padding:24px}
.config-modal,.confirm-modal{width:min(700px,100%);background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:0 28px 90px rgba(0,0,0,.25);padding:24px}
.confirm-modal{width:min(480px,100%)}
.modal-head{display:flex;justify-content:space-between;align-items:start;margin-bottom:22px}
.modal-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:22px}
```

| # | 问题 | 严重度 |
|---|---|---|
| 1 | **无进出动画**——瞬间出现瞬间消失，最像"没做完"的一处 | 高 |
| 2 | **点背景不关闭**（`modal-backdrop` 无 onClick） | 中 |
| 3 | **Esc 不关闭**（全站无 keydown 监听） | 中 |
| 4 | **无焦点陷阱**——Tab 会跑到模态背后的页面上 | 中（无障碍） |
| 5 | **打开时 body 不锁滚动**——背景页面还能滚 | 中 |
| 6 | `rgba(10,15,12,.42)` 硬编码，暗色下遮罩偏亮 | 低 |
| 7 | `border-radius:18px` 超出四档 | 低 |
| 8 | 模态标题用 `h2{font-size:21px}`，与抽屉标题不同档 | 低 |

### 4.2 模式确认模态内容太薄 【规范欠账 §7】

`App.tsx:75` 全文：

```tsx
<h2>{mode==='automatic'?'切换到「待我开始」？':'切换到「全自动」？'}</h2>
<p>{mode==='automatic'?'之后收到的新问题会先等待确认，已经开始的任务不受影响。':'已收录且仍可处理的任务会自动进入队列。'}</p>
```

规范 §7 要求："切到全自动前的确认 sheet 必须展示**队列数 + ready 项目数 + 并发上限**"。

**这不是文案问题，是决策信息缺失**——用户切到全自动时，实际是在授权"接下来 N 个任务自动跑、最多 M 个并行、写入 K 个项目"。现在这三个数字一个都没有。

**改法**：

```tsx
{confirmMode && (
  <ModalShell onClose={() => setConfirmMode(false)} size="sm">
    <span className="modal-kicker">EXECUTION MODE</span>
    <h2>{automatic ? '切换到「待我开始」？' : '切换到「全自动」？'}</h2>

    {!automatic && (
      <dl className="confirm-facts">
        <div><dt>将自动进入队列</dt><dd><b>{queued}</b> 个任务</dd></div>
        <div><dt>可写入项目</dt><dd><b>{readyProjects}</b> / {totalProjects} 个就绪</dd></div>
        <div><dt>并发上限</dt><dd><b>{llmConcurrency}</b> 个并行调用</dd></div>
      </dl>
    )}
    {automatic && (
      <dl className="confirm-facts">
        <div><dt>新任务</dt><dd>等待你逐个开始</dd></div>
        <div><dt>已授权任务</dt><dd><b>{running}</b> 个继续运行</dd></div>
      </dl>
    )}

    <p className="confirm-note">
      {automatic ? '已经开始的任务不受影响，会跑到终态。'
                 : '自动执行仍受各项目的范围与验证策略约束。'}
    </p>

    <div className="modal-actions">
      <button className="ghost" onClick={close}>取消</button>
      <button className="primary" data-busy={saving?'1':undefined} onClick={toggleMode}>
        {saving && <Spinner/>}<span className="btn-label">{automatic ? '切到待我开始' : '开始全自动'}</span>
      </button>
    </div>
  </ModalShell>
)}
```

```css
.confirm-facts{display:grid;gap:0;margin:var(--s-5) 0;border-top:1px solid var(--line)}
.confirm-facts>div{display:flex;justify-content:space-between;align-items:baseline;padding:var(--s-3) 0;border-bottom:1px solid var(--line)}
.confirm-facts dt{font:var(--t-body-sm);color:var(--text-secondary);margin:0}
.confirm-facts dd{margin:0;font:var(--t-body-sm);color:var(--text)}
.confirm-facts dd b{font:600 17px var(--font-mono);font-variant-numeric:tabular-nums;margin-right:3px}
.confirm-note{font:var(--t-caption);color:var(--text-tertiary);margin:0}
```

**确认按钮文案改成动作本身**（"开始全自动" / "切到待我开始"），不用"确认"——用户扫一眼按钮就知道会发生什么，这是确认对话框的基本要求。

### 4.3 ModalShell 组件

三处模态（`confirm-modal`、`config-modal`、`editor-backdrop`）应共用一个壳：

```tsx
// frontend/src/components/ModalShell.tsx
export function ModalShell({onClose, size='md', children}:{onClose:()=>void; size?:'sm'|'md'|'lg'; children:React.ReactNode}){
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    const onKey = (e:KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
      if (e.key === 'Tab') trapFocus(e, ref.current)
    }
    document.addEventListener('keydown', onKey, true)
    ref.current?.querySelector<HTMLElement>('[autofocus],button,input,select')?.focus()
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = ''
      prev?.focus()
    }
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={`modal-panel modal-${size}`} role="dialog" aria-modal="true">{children}</div>
    </div>
  )
}
```

`onMouseDown` 而非 `onClick`——避免在面板内按下、拖到背景松开时误关闭（这是常见 bug）。

```css
.modal-backdrop{
  position:fixed;inset:0;z-index:50;
  display:grid;place-items:center;padding:var(--s-6);
  background:color-mix(in srgb,var(--canvas) 18%,rgba(8,11,10,.5));
  backdrop-filter:blur(3px) saturate(.85);
  animation:modalFade var(--d-standard) var(--e-standard)
}
.modal-panel{
  width:min(var(--mw,640px),100%);max-height:88vh;overflow:auto;
  background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-lg);box-shadow:var(--shadow-overlay);
  padding:var(--s-6);
  animation:modalRise var(--d-emphasis) var(--e-standard)
}
.modal-sm{--mw:460px}
.modal-md{--mw:640px}
.modal-lg{--mw:840px}
@keyframes modalFade{from{opacity:0}}
@keyframes modalRise{from{opacity:0;transform:translateY(10px) scale(.985)}}
.modal-panel h2{font:var(--t-title);margin:var(--s-2) 0 var(--s-3)}
:root[data-theme="dark"] .modal-backdrop{background:rgba(0,0,0,.62)}
```

> 关闭动画需要 `useTransition` 或延迟卸载。**优先级低**——打开有动画、关闭直接消失，感受上已经好很多。

---

## 5. 抽屉 Drawer

### 5.1 贴右修复 【实现硬伤】

见 [05](05-pages-dashboard-tasks.md)——`.drawer-backdrop{place-items:stretch end}` 覆盖了 `.modal-backdrop{place-items:center}`，但**父级的 `padding:24px` 没被重置成 0**（`.drawer-backdrop{padding:0}` 有写，需确认生效顺序）。截图 `08-task-drawer-*` 里抽屉右侧有一条缝。

```css
.drawer-backdrop{place-items:stretch end;padding:0;animation:modalFade var(--d-standard) var(--e-standard)}
.task-drawer{
  width:min(760px,92vw);height:100vh;overflow:auto;
  background:var(--surface);border-left:1px solid var(--line);
  padding:var(--s-6);box-shadow:var(--shadow-overlay);
  animation:drawerIn var(--d-emphasis) var(--e-standard)
}
@keyframes drawerIn{from{transform:translateX(24px);opacity:.4}}
```

`24px` 位移即可——抽屉是"滑出"，不是"飞入"。全宽位移在 760px 上会显得慢。

### 5.2 sticky 头部的负值 hack

```css
.task-drawer .modal-head{position:sticky;top:-28px;...;padding:14px 0}
```

`top:-28px` 是为了抵消 `.task-drawer{padding:28px}`。这个 hack 在 padding 改成 `var(--s-6)`(24px) 后会错位。

**改法**——头部脱离 padding，自己管：

```css
.task-drawer{padding:0}
.task-drawer .modal-head{
  position:sticky;top:0;z-index:2;
  padding:var(--s-5) var(--s-6);
  background:var(--surface);border-bottom:1px solid var(--line);
  margin:0
}
.task-drawer>*:not(.modal-head){padding-inline:var(--s-6)}
.task-drawer>*:last-child{padding-bottom:var(--s-10)}
```

同时**去掉 `backdrop-filter:blur(16px)`**——sticky 头下面滚过的是纯色卡片，模糊看不出效果，只增加合成层。

### 5.3 抽屉缺少的三件事

| # | 缺什么 | 为什么重要 |
|---|---|---|
| 1 | **上/下一个任务导航** | 排查时经常要连看多个失败任务，现在必须关掉抽屉→找到下一行→再打开 |
| 2 | **URL 同步**（`?task=tsk_xxx`） | 无法把某个任务的排查现场发给同事 |
| 3 | **底部固定动作条** | 「开始处理」「重试交付」现在在长内容中间，滚下去就找不到了 |

第 3 条的实现：

```css
.drawer-actions{
  position:sticky;bottom:0;z-index:2;
  display:flex;gap:var(--s-3);justify-content:flex-end;
  padding:var(--s-4) var(--s-6);
  background:var(--surface);border-top:1px solid var(--line);
  margin-top:var(--s-6)
}
```

---

## 6. 加载态 【缺陷 I · 规范欠账 §20】

### 6.1 现状：全站 0 个 skeleton

`grep -c 'skeleton\|spinner\|shimmer'` 三个 CSS 文件 → **0 / 0 / 0**。

所有加载态都是纯文字：

| 位置 | 现状 |
|---|---|
| 设置页 | `<p>正在读取配置…</p>` |
| 来源页 | **无** → 首次加载先闪一遍"还没有工单来源"空态 |
| 项目页 | **无** → 同样闪空态 |
| 任务页 | **无** → 闪"暂时没有任务" |
| 抽屉 | `<p>加载中…</p>` |

**"闪错误空态"是功能性缺陷**——用户会以为数据丢了。

### 6.2 Skeleton 组件

```tsx
// frontend/src/components/Skeleton.tsx
export const Skeleton = ({w, h = 12, r}: {w?: string|number; h?: number; r?: string}) => (
  <span className="sk" style={{width: w ?? '100%', height: h, borderRadius: r} as React.CSSProperties} aria-hidden="true"/>
)
export const SkeletonRows = ({n = 5, children}: {n?: number; children: React.ReactNode}) => (
  <div className="sk-rows" role="status" aria-label="加载中">
    {Array.from({length: n}, (_, i) => <div className="sk-row" key={i} style={{'--i': i} as React.CSSProperties}>{children}</div>)}
  </div>
)
```

```css
.sk{
  display:block;
  background:linear-gradient(90deg,var(--surface-2) 0 40%,var(--surface-3) 50%,var(--surface-2) 60% 100%);
  background-size:280% 100%;
  border-radius:var(--r-xs);
  animation:skShimmer 1.5s var(--e-signal) infinite
}
.sk-rows{display:grid}
.sk-row{
  display:grid;grid-template-columns:1fr auto;gap:var(--s-3);align-items:center;
  padding:var(--s-4) var(--s-5);border-bottom:1px solid var(--line);
  opacity:0;animation:skEnter var(--d-standard) var(--e-standard) forwards;
  animation-delay:calc(var(--i) * 45ms)               /* 逐行浮现 */
}
@keyframes skShimmer{to{background-position:-180% 0}}
@keyframes skEnter{to{opacity:1}}
@media (prefers-reduced-motion:reduce){
  .sk{animation:none;background:var(--surface-2)}
  .sk-row{animation:none;opacity:1}
}
```

**骨架必须与真实布局同构**——任务列表的骨架就是 5 行 `.task-row` 的形状，不是几个通用灰条：

```tsx
{loading ? (
  <SkeletonRows n={6}>
    <div style={{display:'grid',gap:6}}>
      <Skeleton w="42%" h={13}/>
      <Skeleton w="26%" h={10}/>
    </div>
    <Skeleton w={70} h={20} r="var(--r-pill)"/>
  </SkeletonRows>
) : rows.length ? rows.map(...) : <EmptyState .../>}
```

### 6.3 三态必须区分

```tsx
type Load<T> = {state:'loading'} | {state:'error'; message:string} | {state:'ready'; data:T}
```

现在四个页面都是 `const [items, setItems] = useState([])`，**loading 和 empty 无法区分**。这是造成"闪空态"的根因，必须从 state 层面改，不是加个 CSS 能解决的。

最小改动：加一个 `loaded` boolean。

---

## 7. 空态 【缺陷 I】

### 7.1 现状

```css
.empty-state{border:1px dashed var(--lineStrong);border-radius:18px;background:color-mix(in srgb,var(--surface) 65%,transparent);padding:70px 30px;text-align:center}
.empty-state h2{font-size:20px}
.empty-state p{max-width:520px;margin:10px auto 20px;color:var(--muted);line-height:1.7}
```

四个页面共用同一个虚线大盒 + 居中文字。70px 上下 padding 在 1000px 高的窗口里撑出一块巨大的空。

**更关键的问题**：空态没有区分**语义**。

| 页面 | 空的含义 | 应该说什么 |
|---|---|---|
| 首页 | **系统待命中**（正常状态） | 「轮询正常 · 等待新工单」+ 心跳 |
| 任务页（无筛选） | 同上 | 同上 |
| 任务页（有筛选） | **筛选条件无结果**（不是没数据） | 「当前筛选下没有任务」+ 清除筛选按钮 |
| 项目页 | **未完成配置**（需要行动） | 三步引导 |
| 来源页 | 同上 | 引导 + 两个来源类型入口 |

现在五种情况长得一模一样。

### 7.2 改法

```css
.empty-state{
  border:1px dashed var(--line-strong);border-radius:var(--r-lg);
  background:
    repeating-linear-gradient(45deg,color-mix(in srgb,var(--line) 22%,transparent) 0 1px,transparent 1px 9px),
    var(--surface);
  padding:var(--s-12) var(--s-8);
  display:grid;justify-items:center;gap:var(--s-3);text-align:center
}
.empty-state h2{font:var(--t-section);margin:0}
.empty-state p{font:var(--t-body);color:var(--text-secondary);max-width:46ch;margin:0}
.empty-state .kicker{font:var(--t-kicker);letter-spacing:.16em;text-transform:uppercase;color:var(--text-tertiary)}
.empty-state>button{margin-top:var(--s-3)}

/* 待命型（首页 / 任务页无筛选）：静，但有心跳 */
.empty-standby{padding:var(--s-10) var(--s-8)}
.empty-standby .standby-pulse{
  width:8px;height:8px;border-radius:var(--r-dot);background:var(--st-success);
  animation:pollBeat 3s var(--e-signal) infinite
}
/* 筛选无结果型：不用虚线大盒，只用一行 */
.empty-filtered{
  border:0;border-radius:0;background:none;padding:var(--s-10) 0;
  border-top:1px solid var(--line)
}
/* 引导型（项目 / 来源）：见 06 §1.4 */
```

45° 斜纹是「这块区域是空的、不是加载失败」的视觉编码（施工图纸里的留空表示法），比纯虚线框有性格，而且几乎不增加视觉噪音（22% 的 line 色）。

---

## 8. Toast

### 8.1 现状

```tsx
{toast && <button className="toast" onClick={() => setToast('')}>{toast}</button>}
```

```css
.toast{position:fixed;right:24px;bottom:24px;z-index:70;background:var(--text);color:var(--surface);border:0;border-radius:10px;padding:11px 14px;box-shadow:var(--shadow);font-weight:650}
```

| # | 问题 |
|---|---|
| 1 | **不自动消失**——`setToast('')` 只在点击时调用，成功提示会一直挂在右下角 |
| 2 | **无进出动画**——瞬间出现 |
| 3 | **不分成功/失败**——`'已切换为全自动'` 和 `'模式切换失败'` 长得完全一样（都是黑底白字） |
| 4 | **单条队列**——连续两次操作，第二条直接覆盖第一条 |
| 5 | `<button>` 语义错误，屏幕阅读器不会播报 |
| 6 | 与 xs 底部 tabbar 重叠（`bottom:24px` < tabbar 66px） |

第 1 条和第 3 条是实打实的可用性问题。

### 8.2 改法

```tsx
// frontend/src/components/Toast.tsx
type Toast = {id:number; kind:'ok'|'err'|'info'; text:string}
export function ToastHost({toasts, dismiss}:{toasts:Toast[]; dismiss:(id:number)=>void}){
  return (
    <div className="toast-host" role="region" aria-label="通知">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.kind}`} role={t.kind === 'err' ? 'alert' : 'status'}>
          <i aria-hidden="true"/>
          <span>{t.text}</span>
          <button className="toast-x" onClick={() => dismiss(t.id)} aria-label="关闭">×</button>
        </div>
      ))}
    </div>
  )
}
```

自动消失：成功 3.2s、信息 4.5s、**错误不自动消失**（错误信息用户需要读完、可能要复制）。

```css
.toast-host{
  position:fixed;right:var(--s-6);bottom:var(--s-6);z-index:80;
  display:grid;gap:var(--s-2);justify-items:end;pointer-events:none;
  max-width:min(420px,calc(100vw - var(--s-10)))
}
.toast{
  pointer-events:auto;
  display:grid;grid-template-columns:3px 1fr auto;align-items:center;gap:var(--s-3);
  padding:var(--s-3) var(--s-3) var(--s-3) 0;
  background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-sm);box-shadow:var(--shadow-float);
  font:var(--t-body-sm);color:var(--text);
  animation:toastIn var(--d-standard) var(--e-standard)
}
.toast i{align-self:stretch;border-radius:var(--r-sm) 0 0 var(--r-sm)}
.toast-ok   i{background:var(--st-success)}
.toast-err  i{background:var(--st-failed)}
.toast-info i{background:var(--signal)}
.toast-err{border-color:color-mix(in srgb,var(--st-failed) 30%,var(--line))}
.toast-x{border:0;background:none;color:var(--text-tertiary);cursor:pointer;font-size:16px;line-height:1;padding:0 4px}
.toast-x:hover{color:var(--text)}
@keyframes toastIn{from{opacity:0;transform:translateY(8px)}}
@media (max-width:560px){
  .toast-host{left:var(--s-4);right:var(--s-4);bottom:calc(66px + env(safe-area-inset-bottom,0px) + var(--s-3));max-width:none;justify-items:stretch}
}
```

**从黑底白字改为白底 + 左侧状态条**——理由：黑底 toast 与整个界面的纸张感冲突，而且黑底上没法用状态色。左侧 3px 色条与卡片信号栏、`.failure-effects` 是同一套语汇。

---

## 9. 徽章与状态 chip

现有的状态类：`.task-status`、`.status-pill`、`.delivery-status`、`.muted-tag`、`.path-chip`、`.delivery-tags`、`.badge`——**七套**，样式各不相同。

统一成一个 `StatusChip`：

```tsx
export function StatusChip({tone, shape='pill', children}:{
  tone:'success'|'nochange'|'warning'|'failed'|'reconcile'|'side'|'queued'|'signal'|'neutral'
  shape?:'pill'|'square'; children:React.ReactNode
}){
  return <span className={`chip chip-${tone} chip-${shape}`}>{children}</span>
}
```

```css
.chip{
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 8px;border-radius:var(--r-pill);
  font:var(--t-micro);font-weight:600;white-space:nowrap;
  border:1px solid transparent
}
.chip-square{border-radius:var(--r-xs);font-family:var(--font-mono);letter-spacing:.02em}
.chip::before{content:'';width:5px;height:5px;border-radius:var(--r-dot);background:currentColor;flex:none}
.chip-neutral::before{display:none}

.chip-success  {color:var(--st-success);  background:var(--st-success-soft);  border-color:color-mix(in srgb,var(--st-success) 22%,transparent)}
.chip-nochange {color:var(--st-nochange); background:var(--st-nochange-soft); border-color:color-mix(in srgb,var(--st-nochange) 22%,transparent)}
.chip-warning  {color:var(--st-warning);  background:var(--st-warning-soft);  border-color:color-mix(in srgb,var(--st-warning) 22%,transparent)}
.chip-failed   {color:var(--st-failed);   background:var(--st-failed-soft);   border-color:color-mix(in srgb,var(--st-failed) 22%,transparent)}
.chip-reconcile{color:var(--st-reconcile);background:var(--st-reconcile-soft);border-color:color-mix(in srgb,var(--st-reconcile) 22%,transparent)}
.chip-side     {color:var(--st-side);     background:var(--st-side-soft);     border-color:color-mix(in srgb,var(--st-side) 22%,transparent)}
.chip-signal   {color:var(--signal-text); background:var(--signal-soft);      border-color:var(--signal-line)}
.chip-queued,.chip-neutral{color:var(--text-secondary);background:var(--surface-2);border-color:var(--line)}
```

**用 `shape` 而非新颜色区分类型**：
- `pill` = 状态（处理中 / 已完成 / 失败）
- `square` + mono = 标识（`REDMINE` / `#48217` / `EV-003` / 文件路径）

---

## 10. 图标

`App.tsx` 里 5 个导航图标 + 若干内联 SVG，问题：

| # | 问题 | 改法 |
|---|---|---|
| 1 | `stroke-width` 不统一（1.5 / 1.6 / 1.8 / 2 混用） | 全部 `1.6`，`vector-effect:non-scaling-stroke` |
| 2 | 部分 `fill` 部分 `stroke` | 统一描边风格，`fill="none"` |
| 3 | viewBox 有 `0 0 24 24` 也有 `0 0 20 20` | 统一 24 |
| 4 | 硬编码颜色（`#d97757` / `#4f8b73`） | 全部 `currentColor` |
| 5 | 内联在 TSX 里，重复定义 | 抽到 `components/icons.tsx` |

```css
.ui-icon{width:17px;height:17px;flex:none;stroke:currentColor;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
```

**图标风格建议**：现在的图标偏"通用 SaaS 线性图标"。配合工业方向，建议**改为更几何、更硬的画法**——直角转折代替圆角、线段代替曲线。这一条优先级低，但收益在于整体气质统一。

---

## 11. 验收 checklist

**按钮**
- [ ] `.primary` 是橙色实心，不是近黑
- [ ] `.primary` 默认宽度自适应，不需要 `.compact` 救
- [ ] 所有按钮有 hover + active 态
- [ ] 8 个异步按钮有 spinner
- [ ] disabled 按钮明显看得出不可点
- [ ] focus 环对比度 ≥ 3:1，覆盖所有可聚焦元素

**表单**
- [ ] checkbox / radio / select 无浏览器默认样式
- [ ] label 与字段用 `htmlFor` 关联，点 label 能聚焦
- [ ] 路径 / 密钥字段用 mono
- [ ] 有字段级错误态

**浮层**
- [ ] 模态有进入动画
- [ ] Esc 关闭、点背景关闭、焦点陷阱、锁 body 滚动
- [ ] 模式确认模态显示队列数 / 就绪项目数 / 并发上限
- [ ] 确认按钮文案是动作本身，不是"确认"
- [ ] 抽屉严丝合缝贴右边缘
- [ ] 抽屉底部有固定动作条

**加载与空**
- [ ] 四个页面首次加载显示 skeleton，不闪空态
- [ ] skeleton 形状与真实内容同构
- [ ] 空态按语义分五种，不共用一个虚线大盒
- [ ] 待命型空态有心跳

**Toast**
- [ ] 成功 toast 3 秒后自动消失，错误 toast 不消失
- [ ] 成功与失败视觉可区分
- [ ] 支持多条堆叠
- [ ] xs 下不与 tabbar 重叠

**chip / 图标**
- [ ] 七套状态样式合并为一个 `.chip`
- [ ] 状态用 pill、标识用 square+mono
- [ ] 图标 stroke-width 全站 1.6，颜色全部 currentColor
