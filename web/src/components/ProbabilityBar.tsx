import { formatProbability } from '../lib/format'
import type { RiskLevel } from '../lib/types'

const RISK_BAR: Record<RiskLevel, string> = { LOW: 'bg-low', MEDIUM: 'bg-medium', HIGH: 'bg-high' }

/** Fraud probability as a number plus a small bar (the bar is decorative; the number is the content). */
export function ProbabilityBar({ probability, level }: { probability: number; level: RiskLevel }) {
  const width = Math.min(100, Math.max(0, probability * 100))
  return (
    <span className="flex items-center gap-2.5">
      <span className="w-14 text-right tabular-nums">{formatProbability(probability)}</span>
      <span aria-hidden className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
        <span className={`block h-full rounded-full ${RISK_BAR[level]}`} style={{ width: `max(${width}%, 3px)` }} />
      </span>
    </span>
  )
}
