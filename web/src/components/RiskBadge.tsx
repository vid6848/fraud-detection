import { CircleCheck, OctagonAlert, TriangleAlert } from 'lucide-react'
import type { RiskLevel } from '../lib/types'

const STYLES: Record<RiskLevel, { cls: string; Icon: typeof CircleCheck; label: string }> = {
  LOW: { cls: 'bg-low-soft text-low', Icon: CircleCheck, label: 'Low' },
  MEDIUM: { cls: 'bg-medium-soft text-medium', Icon: TriangleAlert, label: 'Medium' },
  HIGH: { cls: 'bg-high-soft text-high', Icon: OctagonAlert, label: 'High' },
}

/** Risk level with colour, icon AND text, so it never relies on colour alone. */
export function RiskBadge({ level }: { level: RiskLevel }) {
  const { cls, Icon, label } = STYLES[level] ?? STYLES.LOW
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}>
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  )
}
