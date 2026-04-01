import { useState, useRef, useEffect } from 'react'
import { useChatStore, useEventStore, useGuruStore, useRepoStore, useUiStore } from '../store'
import { StatusBadge } from './Primitives'
import { api } from '../lib/api'

function ApprovalCard({ ev }) {
  const resolve = useEventStore(s => s.resolveApproval)
  const addMsg  = useChatStore(s => s.addMessage)
  const isPending = ev.status === 'pending'

  async function handleResolve(resolution) {
    try {
      await api.resolveApproval(ev.id, resolution)
      resolve(ev.id, resolution)
      addMsg({ role: 'ai', text: `${ev.id} ${resolution}. ${resolution === 'approved' ? 'Queued via run_approved wrapper.' : 'No state changed.'}` })
    } catch (e) {
      addMsg({ role: 'ai', text: `Error resolving ${ev.id}: ${e.message}` })
    }
  }

  return (
    <div className="rounded-lg border mx-1 p-3" style={{ borderColor: 'rgba(245,158,11,0.35)', background: 'rgba(245,158,11,0.04)' }}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(245,158,11,0.15)' }}>
          <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="#fcd34d" strokeWidth="1.5">
            <path d="M8 2v6M8 12v.5" strokeLinecap="round"/><circle cx="8" cy="8" r="6.5"/>
          </svg>
        </div>
        <span className="text-[12px] font-medium text-white/80">Approval request</span>
        <span className="text-[10px] font-mono text-white/30 ml-auto">{ev.id}</span>
      </div>
      <div className="text-[11px] text-white/55 leading-relaxed mb-2.5">
        <span className="font-medium text-white/70">{ev.action}</span>
        {' '}via <code className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.1)', color: '#fcd34d' }}>{ev.agent}</code>
        <br />{ev.detail}
      </div>
      {isPending ? (
        <div className="flex gap-2">
          <button onClick={() => handleResolve('approved')}
            className="px-3 py-1 text-[11px] rounded transition-colors"
            style={{ background: 'rgba(34,197,94,0.1)', border: '0.5px solid rgba(34,197,94,0.3)', color: '#86efac' }}>
            Approve
          </button>
          <button onClick={() => handleResolve('denied')}
            className="px-3 py-1 text-[11px] rounded transition-colors"
            style={{ background: 'rgba(239,68,68,0.08)', border: '0.5px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}>
            Deny
          </button>
        </div>
      ) : (
        <StatusBadge status={ev.status} />
      )}
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  const escaped = String(msg.text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  if (msg.role === 'sys') {
    return (
      <div className="flex items-center gap-2 py-1">
        <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
        <span className="text-[10px] font-mono text-white/25 px-2 py-0.5 rounded-full border"
          style={{ borderColor: 'rgba(255,255,255,0.08)' }}>{msg.text}</span>
        <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
      </div>
    )
  }
  const responseTime = msg.response_time_ms != null ? (
    <div className="text-[10px] font-mono text-white/25 mt-1.5" title={`${msg.response_time_ms} ms`}>
      {msg.response_time_ms >= 1000
        ? `${(msg.response_time_ms / 1000).toFixed(2)}s`
        : `${msg.response_time_ms} ms`}
    </div>
  ) : null
  return (
    <div className={`flex gap-2 items-start ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-medium flex-shrink-0 ${
        isUser ? 'bg-indigo-900/60 text-indigo-300' : 'bg-white/8 text-white/40 border border-white/10'}`}>
        {isUser ? 'SG' : 'AI'}
      </div>
      <div className={`max-w-[75%] ${isUser ? '' : 'flex flex-col items-start'}`}>
        <div className={`px-3 py-2 text-[12px] leading-relaxed rounded-xl border ${
          isUser
            ? 'bg-white/6 border-white/8 rounded-tr-sm text-white/80'
            : 'bg-white/4 border-white/6 rounded-tl-sm text-white/70'}`}
          dangerouslySetInnerHTML={{ __html: escaped
            .replace(/\n/g, '<br/>')
            .replace(/`([^`]+)`/g, '<code style="font-family:monospace;font-size:10px;background:rgba(255,255,255,0.08);padding:1px 4px;border-radius:3px;color:rgba(255,255,255,0.6)">$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong style="font-weight:500;color:rgba(255,255,255,0.85)">$1</strong>')
          }}
        />
        {!isUser && responseTime}
      </div>
    </div>
  )
}

export default function ChatPanel() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const { messages, addMessage } = useChatStore()
  const { events } = useEventStore()
  const setTab = useUiStore(s => s.setTab)
  const setSelectedMode = useGuruStore(s => s.setSelectedMode)
  const updateMode = useGuruStore(s => s.updateMode)
  const setSummaries = useRepoStore(s => s.setSummaries)
  const bottomRef = useRef(null)
  /** Ignore stale chat responses if a newer send started (tabs stay mounted; user can send again quickly). */
  const chatRequestGenRef = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    const enterMode = text.match(/^enter\s+(rr|pr|al|tl|atl)$/i)
    if (enterMode) {
      const mode = enterMode[1].toUpperCase()
      setSelectedMode(mode)
      setTab('guru')
      addMessage({ role: 'sys', text: `Guru · ${mode} opened — use Guru tab to configure` })
      return
    }

    const exitMode = text.match(/^exit\s+(rr|pr|al|tl|atl)$/i)
    if (exitMode) {
      setTab('chat')
      addMessage({ role: 'sys', text: `Guru · ${exitMode[1].toUpperCase()} closed` })
      return
    }

    const showRules = text.match(/^show\s+(rr|pr|al|tl|atl)\s+rules$/i)
    if (showRules) {
      const mode = showRules[1].toUpperCase()
      setSelectedMode(mode)
      setTab('guru')
      addMessage({ role: 'sys', text: `Showing ${mode} rules in Guru tab` })
      return
    }

    const revertMode = text.match(/^revert\s+last\s+(rr|pr|al|tl|atl)\s+change$/i)
    if (revertMode) {
      const mode = revertMode[1].toUpperCase()
      setTab('chat')
      addMessage({ role: 'user', text: `Revert last ${mode} change` })
      const gen = ++chatRequestGenRef.current
      setLoading(true)
      try {
        const result = await api.guruRevert(mode)
        if (gen !== chatRequestGenRef.current) return
        updateMode(mode, result)
        addMessage({ role: 'ai', text: result.summary || `Reverted last ${mode} change.` })
      } catch (e) {
        if (gen !== chatRequestGenRef.current) return
        addMessage({ role: 'ai', text: `Revert failed: ${e.message}` })
      } finally {
        if (gen === chatRequestGenRef.current) setLoading(false)
      }
      return
    }

    addMessage({ role: 'user', text })
    const gen = ++chatRequestGenRef.current
    setLoading(true)
    try {
      const res = await api.chat(text, messages.slice(-10).map(m => ({ role: m.role === 'ai' ? 'assistant' : m.role, content: m.text })))
      if (gen !== chatRequestGenRef.current) return
      addMessage({ role: 'ai', text: res.text, response_time_ms: res.response_time_ms })
      const lower = text.toLowerCase()
      if ((lower.includes('scan') && lower.includes('repo')) || (lower.includes('summarize') && lower.includes('repo'))) {
        api.repoSummaries().then(r => setSummaries(r.summaries || [])).catch(() => {})
      }
    } catch (e) {
      if (gen !== chatRequestGenRef.current) return
      addMessage({ role: 'ai', text: `Error: ${e.message}` })
    } finally {
      if (gen === chatRequestGenRef.current) setLoading(false)
    }
  }

  // Inject approval cards for pending approvals
  const pendingApprovals = events.filter(e => e.type === 'approval')

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}
        {pendingApprovals.slice(0, 2).map(ev => (
          ev.status === 'pending' && <ApprovalCard key={ev.id} ev={ev} />
        ))}
        {loading && (
          <div className="flex gap-2 items-start">
            <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono bg-white/8 text-white/40 border border-white/10 flex-shrink-0">AI</div>
            <div className="px-3 py-2 text-[12px] rounded-xl border border-white/6 bg-white/4 text-white/40">
              thinking<span className="cursor-blink" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-white/8 px-3 py-2.5 flex items-center gap-2 flex-shrink-0">
        <div className="flex-1 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3">
          <input
            className="flex-1 bg-transparent border-none outline-none text-[12px] text-white/80 placeholder-white/25 py-2.5"
            placeholder="Route a task, query status, or trigger an agent…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
          />
        </div>
        <button onClick={send} disabled={loading}
          className="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 transition-colors disabled:opacity-30">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M2 8h12M9 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
