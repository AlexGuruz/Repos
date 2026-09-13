import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { SectionLabel } from './Primitives'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [capital, setCapital] = useState(null)

  useEffect(() => {
    let active = true
    Promise.allSettled([api.retailHealth(), api.retailCapital()])
      .then(([healthRes, capitalRes]) => {
        if (!active) return
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (capitalRes.status === 'fulfilled') setCapital(capitalRes.value)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <SectionLabel>Retail</SectionLabel>
      <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[12px] text-white/55">
        <div className="text-white/80 font-medium mb-1">Retail adapter status</div>
        <div>{health?.message || 'Checking retail backend...'}</div>
        <div className="mt-2 text-[10px] font-mono text-white/35">
          status: {health?.status || 'unknown'} · read_only: {String(Boolean(health?.read_only))}
        </div>
      </div>
      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[12px] text-white/55">
        <div className="text-white/80 font-medium mb-1">Capital scenarios</div>
        <div>{capital?.message || 'No capital data loaded.'}</div>
        <div className="mt-2 text-[10px] font-mono text-white/35">
          approvals: {Array.isArray(capital?.approvals) ? capital.approvals.length : 0} · scenarios:{' '}
          {Array.isArray(capital?.scenarios) ? capital.scenarios.length : 0}
        </div>
      </div>
    </div>
  )
}
