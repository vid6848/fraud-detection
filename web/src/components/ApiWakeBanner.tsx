import { Loader2 } from 'lucide-react'
import { useApiStatus } from '../apiStatus/context'
import { useNow } from '../hooks/useNow'
import { unreachableMessage } from '../lib/api'
import { ErrorState } from './StateViews'

/** Shown above every dashboard page while the API is cold-starting or unreachable. */
export function ApiWakeBanner() {
  const { phase, since, retry } = useApiStatus()
  const now = useNow()
  if (phase === 'ready' || phase === 'checking') return null
  if (phase === 'down') {
    return (
      <div className="mb-6">
        <ErrorState title="Can’t reach the API"
          message={`${unreachableMessage()} The live feed and alerts still load from the database.`}
          onRetry={retry} />
      </div>
    )
  }
  const waited = since === null ? 0 : Math.max(0, Math.round((now - since) / 1000))
  return (
    <div className="mb-6 flex animate-rise-in items-start gap-3 rounded-2xl border border-medium/40 bg-medium-soft px-5 py-4">
      <Loader2 aria-hidden className="mt-0.5 size-5 shrink-0 animate-spin text-medium" />
      <div className="min-w-0">
        <p role="status" className="font-semibold">API is waking up (free tier, ~1 min)</p>
        <p className="mt-1 text-sm text-muted">
          The scoring API sleeps after 15 minutes without traffic and is starting again. The live feed and
          alerts already work; explanations and the demo stream will too once it’s up.{' '}
          <span aria-hidden className="tabular-nums">Waiting {waited} s…</span>
        </p>
      </div>
    </div>
  )
}
