import { create } from 'zustand'

const GURU_MODE_META = {
  RR: { label: 'Response Refinement', savePolicy: 'direct' },
  PR: { label: 'Proposal Refinement', savePolicy: 'direct' },
  AL: { label: 'Action List', savePolicy: 'confirm' },
  TL: { label: 'Tool List', savePolicy: 'confirm' },
  ATL: { label: 'Auto Task List', savePolicy: 'confirm' },
}

/* ── Event store ── */
export const useEventStore = create((set, get) => ({
  events: [],           // all ACT + APR events
  pendingCount: 0,

  addEvent(ev) {
    set(s => {
      const withoutExisting = s.events.filter(existing => existing.id !== ev.id)
      const events = [ev, ...withoutExisting].slice(0, 300)
      const pendingCount = events.filter(e => e.type === 'approval' && e.status === 'pending').length
      return { events, pendingCount }
    })
  },

  resolveApproval(id, resolution) {
    set(s => ({
      events: s.events.map(e =>
        e.id === id ? { ...e, status: resolution } : e
      ),
      pendingCount: s.events.filter(
        e => e.type === 'approval' && e.status === 'pending' && e.id !== id
      ).length,
    }))
  },
}))

/* ── Feed store ── */
export const useFeedStore = create((set) => ({
  lines: [],
  addLine(line) {
    set(s => ({ lines: [line, ...s.lines].slice(0, 500) }))
  },
}))

/* ── Hardware store ── */
export const useHardwareStore = create((set) => ({
  gpu: null,
  cpu_percent: 0,
  cpu: null,       // optional: { total_usage_percent, package_temp_c, frequency_current_mhz, ... }
  node: '',       // optional: host/node name from backend
  ram_used_gb: 0,
  ram_total_gb: 0,
  timestamp: null,
  vramHistory: [],   // [{t, value}] last 20 snapshots

  update(snap) {
    set(s => {
      const ramT = Number(snap?.ram_total_gb)
      const ramU = Number(snap?.ram_used_gb)
      const incomingBad =
        (snap?.gpu == null || snap?.gpu === undefined) &&
        (ramT === 0 || Number.isNaN(ramT)) &&
        (ramU === 0 || Number.isNaN(ramU))
      const hadGood = (Number(s.ram_total_gb) > 0) || s.gpu != null
      // WS history can briefly replay a zeroed fallback snapshot; don't clobber a good REST load.
      if (incomingBad && hadGood) {
        return s
      }
      const vramHistory = [
        ...s.vramHistory,
        { t: new Date(snap.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), value: snap.gpu?.vram_used_gb ?? 0 },
      ].slice(-20)
      return {
        gpu: snap.gpu,
        cpu_percent: snap.cpu_percent,
        cpu: snap.cpu ?? null,
        node: snap.node ?? '',
        ram_used_gb: snap.ram_used_gb,
        ram_total_gb: snap.ram_total_gb,
        timestamp: snap.timestamp ?? null,
        vramHistory,
      }
    })
  },
}))

/* ── Chat store ── */
export const useChatStore = create((set) => ({
  messages: [
    { role: 'ai', text: 'Command center online. Main orchestrator connected. Guru settings available in the Guru tab.' }
  ],
  addMessage(msg) {
    set(s => ({ messages: [...s.messages, msg] }))
  },
}))

/* ── Repo store ── */
export const useRepoStore = create((set) => ({
  fileActivity: {},   // path → { op, agent, ts, reads, writes, execs }
  summaries: [],      // [{ name, path, entrypoints }] from cartographer scans

  setSummaries(summaries) {
    set({ summaries: summaries || [] })
  },

  touch(path, op, agent) {
    set(s => {
      const prev = s.fileActivity[path] || { reads: 0, writes: 0, execs: 0 }
      return {
        fileActivity: {
          ...s.fileActivity,
          [path]: {
            ...prev,
            op, agent,
            ts: new Date().toISOString(),
            reads: prev.reads + (op === 'read' ? 1 : 0),
            writes: prev.writes + (op === 'write' ? 1 : 0),
            execs: prev.execs + (op === 'exec' ? 1 : 0),
          },
        },
      }
    })
  },
}))

/* ── UI store ── */
export const useUiStore = create((set) => ({
  tab: 'chat',
  setTab(tab) {
    set({ tab })
  },
}))

/* ── Guru store ── */
function makeModeState(mode) {
  const meta = GURU_MODE_META[mode]
  return {
    mode,
    label: meta.label,
    savePolicy: meta.savePolicy,
    description: '',
    messages: [],
    currentDraft: null,
    lastSavedSummary: null,
    lastUpdatedAt: null,
    currentRules: {},
  }
}

export const useGuruStore = create((set) => ({
  selectedMode: 'RR',
  modes: Object.keys(GURU_MODE_META).reduce((acc, mode) => {
    acc[mode] = makeModeState(mode)
    return acc
  }, {}),

  setSelectedMode(mode) {
    set({ selectedMode: mode })
  },

  hydrateSnapshot(snapshot) {
    const modes = {}
    Object.keys(GURU_MODE_META).forEach(mode => {
      const next = snapshot?.modes?.[mode] || {}
      modes[mode] = {
        ...makeModeState(mode),
        ...next,
        currentDraft: next.current_draft ?? null,
        lastSavedSummary: next.last_saved_summary ?? null,
        lastUpdatedAt: next.last_updated_at ?? null,
        currentRules: next.current_rules ?? {},
      }
    })
    set({ modes })
  },

  updateMode(mode, data) {
    const hasCurrentDraft = Object.prototype.hasOwnProperty.call(data, 'current_draft') || Object.prototype.hasOwnProperty.call(data, 'currentDraft')
    const hasLastSavedSummary = Object.prototype.hasOwnProperty.call(data, 'last_saved_summary') || Object.prototype.hasOwnProperty.call(data, 'lastSavedSummary')
    const hasLastUpdatedAt = Object.prototype.hasOwnProperty.call(data, 'last_updated_at') || Object.prototype.hasOwnProperty.call(data, 'lastUpdatedAt')
    const hasCurrentRules = Object.prototype.hasOwnProperty.call(data, 'current_rules') || Object.prototype.hasOwnProperty.call(data, 'currentRules')

    set(s => ({
      modes: {
        ...s.modes,
        [mode]: {
          ...s.modes[mode],
          ...data,
          currentDraft: hasCurrentDraft ? (data.current_draft ?? data.currentDraft ?? null) : s.modes[mode].currentDraft,
          lastSavedSummary: hasLastSavedSummary ? (data.last_saved_summary ?? data.lastSavedSummary ?? null) : s.modes[mode].lastSavedSummary,
          lastUpdatedAt: hasLastUpdatedAt ? (data.last_updated_at ?? data.lastUpdatedAt ?? null) : s.modes[mode].lastUpdatedAt,
          currentRules: hasCurrentRules ? (data.current_rules ?? data.currentRules ?? {}) : s.modes[mode].currentRules,
        },
      },
    }))
  },
}))
