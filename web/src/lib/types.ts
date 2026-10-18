export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface Reason {
  code: string
  message: string
}

/** A row of public.transactions (without the V1–V28 `features` blob). */
export interface Transaction {
  id: string
  created_at: string
  time_seconds: number
  amount: number
  hour_of_day: number
  probability: number
  risk_level: RiskLevel
  reasons: Reason[]
  model_version: string
  latency_ms: number | null
}

export const TRANSACTION_COLUMNS =
  'id, created_at, time_seconds, amount, hour_of_day, probability, risk_level, reasons, model_version, latency_ms'

/** Normalise a row from PostgREST or a Realtime payload (numeric columns may arrive as strings). */
export function toTransaction(raw: Record<string, unknown>): Transaction {
  const latency = raw.latency_ms
  return {
    id: String(raw.id),
    created_at: String(raw.created_at),
    time_seconds: Number(raw.time_seconds),
    amount: Number(raw.amount),
    hour_of_day: Number(raw.hour_of_day),
    probability: Number(raw.probability),
    risk_level: raw.risk_level as RiskLevel,
    reasons: Array.isArray(raw.reasons) ? (raw.reasons as Reason[]) : [],
    model_version: String(raw.model_version ?? ''),
    latency_ms: latency === null || latency === undefined ? null : Number(latency),
  }
}
