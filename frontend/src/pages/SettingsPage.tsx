import { useEffect, useState } from 'react'
import type { AgentProfileConfig, AgentRuntime, ExecutionMode, ReadinessResponse, SettingsResponse } from '../entities/config'
import { api } from '../lib/api'

type DraftAgent = AgentProfileConfig
type AgentChoice = { id:string; runtime:AgentRuntime; model:string; label:string; note:string }

const agentChoices:AgentChoice[] = [
  { id:'claude-haiku', runtime:'claudeCode', model:'claude-haiku-4-5', label:'Claude Haiku', note:'更快、更省，适合高频任务' },
  { id:'claude-sonnet', runtime:'claudeCode', model:'sonnet', label:'Claude Sonnet', note:'速度与能力平衡' },
  { id:'claude-opus', runtime:'claudeCode', model:'opus', label:'Claude Opus', note:'复杂修复与深度推理' },
  { id:'gpt-5.6-sol', runtime:'codex', model:'gpt-5.6-sol', label:'GPT-5.6 Sol', note:'复杂工程与高难度修复' },
  { id:'gpt-5.6-terra', runtime:'codex', model:'gpt-5.6-terra', label:'GPT-5.6 Terra', note:'能力与消耗平衡' },
  { id:'gpt-5.6-luna', runtime:'codex', model:'gpt-5.6-luna', label:'GPT-5.6 Luna', note:'低消耗、高频任务' },
]
const executableRef=(runtime:AgentRuntime)=>runtime==='claudeCode'?'claude-code-cli':runtime==='codex'?'codex-cli':'opencode-cli'
const profileFromChoice=(choice:AgentChoice):DraftAgent=>({id:choice.id,runtime:choice.runtime,executableRef:executableRef(choice.runtime),model:choice.model,timeoutSeconds:1800})
const runtimeLabel=(runtime:AgentRuntime)=>runtime==='claudeCode'?'Claude Code':runtime==='codex'?'Codex':'OpenCode'
const profileLabel=(profile:AgentProfileConfig)=>{
  if(profile.id==='claude-haiku'||profile.model==='claude-haiku-4-5')return 'Claude Haiku'
  if(profile.id==='claude-sonnet'||profile.model==='sonnet')return 'Claude Sonnet'
  if(profile.id==='claude-opus'||profile.model==='opus')return 'Claude Opus'
  if(profile.model==='gpt-5.6-sol')return 'GPT-5.6 Sol'
  if(profile.model==='gpt-5.6-terra')return 'GPT-5.6 Terra'
  if(profile.model==='gpt-5.6-luna')return 'GPT-5.6 Luna'
  if(profile.model)return `${runtimeLabel(profile.runtime)} · ${profile.model}`
  return `${runtimeLabel(profile.runtime)} · 默认模型`
}

function AgentMark({ runtime }:{ runtime:AgentRuntime }) {
  if(runtime==='claudeCode') return <span className="runtime-mark runtime-claudeCode" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M16 4v24M7.5 7.5l17 17M4 16h24M7.5 24.5l17-17"/><path d="M10.2 4.8l11.6 22.4M4.8 10.2l22.4 11.6M4.8 21.8l22.4-11.6M10.2 27.2L21.8 4.8"/></svg></span>
  if(runtime==='codex') return <span className="runtime-mark runtime-codex" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M16 5.2a6.1 6.1 0 0 1 10.3 4.4 6.1 6.1 0 0 1 .7 11.1 6.1 6.1 0 0 1-10 6.2 6.1 6.1 0 0 1-10.3-4.4A6.1 6.1 0 0 1 6 11.4 6.1 6.1 0 0 1 16 5.2Z"/><path d="m10.7 12.9 5.3-3.1 5.3 3.1v6.2L16 22.2l-5.3-3.1Z"/></svg></span>
  return <span className="runtime-mark runtime-opencode" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M5 8h9v5H10v6h4v5H5Zm13 0h9v16h-9v-5h4v-6h-4Z"/><path d="M13 13h6v6h-6Z"/></svg></span>
}

export function SettingsPage({ onModeChanged }:{ onModeChanged:(mode:ExecutionMode,etag:string)=>void }) {
  const [settings,setSettings]=useState<SettingsResponse|null>(null);const [readiness,setReadiness]=useState<ReadinessResponse|null>(null);const [pathId,setPathId]=useState('');const [pathValue,setPathValue]=useState('');const [notice,setNotice]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false)
  const refreshReadiness=async()=>{setReadiness(await api.readiness())}
  const load=async()=>{const next=await api.settings();setSettings(next);void refreshReadiness().catch(e=>setError(e instanceof Error?e.message:'依赖检查失败'))}
  useEffect(()=>{ load().catch(e=>setError(e instanceof Error?e.message:'加载失败')) },[])
  if(!settings) return <section className="page-stack"><div className="page-heading"><div><h1>设置</h1><p>{error||'正在读取配置…'}</p></div></div></section>
  const put=async(config:SettingsResponse['config'],message:string)=>{setBusy(true);setError('');try{const next=await api.putSettings(config,settings.etag);setSettings(next);setNotice(message);return next}catch(e){setError(e instanceof Error?e.message:'保存失败');return null}finally{setBusy(false)}}
  const changeMode=async(mode:ExecutionMode)=>{setBusy(true);setError('');try{const r=await api.setExecutionMode(mode,settings.etag);const next={...settings,config:{...settings.config,execution:{...settings.config.execution,mode}},etag:r.etag};setSettings(next);onModeChanged(mode,r.etag);setNotice('已保存')}catch(e){setError(e instanceof Error?e.message:'模式保存失败')}finally{setBusy(false)}}
  const savePath=async()=>{if(!pathId||!pathValue)return;const next=await put({...settings.config,pathBindings:{...settings.config.pathBindings,[pathId]:pathValue}},'本机路径已保存');if(next){setPathId('');setPathValue('')}}
  const chooseModel=async(choice:AgentChoice)=>{
    const profile=profileFromChoice(choice)
    const existing=settings.config.agentProfiles.findIndex(item=>item.id===choice.id)
    const profiles=[...settings.config.agentProfiles]
    if(existing>=0)profiles[existing]={...profiles[existing],...profile};else profiles.push(profile)
    const next=await put({...settings.config,agentProfiles:profiles,execution:{...settings.config.execution,currentModelId:choice.id}},`当前模型已切换为 ${choice.label}`)
    if(next)void refreshReadiness().catch(()=>{})
  }
  const dependencyChecks=readiness?.checks.filter(item=>item.id.startsWith('dependency.'))??[]
  const displayedDependencyChecks=readiness?dependencyChecks:Object.keys(settings.config.executableBindings).map(id=>({id:`dependency.${id}`,dependencyId:id,status:'checking' as const,summary:'正在检查',command:settings.config.executableBindings[id]?.command?.[0],version:null}))
  const coreChecks=readiness?.checks.filter(item=>!item.id.startsWith('dependency.'))??[]
  const currentProfile=settings.config.agentProfiles.find(item=>item.id===settings.config.execution.currentModelId)
  const currentChoice=agentChoices.find(item=>item.id===settings.config.execution.currentModelId)
  const currentHealth=currentProfile?dependencyChecks.find(item=>item.dependencyId===currentProfile.executableRef)?.status??'unknown':'failed'
  const currentRuntime=currentProfile?.runtime??currentChoice?.runtime??'claudeCode'
  return <section className="page-stack"><div className="page-heading"><div><h1>设置</h1><p>选择平台如何运行，以及所有任务统一使用的模型。</p></div></div>{notice&&<button className="notice-strip success-note" onClick={()=>setNotice('')}>{notice}</button>}{error&&<button className="notice-strip error-note" onClick={()=>setError('')}>{error}</button>}
  <div className="settings-grid simplified-settings">
  <article className="settings-card settings-environment"><div className="card-title-row"><div><span className="card-index">01 · SYSTEM</span><h2>运行环境</h2><p>只在依赖确实影响任务时提醒你。</p></div><button className="ghost framed" disabled={!readiness} onClick={()=>void refreshReadiness()}>{readiness?'重新检查':'检查中…'}</button></div><div className="readiness-summary"><strong className={readiness?.status??'checking'}>{readiness?.status==='ready'?'环境正常':readiness?.status==='warning'?'可运行，部分能力受限':readiness?.status==='not_ready'?'存在阻断':'正在检查'}</strong><span>{readiness?`${coreChecks.filter(item=>item.status==='ready').length}/${coreChecks.length} 项核心正常 · ${dependencyChecks.filter(item=>item.status==='ready').length} 项命令可用`:'正在验证本机环境'}</span></div><div className="dependency-grid">{displayedDependencyChecks.map(item=><div className={`dependency-row ${item.status}`} key={item.id}><i/><div><b>{item.dependencyId}</b><small>{item.summary}</small></div><code>{item.version??item.command??'—'}</code></div>)}</div></article>
  <article className="settings-card settings-mode"><span className="card-index">02 · CONTROL</span><h2>运行方式</h2><p>选择新任务是自动开始，还是先等你确认。</p><div className="mode-callout"><b>{settings.config.execution.mode==='automatic'?'静默接管':'人工放行'}</b><small>{settings.config.execution.mode==='automatic'?'工单进入后自动分析、修复并交付':'任务进入 Pending，只有你点击开始才执行'}</small></div><div className="segmented"><button disabled={busy} className={settings.config.execution.mode==='awaitingStart'?'selected':''} onClick={()=>void changeMode('awaitingStart')}>待我开始</button><button disabled={busy} className={settings.config.execution.mode==='automatic'?'selected':''} onClick={()=>void changeMode('automatic')}>全自动</button></div></article>
  <article className="settings-card settings-agents"><span className="card-index">03 · MODEL</span><h2>当前模型</h2><p>所有需要 LLM 的阶段统一使用这个模型。</p><div className="current-model-control"><AgentMark runtime={currentRuntime}/><label><select aria-label="当前模型" disabled={busy} value={currentProfile?settings.config.execution.currentModelId:''} onChange={e=>{const choice=agentChoices.find(item=>item.id===e.target.value);if(choice)void chooseModel(choice)}}><option value="" disabled>选择模型</option>{currentProfile&&!currentChoice&&<option value={currentProfile.id}>{profileLabel(currentProfile)}</option>}{agentChoices.map(choice=><option key={choice.id} value={choice.id}>{choice.label}</option>)}</select><small>{currentChoice?.note??(currentProfile?'兼容旧配置；选择上方模型即可切换':'选择一个模型后，所有后续 LLM 调用都会使用它')}</small></label><span className={`profile-health ${currentHealth}`}/></div></article>
  </div>
  <details className="settings-advanced"><summary>高级：本机环境</summary><div className="settings-grid advanced-grid"><article className="settings-card"><h2>路径</h2><div className="binding-list">{Object.entries(settings.config.pathBindings).map(([id,path])=><div key={id}><code>{id}</code><span>{path}</span></div>)}</div><div className="inline-builder"><input placeholder="引用名称" value={pathId} onChange={e=>setPathId(e.target.value)}/><input placeholder="本机路径" value={pathValue} onChange={e=>setPathValue(e.target.value)}/><button className="primary compact" disabled={busy||!pathId||!pathValue} onClick={()=>void savePath()}>添加</button></div></article><article className="settings-card"><h2>命令</h2><div className="binding-list">{Object.keys(settings.config.executableBindings).map(id=>{const binding=settings.config.executableBindings[id];return <div key={id}><code>{id}</code><span>{binding?.command?.join(' ')||'—'}</span></div>})}</div></article></div></details>
  </section>
}
