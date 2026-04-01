import { useEffect, useRef } from 'react'
import { api } from '../lib/api'
import { logDiagnostic } from '../lib/diagnostics'
import { useChatStore, useEventStore, useFeedStore, useHardwareStore, useRepoStore } from '../store'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/events'

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const addEvent    = useEventStore(s => s.addEvent)
  const addLine     = useFeedStore(s => s.addLine)
  const updateHW    = useHardwareStore(s => s.update)
  const touchRepo   = useRepoStore(s => s.touch)
  const setSummaries = useRepoStore(s => s.setSummaries)
  const addChatMessage = useChatStore(s => s.addMessage)

  function connect() {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WS] connected')
      logDiagnostic('ws:open', { url: WS_URL })
      clearTimeout(reconnectRef.current)
    }

    ws.onmessage = (e) => {
      let msg
      try { msg = JSON.parse(e.data) } catch { return }
      const { event, data } = msg
      logDiagnostic('ws:message', { event })

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

    ws.onclose = () => {
      console.log('[WS] disconnected — retrying in 3s')
      logDiagnostic('ws:close', { url: WS_URL })
      reconnectRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      logDiagnostic('ws:error', { url: WS_URL })
      ws.close()
    }
  }

  useEffect(() => {
    api.approvals()
      .then(approvals => { (approvals || []).forEach(ev => addEvent(ev)) })
      .catch(() => {})
    api.repoSummaries()
      .then(res => setSummaries(res.summaries || []))
      .catch(() => {})
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [])
}
