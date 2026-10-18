import type { LiveStatus } from '../lib/realtime'

const TEXT: Record<LiveStatus, string> = {
  connecting: 'Connecting…',
  live: 'Live',
  offline: 'Offline',
  error: 'Disconnected',
}
const DOT: Record<LiveStatus, string> = {
  connecting: 'bg-medium',
  live: 'bg-low',
  offline: 'bg-muted',
  error: 'bg-high',
}

/** Realtime connection status, announced politely to screen readers when it changes. */
export function LiveIndicator({ status, paused = false }: { status: LiveStatus; paused?: boolean }) {
  const label = paused && status === 'live' ? 'Paused' : TEXT[status]
  return (
    <span role="status" className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-sm">
      <span aria-hidden className="relative flex size-2.5">
        {status === 'live' && !paused && <span className="absolute inset-0 animate-ping rounded-full bg-low opacity-60" />}
        <span className={`relative size-2.5 rounded-full ${paused && status === 'live' ? 'bg-muted' : DOT[status]}`} />
      </span>
      {label}
    </span>
  )
}
