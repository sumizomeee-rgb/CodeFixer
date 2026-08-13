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
const executableRef = (runtime:AgentRuntime) => runtime === 'claudeCode' ? 'claude-code-cli' : runtime === 'codex' ? 'codex-cli' : 'opencode-cli'
const profileFromChoice = (choice:AgentChoice):DraftAgent => ({id:choice.id,runtime:choice.runtime,executableRef:executableRef(choice.runtime),model:choice.model,timeoutSeconds:1800})
const runtimeLabel = (runtime:AgentRuntime) => runtime === 'claudeCode' ? 'Claude Code' : runtime === 'codex' ? 'Codex' : 'OpenCode'
const profileLabel = (profile:AgentProfileConfig) => {
  const known = agentChoices.find(item => item.id === profile.id || item.model === profile.model)
  return known?.label ?? `${runtimeLabel(profile.runtime)}${profile.model ? ` · ${profile.model}` : ''}`
}
const dependencyLabel:Record<string,string>={
  'claude-code-cli':'Claude Code CLI',
  'codex-cli':'Codex CLI',
  'opencode-cli':'OpenCode CLI',
  'git-cli':'Git 命令行',
  'svn-cli':'SVN 命令行',
  'python-runtime':'Python 运行时',
}

function AgentMark({ runtime }:{ runtime:AgentRuntime }) {
  if (runtime === 'claudeCode') return <span className="runtime-mark runtime-claudeCode" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M16 4v24M7.5 7.5l17 17M4 16h24M7.5 24.5l17-17"/><path d="M10.2 4.8l11.6 22.4M4.8 10.2l22.4 11.6M4.8 21.8l22.4-11.6M10.2 27.2L21.8 4.8"/></svg></span>
  if (runtime === 'codex') return <span className="runtime-mark runtime-codex" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M16 5.2a6.1 6.1 0 0 1 10.3 4.4 6.1 6.1 0 0 1 .7 11.1 6.1 6.1 0 0 1-10 6.2 6.1 6.1 0 0 1-10.3-4.4A6.1 6.1 0 0 1 6 11.4 6.1 6.1 0 0 1 16 5.2Z"/><path d="m10.7 12.9 5.3-3.1 5.3 3.1v6.2L16 22.2l-5.3-3.1Z"/></svg></span>
  return <span className="runtime-mark runtime-opencode" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M5 8h9v5H10v6h4v5H5Zm13 0h9v16h-9v-5h4v-6h-4Z"/><path d="M13 13h6v6h-6Z"/></svg></span>
}

export function SettingsPage({ onModeChanged }:{ onModeChanged:(mode:ExecutionMode,etag:string)=>void }) {
  const [settings,setSettings] = useState<SettingsResponse|null>(null)
  const [readiness,setReadiness] = useState<ReadinessResponse|null>(null)
  const [notice,setNotice] = useState('')
  const [error,setError] = useState('')
  const [busy,setBusy] = useState(false)

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 3200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const refreshReadiness = async () => setReadiness(await api.readiness())
  const load = async () => {
    const next = await api.settings()
    setSettings(next)
    void refreshReadiness().catch(e => setError(e instanceof Error ? e.message : '依赖检查失败'))
  }
  useEffect(() => { void load().catch(e => setError(e instanceof Error ? e.message : '加载失败')) },[])
  if (!settings) return <section className="page-stack"><div className="page-heading"><div><h1>设置</h1><p>{error || '正在读取配置…'}</p></div></div></section>

  const put = async (config:SettingsResponse['config'],message:string) => {
    setBusy(true); setError('')
    try { const next = await api.putSettings(config,settings.etag); setSettings(next); setNotice(message); return next }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败'); return null }
    finally { setBusy(false) }
  }
  const changeMode = async (mode:ExecutionMode) => {
    setBusy(true); setError('')
    try {
      const result = await api.setExecutionMode(mode,settings.etag)
      setSettings({...settings,config:{...settings.config,execution:{...settings.config.execution,mode}},etag:result.etag})
      onModeChanged(mode,result.etag); setNotice('运行方式已保存')
    } catch (e) { setError(e instanceof Error ? e.message : '模式保存失败') }
    finally { setBusy(false) }
  }
  const chooseModel = async (choice:AgentChoice) => {
    const profile = profileFromChoice(choice)
    const index = settings.config.agentProfiles.findIndex(item => item.id === choice.id)
    const profiles = [...settings.config.agentProfiles]
    if (index >= 0) profiles[index] = {...profiles[index],...profile}; else profiles.push(profile)
    const next = await put({...settings.config,agentProfiles:profiles,execution:{...settings.config.execution,currentModelId:choice.id}},`当前模型已切换为 ${choice.label}`)
    if (next) void refreshReadiness().catch(() => undefined)
  }
  const saveLlmConcurrency = async (value:number) => {
    const safe = Math.max(1,Math.min(64,value || 1))
    await put({...settings.config,execution:{...settings.config.execution,maxConcurrentLlmCalls:safe}},`AI 并行调用数已调整为 ${safe}`)
  }

  const dependencyChecks = readiness?.checks.filter(item => item.id.startsWith('dependency.')) ?? []
  const coreChecks = readiness?.checks.filter(item => !item.id.startsWith('dependency.')) ?? []
  const currentProfile = settings.config.agentProfiles.find(item => item.id === settings.config.execution.currentModelId)
  const currentChoice = agentChoices.find(item => item.id === settings.config.execution.currentModelId)
  const relevantChecks = dependencyChecks.filter(item => item.required || item.dependencyId === currentProfile?.executableRef || item.status === 'failed')
  const currentHealth = currentProfile ? dependencyChecks.find(item => item.dependencyId === currentProfile.executableRef)?.status ?? 'unknown' : 'failed'
  const currentRuntime = currentProfile?.runtime ?? currentChoice?.runtime ?? 'claudeCode'
  const llmConcurrency = settings.config.execution.maxConcurrentLlmCalls ?? 4

  return <section className="page-stack settings-page">
    <div className="page-heading"><div><span className="page-kicker">CONTROL PARAMETERS</span><h1>设置</h1><p>控制平台运行节奏、当前模型和并发容量。</p></div></div>
    {notice && <div className="toast settings-toast" role="status">{notice}</div>}
    {error && <button className="notice-strip error-note" onClick={() => setError('')}>{error}</button>}

    <div className="settings-grid simplified-settings control-grid">
      <article className="settings-card control-card settings-mode"><header><span className="card-index">01</span><div><small>AUTOMATION</small><h2>运行方式</h2></div></header><p>新工单进入后，是静默执行到底，还是等待你在任务页放行。</p><div className={`mode-callout ${settings.config.execution.mode}`}><i/><div><b>{settings.config.execution.mode === 'automatic' ? '全自动接管' : '人工确认后开始'}</b><small>{settings.config.execution.mode === 'automatic' ? '自动分析、修复并执行全部交付动作' : '任务先进入 Pending，不占用 AI 并发'}</small></div></div><div className="segmented"><button disabled={busy} className={settings.config.execution.mode === 'awaitingStart' ? 'selected' : ''} onClick={() => void changeMode('awaitingStart')}>待我开始</button><button disabled={busy} className={settings.config.execution.mode === 'automatic' ? 'selected' : ''} onClick={() => void changeMode('automatic')}>全自动</button></div></article>

      <article className="settings-card control-card settings-agents"><header><span className="card-index">02</span><div><small>MODEL</small><h2>当前模型</h2></div></header><p>双 Agent 定位与修复阶段统一使用这个模型，切换后对新调用生效。</p><div className="current-model-control"><AgentMark runtime={currentRuntime}/><label><select aria-label="当前模型" disabled={busy} value={currentProfile ? settings.config.execution.currentModelId : ''} onChange={e => {const choice = agentChoices.find(item => item.id === e.target.value); if (choice) void chooseModel(choice)}}><option value="" disabled>选择模型</option>{currentProfile && !currentChoice && <option value={currentProfile.id}>{profileLabel(currentProfile)}</option>}{agentChoices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select><small>{currentChoice?.note ?? (currentProfile ? '兼容自定义模型配置' : '选择模型后即可运行 Agent 阶段')}</small></label><span className={`profile-health ${currentHealth}`} title="当前模型运行时状态"/></div></article>

      <article className="settings-card control-card concurrency-card"><header><span className="card-index">03</span><div><small>CAPACITY</small><h2>AI 并发池</h2></div></header><p>限制全平台同时运行的 LLM 调用数。任务可以更多，但会在 Agent 阶段公平排队。</p><div className="concurrency-control"><button aria-label="减少并发" disabled={busy || llmConcurrency <= 1} onClick={() => void saveLlmConcurrency(llmConcurrency - 1)}>−</button><div><strong>{llmConcurrency}</strong><span>个并行调用</span></div><button aria-label="增加并发" disabled={busy || llmConcurrency >= 64} onClick={() => void saveLlmConcurrency(llmConcurrency + 1)}>+</button></div><div className="capacity-meter" aria-label={`当前并发容量 ${llmConcurrency}`}>{Array.from({length:8},(_,index)=><i className={index<llmConcurrency?'active':''} key={index}/>)}</div><div className="capacity-scale"><span className={llmConcurrency <= 2 ? 'active' : ''}>保守</span><i/><span className={llmConcurrency > 2 && llmConcurrency <= 6 ? 'active' : ''}>均衡</span><i/><span className={llmConcurrency > 6 ? 'active' : ''}>高吞吐</span></div></article>

      <article className="settings-card control-card settings-environment"><header><span className="card-index">04</span><div><small>HEALTH</small><h2>运行环境</h2></div><button className="ghost framed" disabled={!readiness} onClick={() => void refreshReadiness()}>{readiness ? '重新检查' : '检查中…'}</button></header><p>这里只显示当前配置真正会用到的依赖；未启用的工具不会制造黄灯。</p><div className="readiness-summary"><strong className={readiness?.status ?? 'checking'}>{readiness?.status === 'ready' ? '环境正常' : readiness?.status === 'warning' ? '可运行，有建议项' : readiness?.status === 'not_ready' ? '存在阻断' : '正在检查'}</strong><span>{readiness ? `${coreChecks.filter(item => item.status === 'ready').length}/${coreChecks.length} 项核心正常` : '正在验证本机环境'}</span></div><div className="dependency-grid relevant-dependencies">{relevantChecks.map(item => <div className={`dependency-row ${item.status}`} key={item.id}><i/><div><b>{dependencyLabel[item.dependencyId??'']??item.dependencyId}</b><small>{item.summary}<code>{item.dependencyId}</code></small></div><span>{item.status === 'ready' ? '可用' : item.status === 'failed' ? '阻断' : '注意'}</span></div>)}{readiness && relevantChecks.length === 0 && <div className="all-clear">当前没有额外命令依赖。</div>}</div></article>
    </div>
  </section>
}
