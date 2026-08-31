import { logDiagnostic } from './diagnostics'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function readHttpError(r) {
  try {
    const text = await r.text()
    if (!text) return `${r.status} ${r.statusText}`
    try {
      const j = JSON.parse(text)
      const detail = j.detail ?? j.message ?? j.error
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) return detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      return text.slice(0, 400)
    } catch {
      return text.slice(0, 400) || `${r.status} ${r.statusText}`
    }
  } catch {
    return `${r.status} ${r.statusText}`
  }
}

/**
 * @param {string} path
 * @param {object} body
 * @param {{ timeoutMs?: number }} [opts] — omit or 0 for no client timeout
 */
async function post(path, body, opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 0
  logDiagnostic('api:request', { method: 'POST', path, body })
  const startedAt = Date.now()
  const ctrl = new AbortController()
  const tid = timeoutMs > 0 ? setTimeout(() => ctrl.abort(), timeoutMs) : null
  let r
  try {
    r = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    })
  } catch (e) {
    if (tid) clearTimeout(tid)
    if (e?.name === 'AbortError') {
      logDiagnostic('api:abort', { path, timeoutMs })
      throw new Error(
        timeoutMs
          ? `Request timed out after ${Math.round(timeoutMs / 1000)}s (is the API / LLM reachable?)`
          : 'Request was cancelled'
      )
    }
    throw e
  }
  if (tid) clearTimeout(tid)
  if (!r.ok) {
    const msg = await readHttpError(r)
    logDiagnostic('api:error', { method: 'POST', path, status: r.status, statusText: r.statusText, duration_ms: Date.now() - startedAt })
    throw new Error(msg)
  }
  const data = await r.json()
  logDiagnostic('api:response', { method: 'POST', path, status: r.status, duration_ms: Date.now() - startedAt })
  return data
}

async function httpDelete(path) {
  logDiagnostic('api:request', { method: 'DELETE', path })
  const startedAt = Date.now()
  const r = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!r.ok) {
    const msg = await readHttpError(r)
    logDiagnostic('api:error', { method: 'DELETE', path, status: r.status, duration_ms: Date.now() - startedAt })
    throw new Error(msg)
  }
  const data = await r.json()
  logDiagnostic('api:response', { method: 'DELETE', path, status: r.status, duration_ms: Date.now() - startedAt })
  return data
}

function buildQuery(params = {}) {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    usp.append(k, typeof v === 'boolean' ? String(v) : v)
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

async function get(path) {
  logDiagnostic('api:request', { method: 'GET', path })
  const startedAt = Date.now()
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) {
    const msg = await readHttpError(r)
    logDiagnostic('api:error', { method: 'GET', path, status: r.status, statusText: r.statusText, duration_ms: Date.now() - startedAt })
    throw new Error(msg)
  }
  const data = await r.json()
  logDiagnostic('api:response', { method: 'GET', path, status: r.status, duration_ms: Date.now() - startedAt })
  return data
}

/**
 * SSE chat: token deltas via data: {"delta":"..."} then data: {"done":true,"text",...}
 */
export async function chatStream(message, history = [], opts = {}) {
  const { onDelta, onDone, onError, sessionId = 'default', clientSubmitEpochMs = null, requestId = null } = opts
  const timeoutMs = 180000
  const ctrl = new AbortController()
  const tid = setTimeout(() => ctrl.abort(), timeoutMs)
  let r
  try {
    const body = { message, history, session_id: sessionId }
    if (clientSubmitEpochMs != null) body.client_submit_epoch_ms = clientSubmitEpochMs
    if (requestId) body.request_id = requestId
    r = await fetch(`${BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    })
  } catch (e) {
    clearTimeout(tid)
    if (e?.name === 'AbortError') {
      const msg = `Request timed out after ${Math.round(timeoutMs / 1000)}s (is the API / LLM reachable?)`
      onError?.(msg)
      throw new Error(msg)
    }
    onError?.(e.message)
    throw e
  }
  clearTimeout(tid)
  if (!r.ok) {
    const err = `${r.status} ${r.statusText}`
    onError?.(err)
    throw new Error(err)
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let sawDone = false
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    buf = buf.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx).trim()
      buf = buf.slice(idx + 2)
      if (!block.startsWith('data: ')) continue
      const line = block.startsWith('data: ') ? block.slice(6) : block
      let j
      try {
        j = JSON.parse(line)
      } catch {
        continue
      }
      if (j.hb) continue
      if (j.delta != null && j.delta !== '' && onDelta) onDelta(j.delta)
      if (j.done) {
        sawDone = true
        onDone?.(j)
        return
      }
      if (j.error) {
        onError?.(j.error)
        return
      }
    }
  }
  if (!sawDone) {
    const msg = 'Stream ended before completion'
    onError?.(msg)
    throw new Error(msg)
  }
}

export const api = {
  /** Local LLM can be slow — allow 3 minutes before client abort */
  chat: (message, history = []) => post('/api/chat', { message, history }, { timeoutMs: 180000 }),
  chatStream,
  resolveApproval: (id, resolution) =>
    post('/api/approvals/resolve', { id, resolution }, { timeoutMs: 45000 }),
  approvals: () => get('/api/approvals'),
  listPermanentApprovals: () => get('/api/approvals/permanent'),
  addPermanentApproval: (body) => post('/api/approvals/permanent', body, { timeoutMs: 30000 }),
  deletePermanentApproval: (ruleId) =>
    httpDelete(`/api/approvals/permanent/${encodeURIComponent(ruleId)}`),
  hardware: () => get('/api/hardware/snapshot'),
  workersHealth: () => get('/api/workers/health'),
  workersMap: () => get('/api/workers/map'),
  workersHealthByName: (name) => get(`/api/workers/health/${encodeURIComponent(name)}`),
  repoDocsStatus: () => get('/api/repo-docs/status'),
  repoTree: () => get('/api/repo/tree'),
  repoSummaries: () => get('/api/repo/summaries'),
  health: () => get('/api/health'),
  guruSnapshot: () => get('/api/guru'),
  guruMode: (mode) => get(`/api/guru/${mode}`),
  guruMessage: (mode, message) => post(`/api/guru/${mode}/message`, { message }),
  guruConfirm: (mode) => post(`/api/guru/${mode}/confirm`, {}),
  guruRevert: (mode) => post(`/api/guru/${mode}/revert`, {}),
  toolsStats: () => get('/api/tools/stats'),
  toolsWorkerReachable: () => get('/api/tools/worker-reachable'),
  toolsInvoke: (op, payload = {}, agent = 'command-center') =>
    post('/api/tools/invoke', { op, agent, payload }),
  tunnelJobs: () => get('/api/tunnel/jobs'),
  tunnelJobCancel: (jobId) =>
    post(`/api/tunnel/jobs/${encodeURIComponent(jobId)}/cancel`, {}, { timeoutMs: 15000 }),
  operatorStatus: () => get('/api/operator/status'),
  preparedContext: () => get('/api/prepared-context'),
  preparedContextByType: (snapshotType) => get(`/api/prepared-context/${encodeURIComponent(snapshotType)}`),
  refreshPreparedContext: (snapshotType) => post(`/api/prepared-context/refresh/${encodeURIComponent(snapshotType)}`, {}),
  preparedContextRefresherStatus: () => get('/api/prepared-context/status/refresher'),
  growflowValidationStatus: () => get('/api/growflow/validation-status'),
  retailHealth: () => get('/api/retail/health'),
  retailDashboard: (runId) =>
    get(runId ? `/api/retail/dashboard?run_id=${encodeURIComponent(runId)}` : '/api/retail/dashboard'),
  /**
   * On-demand dashboard for an arbitrary range + filters (built from facts, no GraphQL).
   * @param {{start:string,end:string,compare?:boolean,compareStart?:string,compareEnd?:string,
   *          storeId?:string,channel?:string,brand?:string,category?:string,budtender?:string}} p
   */
  retailDashboardRange: (p = {}) =>
    get(`/api/retail/dashboard/range${buildQuery({
      start: p.start,
      end: p.end,
      compare: p.compare,
      compare_start: p.compareStart,
      compare_end: p.compareEnd,
      store_id: p.storeId,
      channel: p.channel,
      brand: p.brand,
      category: p.category,
      budtender: p.budtender,
    })}`),
  retailFacets: () => get('/api/retail/facets'),
  retailLiveStatus: () => get('/api/retail/live-status'),
  retailStores: () => get('/api/retail/stores'),
  retailRefresh: (body = {}) => post('/api/retail/refresh', body, { timeoutMs: 10000 }),
  retailJob: (jobId) => get(`/api/retail/jobs/${encodeURIComponent(jobId)}`),
  retailCapital: () => get('/api/retail/capital'),
  retailCapitalScenario: (body = {}) => post('/api/retail/capital/scenario', body, { timeoutMs: 15000 }),
  retailCapitalApprove: (approvalId) =>
    post(`/api/retail/capital/scenario/${encodeURIComponent(approvalId)}/approve`, {}, { timeoutMs: 15000 }),
  retailCapitalDeny: (approvalId) =>
    post(`/api/retail/capital/scenario/${encodeURIComponent(approvalId)}/deny`, {}, { timeoutMs: 10000 }),
  retailConsignment: () => get('/api/retail/consignment'),
  retailReconciliation: () => get('/api/retail/reconciliation'),
  retailProjection: () => get('/api/retail/projection'),
  retailPlatformHealth: () => get('/api/retail/platform-health'),
  retailPlatformEventsLatest: () => get('/api/retail/platform-events/latest'),
}
