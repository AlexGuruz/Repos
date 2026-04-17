import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import ChatPanel from './ChatPanel'
import { useEventStore, useGuruStore, useUiStore } from '../store'

const { api } = vi.hoisted(() => ({
  api: {
    chat: vi.fn(),
    chatStream: vi.fn(async (_msg, _hist, opts) => {
      opts?.onDone?.({ text: 'AI reply', response_time_ms: 10 })
    }),
    guruRevert: vi.fn(),
    repoSummaries: vi.fn(),
    resolveApproval: vi.fn(),
    addPermanentApproval: vi.fn(),
  },
}))

vi.mock('../lib/api', () => ({ api }))


test('sends chat messages through the API and renders the reply', async () => {
  api.chat.mockResolvedValueOnce({ text: 'AI reply' })
  api.repoSummaries.mockResolvedValueOnce({ summaries: [] })

  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.type(screen.getByPlaceholderText(/Route a task/i), 'hello there{Enter}')

  await waitFor(() => expect(api.chatStream).toHaveBeenCalled())
  expect(screen.getByText('hello there')).toBeInTheDocument()
  expect(await screen.findByText('AI reply')).toBeInTheDocument()
})


test('enter rr command opens the Guru tab without calling chat API', async () => {
  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.type(screen.getByPlaceholderText(/Route a task/i), 'enter rr{Enter}')

  expect(api.chatStream).not.toHaveBeenCalled()
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


test('approval card can add a permanent rule for scoped supervisor approvals', async () => {
  api.addPermanentApproval.mockResolvedValueOnce({ ok: true, rule: { id: 'PAR-TEST01' } })
  useEventStore.setState({
    events: [
      {
        id: 'APR-2',
        type: 'approval',
        status: 'pending',
        action: 'run_approved',
        agent: 'command-center',
        detail: 'run script',
        payload: { script_path: 'registry/foo.py' },
      },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  const user = userEvent.setup()

  await user.click(screen.getByRole('button', { name: 'Always allow (similar)' }))

  await waitFor(() =>
    expect(api.addPermanentApproval).toHaveBeenCalledWith({
      action: 'run_approved',
      match: { script_path: 'registry/foo.py' },
      source_approval_id: 'APR-2',
      note: 'from APR-2',
    }),
  )
})
