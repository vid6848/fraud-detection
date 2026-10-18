import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { createFakeSupabase } from '../test/fakeSupabase'
import { renderWithProviders } from '../test/render'
import { ToastProvider } from '../toast/ToastProvider'
import { AlertNotifier } from './AlertNotifier'

let fake = createFakeSupabase()
vi.mock('../lib/supabase', () => ({ getSupabase: () => fake.client }))

function Where() {
  const l = useLocation()
  return <p>at {l.pathname + l.search}</p>
}

describe('AlertNotifier', () => {
  it('shows a notification for each new alert, linking to it', async () => {
    fake = createFakeSupabase({ transactions: { data: { amount: 94.82, probability: 0.93 } } })
    renderWithProviders(
      <ToastProvider><AlertNotifier /><Routes><Route path="*" element={<Where />} /></Routes></ToastProvider>,
      { route: '/app' },
    )
    await act(async () => fake.emit('alerts', 'INSERT', { id: 88, severity: 'HIGH', transaction_id: 'tx' }))
    expect(await screen.findByText('New high-risk alert')).toBeInTheDocument()
    expect(screen.getByText('$94.82, fraud probability 93.0%')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: 'Review in the alert queue' }))
    expect(screen.getByText('at /app/alerts?id=88')).toBeInTheDocument()
    expect(screen.queryByText('New high-risk alert')).not.toBeInTheDocument()
  })
})
