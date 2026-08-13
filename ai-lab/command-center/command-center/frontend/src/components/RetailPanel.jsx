import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function StatusCard({ title, value, detail }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[10px] uppercase tracking-wide text-white/35">{title}</div>
      <div className="mt-1 text-sm text-white/80">{value}</div>
      {detail ? <div className="mt-1 text-[11px] text-white/35">{detail}</div> : null}
    </div>
  )
}

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [capital, setCapital] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    Promise.allSettled([
      api.retailHealth(),
      api.retailDashboard(),
      api.retailCapital(),
    ]).then(([healthRes, dashboardRes, capitalRes]) => {
      if (!mounted) return
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
      if (dashboardRes.status === 'fulfilled') setDashboard(dashboardRes.value)
      if (capitalRes.status === 'fulfilled') setCapital(capitalRes.value)
      const firstError = [healthRes, dashboardRes, capitalRes].find(r => r.status === 'rejected')
      setError(firstError ? String(firstError.reason?.message || firstError.reason || 'Retail API unavailable') : '')
    })
    return () => {
      mounted = false
    }
  }, [])

  const reason = health?.reason || dashboard?.reason || capital?.reason || error || 'Loading retail status...'

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mb-4">
        <div className="text-sm font-medium text-white/80">Retail</div>
        <div className="mt-1 text-[11px] text-white/40">
          Read-only retail dashboard lane. When the retail pipeline is not configured, this tab reports that state instead of blocking Command Center startup.
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <StatusCard
          title="API health"
          value={health?.ok ? 'ready' : 'unavailable'}
          detail={reason}
        />
        <StatusCard
          title="Dashboard rows"
          value={Array.isArray(dashboard?.rows) ? dashboard.rows.length : 0}
          detail={dashboard?.generated_at || ''}
        />
        <StatusCard
          title="Capital scenarios"
          value={Array.isArray(capital?.scenarios) ? capital.scenarios.length : 0}
          detail={capital?.available_cents == null ? 'No capital data loaded' : `${capital.available_cents} cents available`}
        />
      </div>

      {error ? (
        <div className="mt-4 rounded border border-red-400/20 bg-red-500/10 p-3 text-[11px] text-red-100/80">
          {error}
        </div>
      ) : null}
    </div>
  )
}
