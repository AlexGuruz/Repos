import { useWebSocket } from './hooks/useWebSocket'
import Sidebar    from './components/Sidebar'
import ChatPanel  from './components/ChatPanel'
import ComputePanel from './components/ComputePanel'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import FeedPanel  from './components/FeedPanel'
import GuruPanel  from './components/GuruPanel'
import RepoPanel  from './components/RepoPanel'
import ToolsPanel from './components/ToolsPanel'
import { useChatStore, useGuruStore, useUiStore } from './store'

const MAIN_TABS = [
  { id: 'chat',    label: 'Chat'         },
  { id: 'guru',    label: 'Guru'         },
  { id: 'compute', label: 'Compute'      },
  { id: 'feed',    label: 'Live feed'    },
  { id: 'repo',    label: 'Repo' },
  { id: 'tools',   label: 'Tool usage'   },
  { id: 'diagnostics', label: 'Diagnostics' },
]

export default function App() {
  const tab = useUiStore(s => s.tab)
  const setTab = useUiStore(s => s.setTab)
  const setSelectedMode = useGuruStore(s => s.setSelectedMode)
  const addMessage = useChatStore(s => s.addMessage)

  // Connect WebSocket — populates all stores
  useWebSocket()

  // Global sendPrompt so sub-components can inject chat messages
  window.sendPrompt = (text) => {
    setTab('chat')
    addMessage({ role: 'user', text })
  }

  window.openGuruMode = (mode) => {
    setSelectedMode(mode)
    setTab('guru')
  }

  function handleSidebarSelect(ev) {
    const text = ev.type === 'approval'
      ? `Tell me about ${ev.id}: ${ev.action} — ${ev.detail}`
      : `What happened in ${ev.id}?`
    setTab('chat')
    addMessage({ role: 'user', text })
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
            { label: 'MACHINE=main',  on: false },
            { label: 'worker: online', on: true },
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
