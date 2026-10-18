import { CircleDot, ShieldCheck, ShieldX } from 'lucide-react'
import { STATUS_LABELS, type AlertStatus } from '../lib/alerts'

const STYLES = {
  open: { Icon: CircleDot, cls: 'border-accent/40 text-accent' },
  confirmed_fraud: { Icon: ShieldX, cls: 'border-high/40 text-high' },
  false_alarm: { Icon: ShieldCheck, cls: 'border-low/40 text-low' },
} as const

export function StatusBadge({ status }: { status: AlertStatus }) {
  const { Icon, cls } = STYLES[status]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      <Icon aria-hidden className="size-3.5" />
      {STATUS_LABELS[status]}
    </span>
  )
}
