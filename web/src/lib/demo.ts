import { ApiError, apiGet, apiPost, unreachableMessage } from './api'

/** GET/POST /demo/stream (DemoStreamStatus in api/schemas.py). */
export interface DemoRun {
  id: string
  state: 'running' | 'completed' | 'failed' | 'cancelled'
  total: number
  sent: number
  failed: number
  rate_per_s: number
  started_at: string
  finished_at: string | null
}

export interface DemoStatus { running: boolean; max_rows: number; run: DemoRun | null }

export const fetchDemoStatus = (signal?: AbortSignal) => apiGet<DemoStatus>('/demo/stream', { signal })

export const startDemoStream = (token: string) => apiPost<DemoStatus>('/demo/stream', { token })

/** Why a demo stream couldn't start, in words an analyst can act on. */
export function demoErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error)
  switch (error.status) {
    case 0:
      return unreachableMessage()
    case 401:
      return 'Your session has expired. Sign out and sign in again.'
    case 409:
      return 'A demo stream is already running. Its transactions are arriving below.'
    case 429:
      return error.retryAfterS
        ? `Demo streams are rate-limited. Try again in ${formatWait(error.retryAfterS)}.`
        : 'Demo streams are rate-limited. Try again in a minute.'
    case 503:
      return 'The demo stream isn’t available on this API (it needs Supabase storage configured).'
    default:
      return `The API answered ${error.status}: ${error.message}`
  }
}

export function formatWait(seconds: number): string {
  if (seconds < 90) return `${Math.ceil(seconds)} s`
  return `${Math.ceil(seconds / 60)} min`
}
