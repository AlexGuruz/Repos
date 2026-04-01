import { render, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { useWebSocket } from './useWebSocket'
import { useEventStore, useFeedStore, useHardwareStore, useRepoStore } from '../store'

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
    MockWebSocket.instances.push(this)
  }

  close() {
    this.onclose?.()
  }
}


test('hydrates approvals and repo summaries on connect', async () => {
  api.approvals.mockResolvedValueOnce([{ id: 'APR-1', type: 'approval', status: 'pending' }])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [{ name: 'ai-lab', path: '/tmp', entrypoints: ['main.py'] }] })
  window.WebSocket = MockWebSocket

  render(<Harness />)

  await waitFor(() => expect(useEventStore.getState().events[0].id).toBe('APR-1'))
  expect(useRepoStore.getState().summaries[0].name).toBe('ai-lab')
})


test('routes websocket messages into the zustand stores', async () => {
  api.approvals.mockResolvedValueOnce([])
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })
  window.WebSocket = MockWebSocket

  render(<Harness />)
  const socket = MockWebSocket.instances.at(-1)

  socket.onmessage({
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
  socket.onmessage({
    data: JSON.stringify({
      event: 'feed',
      data: { agent: 'orchestrator', op: 'exec', detail: 'ran tool', timestamp: '2026-03-16T00:00:00Z' },
    }),
  })
  socket.onmessage({
    data: JSON.stringify({
      event: 'repo',
      data: { path: 'ai-lab/file.py', op: 'write', agent: 'fs-watcher', timestamp: '2026-03-16T00:00:00Z' },
    }),
  })

  await waitFor(() => expect(useHardwareStore.getState().cpu_percent).toBe(11.1))
  expect(useFeedStore.getState().lines[0].path).toBe('ai-lab/file.py')
  expect(useRepoStore.getState().fileActivity['ai-lab/file.py'].writes).toBe(1)
})
