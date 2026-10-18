import { apiGet } from './api'

export interface Health {
  status: string
  model_loaded: boolean
  model_version: string | null
  model_name: string | null
  trained_at: string | null
}

export interface Percentiles { count: number; p50: number | null; p95: number | null; p99: number | null }

/** GET /metrics (MetricsResponse in api/schemas.py). */
export interface ApiMetrics {
  uptime_seconds: number
  started_at: string
  requests: { total: number; by_endpoint: Record<string, number> }
  errors: { total: number; by_status: Record<string, number> }
  latency_ms: Percentiles & { window: number; by_endpoint: Record<string, Percentiles> }
  risk_levels: Record<'LOW' | 'MEDIUM' | 'HIGH', number>
  storage: { enabled: boolean; writes_ok: number; writes_failed: number; rows_written: number; rows_failed: number }
  scope: string
}

export interface SystemSnapshot { health: Health; metrics: ApiMetrics }

export async function fetchSystem(signal?: AbortSignal): Promise<SystemSnapshot> {
  const [health, metrics] = await Promise.all([apiGet<Health>('/health', { signal }), apiGet<ApiMetrics>('/metrics', { signal })])
  return { health, metrics }
}

export const PREDICT = 'POST /predict'

/** Scoring latency: POST /predict when it has traffic, otherwise all requests. */
export function scoringLatency(m: ApiMetrics): { source: string; stats: Percentiles } {
  const predict = m.latency_ms.by_endpoint[PREDICT]
  return predict && predict.count > 0 ? { source: PREDICT, stats: predict } : { source: 'all requests', stats: m.latency_ms }
}
