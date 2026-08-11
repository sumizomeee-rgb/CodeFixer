import { useEffect, useState } from 'react'
import type { TaskRecord } from '../entities/task'
import { api } from '../lib/api'

const labels:Record<string,string>={awaiting_start:'待开始',queued:'排队',running:'运行中',cancel_requested:'取消中',completed:'已完成',failed:'失败',canceled:'已取消'}

export function TasksPage(){
  const [items,setItems]=useState<TaskRecord[]>([]); const [selected,setSelected]=useState<TaskRecord|null>(null); const [error,setError]=useState('')
  const load=async()=>{try{setItems((await api.tasks()).items)}catch(e){setError(e instanceof Error?e.message:'任务加载失败')}}
  useEffect(()=>{void load()},[])
  const open=async(id:string)=>{try{setSelected(await api.task(id))}catch(e){setError(e instanceof Error?e.message:'详情加载失败')}}
  const act=async(kind:'start'|'cancel')=>{if(!selected)return;try{const next=kind==='start'?await api.startTask(selected.id):await api.cancelTask(selected.id);setSelected(next);await load()}catch(e){setError(e instanceof Error?e.message:'操作失败')}}
  return <section className="page-stack"><div className="page-heading"><div><span className="eyebrow">TASK FACTS</span><h1>任务</h1><p>Task 是外部 Bug 的长期事实；Run、事件和证据不会因为服务重启而消失。</p></div><button className="ghost" onClick={()=>void load()}>刷新 ↻</button></div>{error&&<div className="inline-alert">{error}</div>}
    {items.length===0?<div className="empty-state"><span className="empty-mark">≡</span><h2>还没有任务</h2><p>配置工单来源后，新 Bug 会按项目路由进入这里。待我开始模式只收录，不调用 Agent。</p></div>:<div className="task-table">{items.map(task=><button key={task.id} className="task-row" onClick={()=>void open(task.id)}><span className={`task-status task-${task.status}`}>{labels[task.status]??task.status}</span><span><small>{task.provider_instance_id} · #{task.external_ticket_id}</small><b>{task.title}</b></span><code>{task.project_id}</code><span className="row-arrow">→</span></button>)}</div>}
    {selected&&<div className="modal-backdrop"><div className="task-drawer" role="dialog" aria-modal="true"><div className="modal-head"><div><span className="ticket">{selected.provider_instance_id} #{selected.external_ticket_id}</span><h2>{selected.title}</h2></div><button className="icon-btn" onClick={()=>setSelected(null)} aria-label="关闭">×</button></div><div className="fact-grid"><div><small>状态</small><b>{labels[selected.status]}</b></div><div><small>项目</small><b>{selected.project_id}</b></div><div><small>Task ID</small><code>{selected.id}</code></div><div><small>当前 Run</small><code>{selected.current_run_id||'—'}</code></div></div>{selected.status==='awaiting_start'&&<button className="primary compact" onClick={()=>void act('start')}>开始完整流程</button>}{['queued','running'].includes(selected.status)&&<button className="danger-button" onClick={()=>void act('cancel')}>取消任务</button>}<div className="timeline"><span className="signal-kicker">EVENT TIMELINE</span>{selected.events?.map(event=><div className="event" key={event.id}><i/><div><b>{event.event_type}</b><small>{event.created_at}</small></div></div>)}</div></div></div>}
  </section>
}
