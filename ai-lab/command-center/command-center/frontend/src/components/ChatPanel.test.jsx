import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import ChatPanel from './ChatPanel'
import { useEventStore, useGuruStore, useUiStore } from '../store'

const { api } = vi.hoisted(() => ({
  api: {
    chat: vi.fn(),
    guruRevert: vi.fn(),
    repoSummaries: vi.fn(),
    resolveApproval: vi.fn(),
  },
}))

vi.mock('../lib/api', () => ({ api }))


test('sends chat messages through the API and renders the reply', async () => {
  api.chat.mockResolvedValueOnce({ text: 'AI reply' })
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })

  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.type(screen.getByPlaceholderText(/Route a task/i), 'hello there{Enter}')

  await waitFor(() => expect(api.chat).toHaveBeenCalled())
  expect(screen.getByText('hello there')).toBeInTheDocument()
  expect(await screen.findByText('AI reply')).toBeInTheDocument()
})


test('enter rr command opens the Guru tab without calling chat API', async () => {
  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.type(screen.getByPlaceholderText(/Route a task/i), 'enter rr{Enter}')

  expect(api.chat).not.toHaveBeenCalled()
  expect(useUiStore.getState().tab).toBe('guru')
  expect(useGuruStore.getState().selectedMode).toBe('RR')
})


test('approval card resolves pending approvals', async () => {
  api.resolveApproval.mockResolvedValueOnce({ ok: true })
  useEventStore.setState({
    events: [
      { id: 'APR-1', type: 'approval', status: 'pending', action: 'restart_service', agent: 'orchestrator', detail: 'restart backend' },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.click(screen.getByRole('button', { name: 'Approve' }))

  await waitFor(() => expect(api.resolveApproval).toHaveBeenCalledWith('APR-1', 'approved'))
  expect(useEventStore.getState().events[0].status).toBe('approved')
})
