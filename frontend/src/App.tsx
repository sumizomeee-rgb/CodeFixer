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
    if (!etag) { setToast('配置尚未加载，请稍后再试'); return }
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
      <div className="brand"><span className="mark"><i/><i/><i/></span><b>CodeFixer</b></div>
      <ModeController mode={mode} onClick={() => setConfirmMode(true)}/>
      <div className="top-actions"><span className={`health ${ready === false ? 'health-failed' : ''}`}><i/>{ready === null ? '检查中' : ready ? '系统正常' : '需要检查'}</span><button className="icon-btn" aria-label="切换主题" onClick={() => setDark(v => !v)}>{dark ? '☀' : '◐'}</button></div>
    </header>
    <aside className="navrail">{nav('dashboard','⌁','首页')}{nav('tasks','≡','任务')}{nav('projects','◇','项目')}{nav('sources','⇄','来源')}{nav('settings','⚙','设置')}</aside>
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
