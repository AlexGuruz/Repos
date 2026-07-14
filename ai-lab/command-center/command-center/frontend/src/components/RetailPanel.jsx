import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

function SmallCard({ title, children }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.02] p-3">
      <div className="text-[10px] font-mono uppercase tracking-wide text-white/30 mb-2">{title}</div>
      {children}
    </div>
  )
}

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [capital, setCapital] = useState(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const loadRetail = useCallback(() => {
    setError('')
    Promise.allSettled([api.retailHealth(), api.retailDashboard(), api.retailCapital()])
      .then(([healthRes, dashboardRes, capitalRes]) => {
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (dashboardRes.status === 'fulfilled') setDashboard(dashboardRes.value)
        if (capitalRes.status === 'fulfilled') setCapital(capitalRes.value)
        const failed = [healthRes, dashboardRes, capitalRes].find(r => r.status === 'rejected')
        if (failed) setError(failed.reason?.message || 'Retail API request failed')
      })
      .catch(e => setError(e?.message || 'Retail API request failed'))
  }, [])

  useEffect(() => {
    loadRetail()
  }, [loadRetail])

  async function handleRefresh() {
    setRefreshing(true)
    setError('')
    try {
      const res = await api.retailRefresh({ scope: 'all' })
      setDashboard(prev => ({ ...(prev || {}), refresh_status: res }))
    } catch (e) {
      setError(e?.message || 'Retail refresh failed')
    } finally {
      setRefreshing(false)
    }
  }

  const stores = Array.isArray(dashboard?.stores) ? dashboard.stores : []
  const warnings = Array.isArray(dashboard?.warnings) ? dashboard.warnings : []
  const scenarios = Array.isArray(capital?.scenarios) ? capital.scenarios : []

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <SectionLabel>Retail operations</SectionLabel>
          <div className="text-[11px] text-white/35">
            Snapshot-backed retail dashboard. No external writes are performed from this panel.
          </div>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-[10px] px-2 py-1 rounded border border-white/15 text-white/55 hover:text-white/80 hover:bg-white/5 disabled:opacity-40 font-mono"
        >
          {refreshing ? 'Refresh...' : 'Request refresh'}
        </button>
      </div>

      {error ? <div className="mb-3 text-[11px] text-red-300/80">{error}</div> : null}

      <div className="grid gap-3 md:grid-cols-3 mb-4">
        <SmallCard title="API health">
          <div className="text-[12px] text-white/70">{health?.ok ? 'online' : 'unknown'}</div>
          <div className="text-[10px] text-white/35 break-all mt-1">{health?.state_dir || 'state path unavailable'}</div>
          {health?.note ? <div className="text-[10px] text-white/30 mt-2">{health.note}</div> : null}
        </SmallCard>
        <SmallCard title="Stores">
          <div className="text-[20px] text-white/80 font-mono">{stores.length}</div>
          <div className="text-[10px] text-white/35">stores in latest dashboard snapshot</div>
        </SmallCard>
        <SmallCard title="Capital scenarios">
          <div className="text-[20px] text-white/80 font-mono">{scenarios.length}</div>
          <div className="text-[10px] text-white/35">pending local scenario rows</div>
        </SmallCard>
      </div>

      {warnings.length > 0 ? (
        <div className="mb-4 rounded border border-amber-300/20 bg-amber-300/[0.04] p-3">
          <div className="text-[10px] font-mono uppercase text-amber-200/60 mb-2">Warnings</div>
          <ul className="text-[11px] text-amber-100/70 list-disc pl-4">
            {warnings.map((w, i) => <li key={`${w}-${i}`}>{String(w)}</li>)}
          </ul>
        </div>
      ) : null}

      <SmallCard title="Latest dashboard payload">
        <pre className="text-[10px] text-white/45 whitespace-pre-wrap break-words max-h-96 overflow-y-auto m-0">
          {JSON.stringify({ health, dashboard, capital }, null, 2)}
        </pre>
      </SmallCard>
    </div>
  )
}
