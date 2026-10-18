import { Activity, BarChart3, ChevronDown, LogOut, ShieldAlert } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { ApiStatusProvider } from '../apiStatus/ApiStatusProvider'
import { useAuth } from '../auth/context'
import { useOpenAlertCount } from '../hooks/useOpenAlertCount'
import { ToastProvider } from '../toast/ToastProvider'
import { AlertNotifier } from './AlertNotifier'
import { ApiWakeBanner } from './ApiWakeBanner'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const NAV_ITEMS = [
  { to: '/app', label: 'Live feed', short: 'Feed', icon: Activity },
  { to: '/app/alerts', label: 'Alerts', short: 'Alerts', icon: ShieldAlert },
  { to: '/app/model', label: 'Model & system', short: 'Model', icon: BarChart3 },
] as const

/** Top navigation tabs with a pill that glides to the active tab. */
function NavTabs({ openAlerts }: { openAlerts: number | null }) {
  const { pathname } = useLocation()
  const listRef = useRef<HTMLUListElement>(null)
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null)

  useLayoutEffect(() => {
    const measure = () => {
      // Measure the <li>: its offsetParent is the list, which the pill is positioned in.
      const active = listRef.current?.querySelector<HTMLElement>('a[aria-current="page"]')?.parentElement
      setPill(active ? { left: active.offsetLeft, width: active.offsetWidth } : null)
    }
    measure()
    // Re-measure once the web font has loaded (label widths change).
    document.fonts?.ready.then(measure)
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [pathname, openAlerts])

  return (
    <nav aria-label="Main" className="min-w-0">
      <ul ref={listRef} className="relative flex items-center gap-1 overflow-x-auto rounded-xl border border-border bg-surface/70 p-1 backdrop-blur">
        {pill && (
          <span aria-hidden className="bg-brand absolute inset-y-1 rounded-lg shadow-[0_4px_14px_-4px_var(--accent)] transition-all duration-300 ease-out"
            style={{ left: pill.left, width: pill.width }} />
        )}
        {NAV_ITEMS.map(({ to, label, short, icon: Icon }) => (
          <li key={to} className="relative flex-1 md:flex-none">
            <NavLink to={to} end={to === '/app'}
              className={({ isActive }) =>
                `flex items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-300 ${
                  isActive ? 'text-accent-fg' : 'text-muted hover:text-fg'}`}>
              <Icon aria-hidden className="size-4" />
              <span className="hidden sm:inline">{label}</span>
              <span className="sm:hidden">{short}</span>
              {to === '/app/alerts' && !!openAlerts && (
                <span className="rounded-full bg-high px-1.5 text-xs font-semibold text-white tabular-nums dark:text-bg">
                  {openAlerts}<span className="sr-only"> open</span>
                </span>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function initials(email?: string) {
  const name = (email ?? 'A').split('@')[0] ?? 'A'
  const parts = name.split(/[._-]/).filter(Boolean)
  return ((parts[0]?.[0] ?? 'A') + (parts[1]?.[0] ?? '')).toUpperCase()
}

/** Avatar button with a small menu: signed-in email and log out. */
function AccountMenu() {
  const { session, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const email = session?.user.email

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="true"
        aria-label="Account menu" className="flex items-center gap-1.5 rounded-xl border border-border bg-surface/70 p-1 pr-2 backdrop-blur hover:bg-surface-2">
        <span className="bg-brand grid size-7 place-items-center rounded-lg text-xs font-bold text-accent-fg">{initials(email)}</span>
        <ChevronDown aria-hidden className={`size-4 text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-64 animate-chip-in rounded-xl border border-border bg-surface p-2 shadow-xl">
          <div className="px-2 py-1.5">
            <p className="text-xs text-muted">Signed in as</p>
            <p className="truncate text-sm font-medium" title={email}>{email ?? 'analyst'}</p>
          </div>
          <div className="my-1 h-px bg-border" />
          <button type="button" disabled={busy}
            onClick={async () => { setBusy(true); try { await signOut() } finally { setBusy(false) } }}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-high hover:bg-high-soft disabled:opacity-60">
            <LogOut aria-hidden className="size-4" /> {busy ? 'Signing out…' : 'Log out'}
          </button>
        </div>
      )}
    </div>
  )
}

/** App shell: sticky glass top bar with tabs; tabs move to their own row on phones. */
export function Layout() {
  const { count: openAlerts } = useOpenAlertCount()
  const { pathname } = useLocation()

  return (
    <ToastProvider>
      <ApiStatusProvider>
        <AlertNotifier />
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/70 backdrop-blur-xl">
          <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
            <Link to="/" aria-label="Fraud Watch home" className="shrink-0 rounded-lg"><Logo /></Link>
            <div className="hidden flex-1 justify-center md:flex"><NavTabs openAlerts={openAlerts} /></div>
            <div className="ml-auto flex items-center gap-2 md:ml-0">
              <ThemeToggle />
              <AccountMenu />
            </div>
          </div>
          <div className="px-4 pb-3 md:hidden"><NavTabs openAlerts={openAlerts} /></div>
          <div aria-hidden className="flow-line h-px animate-flow opacity-70" />
        </header>

        <main id="main" tabIndex={-1} className="mx-auto min-w-0 max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <ApiWakeBanner />
          <div key={pathname} className="animate-page-in"><Outlet /></div>
        </main>
      </ApiStatusProvider>
    </ToastProvider>
  )
}
