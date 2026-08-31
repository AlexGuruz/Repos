import { useState } from 'react'
import { clsx } from 'clsx'
import { useFeedStore } from '../store'
import { LiveDot } from './Primitives'

const FILTERS = ['all', 'read', 'write', 'exec', 'rag']

function agentClass(agent = '') {
  if (agent.includes('worker') || agent.includes('rag')) return 'text-emerald-400/70'
  if (agent === 'user') return 'text-white/40'
  return 'text-indigo-400/70'
}

export default function FeedPanel() {
  const [filter, setFilter] = useState('all')
  const lines = useFeedStore(s => s.lines)

  const visible = filter === 'all' ? lines : lines.filter(l => l.op === filter)

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/8 flex-shrink-0">
        <LiveDot pulse />
        <span className="text-[11px] font-mono text-white/30">streaming · filter:</span>
        <div className="flex gap-1">
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={clsx(
                'text-[10px] font-mono px-2 py-0.5 rounded border transition-colors',
                filter === f
                  ? f === 'all' ? 'bg-white/10 border-white/20 text-white/80' : `op-${f}`
                  : 'border-white/10 text-white/30 hover:text-white/55'
              )}>
              {f}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px] font-mono text-white/20">{visible.length} events</span>
      </div>

      {/* Feed lines */}
      <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-0.5 font-mono text-[11px]">
        {visible.length === 0 && (
          <div className="text-white/20 text-center py-8">No events yet — waiting for agents…</div>
        )}
        {visible.map((l, i) => (
          <div key={i} className="flex items-start gap-2.5 py-1 border-b border-white/4 leading-relaxed">
            <span className="text-white/20 min-w-[46px] flex-shrink-0">
              {l.timestamp ? new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--:--:--'}
            </span>
            <span className={`min-w-[80px] flex-shrink-0 ${agentClass(l.agent)}`}>{l.agent}</span>
            <span className={clsx('min-w-[46px] flex-shrink-0', l.op ? `op-${l.op}` : 'text-white/25',
              'inline-flex items-center text-[10px] px-1 py-0.5 rounded border')}>
              {l.op || 'sys'}
            </span>
            <span className="text-white/50 flex-1 truncate">{l.detail || l.d || ''}</span>
            {(l.bytes || l.b) && l.bytes !== '–' && (
              <span className="text-white/20 flex-shrink-0 text-[10px]">{l.bytes || l.b}</span>
            )}
          </div>
        ))}
        {/* Live cursor */}
        <div className="flex items-start gap-2.5 py-1">
          <span className="text-white/10 min-w-[46px]">now</span>
          <span className="text-indigo-400/40 min-w-[80px]">orchestrator</span>
          <span className="text-white/20 min-w-[46px]">idle</span>
          <span className="text-white/20">awaiting task<span className="cursor-blink" /></span>
        </div>
      </div>
    </div>
  )
}
