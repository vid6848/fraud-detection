import { ArrowLeft, BrainCircuit, Loader2, Radio, ShieldAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Logo } from '../components/Logo'
import { ThemeToggle } from '../components/ThemeToggle'

const inputClass =
  'mt-1.5 block w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm placeholder:text-muted/70 focus:border-accent'

const FEATURES = [
  { icon: Radio, title: 'Live feed', body: 'Transactions appear the moment the API scores them.', tone: 'bg-cyan/15 text-cyan' },
  { icon: ShieldAlert, title: 'Alert queue', body: 'Medium and High scores wait here for your review.', tone: 'bg-rose/15 text-rose' },
  { icon: BrainCircuit, title: 'Reasons for every score', body: 'See which features pushed the risk up or down.', tone: 'bg-violet/15 text-violet' },
]

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
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1.1fr]">
      {/* Brand panel (desktop only) */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-surface/60 p-10 backdrop-blur lg:flex">
        <div aria-hidden className="bg-brand pointer-events-none absolute -bottom-32 -left-32 size-96 rounded-full opacity-20 blur-3xl" />
        <Link to="/" aria-label="Fraud Watch home" className="w-fit rounded-lg"><Logo /></Link>
        <div className="max-w-md">
          <h2 className="text-4xl font-semibold leading-[1.1] tracking-[-0.03em] [font-stretch:88%]">
            The model flags it. You make the call.
          </h2>
          <ul className="mt-8 space-y-5">
            {FEATURES.map(({ icon: Icon, title, body, tone }) => (
              <li key={title} className="flex gap-4">
                <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${tone}`}>
                  <Icon aria-hidden className="size-4.5" />
                </span>
                <div>
                  <p className="font-medium">{title}</p>
                  <p className="mt-0.5 text-sm text-muted">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-muted">Scores come from a Random Forest trained on 284,807 card transactions.</p>
      </aside>

      <main className="relative grid place-items-center px-4 py-10">
        <div className="absolute right-4 top-4"><ThemeToggle /></div>
        <div className="w-full max-w-sm">
          <div className="mb-8 flex justify-center lg:hidden">
            <Link to="/" aria-label="Fraud Watch home" className="rounded-lg"><Logo /></Link>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Analyst sign in</h1>
          <p className="mt-1 text-sm text-muted">Use the account your administrator gave you.</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4" noValidate>
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
              className="inline-flex w-full items-center justify-center gap-2 bg-brand rounded-xl px-4 py-2.5 text-sm font-semibold text-accent-fg shadow-[0_10px_30px_-10px_var(--accent)] hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50">
              {submitting && <Loader2 aria-hidden className="size-4 animate-spin" />}
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="mt-6 text-xs text-muted">
            Accounts are created by an administrator. Public sign-up is turned off.
          </p>
          <Link to="/" className="mt-8 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
            <ArrowLeft aria-hidden className="size-4" /> Back to the home page
          </Link>
        </div>
      </main>
    </div>
  )
}
