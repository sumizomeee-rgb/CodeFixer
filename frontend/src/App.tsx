import { useEffect, useState, type ReactNode } from 'react'
import { ModeController } from './design-system/ModeController'
import type { ExecutionMode } from './entities/config'
import { api } from './lib/api'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'

type PageId = 'dashboard' | 'tasks' | 'projects' | 'sources' | 'settings'
type IconName = PageId | 'sun' | 'moon'

const Icon = ({ name }: { name: IconName }) => {
  const paths: Record<IconName, ReactNode> = {
    dashboard: <><path d="M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-16v4h6V4h-6Z"/></>,
    tasks: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2m-3 7 1 1 2-2m-3 7 1 1 2-2"/></>,
    projects: <><path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
    sources: <><path d="M7 7h11l-3-3m3 3-3 3M17 17H6l3 3m-3-3 3-3"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1v.08h-4V21a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4h-.08v-4H3A1.7 1.7 0 0 0 4.6 8.5a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1v-.08h4V3A1.7 1.7 0 0 0 15.5 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.37.35.7.6 1 .28.28.63.42 1 .4h.08v4H21a1.7 1.7 0 0 0-1.6.6Z"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></>,
    moon: <path d="M20 15.1A8.5 8.5 0 0 1 8.9 4a8.5 8.5 0 1 0 11.1 11.1Z"/>,
  }
  return <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" fill={name === 'dashboard' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

const RepairMark = () => <svg className="repair-mark" viewBox="0 0 40 40" aria-hidden="true">
  <path className="repair-plate" d="M20 4A16 16 0 0 0 20 36V27a7 7 0 0 1 0-14V4Z"/>
  <path className="repair-plate repair-plate-right" d="M20 4A16 16 0 0 1 20 36V27a7 7 0 0 0 0-14V4Z"/>
  <path className="repair-seam" d="m17 7 6 4-6 4 6 4-6 4 6 4-6 4"/>
</svg>

export default function App() {
  const [dark, setDark] = useState(false)
  const [page, setPage] = useState<PageId>('dashboard')
  const [mode, setMode] = useState<ExecutionMode>('automatic')
  const [etag, setEtag] = useState('')
  const [ready, setReady] = useState<boolean | null>(null)
  const [confirmMode, setConfirmMode] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light' }, [dark])
  useEffect(() => {
    api.settings().then(r => { setMode(r.config.execution.mode); setEtag(r.etag) }).catch(() => {})
    api.readiness().then(r => setReady(r.ready)).catch(() => setReady(false))
  }, [])

  const toggleMode = async () => {
    if (!etag) { setToast('配置尚未加载，请稍后再试'); return }
    const next: ExecutionMode = mode === 'automatic' ? 'awaitingStart' : 'automatic'
    try {
      const r = await api.setExecutionMode(next, etag)
      setMode(r.mode); setEtag(r.etag); setConfirmMode(false)
      setToast(next === 'automatic' ? '已切换为全自动' : '已切换为待我开始')
    } catch (e) { setToast(e instanceof Error ? e.message : '模式切换失败') }
  }

  const nav = (id: PageId, label: string) =>
    <button className={page === id ? 'nav-active' : ''} onClick={() => setPage(id)} aria-label={label}><Icon name={id}/><span>{label}</span></button>

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><RepairMark/><div><b>CodeFixer</b><small>自动修复控制台</small></div></div>
      <ModeController mode={mode} onClick={() => setConfirmMode(true)}/>
      <div className="top-actions"><span className={`health ${ready === false ? 'health-failed' : ''}`}><i/>{ready === null ? '检查中' : ready ? '系统正常' : '需要检查'}</span><button className="icon-btn" aria-label="切换主题" onClick={() => setDark(v => !v)}><Icon name={dark ? 'sun' : 'moon'}/></button></div>
    </header>
    <aside className="navrail" aria-label="主导航">{nav('dashboard','首页')}{nav('tasks','任务')}{nav('projects','项目')}{nav('sources','来源')}{nav('settings','设置')}</aside>
    <main>
      {page === 'dashboard' ? <DashboardPage onOpenTasks={() => setPage('tasks')}/> :
       page === 'tasks' ? <TasksPage/> :
       page === 'projects' ? <ProjectsPage/> :
       page === 'sources' ? <ProvidersPage/> :
       <SettingsPage onModeChanged={(m,e) => { setMode(m); setEtag(e) }}/>} 
    </main>
    {confirmMode && <div className="modal-backdrop"><div className="confirm-modal" role="dialog" aria-modal="true"><h2>{mode === 'automatic' ? '切换到「待我开始」？' : '切换到「全自动」？'}</h2><p>{mode === 'automatic' ? '之后收到的新问题会先等待确认，已经开始的任务不受影响。' : '已收录且仍可处理的任务会自动进入队列。'}</p><div className="modal-actions"><button className="ghost" onClick={() => setConfirmMode(false)}>取消</button><button className="primary compact" onClick={() => void toggleMode()}>确认</button></div></div></div>}
    {toast && <button className="toast" onClick={() => setToast('')}>{toast}</button>}
  </div>
}
