import type { Tone } from '../KpiCard'

const TONE: Record<Tone, { text: string; band: string; dot: string; bar: string }> = {
  violet: { text: 'text-violet', band: 'bg-violet/25', dot: 'bg-violet', bar: 'bg-violet' },
  cyan: { text: 'text-cyan', band: 'bg-cyan/25', dot: 'bg-cyan', bar: 'bg-cyan' },
  amber: { text: 'text-amber', band: 'bg-amber/25', dot: 'bg-amber', bar: 'bg-amber' },
  rose: { text: 'text-rose', band: 'bg-rose/25', dot: 'bg-rose', bar: 'bg-rose' },
  emerald: { text: 'text-emerald', band: 'bg-emerald/25', dot: 'bg-emerald', bar: 'bg-emerald' },
}

/**
 * A test-set metric with its bootstrap 95% confidence interval, drawn as a band on a
 * fixed scale with the point estimate as a dot. The numbers are always printed too.
 */
export function MetricCard({ label, value, interval, scale, format, note, tone, delay = 0 }: {
  label: string
  value: number
  interval?: { low: number; high: number }
  scale: [number, number]
  format: (n: number) => string
  note?: string
  tone: Tone
  delay?: number
}) {
  const t = TONE[tone]
  const [min, max] = scale
  const pos = (n: number) => `${Math.min(100, Math.max(0, ((n - min) / (max - min)) * 100))}%`
  return (
    <div className="relative animate-rise-in overflow-hidden rounded-2xl border border-border bg-surface p-4" style={{ animationDelay: `${delay}ms` }}>
      <div aria-hidden className={`absolute inset-x-0 top-0 h-0.5 ${t.bar} opacity-70`} />
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1.5 text-3xl font-semibold tracking-tight tabular-nums">{format(value)}</p>
      {interval && (
        <>
          <div aria-hidden className="relative mt-3 h-2 rounded-full bg-surface-2">
            <span className={`absolute inset-y-0 animate-grow-x rounded-full ${t.band}`}
              style={{ left: pos(interval.low), width: `calc(${pos(interval.high)} - ${pos(interval.low)})`, animationDelay: `${delay + 200}ms` }} />
            <span className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface ${t.dot}`}
              style={{ left: pos(value) }} />
          </div>
          <p className="mt-2 text-xs text-muted tabular-nums">95% CI {format(interval.low)}–{format(interval.high)}</p>
        </>
      )}
      {note && <p className="mt-2 text-xs leading-relaxed text-muted">{note}</p>}
    </div>
  )
}
