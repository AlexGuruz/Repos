import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

const POLL_MS = 60000

function StatusCard({ title, payload }) {
  const ok = payload?.ok === true
  const status = payload?.status || (ok ? 'ok' : 'not_configured')
  return (
    <div className="rounded border border-white/10 bg-white/[0.02] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[12px] text-white/70">{title}</div>
        <span className={`text-[10px] font-mono ${ok ? 'text-emerald-300/70' : 'text-amber-200/70'}`}>
          {status}
        </span>
      </div>
      {payload?.message ? (
        <div className="mt-2 text-[11px] text-white/40 leading-relaxed">{payload.message}</div>
      ) : null}
    </div>
  )
}

export default function RetailPanel() {
  const [state, setState] = useState({ loading: true, error: '', health: null, dashboard: null, stores: null, capital: null })

  useEffect(() => {
    let mounted = true
    const load = () => {
      Promise.allSettled([
        api.retailHealth(),
        api.retailDashboard(),
        api.retailStores(),
        api.retailCapital(),
      ]).then(([health, dashboard, stores, capital]) => {
        if (!mounted) return
        const firstErr = [health, dashboard, stores, capital].find(r => r.status === 'rejected')
        setState({
          loading: false,
          error: firstErr?.reason?.message || '',
          health: health.status === 'fulfilled' ? health.value : null,
          dashboard: dashboard.status === 'fulfilled' ? dashboard.value : null,
          stores: stores.status === 'fulfilled' ? stores.value : null,
          capital: capital.status === 'fulfilled' ? capital.value : null,
        })
      })
    }
    load()
    const t = setInterval(load, POLL_MS)
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <SectionLabel>Retail integration</SectionLabel>
      <p className="text-[11px] text-white/40 mb-4 leading-relaxed">
        Retail routes are present so Command Center can start cleanly. This workspace currently reports the
        integration as not configured until live retail data sources are wired.
      </p>
      {state.loading ? (
        <div className="text-[11px] text-white/35">Loading retail status...</div>
      ) : state.error ? (
        <div className="text-[11px] text-red-300/70">Retail status request failed: {state.error}</div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          <StatusCard title="Health" payload={state.health} />
          <StatusCard title="Dashboard" payload={state.dashboard} />
          <StatusCard title="Stores" payload={state.stores} />
          <StatusCard title="Capital" payload={state.capital} />
        </div>
      )}
    </div>
  )
}
