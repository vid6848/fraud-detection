import { vi } from 'vitest'

type Result = { data?: unknown; error?: { message: string } | null; count?: number | null }
/** What a query did: its table and the chain of builder calls, e.g. [['update', [{status}]], ['eq', ['id', 1]]]. */
export type QueryCall = { table: string; ops: [string, unknown[]][] }
const has = (call: QueryCall, method: string) => call.ops.some(([m]) => m === method)
export const isOp = has
type Handler = { table: string; event: string; cb: (payload: { eventType: string; new: unknown }) => void }

/**
 * A tiny stand-in for the Supabase client: chainable, awaitable queries that resolve to
 * canned results per table, and Realtime channels whose events tests can fire with `emit`.
 */
export function createFakeSupabase(tables: Record<string, Result | ((call: QueryCall) => Result)> = {}) {
  const calls: QueryCall[] = []
  const handlers: Handler[] = []
  const channels: { status: (s: string) => void }[] = []

  function query(table: string) {
    const call: QueryCall = { table, ops: [] }
    calls.push(call)
    const builder: Record<string, unknown> = {}
    for (const m of ['select', 'order', 'limit', 'eq', 'in', 'neq', 'single', 'maybeSingle', 'insert', 'update']) {
      builder[m] = vi.fn((...args: unknown[]) => { call.ops.push([m, args]); return builder })
    }
    builder.then = (resolve: (r: unknown) => unknown, reject: (e: unknown) => unknown) => {
      const entry = tables[table]
      const r = (typeof entry === 'function' ? entry(call) : entry) ?? { data: [] }
      return Promise.resolve({ data: r.data ?? null, error: r.error ?? null, count: r.count ?? null }).then(resolve, reject)
    }
    return builder
  }

  const client = {
    from: vi.fn(query),
    channel: vi.fn(() => {
      const ch = {
        on: vi.fn((_type: string, filter: { table: string; event: string }, cb: Handler['cb']) => {
          handlers.push({ table: filter.table, event: filter.event, cb })
          return ch
        }),
        subscribe: vi.fn((cb?: (status: string) => void) => {
          channels.push({ status: (s) => cb?.(s) })
          cb?.('SUBSCRIBED')
          return ch
        }),
      }
      return ch
    }),
    removeChannel: vi.fn(),
  }

  return {
    client,
    tables,
    calls,
    emit(table: string, event: string, row: unknown) {
      handlers.filter((h) => h.table === table && (h.event === event || h.event === '*'))
        .forEach((h) => h.cb({ eventType: event, new: row }))
    },
    setChannelStatus(status: string) {
      channels.forEach((c) => c.status(status))
    },
  }
}

export function makeTx(overrides: Record<string, unknown> = {}) {
  return {
    id: 'tx-1',
    created_at: new Date().toISOString(),
    time_seconds: 100,
    amount: 42.5,
    hour_of_day: 13,
    probability: 0.0012,
    risk_level: 'LOW',
    reasons: [],
    model_version: '1.0.0',
    latency_ms: 6.5,
    ...overrides,
  }
}
