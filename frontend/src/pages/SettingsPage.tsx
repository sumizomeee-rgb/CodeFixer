import { useEffect, useState } from 'react'
import type { ExecutionMode, SettingsResponse } from '../entities/config'
import { api } from '../lib/api'

export function SettingsPage({ onModeChanged }:{ onModeChanged:(mode:ExecutionMode,etag:string)=>void }) {
  const [settings,setSettings]=useState<SettingsResponse|null>(null)
  const [secretKey,setSecretKey]=useState('')
  const [secretValue,setSecretValue]=useState('')
  const [notice,setNotice]=useState('')
  useEffect(()=>{ api.settings().then(setSettings).catch(e=>setNotice(e instanceof Error?e.message:'加载失败')) },[])
  if(!settings) return <section className="page-stack"><div className="page-heading"><div><span className="eyebrow">SYSTEM CONFIG</span><h1>系统设置</h1><p>{notice||'正在读取配置…'}</p></div></div></section>
  const changeMode=async(mode:ExecutionMode)=>{ const r=await api.setExecutionMode(mode,settings.etag); const next={...settings,config:{...settings.config,execution:{...settings.config.execution,mode}},etag:r.etag};setSettings(next);onModeChanged(mode,r.etag);setNotice('执行模式已保存') }
  const saveSecret=async()=>{ if(!secretKey||!secretValue)return;await api.setSecret(secretKey,secretValue);setSettings({...settings,secrets:{...settings.secrets,[secretKey]:{configured:true}}});setSecretValue('');setNotice(`Secret ${secretKey} 已安全保存`) }
  return <section className="page-stack"><div className="page-heading"><div><span className="eyebrow">SYSTEM CONFIG</span><h1>系统设置</h1><p>机器绑定和 Secret 不进入共享项目配置；运行中 TaskRun 不受热重载影响。</p></div></div>{notice&&<div className="success-banner">{notice}</div>}
    <div className="settings-grid"><article className="settings-card"><span className="signal-kicker">EXECUTION</span><h2>执行模式</h2><p>待我开始只收录工单；一旦授权，任务仍会自动跑完整流水线。</p><div className="segmented"><button className={settings.config.execution.mode==='awaitingStart'?'selected':''} onClick={()=>changeMode('awaitingStart')}>待我开始</button><button className={settings.config.execution.mode==='automatic'?'selected':''} onClick={()=>changeMode('automatic')}>全自动</button></div></article>
    <article className="settings-card"><span className="signal-kicker">PATH BINDINGS</span><h2>机器路径</h2><div className="binding-list">{Object.entries(settings.config.pathBindings).map(([id,path])=><div key={id}><code>{id}</code><span>{path}</span></div>)}</div></article>
    <article className="settings-card"><span className="signal-kicker">EXECUTABLES</span><h2>可执行程序</h2><div className="binding-list">{Object.entries(settings.config.executableBindings).map(([id,binding])=><div key={id}><code>{id}</code><span>{binding.command?.join(' ')||'—'}</span></div>)}</div></article>
    <article className="settings-card"><span className="signal-kicker">SECRETS</span><h2>凭据保险箱</h2><p>API 永远只返回 configured 状态，不回传明文。</p><div className="secret-list">{Object.entries(settings.secrets).map(([key,value])=><span key={key}><i className={value.configured?'ready-dot':''}/>{key}</span>)}</div><div className="secret-form"><input placeholder="secret key" value={secretKey} onChange={e=>setSecretKey(e.target.value)}/><input type="password" placeholder="value" value={secretValue} onChange={e=>setSecretValue(e.target.value)}/><button className="primary compact" onClick={saveSecret}>保存</button></div></article></div>
  </section>
}
