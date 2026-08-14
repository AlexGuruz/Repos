import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

const EMPTY_STATE = {
  health: null,
  dashboard: null,
  stores: null,
  capital: null,
  consignment: null,
  reconciliation: null,
}

function StatusCard({ title, payload }) {
  const ok = payload?.ok === true
  const status = payload?.status || (payload ? 'loaded' : 'loading')
  const color = ok ? 'text-emerald-300/80' : 'text-amber-200/70'

  return (
    <div className="border border-white/10 rounded px-3 py-2 bg-white/[0.02]">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] text-white/65 font-medium">{title}</div>
        <div className={`text-[10px] font-mono ${color}`}>{status}</div>
      </div>
      {payload?.reason ? (
        <div className="text-[10px] text-white/35 mt-1 leading-relaxed">{payload.reason}</div>
      ) : null}
      {payload?.generated_at ? (
        <div className="text-[10px] text-white/25 mt-1 font-mono">generated {payload.generated_at}</div>
      ) : null}
    </div>
  )
}

export default function RetailPanel() {
  const [data, setData] = useState(EMPTY_STATE)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    async function loadRetail() {
      setError('')
      const [
        health,
        dashboard,
        stores,
        capital,
        consignment,
        reconciliation,
      ] = await Promise.allSettled([
        api.retailHealth(),
        api.retailDashboard(),
        api.retailStores(),
        api.retailCapital(),
        api.retailConsignment(),
        api.retailReconciliation(),
      ])

      if (!mounted) return

      const next = { ...EMPTY_STATE }
      const results = { health, dashboard, stores, capital, consignment, reconciliation }
      for (const [key, result] of Object.entries(results)) {
        if (result.status === 'fulfilled') {
          next[key] = result.value
        }
      }
      setData(next)

      const firstRejected = Object.values(results).find(result => result.status === 'rejected')
      if (firstRejected) {
        setError(firstRejected.reason?.message || 'retail endpoints unavailable')
      }
    }

    loadRetail()
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <SectionLabel>Retail operations</SectionLabel>
      <p className="text-[11px] text-white/35 mb-4 leading-relaxed">
        Read-only status from the optional retail pipeline. If the pipeline is not configured,
        these cards report unavailable data without blocking Command Center startup.
      </p>

      {error ? (
        <div className="text-[11px] text-red-300/75 border border-red-500/20 rounded px-3 py-2 mb-4">
          {error}
        </div>
      ) : null}

      <div className="grid gap-2 md:grid-cols-2">
        <StatusCard title="Health" payload={data.health} />
        <StatusCard title="Dashboard" payload={data.dashboard} />
        <StatusCard title="Stores" payload={data.stores} />
        <StatusCard title="Capital" payload={data.capital} />
        <StatusCard title="Consignment" payload={data.consignment} />
        <StatusCard title="Reconciliation" payload={data.reconciliation} />
      </div>
    </div>
  )
}
