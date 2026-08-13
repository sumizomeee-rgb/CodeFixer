import { useEffect, useState, type ReactNode } from 'react'
import { ModeController } from './design-system/ModeController'
import type { ExecutionMode } from './entities/config'
import { api } from './lib/api'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'

type PageId = 'tasks' | 'projects' | 'sources' | 'settings'
export type { PageId }
type IconName = PageId | 'sun' | 'moon'
type ThemeMode = 'light' | 'dark'

const pageIds: readonly PageId[] = ['tasks', 'projects', 'sources', 'settings']

const pageFromLocation = (): PageId => {
  const value = window.location.hash.replace(/^#\/?/, '')
  return pageIds.includes(value as PageId) ? value as PageId : 'tasks'
}

const Icon = ({ name }: { name: IconName }) => {
  const paths: Record<IconName, ReactNode> = {
    tasks: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2m-3 7 1 1 2-2m-3 7 1 1 2-2"/></>,
    projects: <><path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5v-9Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
    sources: <><path d="M7 7h11l-3-3m3 3-3 3M17 17H6l3 3m-3-3 3-3"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1v.08h-4V21a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4h-.08v-4H3A1.7 1.7 0 0 0 4.6 8.5a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1v-.08h4V3A1.7 1.7 0 0 0 15.5 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.37.35.7.6 1 .28.28.63.42 1 .4h.08v4H21a1.7 1.7 0 0 0-1.6.6Z"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></>,
    moon: <path d="M20 15.1A8.5 8.5 0 0 1 8.9 4a8.5 8.5 0 1 0 11.1 11.1Z"/>,
  }
  return <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

const RepairMark = () => <svg className="repair-mark" viewBox="0 0 40 40" aria-hidden="true">
  <rect className="repair-plate" x="3" y="3" width="34" height="34" rx="10"/>
  <path className="repair-seam" d="M9 20h6l2.8-5.4 3 10.8 2.7-5.4H31"/>
  <circle className="repair-terminal" cx="9" cy="20" r="1.8"/>
  <circle className="repair-terminal" cx="31" cy="20" r="1.8"/>
</svg>

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('codefixer-theme')
    return saved === 'dark' ? 'dark' : 'light'
  })
  const [page, setPage] = useState<PageId>(pageFromLocation)
  const [mode, setMode] = useState<ExecutionMode>('automatic')
  const [etag, setEtag] = useState('')
  const [readiness, setReadiness] = useState<'ready'|'warning'|'not_ready'|null>(null)
  const [confirmMode, setConfirmMode] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('codefixer-theme',theme)
  }, [theme])
  useEffect(() => {
    const syncPageFromLocation = () => setPage(pageFromLocation())
    window.addEventListener('hashchange', syncPageFromLocation)
    return () => window.removeEventListener('hashchange', syncPageFromLocation)
  }, [])
  useEffect(() => {
    api.settings().then(r => { setMode(r.config.execution.mode); setEtag(r.etag) }).catch(() => {})
    api.readiness().then(r => setReadiness(r.status)).catch(() => setReadiness('not_ready'))
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

  const navigate = (id: PageId) => {
    const nextHash = `#/${id}`
    if (window.location.hash === nextHash) setPage(id)
    else window.location.hash = nextHash
  }

  const nav = (id: PageId, label: string) =>
    <button className={page === id ? 'nav-active' : ''} onClick={() => navigate(id)} aria-label={label}><Icon name={id}/><span>{label}</span></button>

  const toggleTheme = () => setTheme(value => value === 'light' ? 'dark' : 'light')

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><RepairMark/><div><b>CodeFixer</b><small>自动修复控制台</small></div></div>
      <ModeController mode={mode} onClick={() => setConfirmMode(true)}/>
      <div className="top-actions"><button className="icon-btn" aria-label="切换主题" title={theme === 'dark' ? '切换到浅色' : '切换到深色'} onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'}/></button></div>
    </header>
    <aside className="navrail" aria-label="主导航"><div className="nav-main">{nav('tasks','任务')}{nav('projects','流水线')}{nav('sources','来源')}{nav('settings','设置')}</div><div className={`nav-health health-${readiness??'checking'}`}><span className="nav-heartbeat"/><div><b>{readiness===null?'正在检查':readiness==='ready'?'系统待命':readiness==='warning'?'有建议项':'存在阻断'}</b><small>{readiness==='ready'?'依赖与运行环境正常':'打开设置查看运行环境'}</small></div></div></aside>
    <main>
      {page === 'tasks' ? <TasksPage onNavigate={navigate}/> :
       page === 'projects' ? <ProjectsPage/> :
       page === 'sources' ? <ProvidersPage/> :
       <SettingsPage onModeChanged={(m,e) => { setMode(m); setEtag(e) }}/>}
    </main>
    {confirmMode && <div className="modal-backdrop"><div className="confirm-modal" role="dialog" aria-modal="true"><h2>{mode === 'automatic' ? '让新任务等待授权？' : '授权平台全自动运行？'}</h2><p>{mode === 'automatic' ? '之后收到的新问题会先进入待开始；已经授权并运行中的任务会继续完成。' : '已收录且可处理的任务会进入队列，仍会经过定位、验证与独立复核。'}</p><div className="modal-actions"><button className="ghost" onClick={() => setConfirmMode(false)}>取消</button><button className="primary compact" onClick={() => void toggleMode()}>{mode === 'automatic' ? '切换为待我开始' : '授权全自动运行'}</button></div></div></div>}
    {toast && <button className="toast" onClick={() => setToast('')}>{toast}</button>}
  </div>
}
