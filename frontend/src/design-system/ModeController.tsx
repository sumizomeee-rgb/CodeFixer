import type { ExecutionMode } from '../entities/config'

export function ModeController({ mode, pending, onClick }: { mode: ExecutionMode; pending?: number; onClick: () => void }) {
  const automatic = mode === 'automatic'
  return <button className={`mode-controller ${automatic ? 'mode-automatic' : 'mode-awaiting'}`} onClick={onClick} aria-label="切换执行模式">
    <span className="mode-dot" />
    <span>{automatic ? '全自动' : '待我开始'}</span>
    {pending ? <em>{pending}</em> : null}
  </button>
}
