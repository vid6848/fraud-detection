import { BellRing, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useReducedMotion } from '../../hooks/useReducedMotion'
import { formatCurrency, formatProbability, reasonLabel } from '../../lib/format'
import { makeSampleStream, type SampleTx } from '../../lib/sampleStream'
import { RiskBadge } from '../RiskBadge'

const VISIBLE = 6
const TRAY = 3
const TICK_MS = 1100

const RAIL = { LOW: 'bg-low/70', MEDIUM: 'bg-medium', HIGH: 'bg-high' } as const

function seed(next: () => SampleTx, count: number) {
  return Array.from({ length: count }, next).reverse()
}

/**
 * The landing page's centrepiece: sample payments stream in and get scored;
 * flagged ones drop into a small alert tray. Purely illustrative.
 */
export function ScoringPreview() {
  const reduced = useReducedMotion()
  const [next] = useState(() => makeSampleStream())
  const [rows, setRows] = useState<SampleTx[]>(() => seed(next, VISIBLE))
  const [tray, setTray] = useState<SampleTx[]>(() => rows.filter((r) => r.risk !== 'LOW').slice(0, TRAY))
  const [scored, setScored] = useState(18_437)

  useEffect(() => {
    if (reduced) return
    const id = setInterval(() => {
      const tx = next()
      setRows((r) => [tx, ...r].slice(0, VISIBLE))
      setScored((n) => n + 1)
      if (tx.risk !== 'LOW') setTray((t) => [tx, ...t].slice(0, TRAY))
    }, TICK_MS)
    return () => clearInterval(id)
  }, [reduced, next])

  return (
    <figure className="relative">
      <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_24px_60px_-30px_rgba(20,20,80,0.45)]">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <span aria-hidden className="relative flex size-2">
              {!reduced && <span className="absolute inset-0 animate-ping rounded-full bg-low opacity-60" />}
              <span className="relative size-2 rounded-full bg-low" />
            </span>
            Scoring stream
          </div>
          <span className="text-xs text-muted tabular-nums">{scored.toLocaleString()} scored</span>
        </div>

        <ol aria-label="Sample scored payments" className="divide-y divide-border">
          {rows.map((tx) => (
            <li key={tx.id} className={`relative grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 py-2.5 pl-5 pr-4 sm:grid-cols-[6.5rem_1fr_auto] ${reduced ? '' : 'animate-tape-in'}`}>
              <span aria-hidden className={`absolute inset-y-2 left-2 w-[3px] rounded-full ${RAIL[tx.risk]}`} />
              <span className="font-semibold tabular-nums">{formatCurrency(tx.amount)}</span>
              <span className="order-3 col-span-2 flex items-center gap-2 text-xs text-muted sm:order-none sm:col-span-1">
                <span className="tabular-nums">{formatProbability(tx.probability)}</span>
                <span className="inline-flex items-center gap-0.5"><Zap aria-hidden className="size-3" />{tx.latencyMs.toFixed(1)} ms</span>
                {tx.reasons[0] && <span className="hidden truncate lg:inline">{reasonLabel(tx.reasons[0].code)}</span>}
              </span>
              <RiskBadge level={tx.risk} />
            </li>
          ))}
        </ol>

        <div className="border-t border-border bg-surface-2/60 px-4 py-3">
          <p className="flex items-center gap-2 text-xs font-medium text-muted">
            <BellRing aria-hidden className="size-3.5" /> Sent to the alert queue
          </p>
          <ul className="mt-2 flex min-h-8 flex-wrap gap-2" aria-label="Sample alerts">
            {tray.map((tx) => (
              <li key={tx.id} className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-xs tabular-nums ${
                tx.risk === 'HIGH' ? 'border-high/40 bg-high-soft text-high' : 'border-medium/40 bg-medium-soft text-medium'} ${reduced ? '' : 'animate-chip-in'}`}>
                <span className="font-semibold">{tx.risk === 'HIGH' ? 'High' : 'Medium'}</span>
                <span className="text-fg/80">{formatCurrency(tx.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <figcaption className="mt-3 text-xs text-muted">
        Animated preview with sample data. Sign in to see the real feed.
      </figcaption>
    </figure>
  )
}
