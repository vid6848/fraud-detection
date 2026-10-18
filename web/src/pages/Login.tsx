import { ArrowLeft, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Logo } from '../components/Logo'
import { ThemeToggle } from '../components/ThemeToggle'

const inputClass =
  'mt-1.5 block w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-muted/70 focus:border-accent'


export function Login() {
  const { session, signIn } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/app'
  if (session) return <Navigate to={from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const message = await signIn(email.trim(), password)
    setSubmitting(false)
    if (message) setError(message)
  }

  return (
    <main className="relative grid min-h-dvh place-items-center px-4 py-10">
      <div className="absolute right-4 top-4"><ThemeToggle /></div>
      <div className="w-full max-w-sm animate-rise-in">
        <div className="mb-8 flex justify-center">
          <Link to="/" aria-label="Fraud Watch home" className="rounded-lg"><Logo /></Link>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-[0_30px_80px_-30px_rgba(15,23,42,0.45)] sm:p-8">
          <div aria-hidden className="bg-brand absolute inset-x-0 top-0 h-1" />
          <h1 className="text-center text-2xl font-semibold tracking-tight">Analyst sign in</h1>

          <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <input id="email" type="email" autoComplete="username" required value={email}
                onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="analyst@example.com" />
            </div>
            <div>
              <label htmlFor="password" className="text-sm font-medium">Password</label>
              <input id="password" type="password" autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)} className={inputClass} />
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-high/40 bg-high-soft px-3 py-2 text-sm text-high">
                {error}
              </p>
            )}

            <button type="submit" disabled={submitting || !email || !password}
              className="bg-brand inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-accent-fg shadow-[0_10px_30px_-10px_var(--accent)] hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50">
              {submitting && <Loader2 aria-hidden className="size-4 animate-spin" />}
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
        <div className="mt-6 flex justify-center">
          <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
            <ArrowLeft aria-hidden className="size-4" /> Back to the home page
          </Link>
        </div>
      </div>
    </main>
  )
}
