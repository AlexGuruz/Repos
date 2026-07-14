import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')

  async function refresh() {
    setError('')
    try {
      const [h, d] = await Promise.all([
        api.retailHealth(),
        api.retailDashboard(),
      ])
      setHealth(h)
      setDashboard(d)
    } catch (err) {
      setError(err?.message || String(err))
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const metrics = dashboard?.validation_status_by_metric || {}
  const metricRows = Object.entries(metrics)

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <SectionLabel>Retail operations</SectionLabel>
        <button
          type="button"
          onClick={refresh}
          className="text-[10px] px-2 py-1 rounded border border-white/15 text-white/50 hover:text-white/80 hover:bg-white/5 transition-colors font-mono"
        >
          Refresh
        </button>
      </div>

      {error ? (
        <div className="text-[11px] text-red-300 mb-3">Retail status failed: {error}</div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="text-[11px] text-white/45 mb-1">Growflow health</div>
          <div className="text-sm text-white/80">{health?.ok ? 'Available' : 'Unavailable'}</div>
          <div className="mt-2 text-[10px] text-white/35 font-mono break-all">
            {health?.growflow_root || 'loading...'}
          </div>
          {(health?.warnings || []).map((w) => (
            <div key={w} className="mt-2 text-[11px] text-yellow-300">{w}</div>
          ))}
        </div>

        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
          <div className="text-[11px] text-white/45 mb-1">Dashboard summary</div>
          <div className="text-sm text-white/75">{dashboard?.summary || 'loading...'}</div>
          <div className="mt-2 text-[10px] text-white/35 font-mono">
            generated: {dashboard?.generated_at || '-'}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        <div className="text-[11px] text-white/45 mb-2">Validation metrics</div>
        {metricRows.length === 0 ? (
          <div className="text-[11px] text-white/35">No retail validation metrics are available in prepared context.</div>
        ) : (
          <div className="flex flex-col gap-2">
            {metricRows.map(([name, row]) => (
              <div key={name} className="flex items-center justify-between gap-3 border-b border-white/5 pb-2 last:border-b-0 last:pb-0">
                <span className="text-[11px] text-white/70">{name}</span>
                <span className="text-[10px] text-white/40 font-mono">
                  {row?.ok === true ? 'ok' : row?.ok === false ? 'error' : 'unknown'}
                  {row?.confidence ? ` · ${row.confidence}` : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
