import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiStatusContext, type ApiStatus } from '../apiStatus/context'
import { ApiWakeBanner } from './ApiWakeBanner'

const renderBanner = (status: Partial<ApiStatus>) =>
  render(
    <ApiStatusContext.Provider value={{ phase: 'ready', since: null, retry: vi.fn(), ...status }}>
      <ApiWakeBanner />
    </ApiStatusContext.Provider>,
  )

describe('ApiWakeBanner', () => {
  it.each(['ready', 'checking'] as const)('shows nothing while %s', (phase) => {
    const { container } = renderBanner({ phase })
    expect(container).toBeEmptyDOMElement()
  })

  it('says the free-tier API is waking up, with the time waited so far', () => {
    renderBanner({ phase: 'waking', since: Date.now() - 12_000 })
    expect(screen.getByRole('status')).toHaveTextContent('API is waking up (free tier, ~1 min)')
    expect(screen.getByText(/Waiting 12 s/)).toBeInTheDocument()
    expect(screen.getByText(/live feed and\s+alerts already work/i)).toBeInTheDocument()
  })

  it('offers a retry once it gives up', async () => {
    const retry = vi.fn()
    renderBanner({ phase: 'down', retry })
    expect(screen.getByRole('alert')).toHaveTextContent('Can’t reach the API')
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(retry).toHaveBeenCalled()
  })
})
