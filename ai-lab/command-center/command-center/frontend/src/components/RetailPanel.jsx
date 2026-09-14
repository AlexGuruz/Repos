import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [state, setState] = useState({
    loading: true,
    error: '',
    health: null,
    dashboard: null,
    capital: null,
    consignment: null,
    reconciliation: null,
  })

  async function refresh() {
    setState(s => ({ ...s, loading: true, error: '' }))
    try {
      const [health, dashboard, capital, consignment, reconciliation] = await Promise.all([
        api.retailHealth(),
        api.retailDashboard(),
        api.retailCapital(),
        api.retailConsignment(),
        api.retailReconciliation(),
      ])
      setState({ loading: false, error: '', health, dashboard, capital, consignment, reconciliation })
    } catch (err) {
      setState(s => ({ ...s, loading: false, error: err?.message || 'Retail API request failed' }))
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const summary = state.dashboard?.summary || {}

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <SectionLabel>Retail dashboard</SectionLabel>
        <button
          type="button"
          onClick={refresh}
          className="text-[10px] px-2 py-1 rounded border border-white/15 text-white/50 hover:text-white/80 hover:bg-white/5 transition-colors font-mono"
        >
          Refresh
        </button>
      </div>

      {state.error ? (
        <div className="text-[11px] text-red-300/70 mb-3">{state.error}</div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card title="API status" value={state.health?.ok ? 'available' : 'unknown'} detail={state.health?.mode || 'loading'} />
        <Card title="Stores" value={state.dashboard?.stores?.length ?? state.health?.stores?.length ?? 0} detail="dashboard rows" />
        <Card title="Capital scenarios" value={state.capital?.scenarios?.length ?? 0} detail="preview only" />
        <Card title="Consignment rows" value={state.consignment?.rows?.length ?? 0} detail="read-only snapshot" />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        <JsonBlock title="Dashboard summary" data={summary} loading={state.loading} />
        <JsonBlock title="Reconciliation summary" data={state.reconciliation?.summary || {}} loading={state.loading} />
      </div>

      <p className="mt-4 text-[10px] text-white/30">
        Retail endpoints return explicit empty states when Growflow snapshot files are not present; no refresh or capital action mutates external systems in this checkout.
      </p>
    </div>
  )
}

function Card({ title, value, detail }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[10px] uppercase tracking-wide text-white/30 font-mono">{title}</div>
      <div className="mt-2 text-2xl text-white/80 font-semibold">{value}</div>
      <div className="mt-1 text-[10px] text-white/35">{detail}</div>
    </div>
  )
}

function JsonBlock({ title, data, loading }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3 min-h-36">
      <div className="text-[10px] uppercase tracking-wide text-white/30 font-mono mb-2">{title}</div>
      <pre className="text-[10px] text-white/45 whitespace-pre-wrap break-words m-0">
        {loading ? 'loading...' : JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}
