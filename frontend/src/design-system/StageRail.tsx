export type StageState = 'done' | 'running' | 'queued' | 'failed' | 'reconciling' | 'skipped'
export type StageItem = { label: string; meta: string; state: StageState }

const defaultStages: StageItem[] = [
  { label: 'Prepare', meta: '1.2s', state: 'done' },
  { label: 'Scope', meta: '18s', state: 'done' },
  { label: 'Discovery', meta: '42s', state: 'done' },
  { label: 'Repair', meta: '02:18', state: 'running' },
  { label: 'Verify', meta: 'queued', state: 'queued' },
  { label: 'Review', meta: 'queued', state: 'queued' },
  { label: 'Deliver', meta: 'queued', state: 'queued' },
]

export function StageRail({ stages = defaultStages }: { stages?: StageItem[] }) {
  return <div className="stage-rail" style={{gridTemplateColumns:`repeat(${stages.length},1fr)`}} aria-label="任务阶段">{stages.map((stage, index) => <div className={`stage stage-${stage.state}`} key={`${stage.label}-${index}`}>
    <div className="rail-line" aria-hidden="true" />
    <div className="rail-node"><span>{index + 1}</span></div>
    <strong>{stage.label}</strong><small>{stage.meta}</small>
  </div>)}</div>
}
