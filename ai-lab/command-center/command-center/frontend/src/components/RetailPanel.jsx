import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [capital, setCapital] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let mounted = true
    Promise.allSettled([api.retailHealth(), api.retailDashboard(), api.retailCapital()])
      .then(([healthRes, dashboardRes, capitalRes]) => {
        if (!mounted) return
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (dashboardRes.status === 'fulfilled') setDashboard(dashboardRes.value)
        if (capitalRes.status === 'fulfilled') setCapital(capitalRes.value)
        const failures = [healthRes, dashboardRes, capitalRes].filter(r => r.status === 'rejected')
        setError(failures.length ? failures.map(r => r.reason?.message || String(r.reason)).join('; ') : null)
      })
      .catch(e => {
        if (mounted) setError(e?.message || String(e))
      })
    return () => {
      mounted = false
    }
  }, [])

  const warnings = dashboard?.warnings || []

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <SectionLabel>Retail</SectionLabel>
      {error ? (
        <div className="text-[11px] text-red-300/80 border border-red-500/20 rounded-lg p-3 mb-3">
          Retail API unavailable: {error}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3 mb-4">
        <div className="rounded-lg border border-white/10 bg-white/4 p-3">
          <div className="text-[10px] text-white/35 mb-1">API</div>
          <div className="text-[18px] text-white/80 font-mono">{health?.ok ? 'online' : 'loading'}</div>
          <div className="text-[10px] text-white/30 mt-1">{health?.configured ? 'configured' : 'not configured'}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/4 p-3">
          <div className="text-[10px] text-white/35 mb-1">Stores</div>
          <div className="text-[18px] text-white/80 font-mono">{dashboard?.stores?.length ?? 0}</div>
          <div className="text-[10px] text-white/30 mt-1">read-only snapshot</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/4 p-3">
          <div className="text-[10px] text-white/35 mb-1">Capital scenarios</div>
          <div className="text-[18px] text-white/80 font-mono">{capital?.scenarios?.length ?? 0}</div>
          <div className="text-[10px] text-white/30 mt-1">approval-gated</div>
        </div>
      </div>
      {warnings.length ? (
        <div className="text-[11px] text-amber-200/70 border border-amber-500/20 rounded-lg p-3 mb-3">
          {warnings.join('; ')}
        </div>
      ) : null}
      <div className="rounded-lg border border-white/10 p-3">
        <div className="text-[10px] text-white/35 mb-2">Status detail</div>
        <pre className="text-[10px] text-white/45 whitespace-pre-wrap break-words m-0">
          {JSON.stringify({ health, dashboard, capital }, null, 2)}
        </pre>
      </div>
    </div>
  )
}
