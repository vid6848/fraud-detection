import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeSession, renderWithProviders } from '../test/render'
import { Landing } from './Landing'

describe('Landing', () => {
  it('invites a signed-out visitor to sign in', () => {
    renderWithProviders(<Landing />)
    expect(screen.getByRole('heading', { level: 1, name: 'Every card payment, scored before it settles.' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /sign in to the dashboard/i })).toHaveAttribute('href', '/login')
  })

  it('sends a signed-in analyst straight to the dashboard', () => {
    renderWithProviders(<Landing />, { auth: { session: fakeSession } })
    expect(screen.getByRole('link', { name: /open the dashboard/i })).toHaveAttribute('href', '/app')
  })

  it('shows the pipeline in order and the real test-set results', () => {
    renderWithProviders(<Landing />)
    const steps = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(steps).toEqual(['1Stream', '2Score', '3Store', '4Review'])
    expect(screen.getByText('0.744')).toBeInTheDocument()
    expect(screen.getByText('$3,556')).toBeInTheDocument()
  })

  it('labels the animated stream as sample data', () => {
    renderWithProviders(<Landing />)
    expect(screen.getByText(/animated preview with sample data/i)).toBeInTheDocument()
    expect(screen.getAllByRole('listitem', { hidden: false }).length).toBeGreaterThan(6)
  })
})
