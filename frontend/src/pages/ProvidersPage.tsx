import { useEffect, useState } from 'react'
import type { SettingsResponse, TicketProviderConfig } from '../entities/config'
import { api } from '../lib/api'

type ProviderType = 'redmine'|'tapd'
type AuthMode = 'basic'|'oauth'
type ConnectionState = 'ready'|'failed'

const stringField = (value:unknown) => typeof value === 'string' ? value : ''

export function ProvidersPage() {
  const [settings,setSettings] = useState<SettingsResponse|null>(null)
  const [providers,setProviders] = useState<TicketProviderConfig[]>([])
  const [notice,setNotice] = useState('')
  const [busy,setBusy] = useState('')
  const [show,setShow] = useState(false)
  const [editingId,setEditingId] = useState<string|null>(null)
  const [connectionStates,setConnectionStates] = useState<Record<string,ConnectionState>>({})
  const [type,setType] = useState<ProviderType>('redmine')
  const [id,setId] = useState('')
  const [baseUrl,setBaseUrl] = useState('')
  const [workspaceId,setWorkspaceId] = useState('')
  const [authMode,setAuthMode] = useState<AuthMode>('basic')
  const [secretA,setSecretA] = useState('')
  const [secretB,setSecretB] = useState('')

  const load = async () => {
    try { const [nextSettings,nextProviders] = await Promise.all([api.settings(),api.providers()]); const items = nextProviders.items as TicketProviderConfig[]; setSettings(nextSettings); setProviders(items); return items }
    catch (e) { setNotice(e instanceof Error ? e.message : '反馈源加载失败'); return [] }
  }
  useEffect(() => {
    void load().then(async items => {
      const enabled = items.filter(provider => provider.enabled !== false)
      const results = await Promise.allSettled(enabled.map(provider => api.testProvider(provider.id)))
      setConnectionStates(value => {
        const next = {...value}
        enabled.forEach((provider,index) => { next[provider.id] = results[index].status === 'fulfilled' ? 'ready' : 'failed' })
        return next
      })
    })
  },[])

  const reset = () => { setShow(false); setEditingId(null); setType('redmine'); setId(''); setBaseUrl(''); setWorkspaceId(''); setAuthMode('basic'); setSecretA(''); setSecretB('') }
  const openNew = () => { reset(); setShow(true) }
  const openEdit = (provider:TicketProviderConfig) => {
    setEditingId(provider.id); setType(provider.type); setId(provider.id)
    setBaseUrl(stringField(provider.baseUrl)); setWorkspaceId(stringField(provider.workspaceId))
    const auth = provider.auth && typeof provider.auth === 'object' ? provider.auth as Record<string,unknown> : {}
    setAuthMode(auth.mode === 'oauth' ? 'oauth' : 'basic'); setSecretA(''); setSecretB(''); setShow(true)
  }
  const testConnection = async (providerId:string) => {
    setBusy(`test:${providerId}`)
    try {
      await api.testProvider(providerId); setConnectionStates(value => ({...value,[providerId]:'ready'})); setNotice('连接验证通过')
      await load()
    } catch (e) { setConnectionStates(value => ({...value,[providerId]:'failed'})); setNotice(e instanceof Error ? e.message : '操作失败') }
    finally { setBusy('') }
  }
  const save = async () => {
    if (!settings || !id) return
    const existing = editingId ? settings.config.ticketProviders.find(item => item.id === editingId) : undefined
    const secretPrefix = `provider-${encodeURIComponent(id)}`
    const existingAuth = existing?.auth && typeof existing.auth === 'object' ? existing.auth as Record<string,unknown> : {}
    const provider:TicketProviderConfig = type === 'redmine' ? {
      ...existing,id,type,enabled:existing?.enabled ?? true,baseUrl,
      apiKeySecretRef:stringField(existing?.apiKeySecretRef) || `${secretPrefix}-api-key`,
      pollIntervalSeconds:Number(existing?.pollIntervalSeconds ?? 60),
    } : {
      ...existing,id,type,enabled:existing?.enabled ?? true,workspaceId,
      auth:authMode === 'basic' ? {
        mode:'basic',
        usernameSecretRef:stringField(existingAuth.usernameSecretRef) || `${secretPrefix}-username`,
        passwordSecretRef:stringField(existingAuth.passwordSecretRef) || `${secretPrefix}-password`,
      } : {mode:'oauth',tokenSecretRef:stringField(existingAuth.tokenSecretRef) || `${secretPrefix}-token`},
      pollIntervalSeconds:Number(existing?.pollIntervalSeconds ?? 60),
    }
    const nextProviders = editingId ? settings.config.ticketProviders.map(item => item.id === editingId ? provider : item) : [...settings.config.ticketProviders,provider]
    try {
      setBusy('save')
      if (type === 'redmine' && secretA) await api.setSecret(stringField(provider.apiKeySecretRef),secretA)
      if (type === 'tapd') {
        const auth = provider.auth as Record<string,unknown>
        if (authMode === 'basic') {
          if (secretA) await api.setSecret(stringField(auth.usernameSecretRef),secretA)
          if (secretB) await api.setSecret(stringField(auth.passwordSecretRef),secretB)
        } else if (secretA) await api.setSecret(stringField(auth.tokenSecretRef),secretA)
      }
      const next = await api.putSettings({...settings.config,ticketProviders:nextProviders},settings.etag)
      setSettings(next); reset(); await load()
      try {
        await api.testProvider(provider.id)
        setConnectionStates(value => ({...value,[provider.id]:'ready'}))
        setNotice(editingId ? '反馈源配置已更新，连接正常' : '反馈源已保存，连接正常')
      } catch (e) {
        setConnectionStates(value => ({...value,[provider.id]:'failed'}))
        const reason = e instanceof Error ? e.message : '连接测试失败'
        setNotice(`反馈源已保存，但${reason}`)
      }
    } catch (e) { setNotice(e instanceof Error ? e.message : '保存失败') }
    finally { setBusy('') }
  }

  const secretRequired = !editingId && (!secretA || (type === 'tapd' && authMode === 'basic' && !secretB))
  return <section className="page-stack providers-page">
    <div className="page-heading"><div><span className="page-kicker">INTAKE CHANNELS</span><h1>反馈源</h1><p>连接日常提交 Bug 和需求的平台；登录信息只保存在当前部署机的 .local 中。</p></div>{providers.length > 0 && <button className="primary compact" onClick={openNew}>添加反馈源</button>}</div>
    {notice && <button className="notice-strip" onClick={() => setNotice('')}>{notice}</button>}
    {providers.length === 0 ? <div className="empty-state"><h2>还没有反馈源</h2><p>连接 Redmine 或 TAPD 后，CodeFixer 才能收取真实 Bug。</p><button className="primary compact" onClick={openNew}>连接反馈源</button></div> : <div className="provider-grid refined-provider-grid">{providers.map(provider => {
      const connectionState = connectionStates[provider.id]
      const health = provider.enabled === false ? 'inactive' : connectionState ?? 'unknown'
      const descriptor = provider.type === 'redmine' ? stringField(provider.baseUrl) : `Workspace ${stringField(provider.workspaceId)}`
      return <article className="provider-card provider-channel" data-health={health} key={provider.id}><div className={`provider-monogram ${provider.type}`}><span>{provider.type === 'tapd' ? 'T' : 'R'}</span></div><div className="provider-body"><small>{provider.type === 'tapd' ? 'TAPD' : 'REDMINE'}</small><h2>{provider.id}</h2><code>{descriptor || '尚未填写服务信息'}</code><div className="provider-meta"><span><i className={health === 'ready' ? 'ready-dot' : health === 'failed' ? 'failed-dot' : ''}/>{health === 'ready' ? '连接正常' : health === 'failed' ? '连接失败' : health === 'inactive' ? '已停用' : '已配置 · 待验证'}</span></div></div><div className="provider-actions"><button className="ghost action-link" onClick={() => openEdit(provider)}>编辑</button><button className="ghost framed" disabled={!!busy} onClick={() => void testConnection(provider.id)}>{busy === `test:${provider.id}` ? '测试中…' : '测试连接'}</button></div></article>
    })}</div>}
    {show && <div className="modal-backdrop"><div className="config-modal provider-editor" role="dialog" aria-modal="true"><div className="modal-head"><div><small className="modal-kicker">TICKET PROVIDER</small><h2>{editingId ? '编辑反馈源' : '添加反馈源'}</h2><p>账号、密码和 Token 不会写进项目配置，也不会被页面回显。</p></div><button className="icon-btn" onClick={reset} aria-label="关闭">×</button></div><div className="provider-type-switch"><button className={type === 'redmine' ? 'selected' : ''} disabled={!!editingId} onClick={() => setType('redmine')}><span>R</span><div><b>Redmine</b><small>API Key 登录</small></div></button><button className={type === 'tapd' ? 'selected' : ''} disabled={!!editingId} onClick={() => setType('tapd')}><span>T</span><div><b>TAPD</b><small>账号密码或 Token</small></div></button></div><div className="form-grid polished-form"><label>反馈源名称<input value={id} disabled={!!editingId} onChange={e => setId(e.target.value)} placeholder="例如：公司缺陷库"/></label>{type === 'redmine' ? <><label>服务地址<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="https://redmine.example.com"/></label><label className="span-field">API Key<input type="password" value={secretA} onChange={e => setSecretA(e.target.value)} placeholder={editingId ? '已保存；留空表示不更换' : '输入 Redmine API Key'}/></label></> : <><label>工作区 ID<input value={workspaceId} onChange={e => setWorkspaceId(e.target.value)} placeholder="10101010"/></label><label>登录方式<select value={authMode} onChange={e => setAuthMode(e.target.value as AuthMode)}><option value="basic">账号密码</option><option value="oauth">Access Token</option></select></label>{authMode === 'basic' ? <><label>账号<input value={secretA} onChange={e => setSecretA(e.target.value)} placeholder={editingId ? '已保存；留空不更换' : ''} autoComplete="username"/></label><label>密码<input type="password" value={secretB} onChange={e => setSecretB(e.target.value)} placeholder={editingId ? '已保存；留空不更换' : ''} autoComplete="current-password"/></label></> : <label className="span-field">Access Token<input type="password" value={secretA} onChange={e => setSecretA(e.target.value)} placeholder={editingId ? '已保存；留空不更换' : '输入 TAPD Token'}/></label>}</>}</div><div className="secret-boundary-note"><svg viewBox="0 0 24 24"><path d="M7 10V8a5 5 0 0 1 10 0v2M5 10h14v10H5z"/></svg><div><b>本机私密存储</b><span>保存后界面只知道“已配置”，无法读回真实值。</span></div></div><div className="modal-actions"><button className="ghost" onClick={reset}>取消</button><button className="primary compact" disabled={!!busy || !id || (type === 'redmine' && !baseUrl) || (type === 'tapd' && !workspaceId) || secretRequired} onClick={() => void save()}>{busy === 'save' ? '保存中…' : editingId ? '保存更改' : '保存反馈源'}</button></div></div></div>}
  </section>
}
