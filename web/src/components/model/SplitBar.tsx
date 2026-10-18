import { ArrowRight } from 'lucide-react'
import type { RunMetrics } from '../../lib/modelRuns'

const PARTS = [
  { key: 'train', label: 'Train', cls: 'bg-series-1', dot: 'bg-series-1' },
  { key: 'validation', label: 'Validation', cls: 'bg-series-2', dot: 'bg-series-2' },
  { key: 'test', label: 'Test', cls: 'bg-amber', dot: 'bg-amber' },
] as const

/** The time-ordered split: one bar, widths proportional to row counts. */
export function SplitBar({ split }: { split: NonNullable<RunMetrics['split']> }) {
  const total = PARTS.reduce((n, p) => n + split[p.key].rows, 0)
  return (
    <div>
      <div aria-hidden className="flex h-3 gap-0.5 overflow-hidden rounded-full">
        {PARTS.map((p, i) => (
          <span key={p.key} className={`h-full origin-left animate-grow-x ${p.cls}`}
            style={{ width: `${(split[p.key].rows / total) * 100}%`, animationDelay: `${i * 120}ms` }} />
        ))}
      </div>
      <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
        Ordered by time <ArrowRight aria-hidden className="size-3" /> no future data leaks into training
      </p>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        {PARTS.map((p) => {
          const s = split[p.key]
          return (
            <div key={p.key}>
              <dt className="flex items-center gap-1.5 text-sm font-medium"><span aria-hidden className={`size-2.5 rounded-sm ${p.dot}`} />{p.label}</dt>
              <dd className="mt-1 text-xs text-muted tabular-nums">
                {s.rows.toLocaleString()} rows<br />{s.frauds} frauds ({s.fraud_pct.toFixed(2)}%)
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}
