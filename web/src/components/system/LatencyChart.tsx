import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface LatencyPoint { t: number; p50: number | null; p95: number | null }

const clock = (t: number) => new Date(t).toLocaleTimeString([], { minute: '2-digit', second: '2-digit' })

/** Rolling p50 / p95 latency, one point per poll. */
export function LatencyChart({ points }: { points: LatencyPoint[] }) {
  if (points.length < 2) {
    return <p className="grid h-56 place-items-center rounded-xl bg-surface-2/60 text-sm text-muted">Collecting samples… the chart fills in every 5 seconds.</p>
  }
  const latest = points[points.length - 1]!
  return (
    <figure>
      <div className="h-56" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="t" tickFormatter={clock} tick={{ fill: 'var(--muted)', fontSize: 11 }} stroke="var(--border)" minTickGap={48} />
            <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} stroke="var(--border)" width={56} unit=" ms" allowDecimals={false} />
            <Tooltip
              labelFormatter={(t) => clock(Number(t))}
              formatter={(v) => [`${Number(v).toFixed(1)} ms`]}
              contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, fontSize: 12 }}
              labelStyle={{ color: 'var(--muted)' }}
              itemStyle={{ color: 'var(--fg)' }}
            />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: 'var(--muted)' }} />
            <Line type="monotone" dataKey="p50" name="p50" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
            <Line type="monotone" dataKey="p95" name="p95" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">
        Latest p50 {latest.p50 ?? 'n/a'} ms, p95 {latest.p95 ?? 'n/a'} ms, over {points.length} samples.
      </figcaption>
    </figure>
  )
}
