import { ChevronRight, FilterX, ShieldCheck } from 'lucide-react'
import { useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LiveIndicator } from '../components/LiveIndicator'
import { PageHeader } from '../components/PageHeader'
import { ReasonChips } from '../components/ReasonChips'
import { RiskBadge } from '../components/RiskBadge'
import { Segmented } from '../components/Segmented'
import { EmptyState, ErrorState, Skeleton } from '../components/StateViews'
import { StatusBadge } from '../components/StatusBadge'
import { useAlerts } from '../hooks/useAlerts'
import { matchesFilters, type Alert, type SeverityFilter, type StatusFilter } from '../lib/alerts'
import { formatCurrency, formatFeedTime, formatProbability } from '../lib/format'
import { AlertDetail } from './AlertDetail'

const SEVERITIES: { value: SeverityFilter; label: string }[] = [
  { value: 'all', label: 'All' }, { value: 'HIGH', label: 'High' }, { value: 'MEDIUM', label: 'Medium' },
]
const STATUSES: { value: StatusFilter; label: string }[] = [
  { value: 'open', label: 'Open' }, { value: 'confirmed_fraud', label: 'Confirmed fraud' },
  { value: 'false_alarm', label: 'False alarm' }, { value: 'all', label: 'All' },
]

const pick = <T extends string>(value: string | null, options: { value: T }[], fallback: T): T =>
  (options.find((o) => o.value === value)?.value ?? fallback)

export function Alerts() {
  const [params, setParams] = useSearchParams()
  const severity = pick(params.get('severity'), SEVERITIES, 'all')
  const status = pick(params.get('status'), STATUSES, 'open')
  const selectedId = Number(params.get('id')) || null
  const { loading, alerts, error, live, retry } = useAlerts(status)
  const lastOpened = useRef<number | null>(null)

  const setParam = useCallback((key: string, value: string | null) => {
    setParams((p) => {
      const next = new URLSearchParams(p)
      if (value === null) next.delete(key)
      else next.set(key, value)
      return next
    })
  }, [setParams])

  const open = (id: number) => { lastOpened.current = id; setParam('id', String(id)) }
  const close = useCallback(() => {
    setParam('id', null)
    // Return focus to the row that opened the panel (keyboard users keep their place).
    const id = lastOpened.current
    requestAnimationFrame(() => document.getElementById(`alert-row-${id}`)?.focus())
  }, [setParam])

  const visible = alerts.filter((a) => matchesFilters(a, severity, status))
  const filtered = severity !== 'all' || status !== 'open'

  return (
    <>
      <PageHeader title="Alerts"
        description="Transactions the API flagged as Medium or High risk. High comes first, then the newest."
        actions={<LiveIndicator status={live} />} />

      <div className="mb-5 flex flex-wrap items-end gap-x-6 gap-y-3">
        <Segmented legend="Severity" name="severity" options={SEVERITIES} value={severity}
          onChange={(v) => setParam('severity', v === 'all' ? null : v)} />
        <Segmented legend="Status" name="status" options={STATUSES} value={status}
          onChange={(v) => setParam('status', v === 'open' ? null : v)} />
        {!loading && !error && (
          <p className="pb-2 text-sm text-muted" aria-live="polite">
            {visible.length} {visible.length === 1 ? 'alert' : 'alerts'}
          </p>
        )}
      </div>

      {loading ? <Skeleton rows={5} label="Loading alerts" />
        : error ? <ErrorState title="Couldn’t load alerts" message={error} onRetry={retry} />
        : visible.length === 0 ? (
          filtered ? (
            <EmptyState title="No alerts match these filters" icon={<FilterX className="size-8" />}>
              <button type="button" onClick={() => setParams(new URLSearchParams())}
                className="mt-1 font-medium text-accent hover:underline">Clear filters</button>
            </EmptyState>
          ) : (
            <EmptyState title="No open alerts" icon={<ShieldCheck className="size-8" />}>
              New Medium and High scores appear here as soon as the API flags them.
            </EmptyState>
          )
        ) : (
          <ul className="overflow-hidden rounded-xl border border-border bg-surface" aria-label="Alerts">
            {visible.map((a, i) => (
              <AlertRow key={a.id} alert={a} selected={a.id === selectedId} first={i === 0} onOpen={() => open(a.id)} />
            ))}
          </ul>
        )}

      {selectedId !== null && <AlertDetail id={selectedId} onClose={close} />}
    </>
  )
}

function AlertRow({ alert, selected, first, onOpen }: { alert: Alert; selected: boolean; first: boolean; onOpen: () => void }) {
  const tx = alert.transaction
  return (
    <li className={first ? '' : 'border-t border-border'}>
      <button type="button" id={`alert-row-${alert.id}`} onClick={onOpen} aria-current={selected || undefined}
        className={`grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-3.5 text-left transition-colors hover:bg-surface-2 md:grid-cols-[6rem_7rem_1fr_9rem_auto] ${
          selected ? 'bg-accent-soft/60' : ''}`}>
        <span className="flex items-center gap-2 md:block"><RiskBadge level={alert.severity} /></span>
        <span className="justify-self-end text-base font-semibold tabular-nums md:justify-self-start">
          {tx ? formatCurrency(tx.amount) : '–'}
        </span>
        <span className="col-span-2 min-w-0 md:col-span-1">
          <span className="block text-sm text-muted">
            Fraud probability <span className="font-medium text-fg tabular-nums">{tx ? formatProbability(tx.probability) : '–'}</span>
          </span>
          {tx && tx.reasons.length > 0 && <span className="mt-1 block"><ReasonChips reasons={tx.reasons} /></span>}
        </span>
        <span className="text-sm text-muted tabular-nums">
          <time dateTime={alert.created_at}>{formatFeedTime(alert.created_at)}</time>
        </span>
        <span className="flex items-center justify-end gap-2">
          <StatusBadge status={alert.status} />
          <ChevronRight aria-hidden className="size-4 text-muted" />
        </span>
        <span className="sr-only">Alert #{alert.id}, open details</span>
      </button>
    </li>
  )
}
