import { vi } from 'vitest'
import type { DemoRun, DemoStatus } from '../lib/demo'

export const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })

type Handler = (init?: RequestInit) => Response | Promise<Response>

/** A fetch stub routing "METHOD /path" to handlers; anything else fails like a network error. */
export function fakeApi(routes: Record<string, Handler>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${new URL(url, 'http://api.test').pathname}`
    const handler = routes[key]
    if (!handler) throw new TypeError('Failed to fetch')
    return handler(init)
  })
}

export const HEALTHY = { status: 'ok', model_loaded: true, model_version: '1.0.0', model_name: 'random_forest', trained_at: null }

export function demoRun(overrides: Partial<DemoRun> = {}): DemoRun {
  return {
    id: 'run-1', state: 'running', total: 200, sent: 0, failed: 0, rate_per_s: 10,
    started_at: '2026-10-18T10:00:00+00:00', finished_at: null, ...overrides,
  }
}

export const idleDemo: DemoStatus = { running: false, max_rows: 200, run: null }
export const runningDemo = (overrides: Partial<DemoRun> = {}): DemoStatus =>
  ({ running: true, max_rows: 200, run: demoRun(overrides) })
