import { useState, useEffect } from 'react'
import { readDiagnostics, clearDiagnostics } from '../lib/diagnostics'
import { SectionLabel } from './Primitives'

export default function DiagnosticsPanel() {
  const [entries, setEntries] = useState([])

  function refresh() {
    setEntries(readDiagnostics())
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 2000)
    return () => clearInterval(id)
  }, [])

  function handleClear() {
    clearDiagnostics()
    setEntries([])
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <SectionLabel>Recent diagnostics (localStorage · last 300)</SectionLabel>
        <button
          onClick={handleClear}
          className="text-[10px] px-2 py-1 rounded border border-white/15 text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors font-mono"
        >
          Clear
        </button>
      </div>
      {entries.length === 0 ? (
        <div className="text-[11px] text-white/35">No entries yet. API requests, WS events, and errors are logged here.</div>
      ) : (
        <div className="flex flex-col gap-px font-mono text-[11px]">
          {[...entries].reverse().map((e, i) => (
            <div
              key={i}
              className="flex flex-wrap items-baseline gap-2 py-1.5 border-b border-white/5 text-white/60"
            >
              <span className="text-white/25 shrink-0">{e.at ? new Date(e.at).toLocaleTimeString() : '–'}</span>
              <span className="text-white/50 font-medium shrink-0">{e.channel ?? '?'}</span>
              <pre className="text-white/45 break-all whitespace-pre-wrap m-0">
                {JSON.stringify(Object.fromEntries(Object.entries(e).filter(([k]) => k !== 'at' && k !== 'channel')))}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
