import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function KpiCard({ label, value, hint, icon: Icon, tone = 'default' }: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: LucideIcon
  tone?: 'default' | 'alert'
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted">{label}</p>
        <Icon aria-hidden className={`size-4 ${tone === 'alert' ? 'text-high' : 'text-muted'}`} />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  )
}
