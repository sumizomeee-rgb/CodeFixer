import { useEffect, useMemo, useState } from 'react'
import { StageRail, type StageItem, type StageState } from '../design-system/StageRail'
import type { DeliveryAction, StageRun, TaskRecord, TaskRun } from '../entities/task'
import { api } from '../lib/api'

const labels:Record<string,string>={awaiting_start:'待开始',queued:'等待中',running:'处理中',cancel_requested:'正在取消',completed:'已完成',failed:'失败',canceled:'已取消'}
const stageLabel:Record<string,string>={prepare:'准备',scope_discovery:'范围',discovery:'定位',no_change_verify:'确认',repair:'修复',verify:'验证',review:'复核',pre_delivery_check:'检查',freeze_change:'冻结',deliver:'交付'}
const state=(value:string):StageState=>value==='completed'?'done':value==='running'?'running':value==='failed'?'failed':value==='reconciling'?'reconciling':value==='canceled'?'skipped':'queued'
const resultLabel=(value:string|null|undefined)=>value==='no_change'?'无需修改':value==='changed'?'已修复':'—'
function meta(stage:StageRun){if(stage.started_at&&stage.finished_at){const ms=new Date(stage.finished_at).getTime()-new Date(stage.started_at).getTime();return ms<1000?'完成':`${Math.max(1,Math.round(ms/1000))} 秒`}return stage.status==='running'?'进行中':''}
function stageRail(run:TaskRun):StageItem[]{const order=['prepare','scope_discovery','discovery','repair','verify','review','deliver'];const latest=new Map<string,StageRun>();for(const item of run.stages??[])latest.set(item.stage_id,item);return order.map(id=>{const item=latest.get(id);return{label:stageLabel[id]??id,meta:item?meta(item):'',state:item?state(item.status):'queued'}})}
const deliveryStatus=(value:string)=>value==='completed'||value==='success'?'已完成':value==='failed'?'失败':value==='partial_success'?'部分完成':value==='running'?'处理中':value==='queued'?'等待中':value
const deliveryType=(value:string)=>value==='patch'?'补丁':value==='gitlabMr'?'GitLab 合并请求':value
function Delivery({action}:{action:DeliveryAction}){return <div className={`delivery-card delivery-${action.status}`}><div><b>{deliveryType(action.action_type)}</b></div><span className="delivery-status">{deliveryStatus(action.status)}</span>{action.targets?.map(t=><div className="delivery-target" key={t.id}><span>{t.target_key}</span><span>{deliveryStatus(t.status)}</span>{t.external_url?<a href={t.external_url} target="_blank" rel="noreferrer">打开</a>:null}</div>)}</div>}

export function TasksPage(){
 const[items,setItems]=useState<TaskRecord[]>([]);const[selected,setSelected]=useState<TaskRecord|null>(null);const[error,setError]=useState('');const[filter,setFilter]=useState('all')
 const load=async()=>{try{setItems((await api.tasks()).items)}catch(e){setError(e instanceof Error?e.message:'任务加载失败')}}
 useEffect(()=>{void load();const timer=setInterval(()=>void load(),3000);return()=>clearInterval(timer)},[])
 useEffect(()=>{if(!selected)return;const timer=setInterval(()=>api.task(selected.id).then(setSelected).catch(()=>{}),2000);return()=>clearInterval(timer)},[selected?.id])
 const open=async(id:string)=>{try{setSelected(await api.task(id))}catch(e){setError(e instanceof Error?e.message:'详情加载失败')}}
 const act=async(kind:'start'|'cancel'|'retry-delivery')=>{if(!selected)return;try{const next=kind==='start'?await api.startTask(selected.id):kind==='cancel'?await api.cancelTask(selected.id):await api.retryDelivery(selected.id);setSelected(next);await load()}catch(e){setError(e instanceof Error?e.message:'操作失败')}}
 const visible=useMemo(()=>{if(filter==='all')return items;if(filter==='active')return items.filter(x=>['queued','running','cancel_requested'].includes(x.status));return items.filter(x=>x.status===filter)},[filter,items]);const run=selected?.runs?.[0]
 const filters=[['all','全部'],['active','处理中'],['awaiting_start','待开始'],['failed','失败'],['completed','已完成']] as const
 return <section className="page-stack"><div className="page-heading"><div><h1>任务</h1><p>查看处理进度，需要时再展开技术细节。</p></div><button className="ghost framed" onClick={()=>void load()}>刷新</button></div>{error&&<div className="inline-alert">{error}</div>}
 <div className="filter-strip">{filters.map(([value,label])=><button key={value} className={filter===value?'active':''} onClick={()=>setFilter(value)}>{label}</button>)}</div>
 {visible.length===0?<div className="empty-state"><h2>这里还没有任务</h2><p>连接工单来源后，新问题会自动出现在这里。</p></div>:<div className="task-table">{visible.map(task=><button key={task.id} className="task-row simple-row" onClick={()=>void open(task.id)}><span className={`task-status task-${task.status}`}>{labels[task.status]??task.status}</span><span><small>{task.provider_instance_id} #{task.external_ticket_id}</small><b>{task.title}</b></span><span className="row-arrow">→</span></button>)}</div>}
 {selected&&<div className="modal-backdrop drawer-backdrop"><div className="task-drawer" role="dialog" aria-modal="true"><div className="modal-head"><div><span className="ticket">{selected.provider_instance_id} #{selected.external_ticket_id}</span><h2>{selected.title}</h2></div><button className="icon-btn" onClick={()=>setSelected(null)} aria-label="关闭">×</button></div><div className="fact-grid fact-grid-simple"><div><small>状态</small><b>{labels[selected.status]}</b></div><div><small>结果</small><b>{resultLabel(selected.result)}</b></div><div><small>项目</small><b>{selected.project_id??'未分配'}</b></div></div>
 {selected.failure&&<div className="failure-surface"><b>{String(selected.failure.summary??'任务失败')}</b></div>}
 <div className="task-actions">{selected.status==='awaiting_start'&&<button className="primary compact" onClick={()=>void act('start')}>开始处理</button>}{['queued','running'].includes(selected.status)&&<button className="danger-button" onClick={()=>void act('cancel')}>取消任务</button>}{selected.status==='failed'&&run?.artifacts?.some(a=>a.artifact_type==='change_manifest')&&<button className="primary compact retry-delivery" onClick={()=>void act('retry-delivery')}>重试交付</button>}</div>
 {run&&<><section className="drawer-section"><div className="section-head"><div><h3>处理进度</h3></div></div><StageRail stages={stageRail(run)}/></section>{(run.delivery_actions??[]).length>0&&<section className="drawer-section"><h3>交付结果</h3><div className="delivery-list">{(run.delivery_actions??[]).map(a=><Delivery key={a.id} action={a}/>)}</div></section>}
 <details className="detail-disclosure"><summary>技术详情</summary><div className="technical-grid"><div><small>运行编号</small><code>{run.id}</code></div><div><small>任务编号</small><code>{selected.id}</code></div></div><div className="artifact-list">{(run.artifacts??[]).map(a=><div key={a.id}><span>{a.artifact_type}</span><code>{a.relative_path}</code><small>{Math.max(1,Math.round(a.size_bytes/1024))} KB · {a.sha256.slice(0,10)}</small></div>)}</div></details></>}
 <details className="detail-disclosure"><summary>执行记录</summary><div className="timeline">{selected.events?.map(event=><div className="event" key={event.id}><i/><div><b>{event.event_type}</b><small>{event.created_at}</small></div></div>)}</div></details></div></div>}
 </section>
}
