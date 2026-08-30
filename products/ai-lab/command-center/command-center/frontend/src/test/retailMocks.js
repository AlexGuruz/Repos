// Test-only mocks mirroring Growflow :8791 /api/retail/dashboard/range,
// /facets and /live-status payload shapes. Not bundled into the app.

const isoDate = (d) => d.toISOString().slice(0, 10)
const addDays = (base, n) => new Date(base.getTime() + n * 86_400_000)
const now = () => new Date().toISOString()

export const mockRetailFacets = {
  org_id: 'nugz',
  stores: [{ id: 'store-purcell', name: 'NUGZ Purcell' }],
  channels: ['in_store', 'online'],
  brands: ['Country Cannabis', 'Cloud Cover', 'Terp Town', 'Native Roots', 'High Society', 'Green Peak'],
  categories: ['Flower', 'Vapes', 'Edibles', 'Pre-Rolls', 'Concentrates', 'Accessories'],
  budtenders: ['Alice R.', 'Marcus T.', 'Priya S.', 'Devon K.', 'Lena M.'],
}

function seeded(seed) {
  let s = seed % 2147483647
  if (s <= 0) s += 2147483646
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function sumBy(rows, f) {
  return rows.reduce((a, r) => a + f(r), 0)
}

export function mockRetailLiveStatus() {
  const age = 18 + Math.round(Math.random() * 30)
  return {
    available: true,
    ok: true,
    within_store_hours: true,
    detail: 'pulled 7 lines / 3 orders',
    error: null,
    watermark: now(),
    rows_last_tick: 7,
    orders_last_tick: 3,
    last_success_at: new Date(Date.now() - age * 1000).toISOString(),
    age_seconds: age,
    freshness: age <= 300 ? 'fresh' : 'stale_but_usable',
    slo_seconds: 300,
  }
}

export function buildMockRetailRange(params = {}) {
  const start = String(params.start || isoDate(addDays(new Date(), -29)))
  const end = String(params.end || isoDate(new Date()))
  const compare = params.compare === true || params.compare === 'true'
  const brandFilter = params.brand ? String(params.brand) : null
  const categoryFilter = params.category ? String(params.category) : null
  const budtenderFilter = params.budtender ? String(params.budtender) : null

  const startD = new Date(`${start}T00:00:00`)
  const endD = new Date(`${end}T00:00:00`)
  const dayCount = Math.max(1, Math.round((endD.getTime() - startD.getTime()) / 86_400_000) + 1)
  const rand = seeded(startD.getDate() * 100 + dayCount + (brandFilter ? 7 : 0) + (categoryFilter ? 3 : 0))
  const filterScale = (brandFilter ? 0.28 : 1) * (categoryFilter ? 0.45 : 1) * (budtenderFilter ? 0.22 : 1)

  const discounts_over_time = []
  let storeNet = 0
  let storeOrders = 0
  for (let i = 0; i < dayCount; i++) {
    const d = addDays(startD, i)
    const dow = d.getDay()
    const weekendBoost = dow === 5 || dow === 6 ? 1.35 : dow === 0 ? 0.7 : 1
    const base = 5200 + rand() * 3600
    const net = Math.round(base * weekendBoost * filterScale)
    const orders = Math.max(1, Math.round((net / 46) * (0.9 + rand() * 0.2)))
    const disc = 8 + rand() * 12
    storeNet += net
    storeOrders += orders
    discounts_over_time.push({
      date: isoDate(d),
      net_sales: net,
      order_count: orders,
      effective_discount_pct: Math.round(disc * 10) / 10,
      pct_orders_discounted: Math.round((30 + rand() * 40) * 10) / 10,
    })
  }

  const budtenders = budtenderFilter ? [budtenderFilter] : mockRetailFacets.budtenders
  const budtender_sales = budtenders.map((name, idx) => {
    const net = Math.round((storeNet * (0.32 - idx * 0.05)) || storeNet / budtenders.length)
    const oc = Math.max(1, Math.round(storeOrders * (0.3 - idx * 0.05)) || Math.round(storeOrders / budtenders.length))
    const eff = 9 + idx * 2.5 + rand() * 3
    const flags = eff > 16 ? ['high_discount_vs_store'] : []
    return {
      budtender: name,
      net_sales: net,
      order_count: oc,
      aov: Math.round((net / oc) * 100) / 100,
      effective_discount_pct: Math.round(eff * 10) / 10,
      pct_orders_discounted: Math.round((35 + idx * 5) * 10) / 10,
      pct_net_sales: Math.round((net / storeNet) * 1000) / 10,
      flags,
    }
  })

  const brands = brandFilter ? [brandFilter] : mockRetailFacets.brands
  const brand_summary = brands.map((name, idx) => {
    const net = Math.round(storeNet * (0.26 - idx * 0.035) || storeNet / brands.length)
    const native = 42 + rand() * 14
    const landed = native - (4 + rand() * 6)
    return {
      brand_name: name,
      canonical_brand: name.toLowerCase().replace(/\s+/g, '_'),
      net_sales: Math.max(0, net),
      returns_pct: Math.round(rand() * 30) / 10,
      effective_discount_pct: Math.round((8 + rand() * 10) * 10) / 10,
      native_margin_pct: Math.round(native * 10) / 10,
      landed_margin_pct: Math.round(landed * 10) / 10,
      cog_vs_landed_delta_pct: Math.round((landed - native) * 10) / 10,
      profit_velocity_rank: idx + 1,
    }
  })

  const cats = categoryFilter ? [categoryFilter] : mockRetailFacets.categories
  const budtender_by_category = []
  for (const cat of cats) {
    for (const bt of budtenders.slice(0, 3)) {
      const net = Math.round(storeNet * (0.03 + rand() * 0.05))
      budtender_by_category.push({
        category_name: cat,
        budtender: bt,
        gross_sales: Math.round(net * 1.15),
        net_sales: net,
        item_count: Math.max(1, Math.round(net / 32)),
      })
    }
  }
  budtender_by_category.sort((a, b) => b.net_sales - a.net_sales)

  const effDiscount = Math.round((sumBy(discounts_over_time, (d) => d.effective_discount_pct) / dayCount) * 10) / 10

  const period_compare_kpis = compare
    ? [
        { key: 'net_sales', current: storeNet, prior: Math.round(storeNet * 0.91), delta_abs: Math.round(storeNet * 0.09), delta_pct: 9.9 },
        { key: 'effective_discount_pct', current: effDiscount, prior: effDiscount + 1.4, delta_abs: -1.4, delta_pct: -9.1 },
        { key: 'order_count', current: storeOrders, prior: Math.round(storeOrders * 0.94), delta_abs: Math.round(storeOrders * 0.06), delta_pct: 6.2 },
        { key: 'pct_orders_discounted', current: 41.2, prior: 44.8, delta_abs: -3.6, delta_pct: -8.0 },
      ]
    : []

  const alerts = []
  if (effDiscount > 14) {
    alerts.push({ alert_id: 'discount_spike', severity: 'warning', code: 'discount_spike', message: `Effective discount ${effDiscount}% trending high vs target.` })
  }

  return {
    generated_at: now(),
    meta: {
      period: { start, end },
      prior_period: compare ? { start: isoDate(addDays(startD, -dayCount)), end: isoDate(addDays(startD, -1)) } : null,
      store_id: params.store_id || null,
      channel: params.channel || 'all',
      timezone: 'America/Chicago',
      store_net_sales: storeNet,
      effective_discount_pct: effDiscount,
      order_count: storeOrders,
      line_count: storeOrders * 3,
      built_at: now(),
      org_id: 'nugz',
      filters: {
        store_id: params.store_id || null,
        channel: params.channel || 'all',
        brand: brandFilter,
        category: categoryFilter,
        budtender: budtenderFilter,
      },
      trust: {
        org_id: 'nugz',
        freshness: 'fresh',
        age_seconds: 24,
        slo_seconds: 300,
        fixture_suspected: false,
        healthy: true,
        source: 'live_ingest',
        watermark: now(),
        checked_at: now(),
        live: mockRetailLiveStatus(),
      },
    },
    period_compare_kpis,
    budtender_sales,
    discounts_over_time,
    budtender_by_category,
    brand_summary,
    alerts,
  }
}
