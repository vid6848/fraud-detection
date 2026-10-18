import { apiGet } from './api'

/** GET /drift (DriftResponse in api/schemas.py). */
export interface DriftBin { lower: number; upper: number; reference: number; live: number; contribution: number }

export type DriftStatus = 'OK' | 'Watch' | 'Alert' | 'Not enough data'

export interface DriftReport {
  status: DriftStatus
  psi: number | null
  live_rows: number
  window: number
  min_rows: number
  live_from: string | null
  live_to: string | null
  thresholds: { watch: number; alert: number }
  bins: DriftBin[]
  reference: { rows: number; source: string; model_version: string; created_at: string }
  model_version: string
}

export const fetchDrift = (token: string, signal?: AbortSignal) => apiGet<DriftReport>('/drift', { token, signal })

/** A score as a short percentage: 0.0005 -> "0.05%", 0.42857 -> "42.9%". */
export function scorePct(p: number): string {
  const pct = p * 100
  return `${Number(pct.toPrecision(pct < 1 ? 1 : 3))}%`
}

/** Bin label; the last two bins are the Medium and High risk bands. */
export function bandLabel(bins: DriftBin[], i: number): string {
  const { lower, upper } = bins[i]!
  if (i === 0) return `< ${scorePct(upper)}`
  if (i === bins.length - 1) return `≥ ${scorePct(lower)} (High)`
  const range = `${scorePct(lower)}–${scorePct(upper)}`
  return i === bins.length - 2 ? `${range} (Medium)` : range
}

/** Share of the live window in a bin, or of the training set, as a percentage string. */
export function sharePct(share: number): string {
  if (share === 0) return '0%'
  if (share < 0.001) return '<0.1%'
  return `${(share * 100).toFixed(1)}%`
}
