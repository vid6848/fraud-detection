import { screen } from '@testing-library/react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { fakeSession, renderWithProviders } from '../test/render'
import { ProtectedRoute } from './ProtectedRoute'

function LoginProbe() {
  const state = useLocation().state as { from?: string } | null
  return <p>login page, from={state?.from}</p>
}

const routes = (
  <Routes>
    <Route path="/login" element={<LoginProbe />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/alerts" element={<p>secret alerts</p>} />
    </Route>
  </Routes>
)

describe('ProtectedRoute', () => {
  it('shows a spinner while the session loads', () => {
    renderWithProviders(routes, { auth: { loading: true }, route: '/alerts' })
    expect(screen.getByRole('status')).toHaveTextContent(/checking your session/i)
  })

  it('redirects to /login and remembers the page', () => {
    renderWithProviders(routes, { route: '/alerts?severity=HIGH' })
    expect(screen.getByText('login page, from=/alerts?severity=HIGH')).toBeInTheDocument()
  })

  it('renders the page for a signed-in analyst', () => {
    renderWithProviders(routes, { auth: { session: fakeSession }, route: '/alerts' })
    expect(screen.getByText('secret alerts')).toBeInTheDocument()
  })
})
