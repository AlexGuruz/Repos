import { useEffect, useRef } from 'react'
import { api } from '../lib/api'
import { logDiagnostic } from '../lib/diagnostics'
import { useChatStore, useEventStore, useFeedStore, useHardwareStore, useRepoStore, useUiStore } from '../store'

const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/events').replace(/\/ws\/events\/?$/, '')
const CONTROL_URL = `${WS_BASE}/ws/control`
const OPS_URL = `${WS_BASE}/ws/ops`
const CHAT_URL = `${WS_BASE}/ws/chat`
const TELEMETRY_URL = `${WS_BASE}/ws/telemetry`
const LEGACY_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/events'

function jitter(ms) {
  return ms + Math.floor(Math.random() * Math.min(500, ms * 0.25))
}

function handleMessage(msg, handlers) {
  const { event, data } = msg
  if (!event) return
  logDiagnostic('ws:message', { event, channel: msg.channel })
  const {
    addEvent, addLine, updateHW, touchRepo, addChatMessage,
  } = handlers

  switch (event) {
    case 'action':
      addEvent({ ...data, type: 'action' })
      addLine({ ...data, op: data.op || 'exec' })
      break
    case 'approval':
      addEvent({ ...data, type: 'approval' })
      addLine({ agent: data.agent, op: 'exec', detail: `APR: ${data.action} — ${data.detail}` })
      break
    case 'approval_resolution':
      useEventStore.getState().resolveApproval(data.id, data.resolution)
      addLine({ agent: 'supervisor', op: 'sys', detail: `${data.id} → ${data.resolution}` })
      break
    case 'permanent_rule':
    case 'permanent_rule_deleted':
      addLine({ agent: 'supervisor', op: 'sys', detail: `${event}` })
      break
    case 'hardware':
      updateHW(data)
      break
    case 'feed':
      addLine(data)
      break
    case 'repo':
      touchRepo(data.path, data.op, data.agent)
      addLine({ ...data })
      break
    case 'chat':
      if (data.role && data.text) {
        addChatMessage({
          role: data.role,
          text: data.text,
          response_time_ms: data.response_time_ms,
        })
      }
      addLine({
        agent: data.role === 'user' ? 'user' : 'orchestrator',
        op: 'sys',
        detail: (data.text || '').slice(0, 80),
        timestamp: data.timestamp,
      })
      break
    case 'hardware_alert':
      addLine({
        agent: 'system',
        op: 'exec',
        detail: `Hardware alert: ${(data.alerts || []).join(', ') || 'threshold exceeded'}`,
        timestamp: data.timestamp,
      })
      break
    default:
      break
  }
}

/** Close a channel socket without scheduling reconnect (leave-Compute / unmount / fallback). */
function closeIntentionally(label, { socketsRef, reconnectRef, intentionalCloseRef }) {
  intentionalCloseRef.current[label] = true
  clearTimeout(reconnectRef.current[label])
  reconnectRef.current[label] = null
  try { socketsRef.current[label]?.close() } catch { /* ignore */ }
  if (socketsRef.current[label]) {
    socketsRef.current[label] = null
  }
}

function openSocket(url, {
  onMessage, onOpen, label, socketsRef, reconnectRef, backoffRef, fallbackUsedRef, onChannelFail,
  intentionalCloseRef,
}) {
  intentionalCloseRef.current[label] = false
  const ws = new WebSocket(url)
  socketsRef.current[label] = ws

  ws.onopen = () => {
    console.log(`[WS:${label}] connected`)
    logDiagnostic('ws:open', { url, label })
    backoffRef.current[label] = 1000
    onOpen?.()
  }

  ws.onmessage = (e) => {
    let msg
    try { msg = JSON.parse(e.data) } catch { return }
    onMessage(msg)
  }

  ws.onclose = () => {
    console.log(`[WS:${label}] disconnected`)
    logDiagnostic('ws:close', { url, label, intentional: !!intentionalCloseRef.current[label] })
    if (socketsRef.current[label] === ws) {
      socketsRef.current[label] = null
    }
    // Leave-Compute / unmount / legacy fallback: do not reconnect forever.
    if (intentionalCloseRef.current[label]) {
      return
    }
    const delay = jitter(backoffRef.current[label] || 1000)
    backoffRef.current[label] = Math.min((backoffRef.current[label] || 1000) * 2, 15000)
    clearTimeout(reconnectRef.current[label])
    reconnectRef.current[label] = setTimeout(() => {
      if (intentionalCloseRef.current[label]) return
      if (label !== 'legacy' && onChannelFail && !fallbackUsedRef.current) {
        // After repeated failures, allow one-shot legacy multiplex (no telemetry).
        const fails = (backoffRef.current[`${label}_fails`] || 0) + 1
        backoffRef.current[`${label}_fails`] = fails
        if (fails >= 3) {
          onChannelFail()
          return
        }
      }
      openSocket(url, {
        onMessage, onOpen, label, socketsRef, reconnectRef, backoffRef, fallbackUsedRef, onChannelFail,
        intentionalCloseRef,
      })
    }, delay)
  }

  ws.onerror = () => {
    logDiagnostic('ws:error', { url, label })
    try { ws.close() } catch { /* ignore */ }
  }

  return ws
}

/**
 * Multi-channel WebSocket transport.
 * Always: control + ops (+ optional chat non-token).
 * Telemetry: only while Compute tab is active.
 * Prefer explicit /ws/control|/ws/ops|/ws/chat|/ws/telemetry.
 * Compat: once fall back to deprecated /ws/events (no telemetry) if channel sockets fail repeatedly.
 */
export function useWebSocket() {
  const socketsRef = useRef({})
  const reconnectRef = useRef({})
  const backoffRef = useRef({})
  const fallbackUsedRef = useRef(false)
  const intentionalCloseRef = useRef({})
  const handlersRef = useRef({})

  const addEvent = useEventStore(s => s.addEvent)
  const addLine = useFeedStore(s => s.addLine)
  const updateHW = useHardwareStore(s => s.update)
  const touchRepo = useRepoStore(s => s.touch)
  const setSummaries = useRepoStore(s => s.setSummaries)
  const addChatMessage = useChatStore(s => s.addMessage)
  const tab = useUiStore(s => s.tab)

  handlersRef.current = { addEvent, addLine, updateHW, touchRepo, addChatMessage }

  const onMessage = (msg) => handleMessage(msg, handlersRef.current)

  useEffect(() => {
    api.approvals()
      .then(approvals => {
        ;[...(approvals || [])].reverse().forEach(ev => addEvent(ev))
      })
      .catch(() => {})
    api.repoSummaries()
      .then(res => setSummaries(res.summaries || []))
      .catch(() => {})

    const startChannelSockets = () => {
      const common = {
        onMessage,
        socketsRef,
        reconnectRef,
        backoffRef,
        fallbackUsedRef,
        intentionalCloseRef,
        onChannelFail: () => {
          if (fallbackUsedRef.current) return
          fallbackUsedRef.current = true
          logDiagnostic('ws:fallback_legacy', { url: LEGACY_URL })
          // Close channel sockets intentionally; use legacy multiplex once.
          ;['control', 'ops', 'chat', 'telemetry'].forEach((label) => {
            closeIntentionally(label, { socketsRef, reconnectRef, intentionalCloseRef })
          })
          openSocket(LEGACY_URL, {
            onMessage,
            label: 'legacy',
            socketsRef,
            reconnectRef,
            backoffRef,
            fallbackUsedRef,
            intentionalCloseRef,
          })
        },
      }
      openSocket(CONTROL_URL, { ...common, label: 'control' })
      openSocket(OPS_URL, { ...common, label: 'ops' })
      openSocket(CHAT_URL, { ...common, label: 'chat' })
    }

    startChannelSockets()

    return () => {
      ;['control', 'ops', 'chat', 'telemetry', 'legacy'].forEach((label) => {
        closeIntentionally(label, { socketsRef, reconnectRef, intentionalCloseRef })
      })
      socketsRef.current = {}
    }
  }, [])

  // Telemetry lifecycle: only while Compute tab is mounted/selected.
  useEffect(() => {
    if (fallbackUsedRef.current) return undefined
    if (tab !== 'compute') {
      closeIntentionally('telemetry', { socketsRef, reconnectRef, intentionalCloseRef })
      return undefined
    }
    openSocket(TELEMETRY_URL, {
      onMessage,
      label: 'telemetry',
      socketsRef,
      reconnectRef,
      backoffRef,
      fallbackUsedRef,
      intentionalCloseRef,
    })
    return () => {
      closeIntentionally('telemetry', { socketsRef, reconnectRef, intentionalCloseRef })
    }
  }, [tab])
}
