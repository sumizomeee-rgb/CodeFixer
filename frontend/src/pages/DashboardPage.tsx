import { StageRail } from '../design-system/StageRail'

function Metric({value,label,tone='default'}:{value:string,label:string,tone?:string}) {
  return <div className={`metric metric-${tone}`}><span>{value}</span><small>{label}</small></div>
}

function TaskCard({id,title}:{id:string,title:string}) {
  return <article className="task-card">
    <div className="task-top"><div><span className="ticket">{id}</span><h3>{title}</h3></div><span className="status-pill running">施工中</span></div>
    <div className="task-meta"><span>Product / Lua</span><span>Git · trunk@8a31c42</span><span>Claude Code</span></div>
    <StageRail />
    <div className="task-footer"><span>Repair loop ×1</span><span className="mono">elapsed 03:11</span></div>
  </article>
}

export function DashboardPage() {
  return <>
    <section className="hero"><div><span className="eyebrow">WED · AUG 12</span><h1>维修控制台</h1><p>把每一个 Bug 变成有证据、可验证、可交付的修复。</p></div><div className="slots"><span>并发槽</span><b>2 / 3</b><div className="slotbar"><i/><i/><i className="empty"/></div></div></section>
    <section className="metrics"><Metric value="12" label="24h 已交付" tone="success"/><Metric value="3" label="运行中" tone="running"/><Metric value="2" label="无需修改" tone="nochange"/><Metric value="1" label="需要处理" tone="failed"/><Metric value="$4.82" label="Agent 费用"/></section>
    <section className="content-grid"><div><div className="section-head"><div><span className="signal-kicker">LIVE SIGNAL</span><h2>正在维修</h2></div><button className="ghost">查看全部 18 →</button></div><div className="task-stack"><TaskCard id="TAPD #124902" title="【4.7】【商城】购买礼包后偶现红点未刷新"/><TaskCard id="RM #98142" title="切换角色后音频遮挡参数未恢复"/></div></div>
    <aside className="attention"><div className="section-head"><div><span className="signal-kicker">ATTENTION</span><h2>需要处理</h2></div></div><div className="failure-card"><span className="failure-code">GITLAB · PARTIAL DELIVERY</span><h3>2 / 3 个目标分支已创建 MR</h3><p>release/4.7 在 cherry-pick 时产生冲突。已成功的 MR 保留，不会重复创建。</p><div className="side-effects"><b>外部副作用</b><span>✓ trunk · MR !4812</span><span>✓ release/4.6 · MR !4813</span><span className="bad">× release/4.7 · conflict</span></div><button className="primary">查看并重试失败目标</button></div>
    <div className="evidence-card"><span className="signal-kicker teal">NO CHANGE</span><h3>当前基线无需修改</h3><p>已有 2 项当前状态证据，并通过独立 Review。</p><div className="evidence-row"><span>基线</span><code>4d92e9a</code></div><div className="evidence-row"><span>证据</span><b>2 / 2</b></div></div></aside></section>
  </>
}
