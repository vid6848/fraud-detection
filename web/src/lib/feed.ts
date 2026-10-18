import type { Transaction } from './types'

/** The feed keeps only the newest rows in memory. */
export const FEED_CAP = 200
const MINUTE_MS = 60_000

export interface FeedRow extends Transaction {
  /** Arrived over Realtime (not part of the first load): gets a brief highlight. */
  live?: boolean
}

export interface FeedState {
  status: 'loading' | 'ready' | 'error'
  error: string | null
  rows: FeedRow[]
  /** Rows that arrived while paused; shown when the analyst resumes. */
  buffer: FeedRow[]
  paused: boolean
  /** created_at (ms) of every row seen in the last minute, uncapped, for the rate KPI. */
  recent: { id: string; t: number }[]
}

export type FeedAction =
  | { type: 'loading' }
  | { type: 'loaded'; rows: Transaction[] }
  | { type: 'failed'; error: string }
  | { type: 'received'; row: Transaction }
  | { type: 'pause' }
  | { type: 'resume' }

export const initialFeed: FeedState = { status: 'loading', error: null, rows: [], buffer: [], paused: false, recent: [] }

const time = (r: { created_at: string }) => Date.parse(r.created_at)

/** Newest first, no duplicate ids (a row can arrive over Realtime and in the first load), capped. */
export function mergeRows<T extends Transaction>(incoming: T[], existing: T[], cap = FEED_CAP): T[] {
  const seen = new Set<string>()
  return [...incoming, ...existing]
    .filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)))
    // Rows written in one batch share created_at; fall back to the dataset's own clock.
    .sort((a, b) => time(b) - time(a) || b.time_seconds - a.time_seconds)
    .slice(0, cap)
}

function track(recent: FeedState['recent'], rows: Transaction[]): FeedState['recent'] {
  const ids = new Set(recent.map((r) => r.id))
  const next = [...recent, ...rows.filter((r) => !ids.has(r.id)).map((r) => ({ id: r.id, t: time(r) }))]
  const newest = Math.max(0, ...next.map((r) => r.t))
  return next.filter((r) => newest - r.t <= MINUTE_MS)
}

export function feedReducer(state: FeedState, action: FeedAction): FeedState {
  switch (action.type) {
    case 'loading':
      return { ...state, status: 'loading', error: null }
    case 'loaded':
      return { ...state, status: 'ready', error: null, rows: mergeRows(state.rows, action.rows), recent: track(state.recent, action.rows) }
    case 'failed':
      return { ...state, status: 'error', error: action.error }
    case 'received': {
      const row: FeedRow = { ...action.row, live: true }
      const recent = track(state.recent, [row])
      return state.paused
        ? { ...state, recent, buffer: mergeRows([row], state.buffer) }
        : { ...state, recent, rows: mergeRows([row], state.rows) }
    }
    case 'pause':
      return { ...state, paused: true }
    case 'resume':
      return { ...state, paused: false, rows: mergeRows(state.buffer, state.rows), buffer: [] }
  }
}

export interface FeedKpis {
  perMinute: number
  flagged: number
  flaggedPct: number | null
  avgLatencyMs: number | null
  sample: number
}

/**
 * KPI maths. "Now" is the later of the browser clock and the newest row, so a
 * browser clock that runs behind the database doesn't hide the last minute.
 */
export function computeKpis(state: Pick<FeedState, 'rows' | 'recent'>, nowMs: number): FeedKpis {
  const newest = Math.max(0, ...state.recent.map((r) => r.t))
  const now = Math.max(nowMs, newest)
  const perMinute = state.recent.filter((r) => now - r.t <= MINUTE_MS).length
  const flagged = state.rows.filter((r) => r.risk_level !== 'LOW').length
  const latencies = state.rows.map((r) => r.latency_ms).filter((v): v is number => v !== null && Number.isFinite(v))
  return {
    perMinute,
    flagged,
    flaggedPct: state.rows.length ? (flagged / state.rows.length) * 100 : null,
    avgLatencyMs: latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null,
    sample: state.rows.length,
  }
}
