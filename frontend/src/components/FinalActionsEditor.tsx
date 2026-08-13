import type { FinalActionConfig, GitLabMrActionConfig, PatchActionConfig } from '../entities/config'

const csv=(value:string)=>value.split(',').map(item=>item.trim()).filter(Boolean)
const defaultPatch=():PatchActionConfig=>({id:'primary-patch',type:'patch',outputDirectoryRef:'primary-patches',filenameTemplate:'{task_id}-{run_id}.patch',overwrite:false})
const defaultMr=():GitLabMrActionConfig=>({id:'main-gitlab-mr',type:'gitlabMr',repositoryRef:'',gitExecutableRef:'git-cli',targetBranches:['main'],pathMappings:[{from:'.',to:'.'}],titleTemplate:'[CodeFixer] {task_id}',descriptionTemplate:'Automated repair from CodeFixer run {run_id}.'})

export function FinalActionsEditor({actions,pathIds,onChange}:{actions:FinalActionConfig[];pathIds:string[];onChange:(actions:FinalActionConfig[])=>void}){
 const patch=actions.find((item):item is PatchActionConfig=>item.type==='patch')
 const mr=actions.find((item):item is GitLabMrActionConfig=>item.type==='gitlabMr')
 const setPatch=(next:PatchActionConfig)=>onChange([...actions.filter(item=>item.type!=='patch'),next])
 const setMr=(next:GitLabMrActionConfig)=>onChange([...actions.filter(item=>item.type!=='gitlabMr'),next])
 const toggle=(type:'patch'|'gitlabMr')=>{
   if(type==='patch') onChange(patch?actions.filter(item=>item.type!=='patch'):[...actions,defaultPatch()])
   else onChange(mr?actions.filter(item=>item.type!=='gitlabMr'):[...actions,defaultMr()])
 }
 return <div className="final-actions-editor">
   <div className="action-toggle-row"><button className={patch?'enabled':''} onClick={()=>toggle('patch')}><i/>Patch <small>{patch?'必需动作':'未启用'}</small></button><button className={mr?'enabled':''} onClick={()=>toggle('gitlabMr')}><i/>GitLab MR <small>{mr?'必需动作':'未启用'}</small></button></div>
   {actions.length===0&&<div className="inline-alert">至少启用一个最终动作。所有启用动作都必须成功，任务才能进入 completed。</div>}
   {patch&&<div className="action-config-block"><div className="action-config-head"><span className="signal-kicker">PATCH DELIVERY</span><b>{patch.id}</b></div><div className="form-grid"><label>Action ID<input value={patch.id} onChange={e=>setPatch({...patch,id:e.target.value})}/></label><label>输出目录<select value={patch.outputDirectoryRef} onChange={e=>setPatch({...patch,outputDirectoryRef:e.target.value})}><option value="">选择 pathBinding</option>{pathIds.map(id=><option key={id}>{id}</option>)}</select></label><label>文件名模板<input value={patch.filenameTemplate??''} onChange={e=>setPatch({...patch,filenameTemplate:e.target.value})}/></label><label className="check-row compact-check"><input type="checkbox" checked={!!patch.overwrite} onChange={e=>setPatch({...patch,overwrite:e.target.checked})}/><span>允许覆盖不同内容的同名 Patch</span></label></div></div>}
   {mr&&<div className="action-config-block"><div className="action-config-head"><span className="signal-kicker">GITLAB MR DELIVERY</span><b>{mr.id}</b></div><div className="form-grid"><label>Action ID<input value={mr.id} onChange={e=>setMr({...mr,id:e.target.value})}/></label><label>本地 Git 仓库<select value={mr.repositoryRef} onChange={e=>setMr({...mr,repositoryRef:e.target.value})}><option value="">选择 Git 仓库 pathBinding</option>{pathIds.map(id=><option key={id}>{id}</option>)}</select></label><label>目标分支<input value={mr.targetBranches.join(', ')} onChange={e=>setMr({...mr,targetBranches:csv(e.target.value)})} placeholder="main, release/4.7"/></label><label>Path Mapping<input value={(mr.pathMappings??[{from:'.',to:'.'}]).map(m=>`${m.from}:${m.to}`).join(', ')} onChange={e=>setMr({...mr,pathMappings:csv(e.target.value).map(pair=>{const[from,to]=pair.split(':');return{from:from||'.',to:to||'.'}})})} placeholder=".:. 或 Product/Lua:Assets/Lua"/></label></div></div>}
   {patch&&mr&&<div className="frozen-action-note"><span>FREEZE FAN-OUT</span><b>同一份验证 + Review 通过的 Change Artifact</b><p>Patch 与所有 GitLab 目标只消费同一份冻结修改，不允许分别重新运行 Agent。</p></div>}
 </div>
}
