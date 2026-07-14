import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

function EmptyCard({ title, children }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[11px] font-medium text-white/70 mb-1">{title}</div>
      <div className="text-[10px] text-white/40 leading-relaxed">{children}</div>
    </div>
  )
}

function withTimeout(promise, label, timeoutMs = 3000) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`${label} timed out`)), timeoutMs)
    }),
  ])
}

export default function RetailPanel() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [state, setState] = useState({
    health: null,
    dashboard: null,
    stores: null,
    capital: null,
    consignment: null,
    reconciliation: null,
  })

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      try {
        const results = await Promise.allSettled([
          withTimeout(api.retailHealth(), 'retail health'),
          withTimeout(api.retailDashboard(), 'retail dashboard'),
          withTimeout(api.retailStores(), 'retail stores'),
          withTimeout(api.retailCapital(), 'retail capital'),
          withTimeout(api.retailConsignment(), 'retail consignment'),
          withTimeout(api.retailReconciliation(), 'retail reconciliation'),
        ])
        if (!mounted) return
        const rejected = results.find(r => r.status === 'rejected')
        if (rejected) {
          setError(rejected.reason?.message || 'Retail API request failed')
        }
        setState({
          health: results[0].status === 'fulfilled' ? results[0].value : { status: 'unavailable', message: 'Retail API did not respond.' },
          dashboard: results[1].status === 'fulfilled' ? results[1].value : null,
          stores: results[2].status === 'fulfilled' ? results[2].value : null,
          capital: results[3].status === 'fulfilled' ? results[3].value : null,
          consignment: results[4].status === 'fulfilled' ? results[4].value : null,
          reconciliation: results[5].status === 'fulfilled' ? results[5].value : null,
        })
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [])

  const unavailable = state.health?.status === 'unavailable'

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <SectionLabel>Retail operations</SectionLabel>
          <p className="text-[11px] text-white/40 leading-relaxed max-w-2xl">
            Read-only retail dashboard surface. Mutating capital workflows remain disabled until the backend service is configured.
          </p>
        </div>
        <span
          className="text-[10px] font-mono px-2 py-1 rounded border"
          style={{
            color: unavailable ? '#fbbf24' : '#86efac',
            borderColor: unavailable ? 'rgba(251,191,36,0.35)' : 'rgba(34,197,94,0.35)',
            background: unavailable ? 'rgba(251,191,36,0.08)' : 'rgba(34,197,94,0.08)',
          }}
        >
          {loading ? 'loading' : unavailable ? 'unavailable' : 'connected'}
        </span>
      </div>

      {error ? (
        <div className="rounded border border-red-500/25 bg-red-500/10 text-red-200/70 text-[11px] p-3 mb-4">
          {error}
        </div>
      ) : null}

      {unavailable ? (
        <div className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 mb-4">
          <div className="text-[12px] text-amber-100/80 mb-1">Retail service not configured</div>
          <div className="text-[11px] text-amber-100/50 leading-relaxed">
            {state.health?.message || 'Retail workflows are unavailable in this environment.'}
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <EmptyCard title="Dashboard">
          {loading ? 'Loading dashboard...' : `${state.dashboard?.metrics?.length || 0} metrics available.`}
        </EmptyCard>
        <EmptyCard title="Stores">
          {loading ? 'Loading stores...' : `${state.stores?.stores?.length || 0} stores configured.`}
        </EmptyCard>
        <EmptyCard title="Capital">
          {loading ? 'Loading capital scenarios...' : `${state.capital?.scenarios?.length || 0} scenarios available.`}
        </EmptyCard>
        <EmptyCard title="Consignment">
          {loading ? 'Loading consignment...' : `${state.consignment?.items?.length || 0} consignment rows.`}
        </EmptyCard>
        <EmptyCard title="Reconciliation">
          {loading ? 'Loading reconciliation...' : `${state.reconciliation?.items?.length || 0} reconciliation rows.`}
        </EmptyCard>
      </div>
    </div>
  )
}
