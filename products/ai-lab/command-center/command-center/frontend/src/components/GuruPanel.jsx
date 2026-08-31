import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { LiveDot, SectionLabel, StatusBadge } from './Primitives'
import { useChatStore, useFeedStore, useGuruStore, useUiStore } from '../store'

const MODE_ORDER = ['RR', 'PR', 'AL', 'TL', 'ATL']

function formatJson(value) {
  return JSON.stringify(value ?? {}, null, 2)
}

function ThreadMessage({ msg }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'sys'

  if (isSystem) {
    return (
      <div className="text-[10px] font-mono text-white/30 border border-white/8 rounded-lg px-2 py-1 bg-white/4">
        {msg.text}
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[92%] rounded-xl border px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap ${
        isUser
          ? 'bg-white/6 border-white/10 text-white/80'
          : 'bg-white/4 border-white/8 text-white/70'
      }`}>
        {msg.text}
      </div>
    </div>
  )
}

export default function GuruPanel() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState('')

  const tab = useUiStore(s => s.tab)
  const setTab = useUiStore(s => s.setTab)
  const selectedMode = useGuruStore(s => s.selectedMode)
  const setSelectedMode = useGuruStore(s => s.setSelectedMode)
  const modes = useGuruStore(s => s.modes)
  const hydrateSnapshot = useGuruStore(s => s.hydrateSnapshot)
  const updateMode = useGuruStore(s => s.updateMode)
  const addChatMessage = useChatStore(s => s.addMessage)
  const addFeedLine = useFeedStore(s => s.addLine)

  const mode = modes[selectedMode]

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const snapshot = await api.guruSnapshot()
        if (!cancelled) {
          hydrateSnapshot(snapshot)
        }
      } catch (e) {
        if (!cancelled) {
          addChatMessage({ role: 'sys', text: `Guru snapshot unavailable: ${e.message}` })
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [hydrateSnapshot, addChatMessage])

  useEffect(() => {
    if (tab === 'guru' && selectedMode) {
      api.guruMode(selectedMode)
        .then(data => updateMode(selectedMode, data))
        .catch(() => {})
    }
  }, [tab, selectedMode, updateMode])

  const requiresConfirmation = mode?.savePolicy === 'confirm'
  const currentDraft = mode?.currentDraft

  const modeStatus = useMemo(() => {
    if (!mode) return 'idle'
    if (mode.currentDraft) return 'pending'
    if (mode.lastSavedSummary) return 'done'
    return 'running'
  }, [mode])

  async function sendModeMessage() {
    const text = input.trim()
    if (!text || !mode || loading) return

    setInput('')
    setLoading(true)
    try {
      const result = await api.guruMessage(selectedMode, text)
      updateMode(selectedMode, result)
      if (result.summary) {
        addChatMessage({ role: 'sys', text: `Guru ${selectedMode}: ${result.summary}` })
        addFeedLine({ agent: 'guru', op: result.saved ? 'write' : 'sys', detail: `${selectedMode} · ${result.summary}` })
      }
    } catch (e) {
      addChatMessage({ role: 'sys', text: `Guru ${selectedMode} error: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  async function confirmDraft() {
    if (!mode || !currentDraft) return
    setActionLoading('confirm')
    try {
      const result = await api.guruConfirm(selectedMode)
      updateMode(selectedMode, result)
      if (result.summary) {
        addChatMessage({ role: 'sys', text: `Guru ${selectedMode}: ${result.summary}` })
        addFeedLine({ agent: 'guru', op: 'write', detail: `${selectedMode} · ${result.summary}` })
      }
    } catch (e) {
      addChatMessage({ role: 'sys', text: `Guru ${selectedMode} confirm error: ${e.message}` })
    } finally {
      setActionLoading('')
    }
  }

  async function revertMode() {
    if (!mode) return
    setActionLoading('revert')
    try {
      const result = await api.guruRevert(selectedMode)
      updateMode(selectedMode, result)
      if (result.summary) {
        addChatMessage({ role: 'sys', text: `Guru ${selectedMode}: ${result.summary}` })
        addFeedLine({ agent: 'guru', op: 'write', detail: `${selectedMode} · ${result.summary}` })
      }
    } catch (e) {
      addChatMessage({ role: 'sys', text: `Guru ${selectedMode} revert error: ${e.message}` })
    } finally {
      setActionLoading('')
    }
  }

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <div className="w-[260px] min-w-[260px] border-r border-white/8 bg-white/[0.03] flex flex-col">
        <div className="h-12 px-3 border-b border-white/8 flex items-center gap-2">
          <LiveDot color="#60a5fa" />
          <span className="text-[11px] font-medium tracking-widest uppercase text-white/40">Guru</span>
        </div>
        <div className="p-2 flex flex-col gap-1">
          {MODE_ORDER.map(modeId => {
            const modeState = modes[modeId]
            const active = selectedMode === modeId
            return (
              <button
                key={modeId}
                onClick={() => setSelectedMode(modeId)}
                className={`text-left rounded-lg border px-3 py-2 transition-colors ${
                  active ? 'bg-white/8 border-white/20' : 'bg-white/[0.02] border-white/8 hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-white/80">{modeId}</span>
                  <span className="text-[10px] text-white/35">{modeState?.label}</span>
                </div>
                <div className="mt-1 text-[10px] font-mono text-white/25">
                  {modeState?.savePolicy === 'direct' ? 'save direct' : 'preview/confirm'}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-h-0 flex flex-col">
          <div className="h-12 border-b border-white/8 px-4 flex items-center gap-3">
            <span className="text-[13px] text-white/80 font-medium">{mode?.label ?? selectedMode}</span>
            <StatusBadge status={modeStatus} />
            <span className="text-[10px] font-mono text-white/25">
              {requiresConfirmation ? 'preview/confirm' : 'save direct'}
            </span>
            <button
              onClick={() => setTab('chat')}
              className="ml-auto text-[10px] font-mono px-2 py-1 rounded border border-white/10 text-white/35 hover:text-white/70 hover:bg-white/6"
            >
              Exit {selectedMode}
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-3">
            <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
              <div className="text-[10px] font-mono text-white/25 uppercase tracking-wider mb-1">Purpose</div>
              <div className="text-[12px] text-white/60">{mode?.description || 'Loading Guru mode...'}</div>
            </div>

            {mode?.messages?.map(msg => <ThreadMessage key={msg.id} msg={msg} />)}

            {currentDraft && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/[0.05] p-3">
                <SectionLabel>Pending draft</SectionLabel>
                <pre className="text-[11px] text-white/60 whitespace-pre-wrap overflow-x-auto">{formatJson(currentDraft.draft)}</pre>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={confirmDraft}
                    disabled={actionLoading === 'confirm'}
                    className="px-3 py-1.5 rounded border text-[11px] border-emerald-500/30 text-emerald-300 bg-emerald-500/10 disabled:opacity-40"
                  >
                    Confirm draft
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-white/8 px-3 py-2.5 flex items-center gap-2">
            <div className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendModeMessage()}
                placeholder={`Refine ${selectedMode} behavior…`}
                className="w-full bg-transparent outline-none border-none py-2.5 text-[12px] text-white/80 placeholder-white/25"
              />
            </div>
            <button
              onClick={sendModeMessage}
              disabled={loading}
              className="w-9 h-9 rounded-lg border border-white/10 bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 disabled:opacity-30"
            >
              ↗
            </button>
            <button
              onClick={revertMode}
              disabled={actionLoading === 'revert'}
              className="px-2.5 py-2 rounded-lg border border-white/10 bg-white/5 text-[10px] font-mono text-white/35 hover:text-white/70 hover:bg-white/10 disabled:opacity-30"
            >
              revert
            </button>
          </div>
        </div>

        <div className="w-[360px] min-w-[360px] border-l border-white/8 bg-white/[0.02] p-4 overflow-y-auto">
          <SectionLabel>Current rules</SectionLabel>
          <pre className="text-[11px] text-white/55 whitespace-pre-wrap overflow-x-auto rounded-lg border border-white/8 bg-white/[0.03] p-3">
            {formatJson(mode?.currentRules)}
          </pre>

          <SectionLabel>Last saved</SectionLabel>
          <div className="rounded-lg border border-white/8 bg-white/[0.03] p-3 text-[11px] text-white/55">
            <div>{mode?.lastSavedSummary || 'No saved changes yet.'}</div>
            {mode?.lastUpdatedAt && (
              <div className="mt-2 text-white/25 font-mono">{new Date(mode.lastUpdatedAt).toLocaleString()}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
