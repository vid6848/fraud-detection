import type { Session } from '@supabase/supabase-js'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthContext, type AuthState } from '../auth/context'
import { ThemeProvider } from '../theme/ThemeProvider'

export const fakeSession = {
  access_token: 'test-token',
  user: { id: 'user-1', email: 'analyst@example.com' },
} as unknown as Session

/** Render with a router, theme and a fake auth context (no Supabase). */
export function renderWithProviders(ui: ReactElement, { auth = {}, route = '/' }: {
  auth?: Partial<AuthState>
  route?: string | { pathname: string; state?: unknown }
} = {}) {
  const value: AuthState = {
    session: null,
    loading: false,
    signIn: vi.fn().mockResolvedValue(null),
    signOut: vi.fn().mockResolvedValue(undefined),
    ...auth,
  }
  const result = render(
    <ThemeProvider>
      <AuthContext.Provider value={value}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </ThemeProvider>,
  )
  return { ...result, auth: value }
}
