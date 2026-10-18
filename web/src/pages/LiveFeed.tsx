import { Activity, Flag, Pause, Play, Radio, ShieldAlert, Timer } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CopyCommand } from '../components/CopyCommand'
import { KpiCard } from '../components/KpiCard'
import { LiveIndicator } from '../components/LiveIndicator'
import { PageHeader } from '../components/PageHeader'
import { ProbabilityBar } from '../components/ProbabilityBar'
import { ReasonChips } from '../components/ReasonChips'
import { RiskBadge } from '../components/RiskBadge'
import { EmptyState, ErrorState, Skeleton } from '../components/StateViews'
import { useLiveTransactions } from '../hooks/useLiveTransactions'
import { useNow } from '../hooks/useNow'
import { useOpenAlertCount } from '../hooks/useOpenAlertCount'
import { computeKpis, FEED_CAP, type FeedRow } from '../lib/feed'
import { formatCurrency, formatFeedTime, formatMs, formatPercent } from '../lib/format'

export function LiveFeed() {
  const { state, live, retry, pause, resume } = useLiveTransactions()
  const alerts = useOpenAlertCount()
  const now = useNow()
  const kpis = computeKpis(state, now)
  const waiting = state.buffer.length

  return (
    <>
      <PageHeader
        title="Live feed"
        description={`Every transaction the API scores, newest first. The latest ${FEED_CAP} are kept on screen.`}
        actions={
          <>
            <LiveIndicator status={live} paused={state.paused} />
            <button type="button" onClick={state.paused ? resume : pause} aria-pressed={state.paused}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-2">
              {state.paused ? <Play aria-hidden className="size-4" /> : <Pause aria-hidden className="size-4" />}
              {state.paused ? 'Resume' : 'Pause'}
              {state.paused && waiting > 0 && (
                <span className="rounded-full bg-accent px-1.5 text-xs font-semibold text-accent-fg tabular-nums">
                  {waiting} new
                </span>
              )}
            </button>
          </>
        }
      />

      <section aria-label="Key figures" className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Transactions / min" icon={Activity} value={kpis.perMinute.toLocaleString()} hint="Scored in the last 60 seconds" />
        <KpiCard label="Flagged" icon={Flag} value={formatPercent(kpis.flaggedPct)}
          hint={kpis.sample ? `${kpis.flagged} of the last ${kpis.sample} are Medium or High` : 'No transactions yet'} />
        <KpiCard label="Open alerts" icon={ShieldAlert} tone={alerts.count ? 'alert' : 'default'}
          value={alerts.error ? '–' : alerts.count === null ? '…' : alerts.count.toLocaleString()}
          hint={alerts.error ? 'Couldn’t load alerts' : <Link to="/app/alerts" className="underline-offset-2 hover:underline">Review in the alert queue</Link>} />
        <KpiCard label="Average latency" icon={Timer} value={formatMs(kpis.avgLatencyMs)} hint="API scoring time per transaction" />
      </section>

      {live === 'error' && state.status === 'ready' && (
        <div className="mb-4">
          <ErrorState title="Live updates disconnected"
            message="New transactions won’t appear until the connection is back. The rows below are the last ones loaded."
            onRetry={retry} />
        </div>
      )}

      <FeedBody state={state} retry={retry} />
    </>
  )
}

function FeedBody({ state, retry }: { state: ReturnType<typeof useLiveTransactions>['state']; retry: () => void }) {
  if (state.status === 'loading' && !state.rows.length) return <Skeleton rows={8} label="Loading transactions" />
  if (state.status === 'error') {
    return <ErrorState title="Couldn’t load transactions" message={state.error ?? 'Unknown error'} onRetry={retry} />
  }
  if (!state.rows.length) {
    return (
      <EmptyState title="Waiting for transactions — start the simulator" icon={<Radio className="size-8" />}>
        <p>New transactions appear here the moment the API scores them. Start the API and the simulator from the project folder:</p>
        <div className="mt-4 space-y-2">
          <CopyCommand command="uvicorn api.main:app --no-access-log" />
          <CopyCommand command="python -m simulator --rate 20" />
        </div>
      </EmptyState>
    )
  }
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      {/* Desktop / tablet: table */}
      <table className="hidden w-full text-sm md:table">
        <caption className="sr-only">Latest scored transactions, newest first</caption>
        <thead className="border-b border-border bg-surface-2/60 text-left text-xs text-muted">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">Time</th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">Amount</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Fraud probability</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Risk</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Reasons</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {state.rows.map((row) => <FeedTableRow key={row.id} row={row} />)}
        </tbody>
      </table>

      {/* Phone: stacked cards */}
      <ul className="divide-y divide-border md:hidden" aria-label="Latest scored transactions, newest first">
        {state.rows.map((row) => (
          <li key={row.id} className={`space-y-2 px-4 py-3 ${rowTone(row)}`}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-base font-semibold tabular-nums">{formatCurrency(row.amount)}</span>
              <RiskBadge level={row.risk_level} />
            </div>
            <div className="flex items-center justify-between gap-3 text-sm text-muted">
              <time dateTime={row.created_at} className="tabular-nums">{formatFeedTime(row.created_at)}</time>
              <ProbabilityBar probability={row.probability} level={row.risk_level} />
            </div>
            {row.reasons.length > 0 && <ReasonChips reasons={row.reasons} />}
          </li>
        ))}
      </ul>
    </div>
  )
}

function rowTone(row: FeedRow) {
  const flag = row.risk_level === 'HIGH' ? 'bg-high-soft/50' : row.risk_level === 'MEDIUM' ? 'bg-medium-soft/40' : ''
  return `${flag} ${row.live ? 'animate-row-in' : ''}`
}

function FeedTableRow({ row }: { row: FeedRow }) {
  return (
    <tr className={rowTone(row)}>
      <td className="whitespace-nowrap px-4 py-2.5 text-muted tabular-nums">
        <time dateTime={row.created_at}>{formatFeedTime(row.created_at)}</time>
      </td>
      <td className="whitespace-nowrap px-4 py-2.5 text-right font-medium tabular-nums">{formatCurrency(row.amount)}</td>
      <td className="px-4 py-2.5"><ProbabilityBar probability={row.probability} level={row.risk_level} /></td>
      <td className="px-4 py-2.5"><RiskBadge level={row.risk_level} /></td>
      <td className="px-4 py-2.5"><ReasonChips reasons={row.reasons} /></td>
    </tr>
  )
}
