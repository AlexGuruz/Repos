const STORAGE_KEY = 'command-center:diagnostics'
const LIMIT = 300

function canUseStorage() {
  return typeof window !== 'undefined' && !!window.localStorage
}

export function readDiagnostics() {
  if (!canUseStorage()) return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function logDiagnostic(channel, payload = {}) {
  const entry = {
    at: new Date().toISOString(),
    channel,
    ...payload,
  }

  if (!canUseStorage()) return entry

  try {
    const next = [...readDiagnostics(), entry].slice(-LIMIT)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Ignore diagnostics failures; never block the UI.
  }

  return entry
}

export function clearDiagnostics() {
  if (!canUseStorage()) return
  window.localStorage.removeItem(STORAGE_KEY)
}
