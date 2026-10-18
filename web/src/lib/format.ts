const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const usdWhole = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

export const formatCurrency = (n: number) => usd.format(n)
export const formatCurrencyWhole = (n: number) => usdWhole.format(n)

/** Fraud probability as a percentage; small values keep two decimals so 0.12% ≠ 0%. */
export function formatProbability(p: number): string {
  if (!Number.isFinite(p)) return '–'
  const pct = p * 100
  if (pct === 0) return '0%'
  if (pct < 0.01) return '<0.01%'
  return `${pct.toFixed(pct >= 10 ? 1 : 2)}%`
}

export function formatPercent(pct: number | null, digits = 1): string {
  return pct === null || !Number.isFinite(pct) ? '–' : `${pct.toFixed(digits)}%`
}

export function formatMs(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return '–'
  return ms < 10 ? `${ms.toFixed(1)} ms` : `${Math.round(ms)} ms`
}

export function formatClock(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '–' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/** Feed timestamps: just the clock for today, date + clock for older rows. */
export function formatFeedTime(iso: string, now = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '–'
  return d.toDateString() === now.toDateString() ? formatClock(iso) : formatDateTime(iso)
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '–'
    : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/** Short labels for the API's reason codes (the full message is shown as a tooltip). */
const REASON_LABELS: Record<string, string> = {
  MODEL_HIGH_RISK: 'Model: high risk',
  MODEL_MEDIUM_RISK: 'Model: elevated',
  TINY_AMOUNT: 'Tiny amount',
  NIGHT_HOURS: 'Night hours',
  RULES_ESCALATED: 'Rules escalated',
}

export function reasonLabel(code: string): string {
  return REASON_LABELS[code] ?? code.toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}
