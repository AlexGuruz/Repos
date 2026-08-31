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


test('APR stub card dismisses without Approve/Always', async () => {
  api.resolveApproval.mockResolvedValueOnce({ ok: true, dismissed_only: true })
  useEventStore.setState({
    events: [
      { id: 'APR-1', type: 'approval', status: 'pending', action: 'restart_service', agent: 'orchestrator', detail: 'restart backend' },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  const user = userEvent.setup()

  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Always Approve' })).not.toBeInTheDocument()
  expect(screen.getByText(/dismiss only/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Dismiss' }))

  await waitFor(() => expect(api.resolveApproval).toHaveBeenCalledWith('APR-1', 'denied'))
  expect(useEventStore.getState().events[0].status).toBe('denied')
})


test('brain approval card does not mark approved when API returns ok:false', async () => {
  api.resolveApproval.mockResolvedValueOnce({ ok: false, error: "Approval 'approval-x' not found in queue." })
  useEventStore.setState({
    events: [
      {
        id: 'approval-x',
        type: 'approval',
        status: 'pending',
        action: 'operator_desk_tool',
        agent: 'operator_desk',
        detail: 'missing',
        tool_name: 'growflow_status',
        payload: { tool_name: 'growflow_status' },
      },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Approve' }))

  await waitFor(() => expect(api.resolveApproval).toHaveBeenCalled())
  expect(useEventStore.getState().events[0].status).toBe('pending')
  expect(await screen.findByText(/not found in queue/i)).toBeInTheDocument()
})


test('Always Approve saves permanent rule then resolves approved', async () => {
  api.addPermanentApproval.mockResolvedValueOnce({ ok: true, rule: { id: 'PAR-TEST01' } })
  api.resolveApproval.mockResolvedValueOnce({ ok: true, executed: true })
  useEventStore.setState({
    events: [
      {
        id: 'approval-90',
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

  await user.click(screen.getByRole('button', { name: 'Always Approve' }))

  await waitFor(() =>
    expect(api.addPermanentApproval).toHaveBeenCalledWith({
      approval_id: 'approval-90',
      note: 'from approval-90',
    }),
  )
  await waitFor(() => expect(api.resolveApproval).toHaveBeenCalledWith('approval-90', 'approved'))
  expect(useEventStore.getState().events[0].status).toBe('approved')
})

test('brain execute cards rank above APR stubs and show tool badge', async () => {
  useEventStore.setState({
    events: [
      { id: 'APR-9', type: 'approval', status: 'pending', action: 'restart_service', agent: 'orchestrator', detail: 'stub' },
      {
        id: 'approval-91',
        type: 'approval',
        status: 'pending',
        action: 'operator_desk_tool',
        agent: 'operator_desk',
        detail: 'real',
        tool_name: 'growflow_status',
        payload: { tool_name: 'growflow_status' },
      },
    ],
    pendingCount: 2,
  })

  render(<ChatPanel />)
  expect(screen.getByText(/tool:growflow_status/i)).toBeInTheDocument()
  expect(screen.getByText(/Execute approval/i)).toBeInTheDocument()
  expect(screen.getByText(/dismiss only/i)).toBeInTheDocument()
})


test('Always Approve for brain queue uses approval_id', async () => {
  api.addPermanentApproval.mockResolvedValueOnce({ ok: true, rule: { id: 'PAR-BR01' } })
  api.resolveApproval.mockResolvedValueOnce({ ok: true, executed: true })
  useEventStore.setState({
    events: [
      {
        id: 'approval-42',
        type: 'approval',
        status: 'pending',
        action: 'operator_desk_tool',
        agent: 'operator_desk',
        detail: 'run tool',
        file_path: 'operator_desk',
        payload: { tool_name: 'growflow_status', action_type: 'operator_desk_tool' },
      },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Always Approve' }))

  await waitFor(() =>
    expect(api.addPermanentApproval).toHaveBeenCalledWith({
      approval_id: 'approval-42',
      note: 'from approval-42',
    }),
  )
  await waitFor(() => expect(api.resolveApproval).toHaveBeenCalledWith('approval-42', 'approved'))
})


test('shows pending cards even when newer approvals are already resolved', async () => {
  useEventStore.setState({
    events: [
      { id: 'approval-new', type: 'approval', status: 'approved', action: 'operator_desk_tool', agent: 'operator_desk', detail: 'done' },
      { id: 'approval-new2', type: 'approval', status: 'denied', action: 'operator_desk_tool', agent: 'operator_desk', detail: 'no' },
      { id: 'approval-old', type: 'approval', status: 'pending', action: 'operator_desk_tool', agent: 'operator_desk', detail: 'still waiting' },
    ],
    pendingCount: 1,
  })

  render(<ChatPanel />)
  expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
  expect(screen.getByText(/still waiting/i)).toBeInTheDocument()
})
