import { render, waitFor, act } from '@testing-library/react'
import { vi } from 'vitest'

import { useWebSocket } from './useWebSocket'
import { useEventStore, useFeedStore, useHardwareStore, useRepoStore, useUiStore } from '../store'

const { api } = vi.hoisted(() => ({
  api: {
    approvals: vi.fn(),
    repoSummaries: vi.fn(),
  },
}))

vi.mock('../lib/api', () => ({ api }))

function Harness() {
  useWebSocket()
  return null
}

class MockWebSocket {
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = 1
    MockWebSocket.instances.push(this)
  }

  close() {
    this.onclose?.()
  }
}


beforeEach(() => {
  MockWebSocket.instances = []
  useUiStore.setState({ tab: 'chat' })
  vi.useRealTimers()
})


test('hydrates approvals and repo summaries on connect', async () => {
  api.approvals.mockResolvedValueOnce([{ id: 'APR-1', type: 'approval', status: 'pending' }])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [{ name: 'ai-lab', path: '/tmp', entrypoints: ['main.py'] }] })
  window.WebSocket = MockWebSocket

  render(<Harness />)

  await waitFor(() => expect(useEventStore.getState().events[0].id).toBe('APR-1'))
  expect(useRepoStore.getState().summaries[0].name).toBe('ai-lab')
  const urls = MockWebSocket.instances.map(s => s.url)
  expect(urls.some(u => u.includes('/ws/control'))).toBe(true)
  expect(urls.some(u => u.includes('/ws/ops'))).toBe(true)
  expect(urls.some(u => u.includes('/ws/telemetry'))).toBe(false)
})


test('opens telemetry only when Compute tab is active', async () => {
  api.approvals.mockResolvedValueOnce([])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })
  window.WebSocket = MockWebSocket

  render(<Harness />)
  await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2))
  expect(MockWebSocket.instances.every(s => !s.url.includes('/ws/telemetry'))).toBe(true)

  await act(async () => {
    useUiStore.setState({ tab: 'compute' })
  })
  await waitFor(() => expect(MockWebSocket.instances.some(s => s.url.includes('/ws/telemetry'))).toBe(true))

  const tel = MockWebSocket.instances.find(s => s.url.includes('/ws/telemetry'))
  tel.onmessage({
    data: JSON.stringify({
      event: 'hardware',
      data: {
        gpu: { vram_used_gb: 5.2 },
        cpu_percent: 11.1,
        ram_used_gb: 9.4,
        ram_total_gb: 32.0,
        timestamp: '2026-03-16T00:00:00Z',
      },
    }),
  })
  await waitFor(() => expect(useHardwareStore.getState().cpu_percent).toBe(11.1))
})


test('leaving Compute intentionally closes telemetry and does not reconnect', async () => {
  vi.useFakeTimers()
  api.approvals.mockResolvedValueOnce([])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })
  window.WebSocket = MockWebSocket

  render(<Harness />)
  await act(async () => {
    await Promise.resolve()
  })

  await act(async () => {
    useUiStore.setState({ tab: 'compute' })
  })
  const telCountAfterOpen = MockWebSocket.instances.filter(s => s.url.includes('/ws/telemetry')).length
  expect(telCountAfterOpen).toBeGreaterThanOrEqual(1)

  await act(async () => {
    useUiStore.setState({ tab: 'chat' })
  })
  // Advance past reconnect backoff windows; intentional close must not open new telemetry sockets.
  await act(async () => {
    vi.advanceTimersByTime(30000)
  })
  const telCountAfterLeave = MockWebSocket.instances.filter(s => s.url.includes('/ws/telemetry')).length
  expect(telCountAfterLeave).toBe(telCountAfterOpen)

  vi.useRealTimers()
})


test('routes ops websocket messages into the zustand stores', async () => {
  api.approvals.mockResolvedValueOnce([])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })
  window.WebSocket = MockWebSocket

  render(<Harness />)
  await waitFor(() => expect(MockWebSocket.instances.some(s => s.url.includes('/ws/ops'))).toBe(true))
  const ops = MockWebSocket.instances.find(s => s.url.includes('/ws/ops'))

  ops.onmessage({
    data: JSON.stringify({
      event: 'feed',
      data: { agent: 'orchestrator', op: 'exec', detail: 'ran tool', timestamp: '2026-03-16T00:00:00Z' },
    }),
  })
  ops.onmessage({
    data: JSON.stringify({
      event: 'repo',
      data: { path: 'ai-lab/file.py', op: 'write', agent: 'fs-watcher', timestamp: '2026-03-16T00:00:00Z' },
    }),
  })

  await waitFor(() => expect(useFeedStore.getState().lines[0].path).toBe('ai-lab/file.py'))
  expect(useRepoStore.getState().fileActivity['ai-lab/file.py'].writes).toBe(1)
})
