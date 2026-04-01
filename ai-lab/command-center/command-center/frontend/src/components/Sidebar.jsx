import { useState } from 'react'
import { clsx } from 'clsx'
import { useEventStore } from '../store'
import { StatusBadge, LiveDot } from './Primitives'

const TABS = [
  { id: 'all',      label: 'All' },
  { id: 'approval', label: 'APR' },
  { id: 'action',   label: 'ACT' },
]

function agentColor(agent = '') {
  if (agent.includes('worker')) return '#0f6e56'
  if (agent.includes('rag'))    return '#185fa5'
  if (agent.includes('super'))  return '#5f5e5a'
  return '#4338ca'
}

export default function Sidebar({ onSelect }) {
  const [tab, setTab] = useState('all')
  const { events, pendingCount } = useEventStore()

  const filtered = tab === 'all' ? events
    : events.filter(e => e.type === tab)

  return (
    <div className="flex flex-col border-r border-white/8" style={{ width: 268, minWidth: 268, background: 'rgba(255,255,255,0.025)' }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 border-b border-white/8" style={{ height: 48 }}>
        <LiveDot />
        <span className="text-[11px] font-medium tracking-widest uppercase text-white/40">Activity</span>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/8">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'relative flex-1 py-2 text-[11px] border-b-2 transition-colors',
              tab === t.id
                ? 'text-white border-white/60 font-medium'
                : 'text-white/35 border-transparent hover:text-white/55'
            )}
          >
            {t.label}
            {t.id === 'approval' && pendingCount > 0 && (
              <span className="absolute top-1 right-1 flex items-center justify-center text-[9px] font-bold rounded-full"
                style={{ background: '#ef4444', color: '#fff', minWidth: 14, height: 14, padding: '0 3px' }}>
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <div className="px-3 py-6 text-[11px] text-white/25 text-center">No events yet</div>
        )}
        {filtered.map(ev => (
          <div
            key={ev.id}
            onClick={() => onSelect?.(ev)}
            className={clsx(
              'px-3 py-2.5 cursor-pointer border-l-2 transition-colors hover:bg-white/5',
              ev.type === 'approval' ? 'border-amber-500/60' : 'border-transparent'
            )}
          >
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[11px] font-mono font-medium" style={{ color: agentColor(ev.agent) }}>
                {ev.agent}
              </span>
              <span className="text-[10px] font-mono text-white/25">
                {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
              </span>
            </div>
            <div className="text-[11px] text-white/45 truncate mb-1.5">
              {ev.id} · {ev.action || ev.op}
              {ev.detail ? ` — ${String(ev.detail).slice(0, 40)}` : ''}
            </div>
            <StatusBadge status={ev.status} />
          </div>
        ))}
      </div>
    </div>
  )
}
