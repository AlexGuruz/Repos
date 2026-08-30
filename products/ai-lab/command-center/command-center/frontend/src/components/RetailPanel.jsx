import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import CapitalTab from './CapitalTab'
import ConsignmentTab from './ConsignmentTab'

const SUB_TABS = [
  { id: 'operations', label: 'Operations' },
  { id: 'capital', label: 'Capital' },
  { id: 'consignment', label: 'Consignment' },
]

const LIVE_POLL_MS = 30000
const RANGE_POLL_MS = 60000

// --- date helpers (all store-local, YYYY-MM-DD) ---
function toISO(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function todayISO() { return toISO(new Date()) }
function addDaysISO(iso, n) {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + n)
  return toISO(d)
}
function daysBetween(a, b) {
  return Math.round((new Date(`${b}T00:00:00`) - new Date(`${a}T00:00:00`)) / 86400000) + 1
}

const PRESETS = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'last_7_days', label: '7 days' },
  { id: 'last_30_days', label: '30 days' },
  { id: 'last_90_days', label: '90 days' },
  { id: 'mtd', label: 'MTD' },
  { id: 'custom', label: 'Custom' },
]

function presetRange(id) {
  const today = todayISO()
  switch (id) {
    case 'today': return { start: today, end: today }
    case 'yesterday': { const y = addDaysISO(today, -1); return { start: y, end: y } }
    case 'last_7_days': return { start: addDaysISO(today, -6), end: today }
    case 'last_90_days': return { start: addDaysISO(today, -89), end: today }
    case 'mtd': { const d = new Date(); return { start: toISO(new Date(d.getFullYear(), d.getMonth(), 1)), end: today } }
    case 'last_30_days':
    default: return { start: addDaysISO(today, -29), end: today }
  }
}

// --- formatting ---
function fmtUsd(n, digits = 0) {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
}
function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${Number(n).toFixed(1)}%`
}
function fmtInt(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return Number(n).toLocaleString()
}
function fmtAge(sec) {
  if (sec == null) return '—'
  if (sec < 60) return `${Math.round(sec)}s`
  if (sec < 3600) return `${Math.round(sec / 60)}m`
  return `${Math.round(sec / 3600)}h`
}
function kpiLabel(key) {
  return ({
    net_sales: 'Net Sales',
    effective_discount_pct: 'Eff. Discount',
    order_count: 'Orders',
    pct_orders_discounted: '% Orders Disc.',
  })[key] || key.replace(/_/g, ' ')
}
function kpiValue(key, v) {
  if (v == null) return '—'
  if (key === 'net_sales') return fmtUsd(v)
  if (key.includes('pct') || key.includes('discount')) return fmtPct(v)
  return fmtInt(v)
}

// --- live badge ---
function LiveBadge({ live, autoLive, onToggle }) {
  const fresh = live?.freshness === 'fresh'
  const cls = !live?.available ? 'unknown' : fresh ? 'live' : live?.freshness === 'stale_but_usable' ? 'warn' : 'fail'
  const label = !live?.available
    ? 'No live feed'
    : fresh
    ? `Live · synced ${fmtAge(live.age_seconds)} ago`
    : `${live.freshness} · ${fmtAge(live.age_seconds)} old`
  return (
    <button type="button" className={`retail-live ${cls} ${autoLive ? 'on' : 'off'}`} onClick={onToggle}
      title={autoLive ? 'Auto-refresh ON (click to pause)' : 'Auto-refresh paused (click to resume)'}>
      <span className="dot" />
      <span>{label}</span>
      <span className="retail-live-auto">{autoLive ? 'AUTO' : 'PAUSED'}</span>
    </button>
  )
}

// --- trust strip ---
function TrustStrip({ meta }) {
  const trust = meta?.trust || {}
  const fixture = trust.fixture_suspected || meta?.fixture_suspected
  const freshness = trust.freshness
  const validation = trust.validation || {}
  const validated = trust.validated !== false && validation.ok !== false
  const validationErrors = Array.isArray(validation.errors) ? validation.errors : []
  // Fail closed: fixture OR failed validation is a hard fail; degraded/unavailable freshness warns.
  const cls = fixture || !validated
    ? 'fail'
    : freshness === 'fresh'
    ? 'ok'
    : 'warn'
  const headline = fixture
    ? '✗ fixture / sample data — do not trust'
    : !validated
    ? '✗ validation failed — do not trust'
    : trust.healthy
    ? '✓ trusted'
    : '⚠ verify freshness'
  return (
    <div className={`retail-trust ${cls}`} title={validationErrors.length ? validationErrors.join('; ') : undefined}>
      <span>{headline}</span>
      <span>{validated ? '✓ validated' : `✗ ${validationErrors.length || 'not'} check(s) failed`}</span>
      {freshness && <span>freshness {freshness}</span>}
      {trust.age_seconds != null && <span>age {fmtAge(trust.age_seconds)}</span>}
      {trust.source && <span>src {trust.source}</span>}
      {meta?.store_net_sales != null && <span>net {fmtUsd(meta.store_net_sales)}</span>}
      {meta?.line_count != null && <span>{fmtInt(meta.line_count)} lines</span>}
      {meta?.org_id && <span>org {meta.org_id}</span>}
    </div>
  )
}

// --- KPI cards ---
function KpiCards({ meta, kpis }) {
  const base = [
    { key: 'net_sales', value: meta?.store_net_sales },
    { key: 'order_count', value: meta?.order_count },
    { key: 'effective_discount_pct', value: meta?.effective_discount_pct },
  ]
  const deltaFor = (key) => (kpis || []).find(k => k.key === key)
  return (
    <div className="retail-kpis">
      {base.map(b => {
        const d = deltaFor(b.key)
        return (
          <div key={b.key} className="retail-kpi">
            <div className="label">{kpiLabel(b.key)}</div>
            <div className="value">{kpiValue(b.key, b.value)}</div>
            {d?.delta_pct != null && (
              <div className={`delta ${d.delta_pct >= 0 ? 'up' : 'down'}`}>
                {d.delta_pct >= 0 ? '▲' : '▼'} {fmtPct(Math.abs(d.delta_pct))} vs prior
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// --- inline SVG line/area chart ---
function LineChart({ points, color = '#5eead4', height = 150, valueFmt = (v) => v, label = '' }) {
  const W = 640
  const H = height
  const pad = { l: 8, r: 8, t: 12, b: 18 }
  if (!points?.length) return <div className="retail-chart-empty">No data for this range.</div>
  const ys = points.map(p => p.y)
  const maxY = Math.max(...ys, 1)
  const minY = Math.min(...ys, 0)
  const span = maxY - minY || 1
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const x = (i) => pad.l + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw)
  const y = (v) => pad.t + ih - ((v - minY) / span) * ih
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ')
  const area = `${line} L${x(points.length - 1).toFixed(1)},${(pad.t + ih).toFixed(1)} L${x(0).toFixed(1)},${(pad.t + ih).toFixed(1)} Z`
  const gid = `grad-${label.replace(/\W/g, '')}`
  return (
    <svg className="retail-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" />
      {points.map((p, i) => (
        <circle key={i} cx={x(i)} cy={y(p.y)} r="2.5" fill={color}>
          <title>{`${p.x}: ${valueFmt(p.y)}`}</title>
        </circle>
      ))}
    </svg>
  )
}

// --- inline SVG horizontal bar chart ---
function BarChart({ data, color = '#818cf8', valueFmt = (v) => v }) {
  if (!data?.length) return <div className="retail-chart-empty">No data for this range.</div>
  const max = Math.max(...data.map(d => d.value), 1)
  return (
    <div className="retail-bars">
      {data.map((d, i) => (
        <div key={i} className="retail-bar-row" title={`${d.label}: ${valueFmt(d.value)}`}>
          <span className="retail-bar-label">{d.label}</span>
          <span className="retail-bar-track">
            <span className="retail-bar-fill" style={{ width: `${(d.value / max) * 100}%`, background: color }} />
          </span>
          <span className="retail-bar-value">{valueFmt(d.value)}</span>
        </div>
      ))}
    </div>
  )
}

// --- sortable, searchable table with CSV export ---
function SortableTable({ title, columns, rows, initialSort, searchKeys, rowClass, exportName }) {
  const [sort, setSort] = useState(initialSort || { key: columns[0]?.key, dir: 'desc' })
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    let out = rows || []
    if (query && searchKeys?.length) {
      const q = query.toLowerCase()
      out = out.filter(r => searchKeys.some(k => String(r[k] ?? '').toLowerCase().includes(q)))
    }
    const { key, dir } = sort
    const sorted = [...out].sort((a, b) => {
      const av = a[key]; const bv = b[key]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === 'number' && typeof bv === 'number') return dir === 'asc' ? av - bv : bv - av
      return dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    })
    return sorted
  }, [rows, query, sort, searchKeys])

  const onSort = (key) => setSort(s => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))

  const onExport = () => {
    const head = columns.map(c => `"${c.label}"`).join(',')
    const body = filtered.map(r => columns.map(c => {
      const raw = c.exportValue ? c.exportValue(r) : r[c.key]
      return `"${String(raw ?? '').replace(/"/g, '""')}"`
    }).join(',')).join('\n')
    const blob = new Blob([`${head}\n${body}`], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${exportName || 'export'}_${todayISO()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="retail-card">
      <div className="retail-card-head">
        <h3>{title}</h3>
        <div className="retail-card-tools">
          {searchKeys?.length > 0 && (
            <input className="retail-search" placeholder="Search…" value={query} onChange={e => setQuery(e.target.value)} />
          )}
          <button type="button" className="retail-btn ghost" onClick={onExport} disabled={!filtered.length}>Export CSV</button>
        </div>
      </div>
      <div className="retail-table-wrap">
        <table className="retail-table">
          <thead>
            <tr>
              {columns.map(c => (
                <th key={c.key} className={c.align === 'right' ? 'right' : ''}
                  onClick={c.sortable === false ? undefined : () => onSort(c.key)}
                  style={{ cursor: c.sortable === false ? 'default' : 'pointer' }}>
                  {c.label}{sort.key === c.key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={columns.length} className="retail-empty-cell">No rows.</td></tr>
            )}
            {filtered.map((r, i) => (
              <tr key={i} className={rowClass ? rowClass(r) : ''}>
                {columns.map(c => (
                  <td key={c.key} className={c.align === 'right' ? 'right' : ''}>
                    {c.render ? c.render(r) : r[c.key] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function FilterSelect({ label, value, onChange, options, allLabel }) {
  return (
    <label className="retail-filter">
      <span>{label}</span>
      <select value={value || ''} onChange={e => onChange(e.target.value || null)}>
        <option value="">{allLabel || 'All'}</option>
        {options.map(o => (
          <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
        ))}
      </select>
    </label>
  )
}

export default function RetailPanel() {
  const [subTab, setSubTab] = useState('operations')

  // range + compare
  const [presetId, setPresetId] = useState('last_30_days')
  const [range, setRange] = useState(presetRange('last_30_days'))
  const [compareMode, setCompareMode] = useState('prior') // none | prior | custom
  const [compareRange, setCompareRange] = useState({ start: '', end: '' })

  // filters
  const [facets, setFacets] = useState(null)
  const [filters, setFilters] = useState({ storeId: null, channel: 'all', brand: null, category: null, budtender: null })

  // data + status
  const [data, setData] = useState(null)
  const [live, setLive] = useState(null)
  const [autoLive, setAutoLive] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [disabledInfo, setDisabledInfo] = useState(null)
  const [retailGate, setRetailGate] = useState('checking')
  const [refreshing, setRefreshing] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [reconciliation, setReconciliation] = useState(null)
  const dataRef = useRef(false)

  const applyPreset = (id) => {
    setPresetId(id)
    if (id !== 'custom') setRange(presetRange(id))
  }

  const compareParams = useMemo(() => {
    if (compareMode === 'none') return { compare: false }
    if (compareMode === 'custom' && compareRange.start && compareRange.end) {
      return { compare: true, compareStart: compareRange.start, compareEnd: compareRange.end }
    }
    return { compare: true }
  }, [compareMode, compareRange])

  useEffect(() => {
    let mounted = true
    api.retailHealth()
      .then((h) => {
        if (!mounted) return
        if (h?.disabled || h?.available === false) {
          setDisabledInfo(h)
          setRetailGate('disabled')
          setLoading(false)
        } else {
          setRetailGate('live')
        }
      })
      .catch(() => {
        if (mounted) setRetailGate('live')
      })
    return () => { mounted = false }
  }, [])

  const loadRange = useCallback(async (silent = false) => {
    if (retailGate !== 'live') return
    if (!silent && !dataRef.current) setLoading(true)
    setError(null)
    try {
      const d = await api.retailDashboardRange({
        start: range.start,
        end: range.end,
        ...compareParams,
        storeId: filters.storeId,
        channel: filters.channel,
        brand: filters.brand,
        category: filters.category,
        budtender: filters.budtender,
      })
      setData(d)
      dataRef.current = true
    } catch (e) {
      if (!silent) { setError(e.message); setData(null) }
    } finally {
      if (!silent) setLoading(false)
    }
  }, [range, compareParams, filters, retailGate])

  const loadLive = useCallback(async () => {
    try { setLive(await api.retailLiveStatus()) } catch { /* keep last */ }
  }, [])

  // facets + reconciliation once
  useEffect(() => {
    if (retailGate !== 'live') return undefined
    (async () => {
      try { setFacets(await api.retailFacets()) } catch { setFacets(null) }
      try { setReconciliation(await api.retailReconciliation()) } catch { setReconciliation(null) }
    })()
    return undefined
  }, [retailGate])

  // reload range when range/compare/filters change
  useEffect(() => {
    if (retailGate !== 'live') return
    loadRange(false)
    loadLive()
  }, [loadRange, loadLive, retailGate])

  // live polling
  useEffect(() => {
    const t = setInterval(() => {
      loadLive()
      if (autoLive) loadRange(true)
    }, autoLive ? Math.min(LIVE_POLL_MS, RANGE_POLL_MS) : LIVE_POLL_MS)
    return () => clearInterval(t)
  }, [autoLive, loadLive, loadRange])

  // manual rebuild (ingest+build) job polling
  useEffect(() => {
    if (!jobId) return undefined
    const t = setInterval(async () => {
      try {
        const j = await api.retailJob(jobId)
        if (j.status === 'completed' || j.status === 'failed') {
          clearInterval(t)
          setRefreshing(false)
          setJobId(null)
          if (j.status === 'completed') loadRange(true)
          else setError(j.error || 'rebuild failed')
        }
      } catch { clearInterval(t); setRefreshing(false) }
    }, 2000)
    return () => clearInterval(t)
  }, [jobId, loadRange])

  const onRebuild = async () => {
    setRefreshing(true)
    setError(null)
    try {
      const days = Math.max(1, daysBetween(range.start, range.end))
      const r = await api.retailRefresh({ start: range.start, end: range.end, days, compare: compareMode !== 'none', store_id: filters.storeId, channel: filters.channel })
      if (r.job_id) setJobId(r.job_id); else setRefreshing(false)
    } catch (e) { setError(e.message); setRefreshing(false) }
  }

  if (disabledInfo) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <h2 className="text-[15px] text-white/80 font-medium">Retail</h2>
        <p className="mt-2 text-[12px] text-white/50 max-w-xl">
          {disabledInfo.reason || 'GrowFlow retail is not available on Acheron. Live writers stay on power-1.'}
        </p>
        <p className="mt-2 text-[11px] font-mono text-white/30">
          Status: disabled · available={String(disabledInfo.available)} · machine={disabledInfo.machine || 'acheron'}
        </p>
      </div>
    )
  }

  const meta = data?.meta || {}
  const alerts = data?.alerts || []

  const netSeries = (data?.discounts_over_time || []).map(d => ({ x: d.date, y: d.net_sales }))
  const discSeries = (data?.discounts_over_time || []).map(d => ({ x: d.date, y: d.effective_discount_pct }))
  const brandBars = (data?.brand_summary || []).slice(0, 8).map(b => ({ label: b.brand_name, value: b.net_sales }))
  const categoryBars = useMemo(() => {
    const agg = {}
    for (const r of data?.budtender_by_category || []) agg[r.category_name] = (agg[r.category_name] || 0) + r.net_sales
    return Object.entries(agg).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 8)
  }, [data])

  const activeFilterCount = ['storeId', 'brand', 'category', 'budtender'].filter(k => filters[k]).length + (filters.channel !== 'all' ? 1 : 0)

  return (
    <div className="retail-panel">
      <header className="retail-header">
        <div className="retail-title">
          <h2>Retail Intelligence</h2>
          {subTab === 'operations' && <LiveBadge live={live} autoLive={autoLive} onToggle={() => setAutoLive(v => !v)} />}
        </div>
        {subTab === 'operations' && (
          <div className="retail-controls">
            <div className="retail-presets">
              {PRESETS.map(p => (
                <button key={p.id} type="button" className={presetId === p.id ? 'active' : ''} onClick={() => applyPreset(p.id)}>{p.label}</button>
              ))}
            </div>
            <div className="retail-daterange">
              <input type="date" value={range.start} max={range.end}
                onChange={e => { setPresetId('custom'); setRange(r => ({ ...r, start: e.target.value })) }} />
              <span>→</span>
              <input type="date" value={range.end} min={range.start} max={todayISO()}
                onChange={e => { setPresetId('custom'); setRange(r => ({ ...r, end: e.target.value })) }} />
            </div>
            <div className="retail-compare">
              <span>Compare</span>
              <select value={compareMode} onChange={e => setCompareMode(e.target.value)}>
                <option value="none">Off</option>
                <option value="prior">Prior period</option>
                <option value="custom">Custom</option>
              </select>
              {compareMode === 'custom' && (
                <>
                  <input type="date" value={compareRange.start} onChange={e => setCompareRange(r => ({ ...r, start: e.target.value }))} />
                  <span>→</span>
                  <input type="date" value={compareRange.end} onChange={e => setCompareRange(r => ({ ...r, end: e.target.value }))} />
                </>
              )}
            </div>
            <button type="button" className="retail-btn" onClick={() => loadRange(false)} disabled={loading}>Reload</button>
            <button type="button" className="retail-btn primary" onClick={onRebuild} disabled={refreshing}
              title="Force a full ingest + rebuild for this range (usually not needed — data is live)">
              {refreshing ? 'Rebuilding…' : 'Force rebuild'}
            </button>
          </div>
        )}
      </header>

      <nav className="retail-subnav" role="tablist">
        {SUB_TABS.map(t => (
          <button key={t.id} type="button" role="tab" aria-selected={subTab === t.id}
            className={subTab === t.id ? 'active' : ''} onClick={() => setSubTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {subTab === 'capital' && <CapitalTab />}
      {subTab === 'consignment' && <ConsignmentTab />}

      {subTab === 'operations' && (
        <>
          {facets && (
            <div className="retail-filters">
              <FilterSelect label="Store" value={filters.storeId} allLabel="All stores"
                onChange={v => setFilters(f => ({ ...f, storeId: v }))}
                options={(facets.stores || []).map(s => ({ value: s.id, label: s.name }))} />
              <FilterSelect label="Channel" value={filters.channel === 'all' ? '' : filters.channel} allLabel="All channels"
                onChange={v => setFilters(f => ({ ...f, channel: v || 'all' }))}
                options={(facets.channels || []).map(c => ({ value: c, label: c.replace('_', ' ') }))} />
              <FilterSelect label="Brand" value={filters.brand} allLabel="All brands"
                onChange={v => setFilters(f => ({ ...f, brand: v }))}
                options={(facets.brands || [])} />
              <FilterSelect label="Category" value={filters.category} allLabel="All categories"
                onChange={v => setFilters(f => ({ ...f, category: v }))}
                options={(facets.categories || [])} />
              <FilterSelect label="Budtender" value={filters.budtender} allLabel="All budtenders"
                onChange={v => setFilters(f => ({ ...f, budtender: v }))}
                options={(facets.budtenders || [])} />
              {activeFilterCount > 0 && (
                <button type="button" className="retail-btn ghost" onClick={() => setFilters({ storeId: null, channel: 'all', brand: null, category: null, budtender: null })}>
                  Clear filters ({activeFilterCount})
                </button>
              )}
            </div>
          )}

          {error && <div className="retail-error">⚠ {error}</div>}
          {loading && !data && <div className="retail-loading">Loading dashboard…</div>}

          {data && (
            <>
              <TrustStrip meta={meta} />
              {reconciliation?.status && (
                <div className={`retail-recon ${reconciliation.status === 'pass' ? 'ok' : reconciliation.status === 'fail' ? 'fail' : 'warn'}`}>
                  <span>{reconciliation.status === 'pass' ? '✓' : reconciliation.status === 'fail' ? '✗' : '⚠'} reconciliation {reconciliation.status}</span>
                  {reconciliation.message && <span className="retail-muted">{reconciliation.message}</span>}
                </div>
              )}
              {alerts.length > 0 && (
                <div className="retail-alerts">
                  {alerts.map(a => <div key={a.alert_id} className={`alert ${a.severity}`}>{a.message}</div>)}
                </div>
              )}

              <KpiCards meta={meta} kpis={data.period_compare_kpis} />

              <div className="retail-charts">
                <section className="retail-card">
                  <div className="retail-card-head"><h3>Net Sales Over Time</h3><span className="retail-muted">{range.start} → {range.end}</span></div>
                  <LineChart points={netSeries} color="#5eead4" valueFmt={(v) => fmtUsd(v)} label="net sales" />
                </section>
                <section className="retail-card">
                  <div className="retail-card-head"><h3>Effective Discount %</h3></div>
                  <LineChart points={discSeries} color="#f59e0b" valueFmt={(v) => fmtPct(v)} label="discount" />
                </section>
                <section className="retail-card">
                  <div className="retail-card-head"><h3>Top Brands by Net</h3></div>
                  <BarChart data={brandBars} color="#818cf8" valueFmt={(v) => fmtUsd(v)} />
                </section>
                <section className="retail-card">
                  <div className="retail-card-head"><h3>Category Mix</h3></div>
                  <BarChart data={categoryBars} color="#34d399" valueFmt={(v) => fmtUsd(v)} />
                </section>
              </div>

              <div className="retail-tables">
                <SortableTable
                  title="Budtender Sales"
                  exportName="budtender_sales"
                  searchKeys={['budtender']}
                  initialSort={{ key: 'net_sales', dir: 'desc' }}
                  rowClass={(r) => (r.flags?.length ? 'flagged' : '')}
                  rows={data.budtender_sales}
                  columns={[
                    { key: 'budtender', label: 'Budtender' },
                    { key: 'net_sales', label: 'Net', align: 'right', render: r => fmtUsd(r.net_sales) },
                    { key: 'order_count', label: 'Orders', align: 'right', render: r => fmtInt(r.order_count) },
                    { key: 'aov', label: 'AOV', align: 'right', render: r => fmtUsd(r.aov, 2) },
                    { key: 'effective_discount_pct', label: 'Disc %', align: 'right', render: r => fmtPct(r.effective_discount_pct) },
                    { key: 'pct_net_sales', label: '% Net', align: 'right', render: r => fmtPct(r.pct_net_sales) },
                    { key: 'flags', label: 'Flags', sortable: false, render: r => (r.flags || []).join(', ') || '—', exportValue: r => (r.flags || []).join('; ') },
                  ]}
                />
                <SortableTable
                  title="Brand Summary"
                  exportName="brand_summary"
                  searchKeys={['brand_name']}
                  initialSort={{ key: 'net_sales', dir: 'desc' }}
                  rows={data.brand_summary}
                  columns={[
                    { key: 'brand_name', label: 'Brand' },
                    { key: 'net_sales', label: 'Net', align: 'right', render: r => fmtUsd(r.net_sales) },
                    { key: 'effective_discount_pct', label: 'Disc %', align: 'right', render: r => fmtPct(r.effective_discount_pct) },
                    { key: 'native_margin_pct', label: 'Native margin', align: 'right', render: r => fmtPct(r.native_margin_pct) },
                    { key: 'landed_margin_pct', label: 'Landed margin', align: 'right', render: r => fmtPct(r.landed_margin_pct) },
                    { key: 'profit_velocity_rank', label: 'Rank', align: 'right', render: r => r.profit_velocity_rank ?? '—' },
                  ]}
                />
                <SortableTable
                  title="Daily Detail"
                  exportName="daily_detail"
                  initialSort={{ key: 'date', dir: 'asc' }}
                  rows={data.discounts_over_time}
                  columns={[
                    { key: 'date', label: 'Date' },
                    { key: 'net_sales', label: 'Net', align: 'right', render: r => fmtUsd(r.net_sales) },
                    { key: 'order_count', label: 'Orders', align: 'right', render: r => fmtInt(r.order_count) },
                    { key: 'effective_discount_pct', label: 'Disc %', align: 'right', render: r => fmtPct(r.effective_discount_pct) },
                    { key: 'pct_orders_discounted', label: '% Orders Disc', align: 'right', render: r => fmtPct(r.pct_orders_discounted) },
                  ]}
                />
                <SortableTable
                  title="Budtender × Category"
                  exportName="budtender_by_category"
                  searchKeys={['category_name', 'budtender']}
                  initialSort={{ key: 'net_sales', dir: 'desc' }}
                  rows={data.budtender_by_category}
                  columns={[
                    { key: 'category_name', label: 'Category' },
                    { key: 'budtender', label: 'Budtender' },
                    { key: 'net_sales', label: 'Net', align: 'right', render: r => fmtUsd(r.net_sales) },
                    { key: 'item_count', label: 'Items', align: 'right', render: r => fmtInt(r.item_count) },
                  ]}
                />
              </div>
            </>
          )}
        </>
      )}

      <style>{`
        .retail-panel { padding: 1rem 1.25rem; color: #e8eef2; max-width: 1500px; }
        .retail-header { display: flex; flex-direction: column; gap: 0.6rem; margin-bottom: 0.6rem; }
        .retail-title { display: flex; align-items: center; gap: 1rem; }
        .retail-title h2 { margin: 0; font-size: 1.25rem; color: #5eead4; }
        .retail-live { display: inline-flex; align-items: center; gap: 0.4rem; border-radius: 999px; padding: 0.25rem 0.7rem;
          font-size: 0.75rem; border: 1px solid #334155; background: #0f172a; color: #cbd5e1; cursor: pointer; }
        .retail-live .dot { width: 8px; height: 8px; border-radius: 50%; background: #64748b; }
        .retail-live.live .dot { background: #34d399; box-shadow: 0 0 0 0 rgba(52,211,153,0.7); animation: retailPulse 1.8s infinite; }
        .retail-live.live.off .dot { animation: none; }
        .retail-live.warn .dot { background: #f59e0b; }
        .retail-live.fail .dot { background: #f87171; }
        .retail-live-auto { font-size: 0.6rem; letter-spacing: 0.05em; color: #64748b; }
        .retail-live.on .retail-live-auto { color: #34d399; }
        @keyframes retailPulse { 0% { box-shadow: 0 0 0 0 rgba(52,211,153,0.6); } 70% { box-shadow: 0 0 0 6px rgba(52,211,153,0); } 100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); } }
        .retail-controls { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
        .retail-presets { display: inline-flex; border: 1px solid #334155; border-radius: 6px; overflow: hidden; }
        .retail-presets button { background: #0f172a; border: none; color: #94a3b8; padding: 0.35rem 0.6rem; cursor: pointer; font-size: 0.78rem; border-right: 1px solid #1e293b; }
        .retail-presets button:last-child { border-right: none; }
        .retail-presets button.active { background: #134e4a; color: #99f6e4; }
        .retail-daterange, .retail-compare { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; color: #94a3b8; }
        .retail-daterange input, .retail-compare input, .retail-compare select, .retail-filter select {
          background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.3rem 0.45rem; border-radius: 4px; font-size: 0.78rem; }
        .retail-btn { background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.35rem 0.7rem; border-radius: 4px; cursor: pointer; font-size: 0.78rem; }
        .retail-btn:hover:not(:disabled) { border-color: #5eead4; }
        .retail-btn:disabled { opacity: 0.5; cursor: default; }
        .retail-btn.primary { background: #134e4a; border-color: #0f766e; color: #99f6e4; }
        .retail-btn.ghost { background: transparent; }
        .retail-subnav { display: flex; gap: 0.25rem; margin: 0.5rem 0 1rem; border-bottom: 1px solid #1e293b; }
        .retail-subnav button { background: transparent; border: none; color: #64748b; padding: 0.5rem 0.75rem; border-bottom: 2px solid transparent; margin-bottom: -1px; cursor: pointer; font-size: 0.85rem; }
        .retail-subnav button.active { color: #5eead4; border-bottom-color: #5eead4; }
        .retail-filters { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: flex-end; margin-bottom: 0.75rem; padding: 0.6rem 0.75rem; background: #0b1220; border: 1px solid #1e293b; border-radius: 8px; }
        .retail-filter { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.68rem; text-transform: uppercase; color: #64748b; letter-spacing: 0.03em; }
        .retail-trust { display: flex; gap: 1rem; font-size: 0.8rem; padding: 0.45rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; flex-wrap: wrap; }
        .retail-trust.ok { background: #134e4a; color: #99f6e4; }
        .retail-trust.warn { background: #713f12; color: #fde68a; }
        .retail-trust.fail { background: #450a0a; color: #fecaca; border: 1px solid #f87171; }
        .retail-recon { display: flex; gap: 0.75rem; align-items: center; font-size: 0.76rem; padding: 0.35rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; }
        .retail-recon.ok { background: #0f2f2a; color: #99f6e4; }
        .retail-recon.warn { background: #422006; color: #fde68a; }
        .retail-recon.fail { background: #450a0a; color: #fecaca; }
        .retail-alerts { margin-bottom: 0.75rem; }
        .retail-alerts .alert { padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.82rem; margin-bottom: 0.25rem; }
        .retail-alerts .warning { background: #422006; color: #fde68a; }
        .retail-alerts .info { background: #1e3a5f; color: #bae6fd; }
        .retail-kpis { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .retail-kpi { background: #0f172a; border: 1px solid #1e293b; padding: 0.6rem 0.9rem; border-radius: 8px; min-width: 150px; flex: 1; }
        .retail-kpi .label { font-size: 0.68rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.04em; }
        .retail-kpi .value { font-size: 1.4rem; font-weight: 700; margin: 0.15rem 0; }
        .retail-kpi .delta { font-size: 0.72rem; }
        .retail-kpi .delta.up { color: #34d399; }
        .retail-kpi .delta.down { color: #f87171; }
        .retail-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
        .retail-tables { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .retail-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 0.75rem; }
        .retail-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; gap: 0.5rem; }
        .retail-card-head h3 { margin: 0; font-size: 0.92rem; color: #5eead4; }
        .retail-card-tools { display: flex; gap: 0.4rem; align-items: center; }
        .retail-search { background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 0.25rem 0.45rem; border-radius: 4px; font-size: 0.75rem; width: 120px; }
        .retail-svg { width: 100%; height: 150px; display: block; }
        .retail-chart-empty { color: #64748b; font-size: 0.8rem; padding: 2rem 0; text-align: center; }
        .retail-bars { display: flex; flex-direction: column; gap: 0.35rem; padding: 0.25rem 0; }
        .retail-bar-row { display: grid; grid-template-columns: 110px 1fr 90px; align-items: center; gap: 0.5rem; font-size: 0.75rem; }
        .retail-bar-label { color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .retail-bar-track { background: #1e293b; border-radius: 4px; height: 12px; overflow: hidden; }
        .retail-bar-fill { display: block; height: 100%; border-radius: 4px; }
        .retail-bar-value { text-align: right; color: #94a3b8; }
        .retail-table-wrap { overflow: auto; max-height: 360px; }
        .retail-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
        .retail-table th, .retail-table td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid #1e293b; white-space: nowrap; }
        .retail-table th { color: #94a3b8; font-weight: 500; position: sticky; top: 0; background: #0f172a; }
        .retail-table th.right, .retail-table td.right { text-align: right; }
        .retail-table tr.flagged td { color: #fcd34d; }
        .retail-empty-cell { color: #64748b; text-align: center; padding: 1rem; }
        .retail-error { background: #450a0a; color: #fecaca; padding: 0.5rem 0.75rem; border-radius: 4px; margin-bottom: 0.75rem; }
        .retail-loading { color: #94a3b8; padding: 2rem 0; }
        .retail-muted { color: #64748b; font-size: 0.72rem; }
        @media (max-width: 1100px) { .retail-charts, .retail-tables { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  )
}
