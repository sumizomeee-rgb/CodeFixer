import { useEffect, useState } from 'react'
import { ModeController } from './design-system/ModeController'
import type { ExecutionMode } from './entities/config'
import { api } from './lib/api'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'

type PageId = 'dashboard' | 'tasks' | 'projects' | 'sources' | 'settings'

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
    if (!etag) { setToast('配置尚未加载，稍后重试'); return }
    const next: ExecutionMode = mode === 'automatic' ? 'awaitingStart' : 'automatic'
    try {
      const r = await api.setExecutionMode(next, etag)
      setMode(r.mode); setEtag(r.etag); setConfirmMode(false)
      setToast(next === 'automatic' ? '已切换为全自动' : '已切换为待我开始')
    } catch (e) { setToast(e instanceof Error ? e.message : '模式切换失败') }
  }

  const nav = (id: PageId, icon: string, label: string) =>
    <button className={page === id ? 'nav-active' : ''} onClick={() => setPage(id)} aria-label={label}>{icon}<span>{label}</span></button>

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="mark"><i/><i/><i/></span><div><b>CodeFixer</b><small>REPAIR CONTROL TOWER</small></div></div>
      <ModeController mode={mode} onClick={() => setConfirmMode(true)}/>
      <div className="top-actions"><span className={`health ${ready === false ? 'health-failed' : ''}`}><i/>{ready === null ? '检查中' : ready ? '系统就绪' : '系统未就绪'}</span><button className="icon-btn" aria-label="切换主题" onClick={() => setDark(v => !v)}>{dark ? '☀' : '◐'}</button></div>
    </header>
    <aside className="navrail">{nav('dashboard','⌁','控制台')}{nav('tasks','≡','任务')}{nav('projects','◇','项目')}{nav('sources','⇄','来源')}{nav('settings','⚙','系统设置')}</aside>
    <main>
      {page === 'dashboard' ? <DashboardPage onOpenTasks={() => setPage('tasks')}/> :
       page === 'tasks' ? <TasksPage/> :
       page === 'projects' ? <ProjectsPage/> :
       page === 'sources' ? <ProvidersPage/> :
       <SettingsPage onModeChanged={(m,e) => { setMode(m); setEtag(e) }}/>} 
    </main>
    {confirmMode && <div className="modal-backdrop"><div className="confirm-modal" role="dialog" aria-modal="true"><span className="signal-kicker">EXECUTION MODE</span><h2>{mode === 'automatic' ? '切换到「待我开始」？' : '切换到「全自动」？'}</h2><p>{mode === 'automatic' ? '新收录的 Bug 将等待你点击一次开始；已经授权的任务继续执行。' : '已收录且仍 eligible 的待开始任务会进入队列，所有确定性门禁仍然生效。'}</p><div className="modal-actions"><button className="ghost" onClick={() => setConfirmMode(false)}>取消</button><button className="primary compact" onClick={() => void toggleMode()}>确认切换</button></div></div></div>}
    {toast && <button className="toast" onClick={() => setToast('')}>{toast}</button>}
  </div>
}
