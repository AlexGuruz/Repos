import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [capital, setCapital] = useState(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    Promise.allSettled([api.retailHealth(), api.retailDashboard(), api.retailCapital()])
      .then(([healthRes, dashboardRes, capitalRes]) => {
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (dashboardRes.status === 'fulfilled') setDashboard(dashboardRes.value)
        if (capitalRes.status === 'fulfilled') setCapital(capitalRes.value)
        const failures = [healthRes, dashboardRes, capitalRes].filter(r => r.status === 'rejected')
        setError(failures.length ? 'Some retail endpoints failed to load.' : '')
      })
      .catch(err => setError(String(err?.message || err || 'Retail load failed')))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function handleRefresh() {
    setRefreshing(true)
    api.retailRefresh({ force: false })
      .then(() => load())
      .catch(err => setError(String(err?.message || err || 'Retail refresh failed')))
      .finally(() => setRefreshing(false))
  }

  const configured = health?.configured === true

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <SectionLabel>Retail operations</SectionLabel>
          <div className="text-[11px] text-white/35 mt-1">
            Read-only dashboard hooks for retail health, capital, consignment, and reconciliation.
          </div>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-[10px] px-2 py-1 rounded border border-white/15 text-white/45 hover:text-white/75 hover:bg-white/5 disabled:opacity-40 transition-colors font-mono"
        >
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error ? (
        <div className="text-[11px] text-red-300/75 border border-red-400/20 bg-red-500/5 rounded px-3 py-2 mb-4">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-3">
        <div className="border border-white/10 rounded-lg p-3 bg-white/[0.02]">
          <div className="text-[10px] text-white/30 font-mono mb-1">health</div>
          <div className={configured ? 'text-emerald-300/80 text-sm' : 'text-amber-200/75 text-sm'}>
            {configured ? 'Configured' : 'No live source configured'}
          </div>
          <div className="text-[10px] text-white/35 mt-2">{health?.status || health?.mode || 'loading'}</div>
        </div>

        <div className="border border-white/10 rounded-lg p-3 bg-white/[0.02]">
          <div className="text-[10px] text-white/30 font-mono mb-1">dashboard cards</div>
          <div className="text-white/70 text-sm">{dashboard?.cards?.length ?? 0}</div>
          <div className="text-[10px] text-white/35 mt-2">{dashboard?.message || 'No dashboard data loaded.'}</div>
        </div>

        <div className="border border-white/10 rounded-lg p-3 bg-white/[0.02]">
          <div className="text-[10px] text-white/30 font-mono mb-1">capital scenarios</div>
          <div className="text-white/70 text-sm">{capital?.scenarios?.length ?? 0}</div>
          <div className="text-[10px] text-white/35 mt-2">{capital?.message || 'No capital scenarios loaded.'}</div>
        </div>
      </div>

      <div className="mt-4 border border-white/10 rounded-lg p-3 bg-white/[0.02]">
        <div className="text-[10px] text-white/30 font-mono mb-2">raw health payload</div>
        <pre className="text-[10px] text-white/40 whitespace-pre-wrap break-words m-0">
          {JSON.stringify(health || {}, null, 2)}
        </pre>
      </div>
    </div>
  )
}
