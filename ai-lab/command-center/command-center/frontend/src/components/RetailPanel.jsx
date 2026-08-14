import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import CapitalTab from './CapitalTab'
import ConsignmentTab from './ConsignmentTab'

const SUB_TABS = [
  { id: 'operations', label: 'Operations' },
  { id: 'capital', label: 'Capital' },
  { id: 'consignment', label: 'Consignment' },
]

const PRESETS = [
  { id: 'last_7_days', label: '7 days' },
  { id: 'last_30_days', label: '30 days' },
  { id: 'last_90_days', label: '90 days' },
]

function fmtUsd(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${Number(n).toFixed(1)}%`
}

function TrustStrip({ meta }) {
  const trust = meta?.trust || {}
  const ok = meta?.validation?.ok !== false && trust.healthy !== false
  const fixture = trust.fixture_suspected || meta?.fixture_suspected
  const freshness = trust.freshness
  const cls = fixture ? 'fail' : freshness === 'fresh' && ok ? 'ok' : freshness === 'stale_but_usable' ? 'warn' : 'warn'
  return (
    <div className={`retail-trust ${cls}`}>
      <span>{fixture ? '✗ fixture / sample data — do not trust' : ok ? '✓ sums validated' : '⚠ validation failed'}</span>
      {freshness && <span>freshness {freshness}</span>}
      {trust.age_seconds != null && <span>age {Math.round(trust.age_seconds / 60)}m</span>}
      {meta?.built_at && <span>built {meta.built_at}</span>}
      {meta?.store_net_sales != null && <span>store net {fmtUsd(meta.store_net_sales)}</span>}
      {meta?.org_id && <span>org {meta.org_id}</span>}
    </div>
  )
}

function FreshnessBanner({ meta, projection }) {
  const trust = meta?.trust || {}
  const fixture = trust.fixture_suspected || meta?.fixture_suspected
  const stale = trust.freshness && trust.freshness !== 'fresh'
  if (!fixture && !stale && !projection) return null
  return (
    <div className={`retail-freshness ${fixture ? 'fail' : 'warn'}`}>
      {fixture && <span>Dashboard looks like fixture-scale data (few orders / low net). Rebuild with a real period before ops use.</span>}
      {!fixture && stale && <span>Data freshness is {trust.freshness}. Prefer waiting for scheduled refresh or run orchestrator.</span>}
      {projection && (
        <span>
          EOD projection: {projection.sales_date || '—'} pace {projection.pace_eod_cents != null ? fmtUsd(projection.pace_eod_cents / 100) : '—'}
          {projection.as_of_local ? ` @ ${projection.as_of_local}` : ''}
        </span>
      )}
    </div>
  )
}

function ReconciliationStrip({ reconciliation, reconcileError }) {
  if (reconcileError) {
    return (
      <div className="retail-reconcile unknown">
        <span>Reconciliation status unavailable</span>
        <span className="retail-muted">{reconcileError}</span>
      </div>
    )
  }
  if (!reconciliation) return null

  const status = reconciliation.status || 'unknown'
  const cls = status === 'pass' ? 'ok' : status === 'fail' ? 'fail' : status === 'warning' ? 'warn' : 'unknown'
  const label = {
    pass: '✓ reconciliation pass',
    fail: '✗ reconciliation fail',
    warning: '⚠ reconciliation warning',
    missing: '○ reconciliation not run',
    unknown: '? reconciliation unknown',
  }[status] || '? reconciliation unknown'

  return (
    <div className={`retail-reconcile ${cls}`}>
      <div className="retail-reconcile-head">
        <span>{label}</span>
        {reconciliation.generated_at && <span>checked {reconciliation.generated_at}</span>}
        {reconciliation.reference?.path && (
          <span className="retail-muted" title={reconciliation.reference.path}>
            ref {reconciliation.reference.type || 'file'}
          </span>
        )}
      </div>
      <p className="retail-reconcile-msg">{reconciliation.message}</p>
      {reconciliation.failed_checks?.length > 0 && (
        <ul className="retail-reconcile-fails">
          {reconciliation.failed_checks.slice(0, 5).map(c => (
            <li key={c.name}>
              <code>{c.name}</code>
              {c.delta_abs != null && ` Δ ${c.delta_abs}`}
              {c.message ? ` — ${c.message}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function KpiChips({ kpis }) {
  if (!kpis?.length) return null
  return (
    <div className="retail-kpis">
      {kpis.map(k => (
        <div key={k.key} className="retail-kpi">
          <div className="label">{k.key.replace(/_/g, ' ')}</div>
          <div className="value">{k.key.includes('pct') || k.key.includes('discount') ? fmtPct(k.current) : k.current}</div>
          {k.delta_pct != null && (
            <div className={`delta ${k.delta_pct >= 0 ? 'up' : 'down'}`}>
              {k.delta_pct >= 0 ? '+' : ''}{fmtPct(k.delta_pct)} vs prior
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function TableCaption({ count, noun }) {
  if (!count) return null
  return <div className="retail-table-caption">{count} {noun}{count === 1 ? '' : 's'}</div>
}

function BudtenderTable({ rows }) {
  const list = rows || []
  return (
    <>
      <div className="retail-scroll">
        <table className="retail-table">
          <thead>
            <tr>
              <th>Budtender</th>
              <th>Net sales</th>
              <th>Orders</th>
              <th>AOV</th>
              <th>Disc %</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {list.map(r => (
              <tr key={r.budtender} className={r.flags?.length ? 'flagged' : ''}>
                <td>{r.budtender}</td>
                <td>{fmtUsd(r.net_sales)}</td>
                <td>{r.order_count}</td>
                <td>{fmtUsd(r.aov)}</td>
                <td>{fmtPct(r.effective_discount_pct)}</td>
                <td>{(r.flags || []).join(', ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TableCaption count={list.length} noun="budtender" />
    </>
  )
}

function BrandTable({ rows }) {
  const list = rows || []
  return (
    <>
      <div className="retail-scroll">
        <table className="retail-table">
          <thead>
            <tr>
              <th>Brand</th>
              <th>Net</th>
              <th>Disc %</th>
              <th>Native margin</th>
              <th>Landed margin</th>
              <th>Rank</th>
            </tr>
          </thead>
          <tbody>
            {list.map(r => (
              <tr key={r.canonical_brand || r.brand_name}>
                <td>{r.brand_name}</td>
                <td>{fmtUsd(r.net_sales)}</td>
                <td>{fmtPct(r.effective_discount_pct)}</td>
                <td>{fmtPct(r.native_margin_pct)}</td>
                <td>{fmtPct(r.landed_margin_pct)}</td>
                <td>{r.profit_velocity_rank ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TableCaption count={list.length} noun="brand" />
    </>
  )
}

export default function RetailPanel() {
  const [subTab, setSubTab] = useState('operations')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [preset, setPreset] = useState('last_30_days')
  const [compare, setCompare] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [reconciliation, setReconciliation] = useState(null)
  const [reconcileError, setReconcileError] = useState(null)
  const [projection, setProjection] = useState(null)

  const loadReconciliation = useCallback(async () => {
    try {
      const r = await api.retailReconciliation()
      setReconciliation(r)
      setReconcileError(null)
    } catch (e) {
      setReconcileError(e.message)
      setReconciliation(null)
    }
  }, [])

  const loadProjection = useCallback(async () => {
    try {
      const p = await api.retailProjection()
      setProjection(p)
    } catch {
      setProjection(null)
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await api.retailDashboard()
      setData(d)
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(); loadReconciliation(); loadProjection() }, [load, loadReconciliation, loadProjection])

  // Auto-refresh the board every 5 minutes: re-fetch the latest built dashboard
  // (does NOT trigger a rebuild job). Skips while a manual rebuild is in flight or tab hidden.
  useEffect(() => {
    const FIVE_MIN_MS = 5 * 60 * 1000
    const t = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return
      if (refreshing) return
      load()
      loadReconciliation()
      loadProjection()
    }, FIVE_MIN_MS)
    return () => clearInterval(t)
  }, [load, loadReconciliation, loadProjection, refreshing])

  useEffect(() => {
    if (!jobId) return undefined
    const t = setInterval(async () => {
      try {
        const j = await api.retailJob(jobId)
        if (j.status === 'completed' || j.status === 'failed') {
          clearInterval(t)
          setRefreshing(false)
          setJobId(null)
          if (j.status === 'completed') {
            load()
            loadReconciliation()
          } else setError(j.error || 'refresh failed')
        }
      } catch {
        clearInterval(t)
        setRefreshing(false)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [jobId, load, loadReconciliation])

  const onRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      const r = await api.retailRefresh({ preset, compare, days: preset === 'last_7_days' ? 7 : preset === 'last_90_days' ? 90 : 30 })
      setJobId(r.job_id)
    } catch (e) {
      setError(e.message)
      setRefreshing(false)
    }
  }

  const meta = data?.meta || {}
  const alerts = data?.alerts || []

  return (
    <div className="retail-panel">
      <header className="retail-header">
        <h2>Retail Intelligence</h2>
        {subTab === 'operations' && (
          <div className="retail-controls">
            <select value={preset} onChange={e => setPreset(e.target.value)} disabled={refreshing}>
              {PRESETS.map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <label>
              <input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} disabled={refreshing} />
              compare prior
            </label>
            <button type="button" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
            <button type="button" onClick={load} disabled={loading}>Reload</button>
          </div>
        )}
      </header>

      <nav className="retail-subnav" role="tablist">
        {SUB_TABS.map(t => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={subTab === t.id}
            className={subTab === t.id ? 'active' : ''}
            onClick={() => setSubTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {subTab === 'capital' && <CapitalTab />}

      {subTab === 'consignment' && <ConsignmentTab />}

      {subTab === 'operations' && (
        <>
      <ReconciliationStrip reconciliation={reconciliation} reconcileError={reconcileError} />
      {error && <div className="retail-error">{error}</div>}
      {loading && !data && <div className="retail-loading">Loading dashboard…</div>}

      {data && (
        <>
          <TrustStrip meta={meta} />
          <FreshnessBanner meta={meta} projection={projection} />
          {alerts.length > 0 && (
            <div className="retail-alerts">
              {alerts.map(a => (
                <div key={a.alert_id} className={`alert ${a.severity}`}>{a.message}</div>
              ))}
            </div>
          )}
          <KpiChips kpis={data.period_compare_kpis} />

          <div className="retail-grid">
            <section>
              <h3>Budtender Sales</h3>
              <BudtenderTable rows={data.budtender_sales} />
            </section>
            <section>
              <h3>Brand Summary</h3>
              <BrandTable rows={data.brand_summary} />
            </section>
            <section className="wide">
              <h3>Discounts Over Time</h3>
              <div className="retail-scroll">
                <table className="retail-table compact">
                  <thead>
                    <tr><th>Date</th><th>Net</th><th>Disc %</th><th>% orders disc</th></tr>
                  </thead>
                  <tbody>
                    {(data.discounts_over_time || []).map(d => (
                      <tr key={d.date}>
                        <td>{d.date}</td>
                        <td>{fmtUsd(d.net_sales)}</td>
                        <td>{fmtPct(d.effective_discount_pct)}</td>
                        <td>{fmtPct(d.pct_orders_discounted)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <TableCaption count={(data.discounts_over_time || []).length} noun="day" />
            </section>
            <section className="wide">
              <h3>Budtender by Category</h3>
              <div className="retail-scroll tall">
                <table className="retail-table compact">
                  <thead>
                    <tr><th>Category</th><th>Budtender</th><th>Net</th><th>Items</th></tr>
                  </thead>
                  <tbody>
                    {(data.budtender_by_category || []).map((r, i) => (
                      <tr key={`${r.category_name}-${r.budtender}-${i}`}>
                        <td>{r.category_name}</td>
                        <td>{r.budtender}</td>
                        <td>{fmtUsd(r.net_sales)}</td>
                        <td>{r.item_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <TableCaption count={(data.budtender_by_category || []).length} noun="category × budtender row" />
            </section>
          </div>
        </>
      )}
        </>
      )}

      <style>{`
        .retail-panel {
          padding: 1rem 1.25rem; color: #e8eef2; max-width: 1400px;
          flex: 1 1 auto; min-height: 0; overflow-y: auto; box-sizing: border-box;
        }
        .retail-subnav { display: flex; gap: 0.25rem; margin-bottom: 1rem; border-bottom: 1px solid #1e293b; }
        .retail-subnav button {
          background: transparent; border: none; color: #64748b; padding: 0.5rem 0.75rem;
          border-bottom: 2px solid transparent; margin-bottom: -1px; cursor: pointer; font-size: 0.85rem;
        }
        .retail-subnav button.active { color: #5eead4; border-bottom-color: #5eead4; }
        .retail-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.5rem; }
        .retail-header h2 { margin: 0; font-size: 1.25rem; color: #5eead4; }
        .retail-controls { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
        .retail-controls select, .retail-controls button {
          background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.35rem 0.6rem; border-radius: 4px;
        }
        .retail-controls button:hover:not(:disabled) { border-color: #5eead4; }
        .retail-trust { display: flex; gap: 1rem; font-size: 0.85rem; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; }
        .retail-trust.ok { background: #134e4a; color: #99f6e4; }
        .retail-trust.warn { background: #713f12; color: #fde68a; }
        .retail-trust.fail { background: #450a0a; color: #fecaca; border: 1px solid #f87171; }
        .retail-freshness {
          display: flex; flex-wrap: wrap; gap: 0.75rem; font-size: 0.8rem;
          padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem;
        }
        .retail-freshness.warn { background: #422006; color: #fde68a; border: 1px solid #f59e0b; }
        .retail-freshness.fail { background: #450a0a; color: #fecaca; border: 1px solid #f87171; }
        .retail-reconcile {
          font-size: 0.82rem; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem;
          border: 1px solid #1e293b;
        }
        .retail-reconcile.ok { background: #0f2f2a; color: #99f6e4; border-color: #134e4a; }
        .retail-reconcile.fail { background: #450a0a; color: #fecaca; border-color: #7f1d1d; }
        .retail-reconcile.warn { background: #422006; color: #fde68a; border-color: #713f12; }
        .retail-reconcile.unknown, .retail-reconcile.missing { background: #1e293b; color: #94a3b8; }
        .retail-reconcile-head { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
        .retail-reconcile-msg { margin: 0.35rem 0 0; color: inherit; opacity: 0.9; }
        .retail-reconcile-fails { margin: 0.35rem 0 0; padding-left: 1.1rem; font-size: 0.75rem; }
        .retail-reconcile-fails code { font-size: 0.7rem; }
        .retail-muted { color: #64748b; font-size: 0.75rem; }
        .retail-kpis { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .retail-kpi { background: #0f172a; border: 1px solid #1e293b; padding: 0.5rem 0.75rem; border-radius: 6px; min-width: 120px; }
        .retail-kpi .label { font-size: 0.7rem; text-transform: uppercase; color: #94a3b8; }
        .retail-kpi .value { font-size: 1.1rem; font-weight: 600; }
        .retail-kpi .delta { font-size: 0.75rem; color: #94a3b8; }
        .retail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .retail-grid section { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 0.75rem; overflow: hidden; }
        .retail-grid section.wide { grid-column: 1 / -1; }
        .retail-grid h3 { margin: 0 0 0.5rem; font-size: 0.95rem; color: #5eead4; }
        .retail-scroll { max-height: 340px; overflow: auto; border: 1px solid #1e293b; border-radius: 6px; }
        .retail-scroll.tall { max-height: 460px; }
        .retail-scroll::-webkit-scrollbar { width: 10px; height: 10px; }
        .retail-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 5px; }
        .retail-scroll::-webkit-scrollbar-track { background: #0b1220; }
        .retail-table-caption { margin-top: 0.35rem; font-size: 0.7rem; color: #64748b; }
        .retail-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        .retail-table th, .retail-table td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid #1e293b; }
        .retail-table thead th { position: sticky; top: 0; background: #111f38; z-index: 1; }
        .retail-table th { color: #94a3b8; font-weight: 500; }
        .retail-table tr.flagged td { color: #fcd34d; }
        .retail-table.compact { font-size: 0.75rem; }
        .retail-error { background: #450a0a; color: #fecaca; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; }
        .retail-loading { color: #94a3b8; }
        .retail-alerts { margin-bottom: 0.75rem; }
        .retail-alerts .alert { padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.85rem; margin-bottom: 0.25rem; }
        .retail-alerts .warning { background: #422006; color: #fde68a; }
        .retail-alerts .info { background: #1e3a5f; color: #bae6fd; }
        @media (max-width: 900px) { .retail-grid { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  )
}
