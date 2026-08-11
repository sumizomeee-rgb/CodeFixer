import { useEffect, useMemo, useState } from 'react'
import type { PreflightResult, ProjectConfig, SettingsResponse } from '../entities/config'
import { ApiError, api } from '../lib/api'

const emptyProject = (): ProjectConfig => ({
  id: '', name: '', enabled: true,
  modificationSource: { type: 'git', repositoryRef: '', executableRef: 'git-cli' },
  agents: { discovery: '', repair: '', review: '' },
  verification: { steps: [], allowNoAutomatedTests: false, reason: '' },
  finalActions: [{ id: 'primary-patch', type: 'patch', outputDirectoryRef: 'primary-patches' }],
})

export function ProjectsPage() {
  const [projects,setProjects] = useState<ProjectConfig[]>([])
  const [settings,setSettings] = useState<SettingsResponse | null>(null)
  const [editor,setEditor] = useState<ProjectConfig | null>(null)
  const [preflights,setPreflights] = useState<Record<string,PreflightResult>>({})
  const [error,setError] = useState('')
  const [busy,setBusy] = useState(false)

  const reload = async () => {
    const [p,s] = await Promise.all([api.projects(), api.settings()])
    setProjects(p.items); setSettings(s)
  }
  useEffect(()=>{ reload().catch(e=>setError(e instanceof Error?e.message:'加载失败')) },[])
  const profileIds = useMemo(()=>settings?.config.agentProfiles.map(p=>String(p.id ?? '')).filter(Boolean) ?? [],[settings])

  const save = async () => {
    if (!editor || !settings) return
    setBusy(true); setError('')
    try {
      const result = await api.createProject(editor, settings.etag)
      setSettings({...settings, etag: result.etag})
      setEditor(null)
      await reload()
    } catch(e) { setError(e instanceof ApiError ? e.message : '保存失败') }
    finally { setBusy(false) }
  }
  const preflight = async (id:string) => {
    setBusy(true)
    try { const result = await api.preflight(id); setPreflights(v=>({...v,[id]:result})) }
    catch(e){ setError(e instanceof Error?e.message:'Preflight 失败') }
    finally { setBusy(false) }
  }

  return <section className="page-stack">
    <div className="page-heading"><div><span className="eyebrow">PROJECT POLICY</span><h1>项目</h1><p>每个项目绑定唯一修改源、Agent 策略、验证门禁与最终动作。</p></div><button className="primary compact" onClick={()=>setEditor(emptyProject())}>＋ 新建项目</button></div>
    {error && <div className="inline-alert">{error}</div>}
    {projects.length===0 ? <div className="empty-state"><span className="empty-mark">◇</span><h2>还没有项目</h2><p>先建立一个可执行策略集合。CodeFixer 不会在没有唯一项目路由时猜测修改源。</p><button className="primary compact" onClick={()=>setEditor(emptyProject())}>创建第一个项目</button></div> : <div className="project-grid">{projects.map(project=>{
      const pf=preflights[project.id]
      return <article className="project-card" key={project.id}><div className="project-card-head"><div><span className="ticket">{project.id}</span><h3>{project.name || project.id}</h3></div><span className={`readiness-badge ${pf?.ready?'ready':pf?'failed':'unknown'}`}>{pf?.ready?'READY':pf?'NOT READY':'UNCHECKED'}</span></div>
        <div className="project-spec"><div><small>修改源</small><b>{project.modificationSource?.type?.toUpperCase() ?? '—'} · {project.modificationSource?.repositoryRef || '未绑定'}</b></div><div><small>最终动作</small><b>{project.finalActions?.map(a=>a.type).join(' + ') || '未配置'}</b></div></div>
        {pf && <div className="preflight-mini">{pf.checks.slice(0,6).map(c=><div key={c.id} className={c.status}><i/>{c.summary}</div>)}</div>}
        <button className="ghost action-link" disabled={busy} onClick={()=>preflight(project.id)}>运行 Preflight →</button>
      </article>})}</div>}
    {editor && <div className="modal-backdrop" role="presentation"><div className="config-modal" role="dialog" aria-modal="true" aria-labelledby="project-editor-title"><div className="modal-head"><div><span className="signal-kicker">NEW PROJECT</span><h2 id="project-editor-title">建立项目策略</h2></div><button className="icon-btn" onClick={()=>setEditor(null)} aria-label="关闭">×</button></div>
      <div className="form-grid"><label>项目 ID<input value={editor.id} onChange={e=>setEditor({...editor,id:e.target.value})} placeholder="product-lua"/></label><label>显示名称<input value={editor.name??''} onChange={e=>setEditor({...editor,name:e.target.value})} placeholder="Product / Lua"/></label>
      <label>修改源<select value={editor.modificationSource?.type} onChange={e=>setEditor({...editor,modificationSource:{...editor.modificationSource,type:e.target.value as 'git'|'svn'}})}><option value="git">Git</option><option value="svn">SVN</option></select></label>
      <label>repositoryRef<select value={editor.modificationSource?.repositoryRef} onChange={e=>setEditor({...editor,modificationSource:{...editor.modificationSource,repositoryRef:e.target.value}})}><option value="">选择 pathBinding</option>{Object.keys(settings?.config.pathBindings??{}).map(id=><option key={id}>{id}</option>)}</select></label>
      <label>Discovery Agent<select value={editor.agents?.discovery} onChange={e=>setEditor({...editor,agents:{...editor.agents,discovery:e.target.value}})}><option value="">选择 profile</option>{profileIds.map(id=><option key={id}>{id}</option>)}</select></label>
      <label>Repair Agent<select value={editor.agents?.repair} onChange={e=>setEditor({...editor,agents:{...editor.agents,repair:e.target.value,review:editor.agents?.review||e.target.value}})}><option value="">选择 profile</option>{profileIds.map(id=><option key={id}>{id}</option>)}</select></label></div>
      <label className="check-row"><input type="checkbox" checked={!!editor.verification?.allowNoAutomatedTests} onChange={e=>setEditor({...editor,verification:{...editor.verification,allowNoAutomatedTests:e.target.checked}})}/><span>项目当前没有自动测试；使用显式替代门禁</span></label>
      {editor.verification?.allowNoAutomatedTests && <label className="wide-label">替代门禁说明<textarea value={editor.verification.reason??''} onChange={e=>setEditor({...editor,verification:{...editor.verification,reason:e.target.value}})} placeholder="例如：历史项目暂无单测，使用编译、静态检查和独立 Review"/></label>}
      <div className="modal-actions"><button className="ghost" onClick={()=>setEditor(null)}>取消</button><button className="primary compact" disabled={busy||!editor.id} onClick={save}>{busy?'保存中…':'保存项目'}</button></div>
    </div></div>}
  </section>
}
