import { AlertTriangle, Inbox, Loader2, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'

export function Spinner({ label, className = '' }: { label: string; className?: string }) {
  return (
    <span role="status" className={`inline-flex items-center gap-2 text-sm text-muted ${className}`}>
      <Loader2 aria-hidden className="size-4 animate-spin" />
      <span>{label}</span>
    </span>
  )
}

export function FullPageSpinner({ label }: { label: string }) {
  return (
    <div className="grid min-h-dvh place-items-center">
      <Spinner label={label} />
    </div>
  )
}

/** Grey placeholder blocks shown while data loads. */
export function Skeleton({ rows = 5, label = 'Loading…' }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-lg bg-surface-2" />
      ))}
    </div>
  )
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-12 text-center">
      <div className="mb-3 text-muted" aria-hidden>{icon ?? <Inbox className="size-8" />}</div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  )
}

export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-high/40 bg-high-soft px-5 py-4">
      <div className="flex items-start gap-3">
        <AlertTriangle aria-hidden className="mt-0.5 size-5 shrink-0 text-high" />
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted break-words">{message}</p>
          {onRetry && (
            <button type="button" onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-2">
              <RotateCw aria-hidden className="size-4" /> Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
