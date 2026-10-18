import type { Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

export interface AuthState {
  session: Session | null
  /** True until the stored session (if any) has been read on start-up. */
  loading: boolean
  /** Resolves to an analyst-friendly error message, or null on success. */
  signIn: (email: string, password: string) => Promise<string | null>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** Turn Supabase auth errors into short messages an analyst can act on. */
export function friendlyAuthError(error: { message?: string; status?: number } | null): string | null {
  if (!error) return null
  const msg = (error.message ?? '').toLowerCase()
  if (msg.includes('invalid login credentials')) return 'Invalid email or password.'
  if (msg.includes('email not confirmed')) return 'This account’s email is not confirmed yet.'
  if (error.status === 429 || msg.includes('rate limit')) return 'Too many attempts. Wait a minute and try again.'
  if (msg.includes('failed to fetch') || msg.includes('network')) {
    return 'Can’t reach the login service. Check your connection and try again.'
  }
  return 'Sign-in failed. Please try again.'
}
