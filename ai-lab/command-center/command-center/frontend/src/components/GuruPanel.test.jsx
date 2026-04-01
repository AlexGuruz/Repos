import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import GuruPanel from './GuruPanel'
import { useGuruStore } from '../store'

const { api } = vi.hoisted(() => ({
  api: {
    guruSnapshot: vi.fn(),
    guruMode: vi.fn(),
    guruMessage: vi.fn(),
    guruConfirm: vi.fn(),
    guruRevert: vi.fn(),
  },
}))

vi.mock('../lib/api', () => ({ api }))


test('loads Guru snapshot and current mode', async () => {
  api.guruSnapshot.mockResolvedValueOnce({
    modes: {
      RR: {
        mode: 'RR',
        label: 'Response Refinement',
        description: 'Shapes future response style.',
        save_policy: 'direct',
        messages: [],
        current_rules: { include_source_references: true },
      },
    },
  })
  api.guruMode.mockResolvedValueOnce({
    mode: 'RR',
    label: 'Response Refinement',
    description: 'Shapes future response style.',
    save_policy: 'direct',
    messages: [],
    current_rules: { include_source_references: true },
  })

  render(<GuruPanel />)

  expect(await screen.findByText('Shapes future response style.')).toBeInTheDocument()
  expect(await screen.findByText(/include_source_references/i)).toBeInTheDocument()
})


test('sends Guru mode messages and updates current mode', async () => {
  api.guruSnapshot.mockResolvedValueOnce({
    modes: {
      RR: {
        mode: 'RR',
        label: 'Response Refinement',
        description: 'Shapes future response style.',
        save_policy: 'direct',
        messages: [],
        current_rules: {},
      },
    },
  })
  api.guruMode.mockResolvedValueOnce({
    mode: 'RR',
    label: 'Response Refinement',
    description: 'Shapes future response style.',
    save_policy: 'direct',
    messages: [],
    current_rules: {},
  })
  api.guruMessage.mockResolvedValueOnce({
    mode: 'RR',
    summary: 'RR updated to include source references',
    saved: true,
    messages: [{ id: 'MSG-1', role: 'assistant', text: 'RR updated to include source references' }],
    current_rules: { include_source_references: true },
  })

  render(<GuruPanel />)
  const user = userEvent.setup()

  await screen.findByText('Shapes future response style.')
  await user.type(screen.getByPlaceholderText(/Refine RR behavior/i), 'Include source references{Enter}')

  await waitFor(() => expect(api.guruMessage).toHaveBeenCalledWith('RR', 'Include source references'))
  expect(useGuruStore.getState().modes.RR.currentRules.include_source_references).toBe(true)
})


test('confirm button saves pending drafts', async () => {
  api.guruSnapshot.mockResolvedValueOnce({
    modes: {
      ATL: {
        mode: 'ATL',
        label: 'Auto Task List',
        description: 'Shapes what can auto-run.',
        save_policy: 'confirm',
        messages: [],
        current_draft: { draft: { summary: 'pending draft' } },
        current_rules: {},
      },
    },
  })
  api.guruMode.mockResolvedValueOnce({
    mode: 'ATL',
    label: 'Auto Task List',
    description: 'Shapes what can auto-run.',
    save_policy: 'confirm',
    messages: [],
    current_draft: { draft: { summary: 'pending draft' } },
    current_rules: {},
  })
  api.guruConfirm.mockResolvedValueOnce({
    mode: 'ATL',
    summary: 'Confirmed and saved.',
    saved: true,
    current_draft: null,
    current_rules: { repo_scan_to_summaries: true },
  })
  useGuruStore.setState(s => ({ ...s, selectedMode: 'ATL' }))

  render(<GuruPanel />)
  const user = userEvent.setup()

  await screen.findByText('Shapes what can auto-run.')
  await user.click(screen.getByRole('button', { name: /Confirm draft/i }))

  await waitFor(() => expect(api.guruConfirm).toHaveBeenCalledWith('ATL'))
})
