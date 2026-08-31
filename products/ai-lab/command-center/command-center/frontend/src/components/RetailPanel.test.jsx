import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import RetailPanel from './RetailPanel'
import { buildMockRetailRange, mockRetailFacets, mockRetailLiveStatus } from '../test/retailMocks'

const { api } = vi.hoisted(() => ({
  api: {
    retailDashboardRange: vi.fn(),
    retailFacets: vi.fn(),
    retailLiveStatus: vi.fn(),
    retailReconciliation: vi.fn(),
    retailRefresh: vi.fn(),
    retailJob: vi.fn(),
    retailHealth: vi.fn(),
  },
}))
}))

vi.mock('../lib/api', () => ({ api }))

beforeEach(() => {
  api.retailHealth.mockResolvedValue({ ok: true, available: true, disabled: false })
  api.retailFacets.mockResolvedValue(mockRetailFacets)
  api.retailLiveStatus.mockResolvedValue(mockRetailLiveStatus())
  api.retailReconciliation.mockResolvedValue({ status: 'pass', message: 'ok' })
  api.retailDashboardRange.mockImplementation((p) => Promise.resolve(buildMockRetailRange({
    start: p.start, end: p.end, compare: p.compare, brand: p.brand, category: p.category, budtender: p.budtender,
  })))
})

test('loads range dashboard with KPIs, charts and tables', async () => {
  render(<RetailPanel />)
  expect(await screen.findByText('Net Sales Over Time')).toBeInTheDocument()
  expect(screen.getByText('Budtender Sales')).toBeInTheDocument()
  expect(screen.getByText('Brand Summary')).toBeInTheDocument()
  await waitFor(() => expect(api.retailDashboardRange).toHaveBeenCalled())
  expect(screen.getByText('Net Sales')).toBeInTheDocument()
  expect(screen.getByText('Eff. Discount')).toBeInTheDocument()
})

test('shows the live badge from live-status', async () => {
  render(<RetailPanel />)
  expect(await screen.findByText(/Live · synced/i)).toBeInTheDocument()
})

test('changing preset re-queries the range endpoint', async () => {
  render(<RetailPanel />)
  await screen.findByText('Net Sales Over Time')
  api.retailDashboardRange.mockClear()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '7 days' }))
  await waitFor(() => expect(api.retailDashboardRange).toHaveBeenCalled())
  const lastCall = api.retailDashboardRange.mock.calls.at(-1)[0]
  const days = Math.round((new Date(lastCall.end) - new Date(lastCall.start)) / 86400000) + 1
  expect(days).toBe(7)
})

test('applying a brand filter passes it to the range query', async () => {
  render(<RetailPanel />)
  await screen.findByText('Net Sales Over Time')
  api.retailDashboardRange.mockClear()
  const user = userEvent.setup()
  const brandSelect = screen.getByRole('combobox', { name: /Brand/i })
  await user.selectOptions(brandSelect, 'Country Cannabis')
  await waitFor(() => expect(api.retailDashboardRange).toHaveBeenCalledWith(
    expect.objectContaining({ brand: 'Country Cannabis' })
  ))
})

test('toggling compare off removes the prior comparison', async () => {
  render(<RetailPanel />)
  await screen.findByText('Net Sales Over Time')
  api.retailDashboardRange.mockClear()
  const user = userEvent.setup()
  const cmp = screen.getAllByRole('combobox').find(s => s.value === 'prior')
  expect(cmp).toBeTruthy()
  await user.selectOptions(cmp, 'none')
  await waitFor(() => {
    const lastCall = api.retailDashboardRange.mock.calls.at(-1)[0]
    expect(lastCall.compare).toBe(false)
  })
})
