import { logDiagnostic } from './diagnostics'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
    logDiagnostic('api:error', { method: 'POST', path, status: r.status, statusText: r.statusText, duration_ms: Date.now() - startedAt })
    throw new Error(`${r.status} ${r.statusText}`)
  }
  const data = await r.json()
  logDiagnostic('api:response', { method: 'POST', path, status: r.status, duration_ms: Date.now() - startedAt })
  return data
}

async function get(path) {
  logDiagnostic('api:request', { method: 'GET', path })
  const startedAt = Date.now()
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) {
    logDiagnostic('api:error', { method: 'GET', path, status: r.status, statusText: r.statusText, duration_ms: Date.now() - startedAt })
    throw new Error(`${r.status} ${r.statusText}`)
  }
  const data = await r.json()
  logDiagnostic('api:response', { method: 'GET', path, status: r.status, duration_ms: Date.now() - startedAt })
  return data
}

export const api = {
  /** Local LLM can be slow — allow 3 minutes before client abort */
  chat: (message, history = []) => post('/api/chat', { message, history }, { timeoutMs: 180000 }),
  resolveApproval: (id, resolution) => post('/api/approvals/resolve', { id, resolution }),
  approvals: () => get('/api/approvals'),
  hardware: () => get('/api/hardware/snapshot'),
  workersHealth: () => get('/api/workers/health'),
  workersHealthByName: (name) => get(`/api/workers/health/${encodeURIComponent(name)}`),
  repoTree: () => get('/api/repo/tree'),
  repoSummaries: () => get('/api/repo/summaries'),
  health: () => get('/api/health'),
  guruSnapshot: () => get('/api/guru'),
  guruMode: (mode) => get(`/api/guru/${mode}`),
  guruMessage: (mode, message) => post(`/api/guru/${mode}/message`, { message }),
  guruConfirm: (mode) => post(`/api/guru/${mode}/confirm`, {}),
  guruRevert: (mode) => post(`/api/guru/${mode}/revert`, {}),
  toolsStats: () => get('/api/tools/stats'),
}
