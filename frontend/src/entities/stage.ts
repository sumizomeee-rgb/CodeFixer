import type { StageItem, StageState } from '../design-system/StageRail'
import type { StageRun, TaskRun } from './task'

/** 12 个真实阶段的中文名。完整 12 项供抽屉的原始阶段表使用。 */
export const STAGE_LABELS:Record<string,string>={prepare:'准备',scope_discovery:'范围',discovery:'定位',assess:'评估',workspace_prepare:'工作区',no_change_verify:'确认',repair:'修复',verify:'验证',review:'复核',pre_delivery_check:'检查',freeze_change:'冻结',deliver:'交付'}
/** 主轨顺序：刻意压缩为 8 个业务阶段。workspace_prepare / pre_delivery_check / freeze_change 等内部状态只进原始阶段表，不上主轨。 */
const RAIL_ORDER=['prepare','scope_discovery','discovery','assess','repair','verify','review','deliver']

export const stageState=(value:string):StageState=>value==='completed'?'done':value==='running'?'running':value==='failed'?'failed':value==='reconciling'?'reconciling':value==='canceled'?'skipped':'queued'

export function stageDuration(stage:StageRun):string{
 if(!stage.started_at)return ''
 if(!stage.finished_at)return stage.status==='running'?'进行中':''
 const ms=new Date(stage.finished_at).getTime()-new Date(stage.started_at).getTime()
 return ms<1000?'完成':ms<60000?`${Math.max(1,Math.round(ms/1000))} 秒`:`${Math.max(1,Math.round(ms/60000))} 分`
}

const latestStages=(run:TaskRun)=>{const map=new Map<string,StageRun>();for(const item of run.stages??[])map.set(item.stage_id,item);return map}

export function buildRail(run:TaskRun):StageItem[]{
 const latest=latestStages(run)
 const noChange=latest.get('no_change_verify')
 return RAIL_ORDER.map(id=>{
  const item=id==='verify'&&noChange?noChange:latest.get(id)
  const branchSkipped=Boolean(noChange)&&!item&&(id==='repair'||id==='deliver')
  const state=item?stageState(item.status):branchSkipped?'skipped':'queued'
  // 未开始的阶段不写文案：空心节点本身已经表达了等待
  const meta=state==='queued'?'':item?stageDuration(item):branchSkipped?'无需执行':''
  return{label:STAGE_LABELS[id]??id,meta,state}
 })
}

export const repairAttempts=(run:TaskRun)=>Math.max(0,...(run.stages??[]).filter(item=>item.stage_id==='repair').map(item=>item.attempt||1))

/** 账本行用：当前跑到哪一步。取正在运行的阶段，否则取最后一个已推进的阶段。列表接口未返回 runs 时降级为 null。 */
export function currentStage(run:TaskRun|undefined|null):{label:string;meta:string}|null{
 const stages=run?.stages??[]
 if(!stages.length)return null
 const active=stages.find(item=>item.status==='running'||item.status==='reconciling')
 const target=active??[...stages].reverse().find(item=>item.status!=='queued')
 if(!target)return null
 return{label:STAGE_LABELS[target.stage_id]??target.stage_id,meta:stageDuration(target)}
}
