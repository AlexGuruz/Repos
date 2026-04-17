import { useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

const TOOLS_POLL_MS = 30000

const AGENTS = [
  { key: 'orch',   label: 'orchestrator',  color: 'rgba(67,56,202,0.75)' },
  { key: 'worker', label: 'worker-7b',     color: 'rgba(15,110,86,0.75)' },
  { key: 'rag',    label: 'rag-retriever', color: 'rgba(24,95,165,0.55)' },
  { key: 'sup',    label: 'supervisor',    color: 'rgba(95,94,90,0.65)'  },
]

const DM_FILL = { 'op-read': '#185fa5', 'op-rag': '#0f6e56', 'op-write': '#b45309', 'op-exec': '#64748b' }

export default function ToolsPanel() {
  const [toolCalls, setToolCalls] = useState([])
  const [dataMovement, setDataMovement] = useState([])
  const [registryMeta, setRegistryMeta] = useState({
    registeredTools: [],
    workerReadOps: [],
    controlledOps: [],
    registryPath: '',
    registryCount: 0,
    note: '',
  })

  const fetchTools = useCallback(() => {
    api.toolsStats()
      .then(res => {
        setToolCalls(res.toolCalls || [])
        setDataMovement(res.dataMovement || [])
        setRegistryMeta({
          registeredTools: res.registeredTools || [],
          workerReadOps: res.workerReadOps || [],
          controlledOps: res.controlledOps || [],
          registryPath: res.registryPath || '',
          registryCount: res.registryCount ?? 0,
          note: res.note || '',
        })
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchTools()
    const t = setInterval(fetchTools, TOOLS_POLL_MS)
    return () => clearInterval(t)
  }, [fetchTools])

  const maxCalls = toolCalls.length > 0
    ? Math.max(1, ...toolCalls.map(d => (d.orch || 0) + (d.worker || 0) + (d.rag || 0) + (d.sup || 0)))
    : 1

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <p className="text-[10px] text-white/35 mb-2">Tool usage from API. Refreshes every {TOOLS_POLL_MS / 1000}s.</p>
      {registryMeta.note ? (
        <p className="text-[10px] text-amber-200/40 mb-3 leading-relaxed">{registryMeta.note}</p>
      ) : null}
      <div className="text-[10px] text-white/30 font-mono mb-4 break-all">
        registry: {registryMeta.registryCount} tools
        {registryMeta.registryPath ? ` · ${registryMeta.registryPath}` : ''}
      </div>
      {registryMeta.registeredTools.length > 0 ? (
        <details className="mb-4 group">
          <summary className="text-[11px] text-white/45 cursor-pointer select-none mb-2">Registered tool names ({registryMeta.registeredTools.length})</summary>
          <ul className="text-[10px] font-mono text-white/40 space-y-0.5 max-h-32 overflow-y-auto pl-3 mb-2">
            {registryMeta.registeredTools.map(t => (
              <li key={t.tool_name}>{t.tool_name}{t.repo ? ` · ${t.repo}` : ''}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {(registryMeta.workerReadOps.length > 0 || registryMeta.controlledOps.length > 0) ? (
        <div className="grid gap-2 mb-4 sm:grid-cols-2">
          <details>
            <summary className="text-[11px] text-white/45 cursor-pointer">Worker read ops ({registryMeta.workerReadOps.length})</summary>
            <pre className="text-[9px] font-mono text-white/35 mt-1 max-h-28 overflow-y-auto whitespace-pre-wrap break-words">
              {registryMeta.workerReadOps.join('\n')}
            </pre>
          </details>
          <details>
            <summary className="text-[11px] text-white/45 cursor-pointer">Controlled ops ({registryMeta.controlledOps.length})</summary>
            <pre className="text-[9px] font-mono text-white/35 mt-1 max-h-28 overflow-y-auto whitespace-pre-wrap break-words">
              {registryMeta.controlledOps.join('\n')}
            </pre>
          </details>
        </div>
      ) : null}
      {/* Legend */}
      <div className="flex gap-4 mb-4">
        {AGENTS.map(a => (
          <div key={a.key} className="flex items-center gap-1.5 text-[11px] text-white/50">
            <span className="inline-block rounded-sm w-2.5 h-2.5" style={{ background: a.color }} />
            {a.label}
          </div>
        ))}
      </div>

      {/* Stacked bar chart */}
      <SectionLabel>tool calls · by agent</SectionLabel>
      <div className="flex flex-col gap-1.5 mb-6">
        {toolCalls.length === 0 ? (
          <div className="text-[11px] text-white/35 py-2">No tool stats yet. Instrumentation will populate this when tools run.</div>
        ) : (
          toolCalls.map(d => {
            const total = (d.orch || 0) + (d.worker || 0) + (d.rag || 0) + (d.sup || 0)
            const segments = [
              { val: d.orch || 0,   color: AGENTS[0].color },
              { val: d.worker || 0, color: AGENTS[1].color },
              { val: d.rag || 0,    color: AGENTS[2].color },
              { val: d.sup || 0,    color: AGENTS[3].color },
            ]
            return (
              <div key={d.tool} className="flex items-center gap-3">
                <div className="text-[10px] font-mono text-white/40 text-right" style={{ minWidth: 140 }}>{d.tool}</div>
                <div className="flex-1 flex h-4 rounded overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  {segments.map((seg, i) => seg.val > 0 && (
                    <div key={i} style={{ width: `${(seg.val / maxCalls) * 100}%`, background: seg.color, transition: 'width .4s' }} />
                  ))}
                </div>
                <div className="text-[10px] font-mono text-white/30 min-w-[20px]">{total}</div>
              </div>
            )
          })
        )}
      </div>

      {/* Data movement table */}
      <SectionLabel>data movement · by operation</SectionLabel>
      <div className="flex flex-col gap-px">
        <div className="grid text-[10px] text-white/25 font-medium tracking-wider pb-1 border-b border-white/8"
          style={{ gridTemplateColumns: '180px 1fr 50px' }}>
          <div>operation</div><div>volume</div><div>calls</div>
        </div>
        {dataMovement.length === 0 ? (
          <div className="text-[11px] text-white/35 py-2">No data movement recorded yet.</div>
        ) : (
          dataMovement.map(d => (
            <div key={d.op} className="grid items-center py-2 border-b border-white/5"
              style={{ gridTemplateColumns: '180px 1fr 50px' }}>
              <div>
                <span className={`${d.cls || ''} text-[10px] font-mono px-1.5 py-0.5 rounded border`}>{d.op}</span>
              </div>
              <div className="flex items-center gap-2 pr-4">
                <div className="flex-1 h-[3px] rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${d.pct || 0}%`, background: DM_FILL[d.cls] || '#888' }} />
                </div>
                <span className="text-[10px] font-mono text-white/40 min-w-[40px] text-right">{d.vol || '–'}</span>
              </div>
              <div className="text-[10px] font-mono text-white/35">{d.calls ?? 0}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
