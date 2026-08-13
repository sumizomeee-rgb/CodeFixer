export type StageState = 'done' | 'running' | 'queued' | 'failed' | 'reconciling' | 'skipped'
export type StageItem = { label: string; meta: string; state: StageState }

const defaultStages: StageItem[] = [
  { label: '准备', meta: '完成', state: 'done' },
  { label: '范围', meta: '18 秒', state: 'done' },
  { label: '定位', meta: '42 秒', state: 'done' },
  { label: '修复', meta: '进行中', state: 'running' },
  { label: '验证', meta: '', state: 'queued' },
  { label: '复核', meta: '', state: 'queued' },
  { label: '交付', meta: '', state: 'queued' },
]

const stateLabel:Record<StageState,string>={done:'已完成',running:'进行中',queued:'等待中',failed:'失败',reconciling:'对账中',skipped:'已跳过'}

export function StageRail({ stages = defaultStages, repairLoops = 0 }: { stages?: StageItem[]; repairLoops?: number }) {
  return <div className="stage-rail-wrap"><div className="stage-rail" style={{gridTemplateColumns:`repeat(${stages.length},1fr)`}} aria-label="任务阶段"><div className="rail-track" aria-hidden="true"/>{stages.map((stage, index) => <div className={`stage stage-${stage.state}`} key={`${stage.label}-${index}`}>
    {index < stages.length - 1 && <div className="rail-segment" aria-hidden="true"/>}
    <div className="rail-node" aria-hidden="true"/>
    <strong>{stage.label}</strong>{stage.meta&&<small>{stage.meta}</small>}<span className="sr-only">{stage.label}：{stateLabel[stage.state]}{stage.meta ? `，${stage.meta}` : ''}</span>
  </div>)}</div>{repairLoops > 1 && <div className="repair-loop-band"><span>REPAIR LOOP</span><b>修复循环 ×{repairLoops}</b><i aria-hidden="true"/></div>}</div>
}
