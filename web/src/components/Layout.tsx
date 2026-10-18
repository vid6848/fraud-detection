import { Activity, BarChart3, LogOut, Menu, ShieldAlert, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { useOpenAlertCount } from '../hooks/useOpenAlertCount'
import { ToastProvider } from '../toast/ToastProvider'
import { AlertNotifier } from './AlertNotifier'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const NAV_ITEMS = [
  { to: '/app', label: 'Live feed', icon: Activity },
  { to: '/app/alerts', label: 'Alerts', icon: ShieldAlert },
  { to: '/app/model', label: 'Model & system', icon: BarChart3 },
] as const

function NavItems({ onNavigate, openAlerts }: { onNavigate?: () => void; openAlerts: number | null }) {
  return (
    <ul className="space-y-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <li key={to}>
          <NavLink to={to} end={to === '/app'} onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-surface-2 hover:text-fg'}`}>
            <Icon aria-hidden className="size-4" />
            <span className="flex-1">{label}</span>
            {to === '/app/alerts' && !!openAlerts && (
              <span className="rounded-full bg-high px-1.5 text-xs font-semibold text-white tabular-nums dark:text-bg">
                {openAlerts}<span className="sr-only"> open</span>
              </span>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

function AccountBox() {
  const { session, signOut } = useAuth()
  const [busy, setBusy] = useState(false)
  return (
    <div className="space-y-3 border-t border-border pt-4">
      <div className="min-w-0">
        <p className="text-xs text-muted">Signed in as</p>
        <p className="truncate text-sm font-medium" title={session?.user.email}>{session?.user.email ?? 'analyst'}</p>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" disabled={busy}
          onClick={async () => { setBusy(true); try { await signOut() } finally { setBusy(false) } }}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2 disabled:opacity-60">
          <LogOut aria-hidden className="size-4" /> {busy ? 'Signing out…' : 'Log out'}
        </button>
        <ThemeToggle />
      </div>
    </div>
  )
}

/** App shell: fixed sidebar on desktop, top bar + slide-in drawer on phones. */
export function Layout() {
  const [open, setOpen] = useState(false)
  const { count: openAlerts } = useOpenAlertCount()
  const menuButton = useRef<HTMLButtonElement>(null)
  const drawer = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    drawer.current?.querySelector<HTMLElement>('a, button')?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        menuButton.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <ToastProvider>
      <AlertNotifier />
      <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>

        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-dvh flex-col border-r border-border bg-surface px-4 py-5 md:flex">
          <Link to="/" className="mb-8 block rounded-lg px-1" aria-label="Fraud Watch home"><Logo /></Link>
          <nav aria-label="Main" className="flex-1"><NavItems openAlerts={openAlerts} /></nav>
          <AccountBox />
        </aside>

        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface/95 px-4 py-3 backdrop-blur md:hidden">
          <Logo />
          <button ref={menuButton} type="button" onClick={() => setOpen(true)} aria-label="Open menu"
            aria-expanded={open} aria-controls="mobile-nav"
            className="grid size-9 place-items-center rounded-lg border border-border">
            <Menu aria-hidden className="size-5" />
          </button>
        </header>

        {open && (
          <div className="fixed inset-0 z-40 md:hidden">
            <button type="button" aria-label="Close menu" tabIndex={-1} onClick={() => setOpen(false)}
              className="absolute inset-0 bg-black/50" />
            <div ref={drawer} id="mobile-nav" role="dialog" aria-modal="true" aria-label="Menu"
              className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-surface px-4 py-5 shadow-xl">
              <div className="mb-8 flex items-center justify-between px-1">
                <Logo />
                <button type="button" onClick={() => { setOpen(false); menuButton.current?.focus() }}
                  aria-label="Close menu" className="grid size-9 place-items-center rounded-lg border border-border">
                  <X aria-hidden className="size-5" />
                </button>
              </div>
              <nav aria-label="Main" className="flex-1"><NavItems openAlerts={openAlerts} onNavigate={() => setOpen(false)} /></nav>
              <AccountBox />
            </div>
          </div>
        )}

        <main id="main" tabIndex={-1} className="min-w-0 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl"><Outlet /></div>
        </main>
      </div>
    </ToastProvider>
  )
}
