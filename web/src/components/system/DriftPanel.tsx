import { AlertOctagon, CheckCircle2, Eye, HelpCircle, RotateCw } from 'lucide-react'
import { useApiStatus } from '../../apiStatus/context'
import { useAuth } from '../../auth/context'
import { useAsync } from '../../hooks/useAsync'
import { ApiError, apiErrorMessage } from '../../lib/api'
import { bandLabel, fetchDrift, sharePct, type DriftReport, type DriftStatus } from '../../lib/drift'
import { formatCount, formatDateTime } from '../../lib/format'
import { CopyCommand } from '../CopyCommand'
import { EmptyState, ErrorState, Skeleton, Spinner } from '../StateViews'

const STATUS: Record<DriftStatus, { Icon: typeof Eye; cls: string; meaning: string }> = {
  OK: { Icon: CheckCircle2, cls: 'border-low/40 bg-low-soft text-low', meaning: 'Live scores look like the training scores.' },
  Watch: { Icon: Eye, cls: 'border-medium/40 bg-medium-soft text-medium', meaning: 'A moderate shift: keep an eye on it.' },
  Alert: { Icon: AlertOctagon, cls: 'border-high/40 bg-high-soft text-high', meaning: 'A large shift: the model may need retraining.' },
  'Not enough data': { Icon: HelpCircle, cls: 'border-border bg-surface-2 text-muted', meaning: 'Too few live scores for a reliable reading.' },
}

export function DriftStatusPill({ status }: { status: DriftStatus }) {
  const { Icon, cls } = STATUS[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${cls}`}>
      <Icon aria-hidden className="size-4" /> {status}
    </span>
  )
}

/** PSI between the latest live scores and the training score distribution (GET /drift). */
export function DriftPanel() {
  const { session } = useAuth()
  const { phase } = useApiStatus()
  const token = session?.access_token
  const ready = phase === 'ready' && Boolean(token)
  const drift = useAsync((signal) => fetchDrift(token!, signal), ready ? `drift:${token}` : null)

  if (!ready) return <Spinner label="Waiting for the API…" />
  if (drift.loading && !drift.data) return <Skeleton rows={3} label="Loading drift check" />
  if (drift.error) {
    if (drift.error instanceof ApiError && drift.error.status === 503) {
      return (
        <EmptyState title="Drift check not available" icon={<HelpCircle className="size-8" />}>
          <p>{drift.error.message}.</p>
          <p className="mt-2">It needs Supabase storage on the API and the training score distribution:</p>
          <div className="mt-3"><CopyCommand command="python scripts/make_score_distribution.py" /></div>
        </EmptyState>
      )
    }
    return <ErrorState {...apiErrorMessage(drift.error)} onRetry={drift.reload} />
  }
  return drift.data ? <DriftReportView report={drift.data} onRefresh={drift.reload} refreshing={drift.loading} /> : null
}

function DriftReportView({ report, onRefresh, refreshing }: { report: DriftReport; onRefresh: () => void; refreshing: boolean }) {
  const { meaning } = STATUS[report.status]
  const psi = report.psi
  const enough = report.status !== 'Not enough data'

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div className="animate-rise-in rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted">Population Stability Index</p>
            <p className="mt-1 text-4xl font-semibold tracking-tight tabular-nums">{psi === null ? '–' : psi.toFixed(3)}</p>
          </div>
          <DriftStatusPill status={report.status} />
        </div>
        <p className="mt-3 text-sm">{meaning}</p>
        <p className="mt-2 text-sm text-muted">
          {report.live_rows
            ? <>Latest <strong className="text-fg">{formatCount(report.live_rows)}</strong> live scores
                {report.live_from && report.live_to && <> ({formatDateTime(report.live_from)} – {formatDateTime(report.live_to)})</>}
                {' '}vs {formatCount(report.reference.rows)} training scores, model {report.model_version}.</>
            : 'No live scores from this model yet.'}
        </p>
        {!enough && (
          <p className="mt-2 text-sm text-muted">
            A reliable reading needs at least {formatCount(report.min_rows)} live scores ({formatCount(report.live_rows)} so far).
            Each demo stream adds 200.
          </p>
        )}
        <p className="mt-3 text-xs text-muted">
          PSI &lt; {report.thresholds.watch} OK · {report.thresholds.watch}–{report.thresholds.alert} Watch · ≥ {report.thresholds.alert} Alert.
          Compares at most the latest {formatCount(report.window)} scores.
        </p>
        <button type="button" onClick={onRefresh} disabled={refreshing}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-2 disabled:opacity-60">
          <RotateCw aria-hidden className={`size-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="animate-rise-in overflow-x-auto rounded-2xl border border-border bg-surface" style={{ animationDelay: '80ms' }}>
        <table className="w-full text-sm">
          <caption className="px-4 pb-1 pt-3 text-left text-xs text-muted">
            Share of scores in each fraud-probability band, and how much each band adds to the PSI
          </caption>
          <thead className="border-b border-border text-left text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Score band</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Training</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Live</th>
              <th scope="col" className="px-4 py-2 font-medium">Part of PSI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {report.bins.map((bin, i) => {
              const share = psi ? bin.contribution / psi : 0
              return (
                <tr key={bin.lower}>
                  <th scope="row" className="whitespace-nowrap px-4 py-2 text-left font-medium tabular-nums">{bandLabel(report.bins, i)}</th>
                  <td className="px-4 py-2 text-right tabular-nums text-muted">{sharePct(bin.reference)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{report.live_rows ? sharePct(bin.live) : '–'}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div aria-hidden className="h-2 w-24 overflow-hidden rounded-full bg-surface-2">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(share * 100)}%` }} />
                      </div>
                      <span className="w-10 text-right text-xs tabular-nums text-muted">{psi ? `${Math.round(share * 100)}%` : '–'}</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="px-4 py-3 text-xs text-muted">
          Training scores come from the {report.reference.source}. They are in-sample, but after calibration they sit
          close to held-out scores (PSI training → validation ≈ 0.02).
        </p>
      </div>
    </div>
  )
}
