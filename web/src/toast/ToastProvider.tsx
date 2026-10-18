import { CheckCircle2, Info, OctagonAlert, X, XCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ToastContext, type Toast, type ToastInput } from './context'

const MAX = 3
const DURATION_MS = 6000

const TONES = {
  info: { Icon: Info, cls: 'text-accent' },
  success: { Icon: CheckCircle2, cls: 'text-low' },
  alert: { Icon: OctagonAlert, cls: 'text-high' },
  error: { Icon: XCircle, cls: 'text-high' },
} as const

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
    clearTimeout(timers.current.get(id))
    timers.current.delete(id)
  }, [])

  const notify = useCallback((input: ToastInput) => {
    const id = nextId.current++
    setToasts((t) => [...t, { ...input, id }].slice(-MAX))
    timers.current.set(id, setTimeout(() => dismiss(id), DURATION_MS))
  }, [dismiss])

  useEffect(() => {
    const all = timers.current
    return () => all.forEach(clearTimeout)
  }, [])

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div aria-live="polite" aria-label="Notifications" role="region"
        className="pointer-events-none fixed inset-x-3 bottom-3 z-[60] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:bottom-5 sm:w-96">
        {toasts.map((t) => {
          const { Icon, cls } = TONES[t.tone ?? 'info']
          return (
            <div key={t.id} role="status"
              className="pointer-events-auto flex w-full animate-toast-in items-start gap-3 rounded-xl border border-border bg-surface p-3.5 shadow-lg">
              <Icon aria-hidden className={`mt-0.5 size-5 shrink-0 ${cls}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{t.title}</p>
                {t.body && <p className="mt-0.5 text-sm text-muted">{t.body}</p>}
                {t.action && (
                  <Link to={t.action.to} onClick={() => dismiss(t.id)}
                    className="mt-1.5 inline-block text-sm font-medium text-accent hover:underline">
                    {t.action.label}
                  </Link>
                )}
              </div>
              <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss notification"
                className="grid size-7 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-fg">
                <X aria-hidden className="size-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
