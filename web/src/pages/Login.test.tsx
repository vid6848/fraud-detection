import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { fakeSession, renderWithProviders } from '../test/render'
import { Login } from './Login'

function renderLogin(auth = {}, route: NonNullable<Parameters<typeof renderWithProviders>[1]>['route'] = '/login') {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<p>Live feed page</p>} />
      <Route path="/alerts" element={<p>Alerts page</p>} />
    </Routes>,
    { auth, route },
  )
}

describe('Login', () => {
  it('has labelled email and password fields and no sign-up link', () => {
    renderLogin()
    expect(screen.getByLabelText('Email')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.queryByRole('link', { name: /sign up/i })).not.toBeInTheDocument()
  })

  it('keeps the button disabled until both fields are filled', async () => {
    renderLogin()
    const button = screen.getByRole('button', { name: 'Sign in' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co')
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    expect(button).toBeEnabled()
  })

  it('submits the trimmed email and password', async () => {
    const signIn = vi.fn().mockResolvedValue(null)
    renderLogin({ signIn })
    await userEvent.type(screen.getByLabelText('Email'), '  analyst@example.com ')
    await userEvent.type(screen.getByLabelText('Password'), 'secret{Enter}')
    expect(signIn).toHaveBeenCalledWith('analyst@example.com', 'secret')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the error message when sign-in fails', async () => {
    renderLogin({ signIn: vi.fn().mockResolvedValue('Invalid email or password.') })
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
  })

  it('shows a loading state while signing in', async () => {
    let finish: (v: string | null) => void = () => {}
    renderLogin({ signIn: vi.fn(() => new Promise<string | null>((r) => { finish = r })) })
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co')
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
    finish(null)
  })

  it('redirects a signed-in analyst back to where they were going', () => {
    renderLogin({ session: fakeSession }, { pathname: '/login', state: { from: '/alerts' } })
    expect(screen.getByText('Alerts page')).toBeInTheDocument()
  })

  it('redirects to the live feed by default', () => {
    renderLogin({ session: fakeSession })
    expect(screen.getByText('Live feed page')).toBeInTheDocument()
  })
})
