import { Trophy } from 'lucide-react'
import { comparisonRows, formatParams, type RunMetrics } from '../../lib/modelRuns'

/** Best setting per model family on validation PR-AUC, bars on a 0–1 scale. */
export function ModelComparison({ metrics }: { metrics: RunMetrics }) {
  const rows = comparisonRows(metrics)
  if (!rows.length) return <p className="text-sm text-muted">This run has no model comparison.</p>
  return (
    <ul className="space-y-4" aria-label="Models compared on validation PR-AUC, best first">
      {rows.map((r, i) => (
        <li key={r.key}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <p className="flex items-center gap-2 font-medium">
              {r.name}
              {r.selected && (
                <span className="bg-brand inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-accent-fg">
                  <Trophy aria-hidden className="size-3" /> Deployed
                </span>
              )}
            </p>
            <p className="text-sm tabular-nums"><span className="text-muted">PR-AUC </span><span className="font-semibold">{r.prAuc.toFixed(3)}</span></p>
          </div>
          <div aria-hidden className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-surface-2">
            <div className={`h-full origin-left animate-grow-x rounded-full ${r.selected ? 'bg-brand' : 'bg-muted/40'}`}
              style={{ width: `${r.prAuc * 100}%`, animationDelay: `${i * 90}ms` }} />
          </div>
          <p className="mt-1 text-xs text-muted">{r.strategy}, {formatParams(r.params)}</p>
        </li>
      ))}
    </ul>
  )
}
