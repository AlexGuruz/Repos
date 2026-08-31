import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useEventStore } from '../store'

function fmtUsd(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function fmtVal(v, kind) {
  if (v == null || v === '') return '—'
  if (kind === 'money') return fmtUsd(v)
  if (kind === 'num' || kind === 'wk' || kind === 'd') return Number(v).toLocaleString()
  return String(v)
}

function HBarChart({ rows, labelKey, valueKey, title }) {
  if (!rows?.length) return <p className="retail-muted">No data</p>
  const max = Math.max(...rows.map(r => Number(r[valueKey]) || 0), 1)
  return (
    <div className="capital-chart">
      {title && <h4>{title}</h4>}
      {rows.map(r => (
        <div key={r[labelKey]} className="hbar-row">
          <span className="hbar-label" title={r[labelKey]}>{r[labelKey]}</span>
          <div className="hbar-track">
            <div className="hbar-fill" style={{ width: `${(100 * (Number(r[valueKey]) || 0)) / max}%` }} />
          </div>
          <span className="hbar-val">{valueKey.includes('usd') || valueKey.includes('allocated') ? fmtUsd(r[valueKey]) : Number(r[valueKey]).toFixed(1)}</span>
        </div>
      ))}
    </div>
  )
}

function ScatterChart({ rows, title }) {
  if (!rows?.length) return <p className="retail-muted">No data</p>
  const maxA = Math.max(...rows.map(r => Number(r.allocated_usd) || 0), 1)
  const maxG = Math.max(...rows.map(r => Number(r.projected_gp_usd) || 0), 1)
  return (
    <div className="capital-chart scatter">
      {title && <h4>{title}</h4>}
      <div className="scatter-plot">
        {rows.map((r, i) => (
          <div
            key={`${r.brand}-${r.category}-${i}`}
            className="scatter-dot"
            title={`${r.brand} · ${r.category}: alloc ${fmtUsd(r.allocated_usd)}, GP ${fmtUsd(r.projected_gp_usd)}`}
            style={{
              left: `${(100 * (Number(r.allocated_usd) || 0)) / maxA}%`,
              bottom: `${(100 * (Number(r.projected_gp_usd) || 0)) / maxG}%`,
            }}
          />
        ))}
      </div>
      <div className="scatter-axes">
        <span>alloc →</span>
        <span>↑ GP</span>
      </div>
    </div>
  )
}

function MiniTable({ columns, rows }) {
  if (!rows?.length) return <p className="retail-muted">No rows</p>
  return (
    <table className="retail-table compact">
      <thead>
        <tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {columns.map(c => (
              <td key={c.key}>{c.fmt ? c.fmt(r[c.key]) : (r[c.key] ?? '—')}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function CapitalApprovalCard({ ev, onResolved }) {
  const [busy, setBusy] = useState(false)
  const [cardError, setCardError] = useState(null)
  const resolve = useEventStore(s => s.resolveApproval)

  async function handle(resolution) {
    if (busy) return
    setBusy(true)
    setCardError(null)
    try {
      if (resolution === 'approved') {
        const res = await api.retailCapitalApprove(ev.id)
        resolve(ev.id, resolution)
        window.dispatchEvent(new CustomEvent('retail-capital-job', { detail: { job_id: res.job_id } }))
        onResolved?.(res.job_id)
      } else {
        await api.retailCapitalDeny(ev.id)
        resolve(ev.id, resolution)
      }
    } catch (e) {
      setCardError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="capital-approval-card">
      <strong>Pending approval</strong>
      <p>{ev.detail}</p>
      {ev.payload?.expected_output && (
        <p className="retail-muted">Output: {ev.payload.expected_output}</p>
      )}
      {cardError && <div className="retail-error">{cardError}</div>}
      <div className="capital-approval-actions">
        <button type="button" disabled={busy} onClick={() => handle('approved')}>Approve & run</button>
        <button type="button" disabled={busy} onClick={() => handle('denied')}>Reject</button>
      </div>
    </div>
  )
}

export default function CapitalTab() {
  const events = useEventStore(s => s.events)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [statusMsg, setStatusMsg] = useState(null)
  const [pool, setPool] = useState(18000)
  const [velocityDays, setVelocityDays] = useState(49)
  const [cashCycleDays, setCashCycleDays] = useState(14)
  const [mode, setMode] = useState('buy-plan')

  const pendingCapital = useMemo(
    () => events.filter(e => e.type === 'approval' && e.action === 'retail_capital_scenario' && e.status === 'pending'),
    [events],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await api.retailCapital()
      setData(d)
      if (d?.scenario) {
        if (d.scenario.pool_usd) setPool(d.scenario.pool_usd)
        if (d.scenario.velocity_days) setVelocityDays(d.scenario.velocity_days)
        if (d.scenario.cash_cycle_days) setCashCycleDays(d.scenario.cash_cycle_days)
        if (d.scenario.allocation_mode) setMode(d.scenario.allocation_mode)
      }
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    function onRetailJob(e) {
      const jid = e.detail?.job_id
      if (jid) {
        setJobId(jid)
        setRunning(true)
        setStatusMsg('Scenario approved — running projection…')
      } else {
        load()
      }
    }
    window.addEventListener('retail-capital-job', onRetailJob)
    return () => window.removeEventListener('retail-capital-job', onRetailJob)
  }, [load])

  useEffect(() => {
    if (!jobId) return undefined
    const t = setInterval(async () => {
      try {
        const j = await api.retailJob(jobId)
        if (j.status === 'completed' || j.status === 'failed' || j.status === 'denied') {
          clearInterval(t)
          setRunning(false)
          setJobId(null)
          if (j.status === 'completed') {
            setStatusMsg('Scenario completed — capital data refreshed.')
            load()
          } else {
            setError(j.error || 'Scenario failed')
          }
        }
      } catch (e) {
        clearInterval(t)
        setRunning(false)
        setError(e.message || 'Job status check failed')
      }
    }, 3000)
    return () => clearInterval(t)
  }, [jobId, load])

  const runScenario = async () => {
    setRunning(true)
    setError(null)
    setStatusMsg(null)
    try {
      const r = await api.retailCapitalScenario({
        pool_usd: Number(pool),
        velocity_days: Number(velocityDays),
        cash_cycle_days: Number(cashCycleDays),
        allocation_mode: mode,
        skip_approval: false,
      })
      if (r.approval_required) {
        setRunning(false)
        setStatusMsg(`Approval ${r.approval_id} queued — check sidebar APR tab or card below.`)
      } else {
        setJobId(r.job_id)
      }
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  const meta = data?.meta || {}
  const ok = meta?.validation?.ok !== false

  return (
    <div className="capital-tab">
      <div className="scenario-bar">
        <label>
          Pool $
          <input type="number" value={pool} onChange={e => setPool(e.target.value)} disabled={running} min={1000} step={500} />
        </label>
        <label>
          Velocity days
          <input type="number" value={velocityDays} onChange={e => setVelocityDays(e.target.value)} disabled={running} min={7} />
        </label>
        <label>
          Cash cycle
          <input type="number" value={cashCycleDays} onChange={e => setCashCycleDays(e.target.value)} disabled={running} min={7} />
        </label>
        <label>
          Mode
          <select value={mode} onChange={e => setMode(e.target.value)} disabled={running}>
            <option value="buy-plan">buy-plan</option>
            <option value="throughput">throughput</option>
            <option value="gross-share">gross-share</option>
          </select>
        </label>
        <button type="button" onClick={runScenario} disabled={running}>
          {running ? 'Running…' : 'Run scenario'}
        </button>
        <button type="button" onClick={load} disabled={loading}>Reload</button>
      </div>

      {statusMsg && <div className="retail-info">{statusMsg}</div>}
      {error && <div className="retail-error">{error}</div>}
      {pendingCapital.map(ev => (
        <CapitalApprovalCard key={ev.id} ev={ev} onResolved={id => { setJobId(id); setRunning(true) }} />
      ))}
      {loading && !data && <div className="retail-loading">Loading capital projection…</div>}

      {data && (
        <>
          <div className={`retail-trust ${ok ? 'ok' : 'warn'}`}>
            <span>{ok ? '✓ layer2 loaded' : '⚠ no projection CSV'}</span>
            {meta.built_at && <span>built {meta.built_at}</span>}
            {data.scenario?.remaining_unallocated_usd != null && (
              <span>unallocated {fmtUsd(data.scenario.remaining_unallocated_usd)}</span>
            )}
          </div>

          <div className="capital-kpi-banner">
            {(data.kpi_banner || []).map((k, i) => (
              <div key={i} className="retail-kpi">
                <div className="label">{k.label}</div>
                <div className="value">{fmtVal(k.value, k.kind)}</div>
              </div>
            ))}
          </div>

          <div className="capital-narrative">
            <section>
              <h3>What this says</h3>
              <ul>{(data.narrative || []).map((b, i) => <li key={i}>{b}</li>)}</ul>
            </section>
            <section>
              <h3>Actions</h3>
              <ul>{(data.actions || []).map((a, i) => <li key={i}>{a}</li>)}</ul>
            </section>
          </div>

          <div className="capital-charts-row">
            <HBarChart title="Pool by category" rows={data.charts?.pool_by_category} labelKey="category" valueKey="allocated_usd" />
            <HBarChart title="Brand allocation (top 15)" rows={data.charts?.brand_allocation} labelKey="brand" valueKey="allocated_usd" />
            <HBarChart title="Recovery bucket ($)" rows={data.charts?.recovery_bucket} labelKey="bucket" valueKey="allocated_usd" />
          </div>

          <div className="capital-charts-row two-col">
            <ScatterChart title="Allocation vs projected GP" rows={data.charts?.alloc_vs_profit} />
            <HBarChart
              title={`Category recovery (${data.charts?.category_recovery?.[0]?.unit || 'days'})`}
              rows={(data.charts?.category_recovery || []).map(r => ({
                category: r.category,
                avg_recovery: r.avg_recovery,
              }))}
              labelKey="category"
              valueKey="avg_recovery"
            />
          </div>

          <div className="retail-grid">
            <section>
              <h3>Fastest recovery</h3>
              <MiniTable
                rows={data.tables?.fastest_recovery}
                columns={[
                  { key: 'brand', label: 'Brand' },
                  { key: 'category', label: 'Category' },
                  { key: 'allocated_usd', label: 'Alloc', fmt: fmtUsd },
                  { key: 'projected_gp_usd', label: 'GP', fmt: fmtUsd },
                ]}
              />
            </section>
            <section>
              <h3>Highest projected GP</h3>
              <MiniTable
                rows={data.tables?.highest_gp}
                columns={[
                  { key: 'brand', label: 'Brand' },
                  { key: 'category', label: 'Category' },
                  { key: 'projected_gp_usd', label: 'GP', fmt: fmtUsd },
                  { key: 'allocation_efficiency', label: 'Eff' },
                ]}
              />
            </section>
            <section className="wide">
              <h3>Deployment ledger</h3>
              <MiniTable
                rows={(data.tables?.ledger || []).slice(0, 30)}
                columns={[
                  { key: 'brand', label: 'Brand' },
                  { key: 'category', label: 'Category' },
                  { key: 'allocated_usd', label: 'Alloc', fmt: fmtUsd },
                  { key: 'units_to_buy', label: 'Units' },
                  { key: 'cash_cycle_status', label: 'Status' },
                ]}
              />
            </section>
          </div>
        </>
      )}

      <style>{`
        .capital-tab { padding: 0.5rem 0; }
        .scenario-bar {
          display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: flex-end;
          padding: 0.75rem; background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 1rem;
        }
        .scenario-bar label { display: flex; flex-direction: column; font-size: 0.7rem; color: #94a3b8; gap: 0.25rem; }
        .scenario-bar input, .scenario-bar select {
          background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.35rem 0.5rem; border-radius: 4px; min-width: 100px;
        }
        .scenario-bar button {
          background: #134e4a; border: 1px solid #5eead4; color: #99f6e4; padding: 0.4rem 0.75rem; border-radius: 4px; cursor: pointer;
        }
        .scenario-bar button:disabled { opacity: 0.5; cursor: not-allowed; }
        .capital-kpi-banner { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
        .capital-narrative { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
        .capital-narrative section { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 0.75rem; }
        .capital-narrative h3 { margin: 0 0 0.5rem; font-size: 0.9rem; color: #5eead4; }
        .capital-narrative ul { margin: 0; padding-left: 1.2rem; font-size: 0.8rem; color: #cbd5e1; }
        .capital-charts-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1rem; }
        .capital-charts-row.two-col { grid-template-columns: 1fr 1fr; }
        .capital-chart { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 0.75rem; min-height: 180px; }
        .capital-chart h4 { margin: 0 0 0.5rem; font-size: 0.85rem; color: #5eead4; }
        .hbar-row { display: grid; grid-template-columns: 90px 1fr 56px; gap: 0.35rem; align-items: center; margin-bottom: 0.25rem; font-size: 0.72rem; }
        .hbar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8; }
        .hbar-track { background: #1e293b; height: 8px; border-radius: 4px; overflow: hidden; }
        .hbar-fill { background: #5eead4; height: 100%; border-radius: 4px; }
        .hbar-val { text-align: right; color: #e2e8f0; }
        .scatter-plot { position: relative; height: 140px; background: #1e293b; border-radius: 4px; margin-bottom: 0.35rem; }
        .scatter-dot { position: absolute; width: 8px; height: 8px; border-radius: 50%; background: #5eead4; transform: translate(-50%, 50%); }
        .scatter-axes { display: flex; justify-content: space-between; font-size: 0.65rem; color: #64748b; }
        .retail-muted { color: #64748b; font-size: 0.8rem; }
        .retail-info { background: #1e3a5f; color: #bae6fd; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; font-size: 0.85rem; }
        .capital-approval-card {
          background: rgba(245,158,11,0.06); border: 1px solid rgba(245,158,11,0.35);
          border-radius: 8px; padding: 0.75rem; margin-bottom: 1rem; font-size: 0.85rem;
        }
        .capital-approval-card p { margin: 0.35rem 0; color: #cbd5e1; }
        .capital-approval-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
        .capital-approval-actions button {
          padding: 0.35rem 0.65rem; border-radius: 4px; font-size: 0.8rem; cursor: pointer;
          background: #1e293b; border: 1px solid #334155; color: #e2e8f0;
        }
        @media (max-width: 1000px) {
          .capital-charts-row, .capital-narrative { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  )
}
