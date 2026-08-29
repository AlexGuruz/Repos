import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

function fmtUsd(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function StatusBadge({ status }) {
  const s = String(status || 'OK').toUpperCase()
  const color = s.includes('OVERDUE') ? '#fca5a5' : s.includes('DUE') ? '#fde68a' : '#86efac'
  return (
    <span className="consignment-badge" style={{ borderColor: color, color }}>{status || 'OK'}</span>
  )
}

export default function ConsignmentTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await api.retailConsignment()
      setData(d)
    } catch (e) {
      setError(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const meta = data?.meta || {}
  const kpis = data?.kpis || data?.kpi_strip || {}
  const ok = meta?.validation?.ok !== false
  const empty = data?.status === 'empty' || meta?.source_exists === false
  const generatedAt = data?.generated_at || meta?.built_at
  const latestByVendor = data?.latest_by_vendor || data?.latest_day_by_vendor || []

  return (
    <div className="consignment-tab">
      <div className="consignment-toolbar">
        <button type="button" onClick={load} disabled={loading}>Reload</button>
        {meta?.latest_date && <span className="retail-muted">Latest day: {meta.latest_date}</span>}
        {generatedAt && <span className="retail-muted">Generated {generatedAt}</span>}
      </div>

      {error && <div className="retail-error">{error}</div>}
      {loading && !data && <div className="retail-loading">Loading consignment…</div>}

      {data && empty && (
        <div className="consignment-empty">
          <p>No consignment data — <code>data/consignment.db</code> is missing or empty.</p>
          <p className="retail-muted">
            Run <code>scripts/build_retail_consignment.py</code> after
            <code> consignment_daily_allocation.py</code> populates the database.
          </p>
        </div>
      )}

      {data && !empty && (
        <>
          <div className={`retail-trust ${ok ? 'ok' : 'warn'}`}>
            <span>{ok ? '✓ consignment.db loaded' : '⚠ validation issue'}</span>
            {generatedAt && <span>built {generatedAt}</span>}
            {kpis.status_chip && <span>{kpis.status_chip}</span>}
          </div>

          <div className="consignment-kpi-strip">
            {[
              ['Today pull', kpis.today_recommended_pull_usd],
              ['Backlog', kpis.open_backlog_usd],
              ['Due in 7d', kpis.due_in_7_usd],
              ['Overdue', kpis.overdue_usd],
              ['MTD confirmed', kpis.mtd_confirmed_usd],
              ['Active vendors', kpis.vendors_active],
            ].map(([label, val]) => (
              <div key={label} className="retail-kpi">
                <div className="label">{label}</div>
                <div className="value">{typeof val === 'number' && label !== 'Active vendors' ? fmtUsd(val) : (val ?? '—')}</div>
              </div>
            ))}
          </div>

          <div className="retail-grid">
            <section>
              <h3>Active transfers</h3>
              <div className="table-scroll">
                <table className="retail-table compact">
                  <thead>
                    <tr>
                      <th>Vendor</th>
                      <th>Transfer</th>
                      <th>Received</th>
                      <th>Original</th>
                      <th>Remaining</th>
                      <th>Due</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.active_transfers || []).length === 0 ? (
                      <tr><td colSpan={6} className="retail-muted">No active transfers</td></tr>
                    ) : (data.active_transfers || []).map(r => (
                      <tr key={r.transfer_id}>
                        <td>{r.vendor_name}</td>
                        <td>{r.transfer_id}</td>
                        <td>{r.received_date}</td>
                        <td>{fmtUsd(r.original_amount_usd)}</td>
                        <td>{r.units_remaining} u</td>
                        <td>{r.due_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section>
              <h3>Latest day by vendor</h3>
              <div className="table-scroll">
                <table className="retail-table compact">
                  <thead>
                    <tr>
                      <th>Vendor</th>
                      <th>Accrual</th>
                      <th>Backlog</th>
                      <th>Rec. pull</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latestByVendor.length === 0 ? (
                      <tr><td colSpan={5} className="retail-muted">No vendor rows for latest day</td></tr>
                    ) : latestByVendor.map(r => (
                      <tr key={r.vendor_id}>
                        <td>{r.vendor_name}</td>
                        <td>{fmtUsd(r.accrual_usd)}</td>
                        <td>{fmtUsd(r.backlog_usd)}</td>
                        <td>{fmtUsd(r.recommended_pull_usd)}</td>
                        <td><StatusBadge status={r.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="wide">
              <h3>Daily ledger</h3>
              <div className="table-scroll wide">
                <table className="retail-table compact">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Vendor</th>
                      <th>Accrual</th>
                      <th>Backlog</th>
                      <th>Rec. pull</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.daily_ledger || []).length === 0 ? (
                      <tr><td colSpan={6} className="retail-muted">No ledger rows</td></tr>
                    ) : (data.daily_ledger || []).slice(0, 50).map((r, i) => (
                      <tr key={`${r.date}-${r.vendor_id}-${i}`}>
                        <td>{r.date}</td>
                        <td>{r.vendor_name}</td>
                        <td>{fmtUsd(r.accrual_usd)}</td>
                        <td>{fmtUsd(r.backlog_usd)}</td>
                        <td>{fmtUsd(r.recommended_pull_usd)}</td>
                        <td>{r.status || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}

      <style>{`
        .consignment-tab { padding: 0.5rem 0; }
        .consignment-toolbar { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-bottom: 0.75rem; }
        .consignment-toolbar button {
          background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.35rem 0.6rem; border-radius: 4px;
        }
        .consignment-kpi-strip { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
        .consignment-badge {
          font-size: 0.65rem; padding: 0.1rem 0.35rem; border-radius: 3px; border: 1px solid;
        }
        .consignment-empty {
          background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 1rem; color: #cbd5e1;
          font-size: 0.85rem;
        }
        .consignment-empty p { margin: 0.35rem 0; }
        .table-scroll { overflow-x: auto; max-width: 100%; -webkit-overflow-scrolling: touch; }
        .table-scroll.wide { max-height: 420px; overflow-y: auto; }
      `}</style>
    </div>
  )
}
