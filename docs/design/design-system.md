# CodeFixer Web 设计系统与交互规范

> 文档状态：V2 · Industrial Repair Ledger
> 最后更新：2026-08-13
> 关联：`docs/design-spec.md`、`docs/engineering-readiness-spec.md`

## 1. 设计目标

CodeFixer 的 Web 不是传统 CRUD Admin，也不是“AI 聊天窗口 + 日志”。

产品视觉应表达三个核心概念：

1. **维修**：问题被定位、拆解、修复、验证和交付。
2. **控制塔**：系统持续运行，用户主要观察、理解和在关键时刻介入。
3. **证据**：所有成功、失败和 `no_change` 都有可展开的事实链，而不是模型情绪化结论。

最终体验应同时满足：

- 高信息密度。
- 一眼可读的运行态。
- 足够强的品牌识别。
- 长时间挂屏不疲劳。
- 明/暗主题都成立。
- 动效服务于状态理解，不做装饰性炫技。

## 2. 视觉概念：Industrial Repair Ledger

CodeFixer 是一台无人值守的修复机床，也是一本保存每次处理证据的维修账。它使用一套“Repair Signal”视觉语言，把持续收单、机器施工、变更封存串成同一条叙事。

核心不是拟物化扳手或机器人，而是：

- 连续诊断轨道。
- 信号节点。
- 冻结产物的“封存”语义。
- 外部副作用的“越界输出”语义。
- 可追踪的证据引用。
- 局部扫描/脉冲动效。
- 账本式横线、固定栏目与左侧状态边。
- 铭牌式微标签与对齐的机器数据。

品牌感来自结构、节奏和状态表达，而不是大面积插画。

视觉锚点是示波器、维修台账和机床铭牌。明确排除蓝紫玻璃拟态、满屏柔和卡片、拟物齿轮与无意义装饰动画。

### 2.1 视觉关键词

- precise
- kinetic
- engineered
- calm under load
- traceable
- slightly futuristic
- not cyberpunk
- not generic SaaS
- not Material clone

## 3. 色彩系统

所有产品语义颜色必须通过 semantic token 使用，组件禁止直接写业务状态色值。第三方来源/Agent 可在小面积识别标记内保留受控品牌色，但不得代替健康状态色。

### 3.1 Neutral

Light：

```text
canvas            #F5F6F4
surface-1         #FFFFFF
surface-2         #F0F2EF
surface-raised    #FFFFFF
line              #D8DCD6
line-strong       #B7BDB5
text-primary      #171A17
text-secondary    #5D655F
text-tertiary     #858D87
```

Dark：

```text
canvas            #0E1110
surface-1         #141817
surface-2         #1B201E
surface-raised    #202624
line              #2B322F
line-strong       #3A4440
text-primary      #EDF1ED
text-secondary    #AAB3AD
text-tertiary     #77817B
```

### 3.2 Signature Accent

CodeFixer 主识别色定义为 `signal`，使用偏暖的高能橙红，而不是常见 SaaS 蓝紫：

```text
signal-50    #FFF1EC
signal-100   #FFD8CC
signal-300   #FF9A7A
signal-500   #F4603C
signal-600   #DA4C2C
signal-700   #B83B20
```

用途：

- 全局执行模式控制器。
- 当前正在工作的关键 Rail node。
- Primary action。
- 品牌 mark。
- 聚焦的当前 Task。

禁止把所有卡片都涂成 signal。

### 3.3 Status Semantic

```text
status-running        signal
status-success        #36A26B
status-no-change      #3C8C91
status-warning        #D69A32
status-failed         #D94A55
status-canceled       neutral
status-reconciling    #7D68C7
status-side-effect    #C258A0
```

`no_change` 必须拥有独立颜色，不与 success 完全相同，因为业务含义不同。

`partial_delivery` 使用 failed 主语义 + side-effect 辅助语义，不创造“半成功绿”。

### 3.4 对比度

- 正文和关键状态文本必须满足可读对比。
- 颜色不是状态唯一载体；必须同时有形状、图标或文字。
- 在 Light/Dark 两主题分别验证，不允许简单反色。

## 4. 字体与数字

### 4.1 字体角色

- UI 正文与中文标题：仓库内依赖的 `Noto Sans SC`，英文回退/搭配 `IBM Plex Sans`。
- 数据、代码、SHA、耗时、ID 与机器微标签：`IBM Plex Mono`。
- 中文不使用负字距，也不强行套用不含中文字形的 Mono；英文机器标签可使用 `.12em–.16em` 字距。
- 字体随前端依赖打包，禁止依赖部署机预装字体或运行时外部 CDN。

### 4.2 Type Scale

```text
display        36/43, 600
page-title     30/36, 600
section-title  18/24, 600
body           14/22, 400
body-strong    14/22, 600
caption        12/18, 500
micro          10/14, 600（全站可见文字下限）
mono           11/17, 500
```

### 4.3 Tabular Data

耗时、费用、计数、并发槽、commit 数使用 tabular numerals，避免实时变化导致布局抖动。

## 5. Layout

### 5.1 Desktop First

第一版主目标是工程师桌面浏览器。

主 baseline：

```text
1440 × 900
```

同时保证：

```text
1280 × 720
1024 × 768
```

可用。

低于 960px 进入 compact desktop，不承诺完整手机端第一版体验，但不能内容溢出不可操作。

### 5.2 App Shell

推荐：

```text
┌────────────────────────────────────────────────────────────┐
│ Global Command Bar / Mode Controller / Health              │
├────────────┬───────────────────────────────────────────────┤
│ Nav Rail   │ Page                                          │
│            │                                               │
│            │                                               │
└────────────┴───────────────────────────────────────────────┘
```

左侧导航是固定的文字信号栏，不依赖 hover 才能理解：

- `>1080px`：188px，图标与文字始终可见。
- `721–1080px`：78px，图标与短文字上下排列，不能只剩无文字图标。
- `≤720px`：底部三项 tabbar（任务 / 流水线 / 设置），内容区必须预留其高度与安全区。
- 健康心跳放在侧栏底部；顶部保留品牌、全局授权模式和主题控制。
- 内容区宽度充分留给 timeline/diff，背景可使用低对比 32px 工程格线，不使用噪点贴图。

顶部全局模式控制器始终具有强识别，但不应像危险的巨大红色按钮长期抢占视线。

## 6. Signature Component：StageRail

StageRail 是 CodeFixer 最重要的产品视觉组件。

它不是普通 Stepper。

### 6.1 信息

业务主轨固定为八个可理解阶段：准备、范围、定位、评估、修复、验证、复核、交付。每个节点可表达：

- stage ID。
- 状态。
- attempt 数。
- 实际耗时。
- 当前 runner/agent。
- 是否产生 Artifact。
- 是否发生 repair loop。
- 是否有 failure/side effect。

`workspace_prepare`、`no_change_verify`、`pre_delivery_check`、`freeze_change` 等技术阶段不得丢失，但进入任务详情的“原始阶段”账本；关键分支另外通过 NoChangeSurface / FrozenChange 表达。不得为了技术完整性把主轨压成十二个难以阅读的节点。

### 6.2 形态

基础：

```text
●━━●━━◉──○──○
P  D  R  V  R
```

实际 UI 使用：

- 已完成：实心节点 + 连续实线。
- 当前：双层节点，内核缓慢 pulse。
- queued：空心节点。
- skipped：短虚线与斜杠。
- failed：节点断开并在断点处显示 error notch。
- reconciling：旋转不是 spinner，而是沿节点边缘的慢速 traveling signal。
- superseded：整段 rail 降低不透明度并显示新的 run 分叉引用。

### 6.3 Repair Loop

`repair → verify → review → repair` 不得在 Rail 上假装成一次线性通过。

呈现为主轨道下方的 loop band：

```text
Repair #1 → Verify #1 → Review #1
   ↑                       │ needs_repair
   └──── Repair #2 ←───────┘
```

详情页可展开每轮；任务卡仅显示：

```text
Repair loop ×2
```

### 6.4 Motion

当前阶段的 Rail 信号以低频运动表现“系统仍活着”。

禁止：

- 无限高速流光。
- 全屏粒子。
- 每个卡片都同时发光。
- loading 时改变布局。

`prefers-reduced-motion` 下改为静态强调。

## 7. Signature Component：Execution Mode Controller

这是全局最重要的用户授权控件。

语义：

```text
待我开始  ←→  全自动
```

不是普通 toggle。

### 7.1 待我开始

视觉更沉静。

显示：

- 当前收录仍进行。
- 待开始数量。
- “不会调用 Agent/修改代码/交付”的简短说明。

### 7.2 切到全自动

如果已有待开始任务：

必须先打开确认 sheet/dialog，展示：

- 将进入队列的任务数量。
- 当前 ready/not-ready 流水线数量。
- 并发上限。
- 不会绕过验证与 Review。

确认后控制器发生一次明确但短促的“signal engage”动画。

### 7.3 从全自动切回

不暗示正在运行的任务会被取消。

控件旁明确：

```text
新任务将等待开始 · 3 个已授权任务继续运行
```

## 8. 任务行与两级结果弹窗

任务行必须首先回答：

1. 这是什么 Bug？
2. 现在在哪？
3. 是否需要我处理？
4. 终态结论是什么？

结构建议：

```text
状态       工单与标题                              进展
处理中     #248625  商城礼包购买后红点未刷新       Repair · 02:41  →
已完成     #248626  阵容卡片匹配度异常             已修复          →
```

任务列表不显示 Patch 路径、Commit SHA、远端分支或文件清单。点击任务行打开一级“任务结论”弹窗；已修复任务从一级弹窗再进入替换式二级“交付结果”弹窗，禁止两个模态层叠放。

一级弹窗阅读顺序固定为：结论、原因、修复方案、验证状态。每段只承载一个问题，原因和方案各不超过两句。运行中则显示阶段轨道，不生成虚假结论占位。

二级弹窗顶部只突出交付状态与下一步，动作结果使用紧凑行；SHA、分支、hash 等进入技术折叠区。最后固定展示相对仓库根目录的“修改文件”清单。

失败卡优先替换中部信息为：

```text
Verify 失败
2/5 required checks failed
建议：查看 build stderr 后重新运行
```

## 9. FailureSurface

失败不是红色 Toast。

FailureSurface 是标准产品组件。

必须展示顺序：

1. 用户可读 summary。
2. stage / failure code。
3. 影响：是否产生外部副作用。
4. retryable。
5. suggested action。
6. evidence/log links。
7. 原始 stderr（折叠）。

高风险 side effect 使用独立 `side-effect` 标记。

例如：

```text
GitLab 推送结果不确定
当前不能安全重推同名任务分支。

可能存在：
  branch  codefixer/B1250062/a81c3312
  commit  a81c3312（未确认远端可达）

系统将继续按远端分支 SHA 对账；请不要手工覆盖。
```

## 10. NoChangeSurface

`no_change` 不是“绿色勾 + 不需要修改”。

必须展示证据结构：

```text
无需修改 · already_fixed

Current baseline   8f43a17
Evidence           3
Verification       Passed
Independent review Approved

Why
当前调用链已包含工单描述的 null guard...

Related fix
commit ...
```

颜色使用 no-change teal，避免与 changed success 混淆。

## 11. Freeze Change

`freeze_change` 是视觉上的关键转折。

Repair/Verify/Review 属于“可变施工区”。

Freeze 后进入“封存交付区”。

详情页在该节点用细微的双线/锁定符号表达：

```text
Candidate
   ↓
╔═ Frozen Change v2 ═════════╗
 diff SHA ...
 4 files
 verification ✓
 review ✓
╚═════════════════════════════╝
   ↓
Delivery
```

“冻结”不使用大锁图标拟物化；通过边框、checksum 和 immutable 标签建立语义。

## 12. Delivery Visual Language

### 12.1 Patch

Patch 是本地 Artifact。

显示：

- filename。
- hash 短值。
- size。
- created time。
- download/open action。

### 12.2 GitLab Push

一个动作只有一个远端任务分支和一个交付 Commit：

```text
推送到 GitLab                         已完成
在 GitLab 查看 Commit  →
下一步：在 GitLab Web 选择目标分支并 Cherry-pick
```

不要在可见主层重复显示 SHA、分支名和 Commit URL；它们进入“技术信息”，主操作本身链接到 Commit。GitLab Push 没有 assignee、目标分支和部分成功。

### 12.3 修改文件

二级交付弹窗最后固定展示：

```text
修改文件 · 3
M  Script/Module/TargetOverview.lua
M  Script/Module/FormationCard.lua
A  Test/Module/FormationCardTest.lua
```

- 路径相对仓库根目录，不带分支名、仓库名或本机盘符。
- 目录使用弱化文字，文件名保持主文字；统一 `/`。
- 长路径中段省略但保留完整可复制值；悬停显示完整路径。
- 点击复制完整路径，并用不改变控件高度的原位反馈提示成功。
- 超过 12 行时列表内部滚动，同时提供“复制全部路径”。

### 12.4 Side Effects

远程 branch、Commit、GitHub PR、materialization ref 都可以进入 SideEffectList。

Side effect ≠ error；它描述已经发生且需要审计的外部事实。

## 13. Evidence UI

EvidenceRef 使用可复用 EvidenceChip / EvidenceRow。

类型图形语言：

- source：code glyph。
- history：commit glyph。
- ticket：ticket glyph。
- attachment：attachment glyph。
- verification：check glyph。

点击不直接跳转离开页面，优先打开 side inspector；外部 URL 再提供明确“打开外部”。

引用显示稳定 ID：

```text
EV-003 · source
XShopManager.lua:142–168
```

## 14. Diff

Diff 是任务详情关键面。

要求：

- unified / split 可切换。
- 文件列表与 diff 联动。
- add/modify/delete/rename 明确。
- 大 diff 虚拟滚动或按文件懒加载。
- 当前 Review issue 可以锚定到文件/行。
- 不把语法高亮颜色与 status 色混用。

Diff header 固定显示：

- change version。
- base revision。
- diff hash。
- file count。
- verification/review status。

## 15. Motion Tokens

```text
motion-instant     80ms
motion-fast        140ms
motion-standard    220ms
motion-emphasis    360ms
motion-signal      1200–1800ms loop
```

Easing：

```text
standard   cubic-bezier(.2,.8,.2,1)
exit       cubic-bezier(.4,0,1,1)
spring-like 仅用于小范围 mode/rail，不使用真实弹簧过冲影响可读性
```

规则：

- hover 不超过 fast。
- panel transition 用 standard。
- mode engage 可用 emphasis。
- running signal 是低频 loop。
- 数字变化不弹跳。
- 新事件进入 timeline 可使用轻微 translate + fade。
- 失败不 shake 整个页面。

第一版只实现四类有业务含义的运动：运行节点呼吸、对账信号沿轨道行进、Frozen Change 状态硬化、Drawer/Dialog/Toast 进入退出。不得按动画数量凑验收指标；空闲页除侧栏低频心跳外保持静止。

## 16. Surface 与圆角

避免“满屏圆角卡片”。

建议：

```text
radius-sharp   3
radius-sm      7
radius-md      11
radius-overlay 16
```

大多数工作区使用 `sm/md`。

只有 Dialog、浮层使用 `overlay`。`999px` 只允许执行模式控制器；状态标识和列表行不得做成胶囊。

列表中的连续信息优先通过线、分组和间距组织，不把每一行包进独立胶囊。

## 17. Shadow

暗色主题尤其避免重阴影。

层级主要靠：

- surface tone。
- border。
- spacing。
- 少量 shadow。

只有浮层、dialog、popover 使用明显 shadow。

## 18. Icon

统一使用一套线性 icon 库作为基础，但 CodeFixer 至少有自定义：

- CodeFixer mark。
- StageRail node glyph。
- freeze/change mark。
- side-effect indicator。
- execution mode glyph。

禁止大量 emoji 作为正式图标。

## 19. 空态

空态不是营销插画。

示例：

### 没有任务

```text
这本任务账还是空的
界面更新于 18 秒前 · 新问题进入后会出现在这里
```

### 没有失败

```text
当前没有需要处理的失败
```

### 流水线未配置

给具体下一步：

```text
还没有可以收问题的流水线
新增流水线时可以直接接入 Redmine 或 TAPD，并继续配置定位、修改、验证和交付。
[新增流水线]
```

## 20. Loading

优先 skeleton，且布局与最终内容一致。

实时状态请求使用局部 signal，不使用全屏 spinner。

超过 1 秒才出现用户可读 loading caption。

## 21. Toast

Toast 只用于瞬时操作反馈：

- 设置已保存。
- 已请求取消。
- 已复制 hash。

任务运行失败、MR partial success、readiness failed 不允许只靠 Toast 表示；必须进入持久 UI。

## 22. Dialog 与危险操作

需要二次确认：

- 切换到全自动且会排队已有任务。
- 取消 running task。
- rerun 会产生新外部动作版本。
- 删除本地产物。
- 清理已知远程 side effect（若未来实现）。

Dialog 必须说出结果，不写：

```text
确定吗？
```

而写：

```text
取消正在运行的 Task #248625？
当前 Repair Agent 将被终止，未交付修改会被清理。
```

## 23. Accessibility

最低要求：

- 所有交互可键盘操作。
- focus ring 不被 `outline:none` 吞掉。
- 状态不只依赖颜色。
- Dialog 正确 focus trap/restore。
- Tooltip 不是唯一信息来源。
- icon-only action 有 accessible name。
- Rail 可用文本/ARIA 读取阶段与状态。
- reduced motion。
- 不用低对比灰字展示重要失败原因。

## 24. 主题

主题：

```text
light
dark
```

主题控制器只在浅色与深色之间切换，点击一次必须立即得到相反主题；用户选择保存在浏览器。这里不提供“跟随系统”第三态，避免控制结果不确定。

主题切换不能刷新页面。

Design Token 使用 CSS custom properties；组件禁止在 JSX 中通过三元表达式复制两套色值。

## 25. Visual Regression Baselines

第一版至少冻结：

```text
task-list-running
task-list-failed
task-detail-changed
task-detail-no-change
task-detail-repair-loop
task-detail-partial-delivery
pipeline-preflight-ready
pipeline-preflight-failed
execution-mode-confirm
```

动态内容使用 fixture + fixed clock。

默认 golden 环境：

- Linux。
- Chromium。
- 固定 viewport。
- 固定字体环境。
- reduced animations/test clock。

每个 baseline 必须由固定 fixture 提供数据。业务状态断言与截图断言分开；不能用当前开发数据库碰巧存在的数据充当 golden。优先冻结任务运行/失败/无需修改详情、流水线体检与执行模式确认，再扩到任务、流水线、设置三页的四档响应式。

Golden 更新必须人工明确执行 update snapshot，并审阅 diff。

## 26. 页面设计优先级

### P0

- AppShell。
- Task List。
- Task Detail。
- Pipeline List / Editor。
- Pipeline Preflight。
- Execution Mode Controller。

### P1

- Ticket Providers。
- Agent/Knowledge。
- Final Actions。
- Settings。
- Artifact inspector。

### P2

- 成本/指标深度分析。
- 高级过滤保存。
- Timeline compare。

## 27. Phase 0 必须完成的组件

Design primitives 按真实复用建立，不以“文件数量”作为完成标准。第一批需要稳定的语法包括：

- Button。
- IconButton。
- Input。
- Select。
- SegmentedControl。
- Dialog。
- Tooltip。
- Popover。
- Surface。
- Divider。
- Badge。
- StatusDot。
- Skeleton。
- CodeText。

Product patterns：

- ExecutionModeController。
- StageRail。
- TaskCard。
- FailureSurface。
- NoChangeSurface。
- EvidenceRow。
- SideEffectBadge。
- ArtifactRow。
- PreflightCheckRow。

这些组件先用 fixtures 构建和测试，不等待真实 API。

## 28. 视觉验收原则

不接受以下完成标准：

- “功能都有，之后再统一美化”。
- “套一个 Admin Template 先跑起来”。
- “用状态颜色就算设计系统”。
- “页面截图差异太多所以关掉 visual test”。

接受的迭代方式：

- Phase 0 定语法。
- 各阶段按语法实现。
- 阶段六统一 polish，而不是推倒重做。

最终视觉是否优秀仍需要人工审美验收；自动视觉回归负责确保“已经批准的优秀视觉不会被后续改坏”，而不是替代设计判断。
