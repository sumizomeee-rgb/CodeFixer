import { useEffect, useState } from 'react'
import type { DashboardData, StageRun, TaskRecord, TaskRun } from '../entities/task'
import { StageRail, type StageItem, type StageState } from '../design-system/StageRail'
import { api } from '../lib/api'

const stageLabels:Record<string,string>={prepare:'准备',scope_discovery:'范围',discovery:'定位',no_change_verify:'确认',repair:'修复',verify:'验证',review:'复核',pre_delivery_check:'检查',freeze_change:'冻结',deliver:'交付'}
const state=(value:string):StageState=>value==='completed'?'done':value==='running'?'running':value==='failed'?'failed':value==='reconciling'?'reconciling':value==='canceled'?'skipped':'queued'
const duration=(stage:StageRun)=>{if(!stage.started_at)return '';if(!stage.finished_at)return stage.status==='running'?'进行中':'';const ms=new Date(stage.finished_at).getTime()-new Date(stage.started_at).getTime();return ms<1000?'完成':ms<60000?`${Math.max(1,Math.round(ms/1000))} 秒`:`${Math.max(1,Math.round(ms/60000))} 分`}
function rail(run:TaskRun):StageItem[]{const stages=(run.stages??[]) as StageRun[];const grouped=new Map<string,StageRun>();for(const item of stages)grouped.set(item.stage_id,item);const order=['prepare','scope_discovery','discovery','repair','verify','review','deliver'];return order.map(id=>{const item=grouped.get(id);return{label:stageLabels[id]??id,meta:item?duration(item):'',state:item?state(item.status):'queued'}})}
function Metric({value,label,tone='default'}:{value:string|number,label:string,tone?:string}){return <div className={`metric metric-${tone}`}><span>{value}</span><small>{label}</small></div>}
function LiveTask({task}:{task:TaskRecord}){const run=task.runs?.[0];return <article className="task-card"><div className="task-top"><div><span className="ticket">{task.provider_instance_id} #{task.external_ticket_id}</span><h3>{task.title}</h3></div><span className={`status-pill ${task.status==='running'?'running':''}`}>{task.status==='running'?'处理中':task.status==='queued'?'等待中':'处理中'}</span></div>{task.project_id&&<div className="task-meta"><span>{task.project_id}</span></div>}{run?<StageRail stages={rail(run)}/>:null}</article>}

export function DashboardPage({onOpenTasks}:{onOpenTasks:()=>void}){
 const[data,setData]=useState<DashboardData|null>(null);const[error,setError]=useState('')
 const load=()=>api.dashboard().then(setData).catch(e=>setError(e instanceof Error?e.message:'首页加载失败'))
 useEffect(()=>{load();const timer=setInterval(load,3000);return()=>clearInterval(timer)},[])
 const metrics=data?.metrics??{active:0,queued:0,running:0,completedChanged:0,completedNoChange:0,failed:0};const active=(data?.recentTasks??[]).filter(t=>['queued','running','cancel_requested'].includes(t.status)).slice(0,3);const completed=metrics.completedChanged+metrics.completedNoChange
 return <><section className="hero"><div><h1>维修控制台</h1><p>只看正在处理的任务和需要你关注的问题。</p></div><div className="slots"><span>活跃</span><b>{metrics.active}</b></div></section>{error&&<div className="inline-alert">{error}</div>}
 <section className="metrics metrics-compact"><Metric value={metrics.running} label="处理中" tone="running"/><Metric value={completed} label="已完成" tone="success"/><Metric value={metrics.failed} label="需要处理" tone="failed"/></section>
 <section className="content-grid"><div><div className="section-head"><div><h2>正在处理</h2></div><button className="ghost" onClick={onOpenTasks}>全部任务</button></div><div className="task-stack">{active.length?active.map(t=><LiveTask task={t} key={t.id}/>):<div className="quiet-panel"><b>现在没有进行中的任务</b></div>}</div></div>
 <aside className="attention"><div className="section-head"><div><h2>需要处理</h2></div></div>{(data?.attention??[]).length?(data?.attention??[]).slice(0,2).map(t=><div className="failure-card" key={t.id}><h3>{t.title}</h3><p>{String((t.failure as Record<string,unknown>|null)?.summary??'这个任务需要检查。')}</p><button className="primary" onClick={onOpenTasks}>查看任务</button></div>):<div className="evidence-card calm-card"><h3>一切正常</h3><p>暂无需要你处理的问题。</p></div>}</aside></section></>
}
