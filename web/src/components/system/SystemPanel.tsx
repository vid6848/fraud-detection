import { Activity, AlertOctagon, CheckCircle2, Clock, Database, Gauge, PlugZap, Server } from 'lucide-react'
import { useNow } from '../../hooks/useNow'
import { usePolling } from '../../hooks/usePolling'
import { ApiError, apiUrl } from '../../lib/api'
import { formatCount, formatDuration, formatMs } from '../../lib/format'
import { fetchSystem, scoringLatency, type SystemSnapshot } from '../../lib/system'
import { CopyCommand } from '../CopyCommand'
import { KpiCard } from '../KpiCard'
import { ErrorState, Skeleton } from '../StateViews'
import { LatencyChart } from './LatencyChart'

export const POLL_MS = 5000

function StatusPill({ snapshot, error }: { snapshot?: SystemSnapshot; error?: unknown }) {
  const [label, cls, Icon] = error
    ? (error instanceof ApiError && error.status === 503
      ? ['Model not loaded', 'border-medium/40 bg-medium-soft text-medium', AlertOctagon]
      : ['API unreachable', 'border-high/40 bg-high-soft text-high', PlugZap])
    : snapshot?.health.model_loaded
      ? ['Healthy', 'border-low/40 bg-low-soft text-low', CheckCircle2]
      : ['Checking…', 'border-border bg-surface text-muted', Activity]
  return (
    <span role="status" className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium ${cls}`}>
      <Icon aria-hidden className="size-4" /> {label}
    </span>
  )
}

export function SystemPanel() {
  const poll = usePolling(fetchSystem, POLL_MS)
  const now = useNow()
  const snap = poll.data
  const stale = Boolean(poll.error && snap)
  const ago = poll.updatedAt ? Math.max(0, Math.round((now - poll.updatedAt) / 1000)) : null

  const points = poll.history.map(({ t, data }) => {
    const { stats } = scoringLatency(data.metrics)
    return { t, p50: stats.p50, p95: stats.p95 }
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill snapshot={snap} error={poll.error} />
          {snap?.health.model_version && (
            <span className="rounded-full border border-border bg-surface px-3 py-1 text-sm text-muted">
              Model <span className="font-medium text-fg">{snap.health.model_name ?? 'model'} {snap.health.model_version}</span>
            </span>
          )}
        </div>
        <p className="text-xs text-muted" aria-live="off">
          {ago === null ? `Polling ${apiUrl()} every ${POLL_MS / 1000} s` : `Updated ${ago}s ago, every ${POLL_MS / 1000} s`}
        </p>
      </div>

      {poll.error !== undefined && (
        <div className="space-y-2">
          <ErrorState
            title={stale ? 'Lost contact with the API' : 'Can’t reach the API'}
            message={`${stale ? 'Showing the last values received. ' : ''}Nothing is answering at ${apiUrl()}. Start the API from the project folder, and this page reconnects by itself (it retries every ${POLL_MS / 1000} s).`}
            onRetry={poll.retry} />
          {!(poll.error instanceof ApiError && poll.error.status === 503) && <CopyCommand command="uvicorn api.main:app --no-access-log" />}
        </div>
      )}

      {poll.loading ? <Skeleton rows={4} label="Loading API status" /> : snap && <SystemBody snap={snap} points={points} stale={stale} />}
    </div>
  )
}

function SystemBody({ snap, points, stale }: { snap: SystemSnapshot; points: { t: number; p50: number | null; p95: number | null }[]; stale: boolean }) {
  const m = snap.metrics
  const { source, stats } = scoringLatency(m)
  const endpoints = Object.entries(m.latency_ms.by_endpoint).sort((a, b) => b[1].count - a[1].count)
  const risk = m.risk_levels
  const riskTotal = risk.LOW + risk.MEDIUM + risk.HIGH

  return (
    <div className={`space-y-4 transition-opacity ${stale ? 'opacity-50 grayscale' : ''}`} aria-busy={stale}>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Uptime" icon={Clock} tone="emerald" value={formatDuration(m.uptime_seconds)}
          hint={`Since ${new Date(m.started_at).toLocaleTimeString()}`} />
        <KpiCard label="Requests" icon={Server} tone="violet" value={formatCount(m.requests.total)}
          hint={`${formatCount(m.requests.by_endpoint['POST /predict'] ?? 0)} to /predict`} delay={60} />
        <KpiCard label="Errors" icon={AlertOctagon} tone="rose" value={formatCount(m.errors.total)} delay={120}
          hint={m.errors.total ? Object.entries(m.errors.by_status).map(([s, n]) => `${n}× ${s}`).join(', ') : 'No failed requests'} />
        <KpiCard label="Scoring latency" icon={Gauge} tone="cyan" delay={180}
          value={<span>{formatMs(stats.p50)} <span className="text-base font-normal text-muted">p50</span></span>}
          hint={`p95 ${formatMs(stats.p95)}, p99 ${formatMs(stats.p99)} (${source})`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
        <section aria-labelledby="latency-title" className="rounded-2xl border border-border bg-surface p-4">
          <h3 id="latency-title" className="font-semibold">Latency over time</h3>
          <p className="mb-3 mt-0.5 text-xs text-muted">
            Rolling p50 and p95 for {source} over the API’s last {formatCount(m.latency_ms.window)} requests, sampled at each poll.
          </p>
          <LatencyChart points={points} />
        </section>

        <div className="space-y-4">
          <section aria-labelledby="risk-title" className="rounded-2xl border border-border bg-surface p-4">
            <h3 id="risk-title" className="font-semibold">Risk levels scored</h3>
            {riskTotal === 0 ? (
              <p className="mt-2 text-sm text-muted">No transactions scored since the API started.</p>
            ) : (
              <>
                <div aria-hidden className="mt-3 flex h-3 gap-0.5 overflow-hidden rounded-full">
                  <span className="bg-low" style={{ width: `${(risk.LOW / riskTotal) * 100}%` }} />
                  <span className="bg-medium" style={{ width: `${(risk.MEDIUM / riskTotal) * 100}%` }} />
                  <span className="bg-high" style={{ width: `${(risk.HIGH / riskTotal) * 100}%` }} />
                </div>
                <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                  {(['LOW', 'MEDIUM', 'HIGH'] as const).map((k) => (
                    <div key={k}>
                      <dt className="text-xs text-muted">{k[0] + k.slice(1).toLowerCase()}</dt>
                      <dd className="font-semibold tabular-nums">{formatCount(risk[k])}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </section>

          <section aria-labelledby="storage-title" className="rounded-2xl border border-border bg-surface p-4">
            <h3 id="storage-title" className="flex items-center gap-2 font-semibold"><Database aria-hidden className="size-4 text-emerald" /> Supabase writes</h3>
            {m.storage.enabled ? (
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div><dt className="text-xs text-muted">Rows saved</dt><dd className="font-semibold tabular-nums">{formatCount(m.storage.rows_written)}</dd></div>
                <div><dt className="text-xs text-muted">Rows failed</dt><dd className={`font-semibold tabular-nums ${m.storage.rows_failed ? 'text-high' : ''}`}>{formatCount(m.storage.rows_failed)}</dd></div>
              </dl>
            ) : <p className="mt-2 text-sm text-muted">Storage is off: the API scores but doesn’t save (SUPABASE_URL not set).</p>}
          </section>
        </div>
      </div>

      <section aria-labelledby="endpoints-title" className="overflow-hidden rounded-2xl border border-border bg-surface">
        <h3 id="endpoints-title" className="px-4 pt-4 font-semibold">Endpoints</h3>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Endpoint latency table (scrolls sideways)">
          <table className="mt-2 w-full min-w-[32rem] text-sm">
            <thead className="border-y border-border bg-surface-2/60 text-left text-xs text-muted">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Endpoint</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Requests</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">p50</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">p95</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">p99</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {endpoints.map(([name, s]) => (
                <tr key={name}>
                  <td className="px-4 py-2 font-mono text-xs">{name}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatCount(s.count)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatMs(s.p50)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatMs(s.p95)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatMs(s.p99)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-4 py-3 text-xs text-muted">
          Figures are {m.scope}. They include this page’s own /health and /metrics checks.
        </p>
      </section>
    </div>
  )
}
