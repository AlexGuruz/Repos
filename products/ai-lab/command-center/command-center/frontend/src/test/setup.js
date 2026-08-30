import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

import { useChatStore, useEventStore, useFeedStore, useGuruStore, useHardwareStore, useRepoStore, useUiStore } from '../store'
import { clearDiagnostics } from '../lib/diagnostics'

beforeEach(() => {
  vi.clearAllMocks()
  useEventStore.setState({ events: [], pendingCount: 0 })
  useFeedStore.setState({ lines: [] })
  useHardwareStore.setState({ gpu: null, cpu_percent: 0, ram_used_gb: 0, ram_total_gb: 0, vramHistory: [] })
  useChatStore.setState({
    messages: [
      { role: 'ai', text: 'Command center online. Main orchestrator connected. Guru settings available in the Guru tab.' },
    ],
  })
  useRepoStore.setState({ fileActivity: {}, summaries: [] })
  useUiStore.setState({ tab: 'chat' })
  useGuruStore.setState({
    selectedMode: 'RR',
    modes: {
      RR: { mode: 'RR', label: 'Response Refinement', savePolicy: 'direct', description: '', messages: [], currentDraft: null, lastSavedSummary: null, lastUpdatedAt: null, currentRules: {} },
      PR: { mode: 'PR', label: 'Proposal Refinement', savePolicy: 'direct', description: '', messages: [], currentDraft: null, lastSavedSummary: null, lastUpdatedAt: null, currentRules: {} },
      AL: { mode: 'AL', label: 'Action List', savePolicy: 'confirm', description: '', messages: [], currentDraft: null, lastSavedSummary: null, lastUpdatedAt: null, currentRules: {} },
      TL: { mode: 'TL', label: 'Tool List', savePolicy: 'confirm', description: '', messages: [], currentDraft: null, lastSavedSummary: null, lastUpdatedAt: null, currentRules: {} },
      ATL: { mode: 'ATL', label: 'Auto Task List', savePolicy: 'confirm', description: '', messages: [], currentDraft: null, lastSavedSummary: null, lastUpdatedAt: null, currentRules: {} },
    },
  })
  clearDiagnostics()
  window.sendPrompt = undefined
  window.openGuruMode = undefined
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  cleanup()
})
