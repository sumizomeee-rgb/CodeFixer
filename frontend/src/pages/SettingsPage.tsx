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
  if (runtime === 'claudeCode') return <span className="runtime-mark runtime-claudeCode" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z"/></svg></span>
  if (runtime === 'codex') return <span className="runtime-mark runtime-codex" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/></svg></span>
  return <span className="runtime-mark runtime-opencode" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M5 8h9v5H10v6h4v5H5Zm13 0h9v16h-9v-5h4v-6h-4Z"/><path d="M13 13h6v6h-6Z"/></svg></span>
}

export function SettingsPage({ onModeChanged }:{ onModeChanged:(mode:ExecutionMode,etag:string)=>void }) {
  const [settings,setSettings] = useState<SettingsResponse|null>(null)
  const [readiness,setReadiness] = useState<ReadinessResponse|null>(null)
  const [notice,setNotice] = useState('')
  const [error,setError] = useState('')
  // 按卡区分忙碌态：改并发不该把运行方式和模型选择一起灰掉。
  const [busy,setBusy] = useState<'mode'|'model'|'concurrency'|''>('')
  // 依赖检查要跑 subprocess 取版本，比 settings 慢得多。重查期间保留上一份结果，只标记检查中。
  const [checking,setChecking] = useState(false)

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 3200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const refreshReadiness = async () => { setChecking(true); try { setReadiness(await api.readiness()) } finally { setChecking(false) } }
  const load = async () => {
    const next = await api.settings()
    setSettings(next)
    void refreshReadiness().catch(e => setError(e instanceof Error ? e.message : '依赖检查失败'))
  }
  useEffect(() => { void load().catch(e => setError(e instanceof Error ? e.message : '加载失败')) },[])
  // 加载态与就绪态共用同一套标题区结构（kicker → h1 → 说明），
  // 否则接口回来时标题区从两行变三行，整页内容跟着往下跳。
  const heading = <div className="page-heading"><div><span className="page-kicker">CONTROL PARAMETERS</span><h1>设置</h1><p>控制平台运行节奏、当前模型和并发容量。</p></div></div>
  if (!settings) return <section className="page-stack settings-page">{heading}{error ? <div className="inline-alert">{error}</div> : <div className="settings-grid simplified-settings control-grid">{['01','02','03','04'].map(index => <article className="settings-card control-card card-skeleton" key={index} aria-hidden="true"><header><span className="card-index">{index}</span><div><small/><h2/></div></header><p/><div className="skeleton-control"/></article>)}</div>}</section>

  const put = async (config:SettingsResponse['config'],message:string,scope:'model'|'concurrency') => {
    setBusy(scope); setError('')
    try { const next = await api.putSettings(config,settings.etag); setSettings(next); setNotice(message); return next }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败'); return null }
    finally { setBusy('') }
  }
  const changeMode = async (mode:ExecutionMode) => {
    setBusy('mode'); setError('')
    try {
      const result = await api.setExecutionMode(mode,settings.etag)
      setSettings({...settings,config:{...settings.config,execution:{...settings.config.execution,mode}},etag:result.etag})
      onModeChanged(mode,result.etag); setNotice('运行方式已保存')
    } catch (e) { setError(e instanceof Error ? e.message : '模式保存失败') }
    finally { setBusy('') }
  }
  const chooseModel = async (choice:AgentChoice) => {
    const profile = profileFromChoice(choice)
    const index = settings.config.agentProfiles.findIndex(item => item.id === choice.id)
    const profiles = [...settings.config.agentProfiles]
    if (index >= 0) profiles[index] = {...profiles[index],...profile}; else profiles.push(profile)
    const next = await put({...settings.config,agentProfiles:profiles,execution:{...settings.config.execution,currentModelId:choice.id}},`当前模型已切换为 ${choice.label}`,'model')
    if (next) void refreshReadiness().catch(() => undefined)
  }
  const saveLlmConcurrency = async (value:number) => {
    const safe = Math.max(1,Math.min(64,value || 1))
    await put({...settings.config,execution:{...settings.config.execution,maxConcurrentLlmCalls:safe}},`AI 并行调用数已调整为 ${safe}`,'concurrency')
  }

  const dependencyChecks = readiness?.checks.filter(item => item.id.startsWith('dependency.')) ?? []
  const blockedChecks = readiness?.checks.filter(item => item.status === 'failed') ?? []
  const currentProfile = settings.config.agentProfiles.find(item => item.id === settings.config.execution.currentModelId)
  const currentChoice = agentChoices.find(item => item.id === settings.config.execution.currentModelId)
  const relevantChecks = dependencyChecks.filter(item => item.required || item.dependencyId === currentProfile?.executableRef || item.status === 'failed')
  const currentHealth = currentProfile ? dependencyChecks.find(item => item.dependencyId === currentProfile.executableRef)?.status ?? 'unknown' : 'failed'
  const currentRuntime = currentProfile?.runtime ?? currentChoice?.runtime ?? 'claudeCode'
  const llmConcurrency = settings.config.execution.maxConcurrentLlmCalls ?? 4

  return <section className="page-stack settings-page">
    {heading}
    {notice && <div className="toast settings-toast" role="status">{notice}</div>}
    {error && <button className="notice-strip error-note" onClick={() => setError('')}>{error}</button>}

    <div className="settings-grid simplified-settings control-grid">
      <article className="settings-card control-card settings-mode"><header><span className="card-index">01</span><div><small>AUTOMATION</small><h2>运行方式</h2></div></header><p>新工单进入后，是静默执行到底，还是等待你在任务页放行。</p><div className={`mode-callout ${settings.config.execution.mode}`}><i/><div><b>{settings.config.execution.mode === 'automatic' ? '全自动接管' : '人工确认后开始'}</b><small>{settings.config.execution.mode === 'automatic' ? '自动分析、修复并执行全部交付动作' : '任务先进入 Pending，不占用 AI 并发'}</small></div></div><div className="segmented"><button disabled={busy === 'mode'} className={settings.config.execution.mode === 'awaitingStart' ? 'selected' : ''} onClick={() => void changeMode('awaitingStart')}>待我开始</button><button disabled={busy === 'mode'} className={settings.config.execution.mode === 'automatic' ? 'selected' : ''} onClick={() => void changeMode('automatic')}>全自动</button></div></article>

      <article className="settings-card control-card settings-agents"><header><span className="card-index">02</span><div><small>MODEL</small><h2>当前模型</h2></div></header><p>问题定位和代码修复统一使用这个模型，切换后对新的处理请求生效。</p><div className="current-model-control"><AgentMark runtime={currentRuntime}/><label><select aria-label="当前模型" disabled={busy === 'model'} value={currentProfile ? settings.config.execution.currentModelId : ''} onChange={e => {const choice = agentChoices.find(item => item.id === e.target.value); if (choice) void chooseModel(choice)}}><option value="" disabled>选择模型</option>{currentProfile && !currentChoice && <option value={currentProfile.id}>{profileLabel(currentProfile)}</option>}{agentChoices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select><small>{currentChoice?.note ?? (currentProfile ? '兼容自定义模型配置' : '选择模型后即可开始处理任务')}</small></label><span className={`profile-health ${currentHealth}`} title="当前模型运行时状态"/></div></article>

      <article className="settings-card control-card concurrency-card"><header><span className="card-index">03</span><div><small>CAPACITY</small><h2>AI 并发池</h2></div></header><p>限制全平台同时进行的问题分析和代码修改数量；更多任务会自动排队。</p><div className="concurrency-control"><button aria-label="减少并发" disabled={busy === 'concurrency' || llmConcurrency <= 1} onClick={() => void saveLlmConcurrency(llmConcurrency - 1)}>−</button><div><strong>{llmConcurrency}</strong><span>个并行调用</span></div><button aria-label="增加并发" disabled={busy === 'concurrency' || llmConcurrency >= 64} onClick={() => void saveLlmConcurrency(llmConcurrency + 1)}>+</button></div><div className="capacity-meter" aria-label={`当前并发容量 ${llmConcurrency}`}>{Array.from({length:8},(_,index)=><i className={index<llmConcurrency?'active':''} key={index}/>)}</div><div className="capacity-scale"><span className={llmConcurrency <= 2 ? 'active' : ''}>保守</span><i/><span className={llmConcurrency > 2 && llmConcurrency <= 6 ? 'active' : ''}>均衡</span><i/><span className={llmConcurrency > 6 ? 'active' : ''}>高吞吐</span></div></article>

      <article className="settings-card control-card settings-environment"><header><span className="card-index">04</span><div><small>HEALTH</small><h2>运行环境</h2></div><button className="ghost framed" disabled={checking} onClick={() => void refreshReadiness()}>{checking ? '检查中…' : '重新检查'}</button></header><p>这里只列出当前配置真正会用到的命令行工具；未启用的工具不参与判定。</p><div className={checking ? 'dependency-grid relevant-dependencies is-checking' : 'dependency-grid relevant-dependencies'}>{relevantChecks.map(item => <div className={`dependency-row ${item.status}`} key={item.id}><i/><div><b>{dependencyLabel[item.dependencyId??'']??item.dependencyId}</b><small>{item.status === 'ready' ? (item.version ? `版本 ${item.version}` : '已就绪') : item.summary}{item.status !== 'ready' && (item.suggestion || item.command) && <code>{item.suggestion ?? item.command}</code>}</small></div><span>{item.status === 'ready' ? '可用' : item.status === 'failed' ? '阻断' : '注意'}</span></div>)}
      {/* 平台自身的四项自检（配置、数据目录、SQLite、构建产物）不列出：它们正常是打开这个页面的前提，
          报一句「4/4 正常」既不可点开也无从核对。只有真的挂了才需要占位置。 */}
      {blockedChecks.filter(item => !item.id.startsWith('dependency.')).map(item => <div className="dependency-row failed" key={item.id}><i/><div><b>{item.summary}</b><small>平台自检未通过<code>{item.id}</code></small></div><span>阻断</span></div>)}
      {readiness && relevantChecks.length === 0 && blockedChecks.length === 0 && <div className="all-clear">当前模型不依赖额外命令行工具。</div>}
      {/* 首次检查未回时占一行的位，避免结果到达时卡片高度跳一次 */}
      {!readiness && <div className="dependency-row" aria-hidden="true"><i/><div><b className="skeleton-text"/><small className="skeleton-text"/></div></div>}</div></article>
    </div>
  </section>
}
