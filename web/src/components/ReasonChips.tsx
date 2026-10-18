import { reasonLabel } from '../lib/format'
import type { Reason } from '../lib/types'

export function ReasonChips({ reasons }: { reasons: Reason[] }) {
  if (!reasons.length) return <span className="text-muted">None</span>
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Reasons">
      {reasons.map((r) => (
        <li key={r.code} title={r.message}
          className="rounded-md border border-border bg-surface-2 px-1.5 py-0.5 text-xs text-fg/85">
          {reasonLabel(r.code)}
          <span className="sr-only">: {r.message}</span>
        </li>
      ))}
    </ul>
  )
}
