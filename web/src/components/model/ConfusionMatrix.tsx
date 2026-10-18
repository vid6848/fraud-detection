import type { Confusion } from '../../lib/modelRuns'

/** The four outcomes at the alert threshold, labelled in analyst terms. */
export function ConfusionMatrix({ cm }: { cm: Confusion }) {
  const cells = [
    { key: 'tp', label: 'Fraud caught', n: cm.tp, cls: 'bg-emerald/10 border-emerald/50', dot: 'bg-emerald' },
    { key: 'fn', label: 'Fraud missed', n: cm.fn, cls: 'bg-rose/10 border-rose/50', dot: 'bg-rose' },
    { key: 'fp', label: 'False alarms', n: cm.fp, cls: 'bg-amber/10 border-amber/50', dot: 'bg-amber' },
    { key: 'tn', label: 'Legit, not flagged', n: cm.tn, cls: 'bg-surface-2 border-border', dot: 'bg-muted' },
  ]
  return (
    <table className="w-full border-separate border-spacing-2 text-sm">
      <caption className="sr-only">Test-set confusion matrix at the alert threshold</caption>
      <thead>
        <tr>
          <td />
          <th scope="col" className="pb-1 text-xs font-medium text-muted">Flagged</th>
          <th scope="col" className="pb-1 text-xs font-medium text-muted">Not flagged</th>
        </tr>
      </thead>
      <tbody>
        {[['Actually fraud', cells[0]!, cells[1]!], ['Actually legit', cells[2]!, cells[3]!]].map(([rowLabel, a, b]) => (
          <tr key={rowLabel as string}>
            <th scope="row" className="w-24 pr-1 text-left text-xs font-medium text-muted">{rowLabel as string}</th>
            {[a, b].map((c) => {
              const cell = c as (typeof cells)[number]
              return (
                <td key={cell.key} className={`rounded-xl border p-3 text-center ${cell.cls}`}>
                  <span className="block text-2xl font-semibold tabular-nums">{cell.n.toLocaleString()}</span>
                  <span className="mt-0.5 flex items-center justify-center gap-1.5 text-xs text-muted">
                    <span aria-hidden className={`size-2 rounded-full ${cell.dot}`} />{cell.label}
                  </span>
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
