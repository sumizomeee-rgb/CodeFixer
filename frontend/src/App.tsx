import { useEffect, useState } from 'react'
import { ModeController } from './design-system/ModeController'
import type { ExecutionMode } from './entities/config'
import { api } from './lib/api'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SettingsPage } from './pages/SettingsPage'

type PageId = 'dashboard'|'tasks'|'projects'|'sources'|'settings'

export default function App() {
  const [dark,setDark] = useState(false)
  const [page,setPage] = useState<PageId>('dashboard')
  const [mode,setMode] = useState<ExecutionMode>('automatic')
  const [etag,setEtag] = useState('')
  const [ready,setReady] = useState<boolean|null>(null)
  const [confirmMode,setConfirmMode] = useState(false)
  const [toast,setToast] = useState('')

  useEffect(()=>{ document.documentElement.dataset.theme = dark ? 'dark' : 'light' },[dark])
  useEffect(()=>{
    api.settings().then(r=>{setMode(r.config.execution.mode);setEtag(r.etag)}).catch(()=>{})
    api.readiness().then(r=>setReady(r.ready)).catch(()=>setReady(false))
  },[])

  const toggleMode=async()=>{
    if(!etag){setToast('配置尚未加载，稍后重试');return}
    const next:ExecutionMode=mode==='automatic'?'awaitingStart':'automatic'
    try{const r=await api.setExecutionMode(next,etag);setMode(r.mode);setEtag(r.etag);setConfirmMode(false);setToast(next==='automatic'?'已切换为全自动':'已切换为待我开始')}
    catch(e){setToast(e instanceof Error?e.message:'模式切换失败')}
  }

  return <div className="app-shell">
    <header className="topbar"><div className="brand"><span className="mark"><i/><i/><i/></span><div><b>CodeFixer</b><small>REPAIR CONTROL TOWER</small></div></div><ModeController mode={mode} onClick={()=>setConfirmMode(true)}/><div className="top-actions"><span className={`health ${ready===false?'health-failed':''}`}><i/>{ready===null?'检查中':ready?'系统就绪':'系统未就绪'}</span><button className="icon-btn" aria-label="切换主题" onClick={()=>setDark(v=>!v)}>{dark?'☀':'◐'}</button></div></header>
    <aside className="navrail"><button className={page==='dashboard'?'nav-active':''} onClick={()=>setPage('dashboard')} aria-label="控制台">⌁<span>控制台</span></button><button className={page==='tasks'?'nav-active':''} onClick={()=>setPage('tasks')} aria-label="任务">≡<span>任务</span></button><button className={page==='projects'?'nav-active':''} onClick={()=>setPage('projects')} aria-label="项目">◇<span>项目</span></button><button className={page==='sources'?'nav-active':''} onClick={()=>setPage('sources')} aria-label="来源">⇄<span>来源</span></button><button className={page==='settings'?'nav-active':''} onClick={()=>setPage('settings')} aria-label="系统设置">⚙<span>系统</span></button></aside>
    <main>{page==='dashboard'?<DashboardPage/>:page==='projects'?<ProjectsPage/>:page==='settings'?<SettingsPage onModeChanged={(m,e)=>{setMode(m);setEtag(e)}}/>:<section className="page-stack"><div className="page-heading"><div><span className="eyebrow">COMING NEXT</span><h1>{page==='tasks'?'任务':'工单来源'}</h1><p>这一纵切将在下一施工阶段接入持久化任务与 Provider。</p></div></div></section>}</main>
    {confirmMode&&<div className="modal-backdrop"><div className="confirm-modal" role="dialog" aria-modal="true"><span className="signal-kicker">EXECUTION MODE</span><h2>{mode==='automatic'?'切换到「待我开始」？':'切换到「全自动」？'}</h2><p>{mode==='automatic'?'新收录的 Bug 将等待你点击一次开始；已经授权的任务继续执行。':'已收录且仍 eligible 的待开始任务会进入队列，所有确定性门禁仍然生效。'}</p><div className="modal-actions"><button className="ghost" onClick={()=>setConfirmMode(false)}>取消</button><button className="primary compact" onClick={toggleMode}>确认切换</button></div></div></div>}
    {toast&&<button className="toast" onClick={()=>setToast('')}>{toast}</button>}
  </div>
}
