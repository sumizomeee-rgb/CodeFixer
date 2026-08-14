import { useEffect, useMemo, useState } from 'react'
import type {
  FinalActionConfig,
  GitHubPrActionConfig,
  GitLabPushActionConfig,
  PatchActionConfig,
  PreflightResult,
  ProjectConfig,
  RoutingOperator,
  SettingsResponse,
  VerificationStepConfig,
  WorkspaceDetection,
} from '../entities/config'
import { ApiError, api } from '../lib/api'

type Step = 1 | 2 | 3 | 4

const emptyProject = (): ProjectConfig => ({
  id: '',
  name: '',
  enabled: true,
  routingRules: [{ id: 'primary-route', providerRef: '', priority: 100, catchAll: true, conditions: [] }],
  localizationSource: { id: 'localization-source', type: 'directory', path: '', readOnly: true },
  modificationWorkspace: { id: 'modification-workspace', path: '', allowedRoots: ['.'], deniedRoots: [], allowedExtensions: [] },
  verification: { timeoutSeconds: 1200, steps: [], allowNoAutomatedTests: false, reason: '' },
  deliveryLog: { technologyTag:'Lua', submitterName:'' },
  finalActions: [],
})

const csv = (value:string) => value.split(',').map(item => item.trim()).filter(Boolean)
const firstRule = (project:ProjectConfig) => project.routingRules?.[0] ?? { id:'primary-route', providerRef:'', priority:100, catchAll:true, conditions:[] }
const patchDefault = ():PatchActionConfig => ({ id:'patch', type:'patch', outputDirectory:'', overwrite:false, required:true })
const pushDefault = ():GitLabPushActionConfig => ({ id:'gitlab-push', type:'gitlabPush', required:true })
const prDefault = ():GitHubPrActionConfig => ({ id:'github-pr', type:'githubPr', targetBranches:['main'], titleTemplate:'[CodeFixer] {task_id}', descriptionTemplate:'CodeFixer 自动修复任务 {run_id}。', required:true })
const labelForAction = (action:FinalActionConfig) => action.type === 'patch' ? 'Patch' : action.type === 'gitlabPush' ? 'GitLab Push' : 'GitHub PR'
const actionOf = <T extends FinalActionConfig['type']>(actions:FinalActionConfig[] | undefined, type:T) => actions?.find(item => item.type === type) as Extract<FinalActionConfig,{type:T}> | undefined

function StatusIcon({ status }:{ status:'ready'|'warning'|'failed' }) {
  return <span className={`detect-icon ${status}`} aria-hidden="true">
    {status === 'ready' ? <svg viewBox="0 0 20 20"><path d="m4 10 4 4 8-9"/></svg> : status === 'warning' ? <svg viewBox="0 0 20 20"><path d="M10 3 18 17H2Z"/><path d="M10 8v4m0 2v.1"/></svg> : <svg viewBox="0 0 20 20"><path d="m5 5 10 10M15 5 5 15"/></svg>}
  </span>
}

function StepMark({ number, current, complete, title, detail, onClick }:{ number:Step; current:Step; complete:boolean; title:string; detail:string; onClick:()=>void }) {
  const state = current === number ? 'current' : complete ? 'complete' : ''
  return <button type="button" className={`project-step ${state}`} onClick={onClick}>
    <span>{complete && current !== number ? <svg viewBox="0 0 20 20"><path d="m4 10 4 4 8-9"/></svg> : number}</span>
    <div><b>{title}</b><small>{detail}</small></div>
  </button>
}

export function ProjectsPage() {
  const [projects,setProjects] = useState<ProjectConfig[]>([])
  const [settings,setSettings] = useState<SettingsResponse|null>(null)
  const [editor,setEditor] = useState<ProjectConfig|null>(null)
  const [editingId,setEditingId] = useState<string|null>(null)
  const [step,setStep] = useState<Step>(1)
  const [detection,setDetection] = useState<WorkspaceDetection|null>(null)
  const [preflights,setPreflights] = useState<Record<string,PreflightResult>>({})
  const [error,setError] = useState('')
  const [busy,setBusy] = useState('')

  const reload = async () => {
    const [p,s] = await Promise.all([api.projects(),api.settings()])
    setProjects(p.items)
    setSettings(s)
  }
  useEffect(() => { void reload().catch(e => setError(e instanceof Error ? e.message : '加载失败')) }, [])

  const providerIds = useMemo(() => settings?.config.ticketProviders.map(item => item.id).filter(Boolean) ?? [],[settings])
  const executableIds = useMemo(() => Object.keys(settings?.config.executableBindings ?? {}),[settings])
  const route = editor ? firstRule(editor) : null
  const routeCondition = route?.conditions?.[0]
  const actions = editor?.finalActions ?? []
  const deliveryLog = editor?.deliveryLog ?? {technologyTag:'Lua',submitterName:''}
  const patch = actionOf(actions,'patch')
  const gitlabPush = actionOf(actions,'gitlabPush')
  const pr = actionOf(actions,'githubPr')

  const openEditor = (project?:ProjectConfig) => {
    const next = project ? structuredClone(project) : emptyProject()
    setEditor(next)
    setEditingId(project?.id ?? null)
    setStep(1)
    setError('')
    const workspace = next.modificationWorkspace
    setDetection(workspace?.vcsKind ? {
      path:workspace.path,
      ready:workspace.vcsKind !== 'unknown',
      vcsKind:workspace.vcsKind,
      hostingKind:workspace.hostingKind ?? 'none',
      repositoryRoot:workspace.repositoryRoot,
      remoteUrl:workspace.remoteUrl,
      webBaseUrl:workspace.webBaseUrl,
      summary:'已保存的识别结果',
      checks:[],
    } : null)
  }
  const closeEditor = () => { setEditor(null); setEditingId(null); setDetection(null) }
  const updateRule = (patch:Partial<NonNullable<ProjectConfig['routingRules']>[number]>) => editor && setEditor({...editor,routingRules:[{...firstRule(editor),...patch}]})
  const updateLocalization = (patch:Partial<NonNullable<ProjectConfig['localizationSource']>>) => editor && setEditor({...editor,localizationSource:{id:'localization-source',path:'',readOnly:true,...editor.localizationSource,...patch}})
  const updateWorkspace = (patch:Partial<NonNullable<ProjectConfig['modificationWorkspace']>>) => editor && setEditor({...editor,modificationWorkspace:{id:'modification-workspace',path:'',...editor.modificationWorkspace,...patch}})
  const updateDeliveryLog = (patch:Partial<NonNullable<ProjectConfig['deliveryLog']>>) => editor && setEditor({...editor,deliveryLog:{...deliveryLog,...patch}})
  const setAction = (action:FinalActionConfig) => editor && setEditor({...editor,finalActions:[...actions.filter(item => item.type !== action.type),action]})
  const toggleAction = (type:FinalActionConfig['type']) => {
    if (!editor) return
    if (actions.some(item => item.type === type)) setEditor({...editor,finalActions:actions.filter(item => item.type !== type)})
    else setAction(type === 'patch' ? patchDefault() : type === 'gitlabPush' ? pushDefault() : prDefault())
  }
  const detect = async () => {
    const path = editor?.modificationWorkspace?.path.trim()
    if (!path) return
    setBusy('detect'); setError('')
    try {
      const result = await api.detectWorkspace(path)
      setDetection(result)
      updateWorkspace({path:result.path,vcsKind:result.vcsKind,hostingKind:result.hostingKind,repositoryRoot:result.repositoryRoot,remoteUrl:result.remoteUrl,webBaseUrl:result.webBaseUrl})
      if (result.hostingKind !== 'gitlab' && gitlabPush) setEditor(current => current ? {...current,finalActions:(current.finalActions??[]).filter(item => item.type !== 'gitlabPush')} : current)
      if (result.hostingKind !== 'github' && pr) setEditor(current => current ? {...current,finalActions:(current.finalActions??[]).filter(item => item.type !== 'githubPr')} : current)
    } catch (e) { setDetection(null); setError(e instanceof Error ? e.message : '无法识别目录') }
    finally { setBusy('') }
  }
  const save = async () => {
    if (!editor || !settings) return
    setBusy('save'); setError('')
    try {
      const result = editingId ? await api.updateProject(editingId,editor,settings.etag) : await api.createProject(editor,settings.etag)
      setSettings({...settings,etag:result.etag})
      closeEditor()
      await reload()
      void preflight(result.project.id)
    } catch (e) { setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : '保存失败') }
    finally { setBusy('') }
  }
  const preflight = async (id:string) => {
    setBusy(`preflight:${id}`)
    try { const result = await api.preflight(id); setPreflights(value => ({...value,[id]:result})) }
    catch (e) { setError(e instanceof Error ? e.message : '检查失败') }
    finally { setBusy('') }
  }
  const addVerification = () => {
    if (!editor) return
    const steps = editor.verification?.steps ?? []
    const next:VerificationStepConfig = {id:`step-${steps.length+1}`,executableRef:'',args:[],workingDirectory:'.',required:true}
    setEditor({...editor,verification:{...editor.verification,steps:[...steps,next]}})
  }
  const updateVerification = (index:number,patch:Partial<VerificationStepConfig>) => {
    if (!editor) return
    const steps = [...(editor.verification?.steps ?? [])]
    steps[index] = {...steps[index],...patch}
    setEditor({...editor,verification:{...editor.verification,steps}})
  }

  const stepComplete = {
    1:Boolean(editor?.name?.trim() && route?.providerRef),
    2:Boolean(editor?.localizationSource?.path),
    3:Boolean(editor?.modificationWorkspace?.path && detection?.ready),
    4:Boolean(actions.length) && Boolean(editor?.deliveryLog?.technologyTag.trim() && editor.deliveryLog.submitterName.trim()) && actions.every(action => action.type === 'patch' ? Boolean(action.outputDirectory?.trim()) : action.type === 'githubPr' ? action.targetBranches.length > 0 : true),
  }
  const canSave = stepComplete[1] && stepComplete[2] && stepComplete[3] && stepComplete[4]
  const next = () => setStep(value => Math.min(4,value + 1) as Step)
  const sourceLabel = (project:ProjectConfig) => project.modificationWorkspace?.vcsKind?.toUpperCase() ?? '未识别'

  return <section className="page-stack project-page">
    <div className="page-heading"><div><span className="page-kicker">REPAIR PIPELINES</span><h1>流水线</h1><p>把工单、定位资料、修改工程与交付出口连成一条修复线路。</p></div><button className="primary compact" onClick={() => openEditor()}>新增流水线</button></div>
    {error && <button className="notice-strip error-note" onClick={() => setError('')}>{error}</button>}

    {projects.length === 0 ? <div className="empty-state project-empty"><span className="empty-symbol"><svg viewBox="0 0 36 36"><path d="M8 9h20v18H8z"/><path d="M13 5v8M23 5v8M5 15h6M25 15h6M13 22h10"/></svg></span><h2>建立第一条修复通道</h2><p>从一个工单反馈来源开始，再告诉 CodeFixer 去哪里理解问题、修改哪份工程，以及最终如何交付。</p><button className="primary compact" onClick={() => openEditor()}>开始配置</button></div> :
      <div className="project-grid refined-project-grid">{projects.map(project => {
        const pf = preflights[project.id]
        const projectActions = project.finalActions ?? []
        return <article className="project-card project-ledger-card" data-health={pf?.ready ? 'ready' : pf ? 'failed' : project.enabled === false ? 'inactive' : 'unknown'} key={project.id}>
          <header><div><small>修复流水线</small><h2>{project.name || '未命名流水线'}</h2></div><span className={`readiness-badge ${pf?.ready ? 'ready' : pf ? 'failed' : 'unknown'}`}>{pf?.ready ? '已就绪' : pf ? '需处理' : '待体检'}</span></header>
          <div className="project-path-story"><div><span>定位资料</span><b>{project.localizationSource?.path || '未配置'}</b></div><i/><div><span>修改工程 · {sourceLabel(project)}</span><b>{project.modificationWorkspace?.path || '未配置'}</b></div></div>
          <div className="delivery-tags">{projectActions.length ? projectActions.map(item => <span key={item.id}>{labelForAction(item)}</span>) : <span className="muted-tag">未配置交付</span>}</div>
          {pf && !pf.ready && <div className="preflight-issue">{pf.checks.find(item => item.status === 'failed')?.summary ?? '配置尚未就绪'}</div>}
          <footer><button className="ghost action-link" onClick={() => openEditor(project)}>编辑配置</button><button className="ghost framed" disabled={!!busy} onClick={() => void preflight(project.id)}>{busy === `preflight:${project.id}` ? '检查中…' : '运行体检'}</button></footer>
        </article>
      })}</div>}

    {editor && settings && route && <div className="modal-backdrop editor-backdrop"><div className="config-modal project-workbench" role="dialog" aria-modal="true" aria-labelledby="project-editor-title">
      <header className="workbench-head"><div><small>PIPELINE WORKBENCH</small><h2 id="project-editor-title">{editingId ? '编辑流水线' : '新增流水线'}</h2><p>四步完成配置。路径均指 CodeFixer 部署机上的本地目录。</p></div><button className="icon-btn" onClick={closeEditor} aria-label="关闭">×</button></header>
      <div className="workbench-layout">
        <nav className="project-stepper" aria-label="流水线配置步骤">
          <StepMark number={1} current={step} complete={stepComplete[1]} title="工单反馈" detail="问题从哪里进入" onClick={() => setStep(1)}/>
          <StepMark number={2} current={step} complete={stepComplete[2]} title="定位资料" detail="去哪里查找线索" onClick={() => setStep(2)}/>
          <StepMark number={3} current={step} complete={stepComplete[3]} title="修改工程" detail="真正落代码的位置" onClick={() => setStep(3)}/>
          <StepMark number={4} current={step} complete={stepComplete[4]} title="最终交付" detail="可同时选择多个" onClick={() => setStep(4)}/>
        </nav>

        <div className="workbench-body">
          {step === 1 && <div className="step-panel"><div className="step-intro"><span>01</span><div><h3>先确定一张工单进入哪条线</h3><p>反馈源负责收取正文；流水线规则决定由哪套定位、修改和交付策略处理。</p></div></div>
            <div className="form-grid polished-form"><label>流水线名称<input value={editor.name ?? ''} onChange={e => setEditor({...editor,name:e.target.value})} placeholder="例如：客户端 Lua 修复"/></label><label>工单反馈源<select value={route.providerRef} onChange={e => updateRule({providerRef:e.target.value})}><option value="">选择 Redmine / TAPD 来源</option>{providerIds.map(id => <option key={id}>{id}</option>)}</select><small>Token 与账号保存在当前机器，不进入公开仓库。</small></label></div>
            {providerIds.length === 0 && <div className="soft-warning">还没有可选反馈源。请先到“反馈源”连接 Redmine 或 TAPD。</div>}
          </div>}

          {step === 2 && <div className="step-panel"><div className="step-intro"><span>02</span><div><h3>为问题定位提供足够线索</h3><p>这是只读的辅助资料，可以是日志、分析工程或代码仓库；它不等于最终会被修改的工程。</p></div></div>
            <label className="path-field"><span>定位资料路径</span><div><input value={editor.localizationSource?.path ?? ''} onChange={e => updateLocalization({path:e.target.value})} placeholder={String.raw`例如：/srv/knowledge/client 或 E:\Projects\Analyzer`}/><span className="path-chip">只读</span></div><small>平台会从工单和这些资料中查找问题线索，并在修改代码前核对定位结果。</small></label>
            <div className="source-separation"><div><b>定位源</b><span>负责理解“问题在哪里”</span></div><svg viewBox="0 0 80 20"><path d="M2 10h70m-8-7 8 7-8 7"/></svg><div><b>修改工程</b><span>负责回答“代码改在哪里”</span></div></div>
          </div>}

          {step === 3 && <div className="step-panel"><div className="step-intro"><span>03</span><div><h3>选择实际落代码的工程</h3><p>无需手选仓库类型。平台会检查目录、识别 Git/SVN，并读取 origin 判断托管平台。</p></div></div>
            <label className="path-field"><span>修改工程路径</span><div><input value={editor.modificationWorkspace?.path ?? ''} onChange={e => {updateWorkspace({path:e.target.value,vcsKind:'unknown',hostingKind:'none',repositoryRoot:undefined,remoteUrl:undefined,webBaseUrl:undefined});setDetection(null)}} placeholder={String.raw`例如：/srv/repos/client 或 E:\WorkProject\Client`}/><button className="primary compact path-detect-button" disabled={busy === 'detect' || !editor.modificationWorkspace?.path.trim()} onClick={() => void detect()}>{busy === 'detect' ? '识别中…' : '识别目录'}</button></div><small>这里的“本地”指运行 CodeFixer 服务的机器；换机后在新机器重新配置即可。</small></label>
            {detection ? <div className={`detection-report ${detection.ready ? 'ready' : 'failed'}`}>
              <div className="detection-summary"><StatusIcon status={detection.ready ? 'ready' : 'failed'}/><div><b>{detection.summary}</b><span>{detection.repositoryRoot ?? detection.path}</span></div><div className="detection-facts"><span>{detection.vcsKind.toUpperCase()}</span><span>{detection.hostingKind === 'gitlab' ? 'GitLab' : detection.hostingKind === 'github' ? 'GitHub' : detection.hostingKind === 'other' ? '其他 Git 托管' : '本地仓库'}</span></div></div>
              {detection.remoteUrl && <div className="remote-line"><span>ORIGIN</span><code>{detection.remoteUrl}</code></div>}
              {detection.checks.length > 0 && <div className="detection-checks">{detection.checks.map(item => <div key={item.id}><StatusIcon status={item.status}/><span>{item.summary}</span></div>)}</div>}
            </div> : <div className="detect-placeholder"><span>等待识别</span><p>识别完成后，下一步会自动开放这个工程支持的交付方式。</p></div>}
          </div>}

          {step === 4 && <div className="step-panel"><div className="step-intro"><span>04</span><div><h3>选择一个或多个交付出口</h3><p>每个动作共用同一条冻结日志；远端交付失败时会自动额外保留 Patch。</p></div></div>
            <div className="delivery-log-config"><div className="delivery-log-head"><span>交付日志</span><p>工单有修复版本时自动插入；没有版本时直接省略。AI 只生成模块名与修改摘要。</p></div><div className="form-grid polished-form"><label>技术域<input value={deliveryLog.technologyTag} onChange={e => updateDeliveryLog({technologyTag:e.target.value})} placeholder="Lua"/></label><label>提交人姓名<input value={deliveryLog.submitterName} onChange={e => updateDeliveryLog({submitterName:e.target.value})} placeholder="例如：黄永熙"/><small>写入“提交人：”之后；不等同于 Git Author 或 GitLab 用户名。</small></label></div><code>fix：【{deliveryLog.technologyTag || 'Lua'}】【#B1250062】AI 模块名 - AI 修改摘要&nbsp;&nbsp;提交人：{deliveryLog.submitterName || '姓名'}</code></div>
            <div className="action-choice-grid">
              <button className={`action-choice ${patch ? 'selected' : ''}`} onClick={() => toggleAction('patch')}><span className="choice-check">{patch ? '✓' : ''}</span><svg viewBox="0 0 32 32"><path d="M7 5h13l5 5v17H7z"/><path d="M20 5v6h6M11 17h10M11 21h7"/></svg><div><b>生成 Patch</b><small>任何 Git / SVN 工程都可用</small></div></button>
              <button disabled={detection?.hostingKind !== 'gitlab'} className={`action-choice ${gitlabPush ? 'selected' : ''}`} onClick={() => toggleAction('gitlabPush')}><span className="choice-check">{gitlabPush ? '✓' : ''}</span><svg viewBox="0 0 32 32"><path d="m5 13 4-9 4 9h6l4-9 4 9-11 14Z"/></svg><div><b>推送到 GitLab</b><small>{detection?.hostingKind === 'gitlab' ? '返回 Commit，由你在 Web 手动 Cherry-pick' : '仅 GitLab 工程可选'}</small></div></button>
              <button disabled={detection?.hostingKind !== 'github'} className={`action-choice ${pr ? 'selected' : ''}`} onClick={() => toggleAction('githubPr')}><span className="choice-check">{pr ? '✓' : ''}</span><svg viewBox="0 0 32 32"><path d="M16 5a11 11 0 0 0-3.5 21.4c.6.1.8-.3.8-.6v-2.1c-3.3.7-4-1.4-4-1.4-.6-1.4-1.4-1.8-1.4-1.8-1.1-.8.1-.8.1-.8 1.2.1 1.9 1.3 1.9 1.3 1.1 1.9 2.9 1.4 3.6 1.1.1-.8.4-1.4.8-1.7-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C20 8.8 21 9.1 21 9.1c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.2c0 .3.2.7.8.6A11 11 0 0 0 16 5Z"/></svg><div><b>GitHub PR</b><small>{detection?.hostingKind === 'github' ? '使用当前仓库 origin 与 gh 登录态' : '仅 GitHub 工程可选'}</small></div></button>
            </div>
            <div className="action-config-stack">
              {patch && <div className="action-config"><div><b>Patch 输出</b><small>指定部署机上的绝对目录；远端交付失败时另有平台保底目录。</small></div><label>输出目录<input value={patch.outputDirectory ?? ''} onChange={e => setAction({...patch,outputDirectory:e.target.value})} placeholder={String.raw`例如：/srv/codefixer/patches 或 E:\Patches`}/></label></div>}
              {gitlabPush && <div className="action-config action-config-quiet"><div><b>GitLab 已就绪</b><small>使用当前仓库 origin 与本机 Git 认证推送受控任务分支，无需 Token、目标分支或指派人。</small></div></div>}
              {pr && <div className="action-config"><div><b>GitHub PR</b><small>可一次向多个目标分支创建 PR。</small></div><label>目标分支<input value={pr.targetBranches.join(', ')} onChange={e => setAction({...pr,targetBranches:csv(e.target.value)})} placeholder="main, release/1.0"/></label></div>}
              {actions.length === 0 && <div className="no-action-selected">至少选择一种交付方式。</div>}
            </div>
          </div>}

          {/* 规则属于「在这个工程里能改什么、改完怎么验」，语义归第 3 步。
              放在 step 判断之外会让它在四步里全程常驻，用户在选交付出口时也看得到它。 */}
          {step === 3 && <details className="project-policy"><summary><span>修改与检查规则</span><small>限制可改文件，并设置完成后的自动检查</small></summary><div className="policy-body">
            <h4>允许修改哪些文件</h4><div className="form-grid polished-form"><label>可修改目录<input value={(editor.modificationWorkspace?.allowedRoots ?? ['.']).join(', ')} onChange={e => updateWorkspace({allowedRoots:csv(e.target.value)})}/></label><label>禁止修改目录<input value={(editor.modificationWorkspace?.deniedRoots ?? []).join(', ')} onChange={e => updateWorkspace({deniedRoots:csv(e.target.value)})} placeholder="vendor, generated"/></label><label className="span-field">可修改文件类型<input value={(editor.modificationWorkspace?.allowedExtensions ?? []).join(', ')} onChange={e => updateWorkspace({allowedExtensions:csv(e.target.value)})} placeholder="留空表示不限制；例如 .py, .ts, .lua, .prefab"/></label></div>
            <div className="advanced-heading"><h4>完成后自动检查</h4><button className="ghost framed" onClick={addVerification}>添加检查</button></div>
            {(editor.verification?.steps ?? []).map((item,index) => <div className="verification-row" key={`${item.id}-${index}`}><input value={item.id} onChange={e => updateVerification(index,{id:e.target.value})} placeholder="检查名称"/><select value={item.executableRef} onChange={e => updateVerification(index,{executableRef:e.target.value})}><option value="">运行工具</option>{executableIds.map(id => <option key={id}>{id}</option>)}</select><input value={item.args.join(' ')} onChange={e => updateVerification(index,{args:e.target.value.split(' ').filter(Boolean)})} placeholder="运行参数"/><input value={item.workingDirectory ?? '.'} onChange={e => updateVerification(index,{workingDirectory:e.target.value})} placeholder="运行目录"/><button className="ghost" aria-label="移除检查" onClick={() => setEditor({...editor,verification:{...editor.verification,steps:(editor.verification?.steps ?? []).filter((_,i) => i !== index)}})}>×</button></div>)}
            <label className="check-row"><input type="checkbox" checked={!!editor.verification?.allowNoAutomatedTests} onChange={e => setEditor({...editor,verification:{...editor.verification,allowNoAutomatedTests:e.target.checked}})}/><span>这个工程暂时没有可自动执行的检查</span></label>
            {editor.verification?.allowNoAutomatedTests && <label className="wide-label">原因<textarea value={editor.verification.reason ?? ''} onChange={e => setEditor({...editor,verification:{...editor.verification,reason:e.target.value}})}/></label>}
            <h4>工单接收规则</h4><div className="form-grid polished-form"><label>匹配优先级<input type="number" value={route.priority} onChange={e => updateRule({priority:Number(e.target.value) || 0})}/></label><label className="check-row"><input type="checkbox" checked={!!route.catchAll} onChange={e => updateRule({catchAll:e.target.checked,conditions:e.target.checked ? [] : [{field:'module',operator:'contains',value:''}]})}/><span>接收该反馈源的全部工单</span></label></div>
            {!route.catchAll && <div className="route-condition"><label>字段<input value={String(routeCondition?.field ?? 'module')} onChange={e => updateRule({conditions:[{field:e.target.value,operator:(routeCondition?.operator ?? 'contains') as RoutingOperator,value:routeCondition?.value ?? ''}]})}/></label><label>条件<select value={routeCondition?.operator ?? 'contains'} onChange={e => updateRule({conditions:[{field:routeCondition?.field ?? 'module',operator:e.target.value as RoutingOperator,value:routeCondition?.value ?? ''}]})}><option value="contains">包含</option><option value="eq">等于</option><option value="neq">不等于</option><option value="exists">存在</option></select></label><label>值<input disabled={routeCondition?.operator === 'exists'} value={String(routeCondition?.value ?? '')} onChange={e => updateRule({conditions:[{field:routeCondition?.field ?? 'module',operator:(routeCondition?.operator ?? 'contains') as RoutingOperator,value:e.target.value}]})}/></label></div>}
          </div></details>}
        </div>
      </div>
      <footer className="workbench-actions"><span>{canSave ? '配置完整，可以保存' : `第 ${step} 步还有必填项`}</span><div><button className="ghost" onClick={closeEditor}>取消</button>{step > 1 && <button className="ghost framed" onClick={() => setStep(value => Math.max(1,value - 1) as Step)}>上一步</button>}{step < 4 ? <button className="primary compact" disabled={!stepComplete[step]} onClick={next}>继续</button> : <button className="primary compact" disabled={busy === 'save' || !canSave} onClick={() => void save()}>{busy === 'save' ? '保存中…' : '保存并体检'}</button>}</div></footer>
    </div></div>}
  </section>
}
