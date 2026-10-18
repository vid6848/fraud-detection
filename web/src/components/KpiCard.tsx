import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export type Tone = 'violet' | 'cyan' | 'amber' | 'rose' | 'emerald'

// Static class names so Tailwind can see them.
const TONES: Record<Tone, { chip: string; glow: string; bar: string }> = {
  violet: { chip: 'bg-violet/15 text-violet', glow: 'from-violet/25', bar: 'bg-violet' },
  cyan: { chip: 'bg-cyan/15 text-cyan', glow: 'from-cyan/25', bar: 'bg-cyan' },
  amber: { chip: 'bg-amber/15 text-amber', glow: 'from-amber/25', bar: 'bg-amber' },
  rose: { chip: 'bg-rose/15 text-rose', glow: 'from-rose/25', bar: 'bg-rose' },
  emerald: { chip: 'bg-emerald/15 text-emerald', glow: 'from-emerald/25', bar: 'bg-emerald' },
}

export function KpiCard({ label, value, hint, icon: Icon, tone = 'violet', delay = 0 }: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: LucideIcon
  tone?: Tone
  /** Entrance stagger, in ms. */
  delay?: number
}) {
  const t = TONES[tone]
  return (
    <div className="group relative animate-rise-in overflow-hidden rounded-2xl border border-border bg-surface p-4 transition-transform duration-300 hover:-translate-y-0.5"
      style={{ animationDelay: `${delay}ms` }}>
      <div aria-hidden className={`pointer-events-none absolute -right-10 -top-10 size-32 rounded-full bg-gradient-to-br ${t.glow} to-transparent blur-2xl`} />
      <div aria-hidden className={`absolute inset-x-0 top-0 h-0.5 ${t.bar} opacity-70`} />
      <div className="relative flex items-center justify-between gap-2">
        <p className="text-sm text-muted">{label}</p>
        <span className={`grid size-8 place-items-center rounded-lg ${t.chip}`}>
          <Icon aria-hidden className="size-4" />
        </span>
      </div>
      <p className="relative mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="relative mt-1 text-xs text-muted">{hint}</p>}
    </div>
  )
}
