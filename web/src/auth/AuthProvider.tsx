import type { Session } from '@supabase/supabase-js'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getSupabase } from '../lib/supabase'
import { AuthContext, friendlyAuthError, type AuthState } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = getSupabase()
    let active = true
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return
      setSession(data.session)
      setLoading(false)
    })
    // Fires on sign-in, sign-out and token refresh, so the session is always current.
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      setLoading(false)
    })
    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  const value = useMemo<AuthState>(() => ({
    session,
    loading,
    async signIn(email, password) {
      try {
        const { error } = await getSupabase().auth.signInWithPassword({ email, password })
        return friendlyAuthError(error)
      } catch (e) {
        return friendlyAuthError({ message: e instanceof Error ? e.message : String(e) })
      }
    },
    async signOut() {
      await getSupabase().auth.signOut()
    },
  }), [session, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
