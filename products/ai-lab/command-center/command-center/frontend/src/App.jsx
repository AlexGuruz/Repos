import { useWebSocket } from './hooks/useWebSocket'
import { useEffect, useMemo, useState } from 'react'
import Sidebar    from './components/Sidebar'
import ChatPanel  from './components/ChatPanel'
import ComputePanel from './components/ComputePanel'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import FeedPanel  from './components/FeedPanel'
import GuruPanel  from './components/GuruPanel'
import RepoPanel  from './components/RepoPanel'
import ToolsPanel from './components/ToolsPanel'
import RetailPanel from './components/RetailPanel'
import { useChatStore, useGuruStore, useUiStore } from './store'
import { api } from './lib/api'

const MAIN_TABS = [
  { id: 'chat',    label: 'Chat'         },
  { id: 'guru',    label: 'Guru'         },
  { id: 'compute', label: 'Compute'      },
  { id: 'feed',    label: 'Live feed'    },
  { id: 'repo',    label: 'Repo' },
  { id: 'retail',  label: 'Retail'       },
  { id: 'tools',   label: 'Tool usage'   },
  { id: 'diagnostics', label: 'Diagnostics' },
]

export default function App() {
  const tab = useUiStore(s => s.tab)
  const setTab = useUiStore(s => s.setTab)
  const setSelectedMode = useGuruStore(s => s.setSelectedMode)
  const requestChatSubmit = useChatStore(s => s.requestChatSubmit)
  const [pcHealth, setPcHealth] = useState({
    level: 'warning',
    staleCount: 0,
    oldestAgeMin: null,
    lastSuccess: null,
    detail: 'loading',
  })
  const [pcBadgeOpen, setPcBadgeOpen] = useState(false)
  const [pcDiag, setPcDiag] = useState({ stale: [], failing: [], thresholdBreaches: [] })
  const [workerBadge, setWorkerBadge] = useState({ label: 'worker: checking', on: false })

  // Connect WebSocket — populates all stores
  useWebSocket()

  useEffect(() => {
    let mounted = true
    const tick = async () => {
      try {
        const h = await api.workersHealth()
        if (!mounted) return
        const st = h?.worker_status || 'unknown'
        const name = h?.worker_name || 'power-1'
        setWorkerBadge({
          label: `${name}: ${st}`,
          on: st === 'online',
        })
      } catch {
        if (!mounted) return
        setWorkerBadge({ label: 'worker: unreachable', on: false })
      }
    }
    tick()
    const t = setInterval(tick, 20000)
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [])

  // Global sendPrompt so sub-components can inject chat messages (runs orchestrator stream via ChatPanel)
  window.sendPrompt = (text) => {
    setTab('chat')
    requestChatSubmit(text)
  }

  window.openGuruMode = (mode) => {
    setSelectedMode(mode)
    setTab('guru')
  }

  useEffect(() => {
    let mounted = true
    const CRITICAL = new Set(['system_snapshot', 'repo_pulse', 'worker_snapshot'])
    const ageMinutes = (iso) => {
      if (!iso) return null
      const t = Date.parse(iso)
      if (Number.isNaN(t)) return null
      return Math.max(0, Math.round((Date.now() - t) / 60000))
    }
    const compute = async () => {
      try {
        const [ctx, refresher] = await Promise.all([
          api.preparedContext(),
          api.preparedContextRefresherStatus(),
        ])
        if (!mounted) return
        const snaps = ctx?.index?.snapshots || []
        const staleCount = snaps.filter(s => !!s?.stale).length
        const criticalStale = snaps.filter(s => CRITICAL.has(s?.snapshot_type) && !!s?.stale).length
        const oldestAgeMin = snaps.length
          ? Math.max(...snaps.map(s => ageMinutes(s?.generated_at) ?? 0))
          : null
        const runs = refresher?.last_runs || {}
        const successes = Object.values(runs).filter(r => r?.ok && r?.finished_at).map(r => r.finished_at)
        const lastSuccess = successes.length
          ? successes.sort((a, b) => Date.parse(b) - Date.parse(a))[0]
          : null
        const startupOk = refresher?.startup_warmup_ok !== false
        const running = !!refresher?.running
        const anyCriticalFailure = Object.entries(runs).some(([k, v]) => CRITICAL.has(k) && v?.ok === false)
        const staleNames = snaps.filter(s => !!s?.stale).map(s => s.snapshot_type)
        const thresholdBreaches = snaps
          .filter(s => CRITICAL.has(s?.snapshot_type))
          .map(s => {
            const ageMin = ageMinutes(s?.generated_at)
            const freshSec = Number(s?.freshness_seconds || 0)
            const thresholdMin = freshSec > 0 ? Math.round(freshSec / 60) : null
            if (ageMin == null || thresholdMin == null) return null
            if (ageMin > thresholdMin) {
              return {
                snapshot_type: s.snapshot_type,
                ageMin,
                thresholdMin,
                overByMin: ageMin - thresholdMin,
              }
            }
            return null
          })
          .filter(Boolean)
        const failing = Object.entries(runs)
          .filter(([, v]) => v?.ok === false)
          .map(([k, v]) => ({ snapshot_type: k, error: v?.error || 'failed' }))
        let level = 'green'
        if (!running || !startupOk || anyCriticalFailure) {
          level = 'red'
        } else if (staleCount > 0 || criticalStale > 0) {
          level = 'yellow'
        }
        setPcHealth({
          level,
          staleCount,
          oldestAgeMin,
          lastSuccess,
          detail: running ? 'running' : 'stopped',
        })
        setPcDiag({ stale: staleNames, failing, thresholdBreaches })
      } catch {
        if (!mounted) return
        setPcHealth({
          level: 'red',
          staleCount: 0,
          oldestAgeMin: null,
          lastSuccess: null,
          detail: 'error',
        })
        setPcDiag({
          stale: [],
          failing: [{ snapshot_type: 'refresher', error: 'status fetch failed' }],
          thresholdBreaches: [],
        })
      }
    }
    compute()
    const t = setInterval(compute, 45000)
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [])

  const badgeColor = useMemo(() => {
    if (pcHealth.level === 'green') return '#22c55e'
    if (pcHealth.level === 'yellow') return '#eab308'
    return '#ef4444'
  }, [pcHealth.level])
  const statusLabel = useMemo(() => {
    if (pcHealth.level === 'green') return 'healthy'
    if (pcHealth.level === 'yellow') return 'warning'
    return 'error'
  }, [pcHealth.level])

  function handleSidebarSelect(ev) {
    const text = ev.type === 'approval'
      ? `Tell me about ${ev.id}: ${ev.action} — ${ev.detail}`
      : `What happened in ${ev.id}?`
    setTab('chat')
    requestChatSubmit(text)
  }

  function handlePreparedBadgeClick() {
    setPcBadgeOpen(v => !v)
  }

  function handleOpenPreparedTools() {
    setTab('tools')
    window.dispatchEvent(new Event('focusPreparedContextSection'))
    setPcBadgeOpen(false)
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#0d0d0d' }}>
      {/* Left sidebar */}
      <Sidebar onSelect={handleSidebarSelect} />

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Top bar */}
        <div style={{
          height: 48, borderBottom: '0.5px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8, flexShrink: 0,
        }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'rgba(255,255,255,0.75)', flex: 1 }}>
            AI Lab · Command center
          </span>
          {[
            { label: 'ENFORCEMENT=1', on: true },
            { label: 'MACHINE=main',  on: true },
            workerBadge,
          ].map(t => (
            <span key={t.label} style={{
              fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
              padding: '2px 8px', borderRadius: 4,
              background: t.on ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.05)',
              border: `0.5px solid ${t.on ? 'rgba(34,197,94,0.25)' : 'rgba(255,255,255,0.1)'}`,
              color: t.on ? '#86efac' : 'rgba(255,255,255,0.3)',
            }}>
              {t.label}
            </span>
          ))}
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={handlePreparedBadgeClick}
              title="Prepared Context status"
              style={{
                fontSize: 10,
                fontFamily: 'JetBrains Mono, monospace',
                padding: '2px 8px',
                borderRadius: 4,
                background: 'rgba(255,255,255,0.05)',
                border: '0.5px solid rgba(255,255,255,0.15)',
                color: 'rgba(255,255,255,0.8)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                cursor: 'pointer',
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: 999, background: badgeColor, display: 'inline-block' }} />
              {`prepared ${statusLabel} · stale ${pcHealth.staleCount} · oldest ${pcHealth.oldestAgeMin ?? '-'}m · last ${pcHealth.lastSuccess ? Math.max(0, Math.round((Date.now() - Date.parse(pcHealth.lastSuccess)) / 60000)) : '-'}m`}
            </button>
            {pcBadgeOpen ? (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 28,
                  zIndex: 50,
                  minWidth: 360,
                  maxWidth: 480,
                  background: 'rgba(17,24,39,0.98)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: 8,
                  padding: 10,
                  boxShadow: '0 6px 24px rgba(0,0,0,0.45)',
                }}
              >
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.8)', marginBottom: 6 }}>Prepared context diagnostics</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', marginBottom: 6 }}>
                  status: {statusLabel} · stale: {pcDiag.stale.length} · failing: {pcDiag.failing.length}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)' }}>
                  stale snapshots: {pcDiag.stale.length
                    ? pcDiag.stale.map((name, i) => (
                        <span key={name} style={{ color: '#f59e0b' }}>
                          {i > 0 ? ', ' : ''}{name}
                        </span>
                      ))
                    : 'none'}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)', marginTop: 4 }}>
                  failing snapshots: {pcDiag.failing.length
                    ? pcDiag.failing.map((f, i) => (
                        <span key={f.snapshot_type + i} style={{ color: '#ef4444' }}>
                          {i > 0 ? '; ' : ''}{f.snapshot_type} ({f.error})
                        </span>
                      ))
                    : 'none'}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)', marginTop: 4 }}>
                  critical threshold breaches: {pcDiag.thresholdBreaches.length
                    ? pcDiag.thresholdBreaches.map((b, i) => (
                        <span key={b.snapshot_type + i} style={{ color: '#f97316' }}>
                          {i > 0 ? '; ' : ''}{b.snapshot_type} (+{b.overByMin}m over {b.thresholdMin}m)
                        </span>
                      ))
                    : 'none'}
                </div>
                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    onClick={handleOpenPreparedTools}
                    style={{
                      fontSize: 10,
                      padding: '3px 8px',
                      borderRadius: 4,
                      border: '1px solid rgba(255,255,255,0.2)',
                      background: 'rgba(255,255,255,0.06)',
                      color: 'rgba(255,255,255,0.85)',
                      cursor: 'pointer',
                    }}
                  >
                    Open Tools prepared-context section
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* Tab nav */}
        <div style={{
          display: 'flex', borderBottom: '0.5px solid rgba(255,255,255,0.08)',
          background: 'rgba(255,255,255,0.02)', flexShrink: 0, overflowX: 'auto', minHeight: 42,
        }}>
          {MAIN_TABS.map(t => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              onClick={() => setTab(t.id)}
              style={{
              padding: '8px 18px', fontSize: 12, border: 'none', cursor: 'pointer',
              background: tab === t.id ? 'rgba(255,255,255,0.04)' : 'none',
              color: tab === t.id ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.35)',
              borderBottom: `2px solid ${tab === t.id ? 'rgba(255,255,255,0.5)' : 'transparent'}`,
              fontWeight: tab === t.id ? 500 : 400,
              transition: 'color .15s, border-color .15s',
              fontFamily: 'system-ui, sans-serif',
            }}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Panel area — keep all tabs mounted so WS, chat in-flight, and polling continue when switching tabs */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
          {[
            { id: 'chat', Panel: ChatPanel },
            { id: 'guru', Panel: GuruPanel },
            { id: 'compute', Panel: ComputePanel },
            { id: 'feed', Panel: FeedPanel },
            { id: 'repo', Panel: RepoPanel },
            { id: 'retail', Panel: RetailPanel },
            { id: 'tools', Panel: ToolsPanel },
            { id: 'diagnostics', Panel: DiagnosticsPanel },
          ].map(({ id, Panel }) => {
            const active = tab === id
            return (
              <div
                key={id}
                role="tabpanel"
                id={`panel-${id}`}
                aria-labelledby={`tab-${id}`}
                aria-hidden={!active}
                style={{
                  flex: 1,
                  minHeight: 0,
                  display: active ? 'flex' : 'none',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
                <Panel />
              </div>
            )
          })}
        </div>

      </div>
    </div>
  )
}
