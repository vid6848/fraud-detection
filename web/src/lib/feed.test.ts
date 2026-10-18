import { describe, expect, it } from 'vitest'
import { makeTx } from '../test/fakeSupabase'
import { computeKpis, FEED_CAP, feedReducer, initialFeed, mergeRows, type FeedState } from './feed'
import { toTransaction } from './types'

const at = (sec: number) => new Date(Date.UTC(2026, 9, 18, 12, 0, sec)).toISOString()
const tx = (id: string, sec: number, extra: Record<string, unknown> = {}) =>
  toTransaction(makeTx({ id, created_at: at(sec), ...extra }))

describe('mergeRows', () => {
  it('sorts newest first and drops duplicate ids', () => {
    const rows = mergeRows([tx('b', 2), tx('a', 1)], [tx('a', 1), tx('c', 3)])
    expect(rows.map((r) => r.id)).toEqual(['c', 'b', 'a'])
  })

  it('breaks created_at ties with the dataset time', () => {
    const rows = mergeRows([tx('early', 5, { time_seconds: 10 }), tx('late', 5, { time_seconds: 20 })], [])
    expect(rows.map((r) => r.id)).toEqual(['late', 'early'])
  })

  it(`caps at ${FEED_CAP} rows`, () => {
    const many = Array.from({ length: FEED_CAP + 50 }, (_, i) => tx(`r${i}`, i))
    const rows = mergeRows(many, [])
    expect(rows).toHaveLength(FEED_CAP)
    expect(rows[0]!.id).toBe(`r${FEED_CAP + 49}`)
  })
})

describe('feedReducer', () => {
  const loaded = feedReducer(initialFeed, { type: 'loaded', rows: [tx('a', 1), tx('b', 2)] })

  it('starts loading and becomes ready with rows newest first', () => {
    expect(initialFeed.status).toBe('loading')
    expect(loaded.status).toBe('ready')
    expect(loaded.rows.map((r) => r.id)).toEqual(['b', 'a'])
  })

  it('keeps rows that arrived over Realtime before the first load finished', () => {
    const early = feedReducer(initialFeed, { type: 'received', row: tx('live', 9) })
    const after = feedReducer(early, { type: 'loaded', rows: [tx('a', 1), tx('live', 9)] })
    expect(after.rows.map((r) => r.id)).toEqual(['live', 'a'])
  })

  it('prepends live rows and marks them as live', () => {
    const next = feedReducer(loaded, { type: 'received', row: tx('c', 3) })
    expect(next.rows[0]).toMatchObject({ id: 'c', live: true })
    expect(next.rows[1]!.live).toBeUndefined()
  })

  it('buffers rows while paused and shows them on resume', () => {
    let s = feedReducer(loaded, { type: 'pause' })
    s = feedReducer(s, { type: 'received', row: tx('c', 3) })
    s = feedReducer(s, { type: 'received', row: tx('d', 4) })
    expect(s.rows.map((r) => r.id)).toEqual(['b', 'a'])
    expect(s.buffer.map((r) => r.id)).toEqual(['d', 'c'])
    s = feedReducer(s, { type: 'resume' })
    expect(s.paused).toBe(false)
    expect(s.buffer).toEqual([])
    expect(s.rows.map((r) => r.id)).toEqual(['d', 'c', 'b', 'a'])
  })

  it('records a load failure and clears it on retry', () => {
    const failed = feedReducer(initialFeed, { type: 'failed', error: 'boom' })
    expect(failed).toMatchObject({ status: 'error', error: 'boom' })
    expect(feedReducer(failed, { type: 'loading' })).toMatchObject({ status: 'loading', error: null })
  })
})

describe('computeKpis', () => {
  const state = (rows: ReturnType<typeof tx>[]): Pick<FeedState, 'rows' | 'recent'> =>
    feedReducer(initialFeed, { type: 'loaded', rows })

  it('handles an empty feed', () => {
    expect(computeKpis(state([]), Date.now())).toEqual({ perMinute: 0, flagged: 0, flaggedPct: null, avgLatencyMs: null, sample: 0 })
  })

  it('computes flagged share and average latency, ignoring missing latencies', () => {
    const k = computeKpis(state([
      tx('a', 1, { risk_level: 'HIGH', latency_ms: 10 }),
      tx('b', 2, { risk_level: 'MEDIUM', latency_ms: 20 }),
      tx('c', 3, { latency_ms: null }),
      tx('d', 4, { latency_ms: 30 }),
    ]), Date.parse(at(4)))
    expect(k).toMatchObject({ flagged: 2, flaggedPct: 50, avgLatencyMs: 20, sample: 4 })
  })

  it('counts rows in the last 60 seconds, beyond the 200-row display cap', () => {
    let s = feedReducer(initialFeed, { type: 'loaded', rows: [tx('old', 0)] })
    for (let i = 0; i < 300; i++) s = feedReducer(s, { type: 'received', row: tx(`n${i}`, 30 + (i % 30)) })
    expect(s.rows).toHaveLength(FEED_CAP)
    expect(computeKpis(s, Date.parse(at(70))).perMinute).toBe(300) // 'old' (70 s ago) not counted
  })

  it('uses the newest row as "now" when the browser clock is behind', () => {
    const s = state([tx('a', 50), tx('b', 55)])
    expect(computeKpis(s, Date.parse(at(0))).perMinute).toBe(2)
  })
})
