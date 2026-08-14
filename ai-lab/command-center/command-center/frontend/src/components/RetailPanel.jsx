import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    Promise.allSettled([api.retailHealth(), api.retailDashboard()])
      .then(([healthRes, dashboardRes]) => {
        if (!mounted) return
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (dashboardRes.status === 'fulfilled') setDashboard(dashboardRes.value)
        const firstError = [healthRes, dashboardRes].find(r => r.status === 'rejected')
        if (firstError) setError(firstError.reason?.message || 'Retail API unavailable')
      })
      .catch((err) => {
        if (mounted) setError(err?.message || 'Retail API unavailable')
      })
    return () => {
      mounted = false
    }
  }, [])

  const configured = !!health?.configured
  const metrics = Array.isArray(dashboard?.metrics) ? dashboard.metrics : []
  const stores = Array.isArray(dashboard?.stores) ? dashboard.stores : []

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <SectionLabel>Retail operations</SectionLabel>
      <div className="mt-3 rounded border border-white/10 bg-white/[0.03] p-3 text-[11px] text-white/55">
        <div className={configured ? 'text-emerald-300/80' : 'text-amber-300/80'}>
          {configured ? 'configured' : 'read-only placeholder'}
        </div>
        <div className="mt-1">{health?.message || 'Loading retail status...'}</div>
        {error ? <div className="mt-2 text-red-300/80">{error}</div> : null}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded border border-white/10 bg-black/20 p-3">
          <div className="text-[10px] uppercase tracking-wide text-white/35">Stores</div>
          <div className="mt-2 text-[22px] text-white/75">{stores.length}</div>
        </div>
        <div className="rounded border border-white/10 bg-black/20 p-3">
          <div className="text-[10px] uppercase tracking-wide text-white/35">Metrics</div>
          <div className="mt-2 text-[22px] text-white/75">{metrics.length}</div>
        </div>
      </div>

      {metrics.length > 0 ? (
        <div className="mt-4 space-y-2">
          {metrics.map((m, i) => (
            <div key={m.id || i} className="rounded border border-white/10 px-3 py-2 text-[11px] text-white/55">
              <div className="font-mono text-white/70">{m.label || m.id || `metric-${i + 1}`}</div>
              <div className="mt-1">{m.value ?? 'n/a'}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 text-[11px] text-white/35">
          No retail data source is configured yet; the rest of Command Center remains available.
        </div>
      )}
    </div>
  )
}
