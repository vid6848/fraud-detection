import { Loader2, Play } from 'lucide-react'
import type { DemoStream } from '../hooks/useDemoStream'

/** "Start demo stream" button with live progress and any error underneath. */
export function DemoStreamControl({ demo }: { demo: DemoStream }) {
  const { status, running, starting, apiReady, canStart, error, start, available } = demo
  if (available === false) return null
  const run = running ? status?.run : null
  const label = run ? `Streaming ${run.sent} / ${run.total}`
    : starting ? 'Starting…'
      : !apiReady ? 'Waiting for the API…'
        : 'Start demo stream'
  const busy = Boolean(run) || starting

  return (
    <div className="flex max-w-xs flex-col items-end gap-1.5">
      <button type="button" onClick={() => void start()} disabled={!canStart}
        title="Replay 200 held-out test transactions through the model (about 20 seconds)"
        className="bg-brand inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold text-accent-fg shadow-[0_4px_14px_-4px_var(--accent)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60">
        {busy ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Play aria-hidden className="size-4" />}
        <span className="tabular-nums">{label}</span>
      </button>
      {run && (
        <div role="progressbar" aria-label="Demo stream progress" aria-valuemin={0} aria-valuemax={run.total}
          aria-valuenow={run.sent} className="h-1 w-full overflow-hidden rounded-full bg-surface-2">
          <div className="bg-brand h-full transition-[width] duration-500" style={{ width: `${(100 * run.sent) / Math.max(run.total, 1)}%` }} />
        </div>
      )}
      {error && <p role="alert" className="text-right text-xs text-high">{error}</p>}
    </div>
  )
}
