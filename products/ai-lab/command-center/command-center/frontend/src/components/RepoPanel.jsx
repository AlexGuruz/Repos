import { useState, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import { useRepoStore } from '../store'
import { api } from '../lib/api'

/** Build tree rows from flat API tree: dirs as headers, files under each dir. */
function treeToRows(tree) {
  if (!Array.isArray(tree) || tree.length === 0) return []
  const rows = []
  let lastDir = null
  for (const item of tree) {
    if (item.type === 'dir') {
      lastDir = item.path
      rows.push({ type: 'dir', path: item.path })
    } else if (item.type === 'file' && item.name != null) {
      rows.push({ type: 'file', name: item.name, path: item.path, size_bytes: item.size_bytes, mtime: item.mtime, dir: lastDir })
    }
  }
  return rows
}

const OP_COLORS = { read: '#185fa5', write: '#b45309', exec: '#993c1d', hot: '#ef4444' }

function FileDot({ op, hot }) {
  const c = hot ? OP_COLORS.hot : OP_COLORS[op] || '#64748b'
  return (
    <span className={clsx('inline-block rounded-full flex-shrink-0', hot && 'pulse')}
      style={{ width: 5, height: 5, background: c }} />
  )
}

export default function RepoPanel() {
  const [selected, setSelected] = useState(null)
  const [treeRows, setTreeRows] = useState([])
  const [treeNote, setTreeNote] = useState('')
  const [treeLoading, setTreeLoading] = useState(true)
  const [treeError, setTreeError] = useState(null)
  const [docsStatus, setDocsStatus] = useState(null)
  const { fileActivity, summaries, setSummaries } = useRepoStore()

  useEffect(() => {
    api.repoSummaries()
      .then(res => setSummaries(res.summaries || []))
      .catch(() => {})
    api.repoDocsStatus()
      .then(setDocsStatus)
      .catch(() => setDocsStatus({ ok: false, error: 'repo-docs unavailable' }))
  }, [setSummaries])

  const loadTree = useCallback(() => {
    setTreeLoading(true)
    setTreeError(null)
    api.repoTree()
      .then(res => {
        setTreeRows(treeToRows(res.tree || []))
        setTreeNote(res.note || '')
      })
      .catch((e) => {
        const msg = e?.message ? String(e.message) : String(e)
        setTreeRows([])
        setTreeNote('')
        setTreeError(msg)
      })
      .finally(() => setTreeLoading(false))
  }, [])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  const getDetail = (path) => {
    const live = fileActivity[path]
    if (!live) return null
    return {
      reads: live.reads ?? 0,
      writes: live.writes ?? 0,
      execs: live.execs ?? 0,
      bytes: '–',
      agent: live.agent ?? '–',
      op: live.op,
      events: live.ts ? [{ t: new Date(live.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), ag: live.agent, op: live.op, d: `${live.op} by ${live.agent}` }] : [],
    }
  }

  return (
    <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
      <div className="flex-shrink-0 px-4 py-2 border-b border-white/8">
        <h2 className="text-[13px] font-medium text-white/80">Repo tracker</h2>
        <p className="text-[11px] text-white/40 mt-0.5">File tree and live activity from the repo watcher. Click a file to see reads/writes.</p>
        {docsStatus && (
          <p className="text-[10px] font-mono text-white/35 mt-1">
            repo-docs: {docsStatus.ok ? 'ok' : 'limited'} · findings {docsStatus.findings_count ?? '—'} · stale {String(docsStatus.stale)}
          </p>
        )}
        {Object.keys(fileActivity).length > 0 && (
          <div className="mt-2 space-y-1">
            <div className="text-[10px] font-mono text-white/50">
              {Object.keys(fileActivity).length} file(s) with recent activity (WS)
            </div>
            <div className="text-[9px] font-mono text-white/30 truncate max-h-12 overflow-y-auto" title={Object.keys(fileActivity).slice(0, 10).join('\n')}>
              {Object.entries(fileActivity).slice(0, 5).map(([p, a]) => (
                <div key={p} className="truncate">{`${a?.op || '-'} ${p}`}</div>
              ))}
            </div>
          </div>
        )}
      </div>
      {/* Repo scans (cartographer) */}
      <div className="flex-shrink-0 border-b border-white/8 px-4 py-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-white/30 mb-2">Repo scans</div>
        {summaries.length === 0 ? (
          <div className="text-[11px] text-white/35">No scans yet. In Chat, say “scan repo” or “summarize repo”.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {summaries.map((s, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono border border-white/10 bg-white/5 text-white/70"
                title={s.path || s.name}
              >
                <span>{s.name}</span>
                {s.path && <span className="text-white/30 text-[10px] truncate max-w-[120px]" title={s.path}>{s.path}</span>}
                {s.entrypoints?.length > 0 && (
                  <span className="text-white/35 text-[10px]">{s.entrypoints.join(', ')}</span>
                )}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Tree */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
      <div className="overflow-y-auto border-r border-white/8 py-2" style={{ width: 200, minWidth: 200 }}>
        {treeLoading ? (
          <div className="px-3 py-3 text-[11px] text-white/35">Loading tree…</div>
        ) : treeRows.length === 0 && treeNote ? (
          <div className="px-3 py-3 space-y-2">
            <div className="text-[11px] text-white/35">{treeNote}</div>
            <div className="text-[10px] text-white/25">Ensure the backend is running and (if needed) set AI_LAB_GOVERNANCE_ROOT or run from the ai-lab repo so the watcher can send file events.</div>
          </div>
        ) : treeRows.length === 0 && treeError ? (
          <div className="px-3 py-3 space-y-3">
            <div className="text-[11px] text-red-300/90 font-mono">{`Failed to load repo tree: ${treeError}`}</div>
            <button
              className="text-[10px] px-2 py-1 rounded border border-white/10 text-white/30 hover:text-white/60 hover:bg-white/6 transition-colors font-mono"
              onClick={loadTree}
              type="button"
            >
              Retry ↻
            </button>
          </div>
        ) : treeRows.length === 0 ? (
          <div className="px-3 py-3 text-[11px] text-white/35">Repo tree is empty.</div>
        ) : (
          treeRows.map((f, i) => {
            if (f.type === 'dir') {
              return <div key={`dir-${i}-${f.path}`} className="px-3 pt-2.5 pb-0.5 text-[10px] font-mono tracking-wider text-white/30 font-medium">{f.path}</div>
            }
            const live = fileActivity[f.path]
            const op = live?.op || 'read'
            const hot = live && Date.now() - new Date(live.ts || 0).getTime() < 30000
            return (
              <div key={`file-${i}-${f.path}`} onClick={() => setSelected(f.path)}
                className={clsx('flex items-center gap-1.5 pl-6 pr-3 py-1 cursor-pointer text-[11px] font-mono transition-colors hover:bg-white/5',
                  selected === f.path ? 'bg-white/8 text-white/80' : 'text-white/45')}>
                <FileDot op={op} hot={hot} />
                {f.name}
              </div>
            )
          })
        )}
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-y-auto p-4">
        {!selected ? (
          <div className="text-[12px] text-white/25 text-center pt-12">Select a file to inspect agent activity</div>
        ) : (() => {
          const d = getDetail(selected)
          const displayName = selected.split(/[/\\]/).pop() || selected
          if (!d) return <div className="text-[12px] text-white/25">No activity recorded for <code className="text-white/40">{displayName}</code>. Activity appears when the repo watcher or tools touch this path.</div>
          return (
            <>
              <div className="font-mono font-medium text-white/80 mb-3">{displayName}</div>
              <div className="grid grid-cols-3 gap-2 mb-4">
                {[
                  { label: 'reads', value: d.reads ?? 0, color: '#185fa5' },
                  { label: 'writes', value: d.writes ?? 0, color: '#b45309' },
                  { label: 'execs', value: d.execs ?? 0, color: '#993c1d' },
                  { label: 'data', value: d.bytes ?? '–', color: null },
                  { label: 'agent', value: d.agent ?? '–', color: null },
                  { label: 'last op', value: d.op ?? '–', color: null },
                ].map(m => (
                  <div key={m.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
                    <div className="text-[10px] text-white/30 mb-1">{m.label}</div>
                    <div className="text-[13px] font-mono font-medium" style={{ color: m.color || 'rgba(255,255,255,0.7)' }}>{String(m.value)}</div>
                  </div>
                ))}
              </div>

              {d.events?.length > 0 && (
                <>
                  <div className="text-[10px] font-mono text-white/25 mb-2 uppercase tracking-wider">Event history</div>
                  <div className="flex flex-col">
                    {d.events.map((e, i) => (
                      <div key={i} className="flex items-center gap-2 py-1.5 border-b border-white/5 text-[10px] font-mono">
                        <span className="text-white/25 min-w-[36px]">{e.t}</span>
                        <span style={{ color: e.ag.includes('worker') ? '#0f6e56' : '#4338ca', minWidth: 80 }}>{e.ag}</span>
                        <span className={`op-${e.op} inline-flex text-[9px] px-1 py-0.5 rounded border`}>{e.op}</span>
                        <span className="text-white/45 truncate">{e.d}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              <button className="mt-4 text-[10px] px-2 py-1 rounded border border-white/10 text-white/30 hover:text-white/60 hover:bg-white/6 transition-colors font-mono"
                onClick={() => window.sendPrompt?.(`Full audit of agent activity on ${displayName}`)}>
                full audit ↗
              </button>
            </>
          )
        })()}
      </div>
      </div>
    </div>
  )
}
