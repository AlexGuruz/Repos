import { clsx } from 'clsx'

export function StatusBadge({ status }) {
  return (
    <span className={clsx('inline-flex items-center text-[10px] font-mono px-1.5 py-0.5 rounded', `st-${status}`)}>
      {status}
    </span>
  )
}

export function OpChip({ op, label }) {
  return (
    <span className={clsx('inline-flex items-center text-[10px] font-mono px-1.5 py-0.5 rounded border', `op-${op}`)}>
      {label ?? op}
    </span>
  )
}

export function LiveDot({ color = '#22c55e', pulse = true }) {
  return (
    <span
      className={clsx('inline-block rounded-full flex-shrink-0', pulse && 'pulse')}
      style={{ width: 7, height: 7, background: color }}
    />
  )
}

export function BarMeter({ value, max = 100, color = '#4338ca' }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-[3px] rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[10px] font-mono text-white/40 min-w-[32px] text-right">{value}</span>
    </div>
  )
}

export function SectionLabel({ children }) {
  return (
    <div className="text-[10px] font-mono tracking-wider uppercase text-white/30 mb-2">
      {children}
    </div>
  )
}
