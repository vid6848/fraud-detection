import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { createFakeSupabase } from '../test/fakeSupabase'
import { fakeSession, renderWithProviders } from '../test/render'
import { Layout } from './Layout'

let fake = createFakeSupabase()
vi.mock('../lib/supabase', () => ({ getSupabase: () => fake.client }))

function renderAt(route: string, auth = {}) {
  return renderWithProviders(
    <Routes>
      <Route path="/app" element={<Layout />}>
        <Route index element={<p>feed page</p>} />
        <Route path="alerts" element={<p>alerts page</p>} />
        <Route path="model" element={<p>model page</p>} />
      </Route>
    </Routes>,
    { auth: { session: fakeSession, ...auth }, route },
  )
}

// jsdom renders both the desktop and the phone tab rows; use the first.
const mainNav = () => screen.getAllByRole('navigation', { name: 'Main' })[0]!

describe('Layout', () => {
  it('shows the three sections in the top navigation and marks the current one', async () => {
    fake = createFakeSupabase({ alerts: { count: 0 } })
    renderAt('/app/alerts')
    const links = within(mainNav()).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/app', '/app/alerts', '/app/model'])
    expect(within(mainNav()).getByRole('link', { current: 'page' })).toHaveAttribute('href', '/app/alerts')
    expect(screen.getByText('alerts page')).toBeInTheDocument()
  })

  it('navigates between sections', async () => {
    fake = createFakeSupabase({ alerts: { count: 0 } })
    renderAt('/app')
    await userEvent.click(within(mainNav()).getAllByRole('link')[2]!)
    expect(screen.getByText('model page')).toBeInTheDocument()
  })

  it('shows the number of open alerts on the Alerts tab', async () => {
    fake = createFakeSupabase({ alerts: { count: 4 } })
    renderAt('/app')
    expect((await within(mainNav()).findByText('4')).parentElement).toHaveTextContent('4 open')
  })

  it('opens the account menu with the signed-in email and logs out', async () => {
    fake = createFakeSupabase({ alerts: { count: 0 } })
    const { auth } = renderAt('/app')
    const button = screen.getByRole('button', { name: 'Account menu' })
    expect(button).toHaveTextContent('A') // initials of analyst@example.com
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('analyst@example.com')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(auth.signOut).toHaveBeenCalled()
  })

  it('closes the account menu with Escape', async () => {
    fake = createFakeSupabase({ alerts: { count: 0 } })
    renderAt('/app')
    await userEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByText('analyst@example.com')).not.toBeInTheDocument()
  })

  it('has a skip link to the main content', () => {
    fake = createFakeSupabase({ alerts: { count: 0 } })
    renderAt('/app')
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main')
  })
})
