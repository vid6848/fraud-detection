import type { SupabaseClient } from '@supabase/supabase-js'
import { describe, expect, it } from 'vitest'
import { createFakeSupabase, isOp } from '../test/fakeSupabase'
import { matchesFilters, reviewAlert, saveFeedback, sortAlerts, toAlert, type Alert } from './alerts'

const alert = (id: number, severity: 'HIGH' | 'MEDIUM', minute: number, status: Alert['status'] = 'open') =>
  toAlert({ id, transaction_id: `t${id}`, severity, status, created_at: new Date(Date.UTC(2026, 9, 18, 12, minute)).toISOString(), transactions: null })

describe('alert queue order and filters', () => {
  it('puts HIGH before MEDIUM, then newest first', () => {
    const sorted = sortAlerts([alert(1, 'MEDIUM', 9), alert(2, 'HIGH', 1), alert(3, 'HIGH', 5), alert(4, 'MEDIUM', 2)])
    expect(sorted.map((a) => a.id)).toEqual([3, 2, 1, 4])
  })

  it('filters by severity and status', () => {
    const a = alert(1, 'HIGH', 0, 'false_alarm')
    expect(matchesFilters(a, 'all', 'all')).toBe(true)
    expect(matchesFilters(a, 'HIGH', 'false_alarm')).toBe(true)
    expect(matchesFilters(a, 'MEDIUM', 'all')).toBe(false)
    expect(matchesFilters(a, 'all', 'open')).toBe(false)
  })

  it('normalises the embedded transaction and sorts feedback newest first', () => {
    const a = toAlert({
      id: '7', transaction_id: 'x', severity: 'HIGH', status: 'open', created_at: '2026-10-18T00:00:00Z',
      transactions: { id: 'x', amount: '12.50', probability: '0.9', risk_level: 'HIGH', reasons: null, created_at: '2026-10-18T00:00:00Z' },
      feedback: [{ id: 1, created_at: '2026-10-18T01:00:00Z' }, { id: 2, created_at: '2026-10-18T02:00:00Z' }],
    })
    expect(a.id).toBe(7)
    expect(a.transaction).toMatchObject({ amount: 12.5, probability: 0.9, reasons: [] })
    expect(a.feedback!.map((f) => f.id)).toEqual([2, 1])
  })
})

describe('reviewAlert', () => {
  const client = (fake: ReturnType<typeof createFakeSupabase>) => fake.client as unknown as SupabaseClient

  it('sets the status only if still open, then saves feedback with the trimmed note', async () => {
    const fake = createFakeSupabase({ alerts: { data: [{ id: 5 }] }, feedback: {} })
    expect(await reviewAlert(client(fake), 5, 'confirmed_fraud', '  card stolen  ')).toEqual({ ok: true })
    const [update, insert] = fake.calls
    expect(update).toEqual({ table: 'alerts', ops: [
      ['update', [{ status: 'confirmed_fraud' }]], ['eq', ['id', 5]], ['eq', ['status', 'open']], ['select', ['id']],
    ] })
    expect(insert).toEqual({ table: 'feedback', ops: [['insert', [{ alert_id: 5, label: 'confirmed_fraud', note: 'card stolen' }]]] })
  })

  it('stores an empty note as null', async () => {
    const fake = createFakeSupabase({ feedback: {} })
    await saveFeedback(client(fake), 5, 'false_alarm', '   ')
    expect(fake.calls[0]!.ops[0]).toEqual(['insert', [{ alert_id: 5, label: 'false_alarm', note: null }]])
  })

  it('reports a conflict when another analyst got there first (no feedback written)', async () => {
    const fake = createFakeSupabase({ alerts: { data: [] } })
    const r = await reviewAlert(client(fake), 5, 'false_alarm', '')
    expect(r).toMatchObject({ ok: false, stage: 'conflict' })
    expect(fake.calls.some((c) => c.table === 'feedback')).toBe(false)
  })

  it('reports which step failed', async () => {
    const statusFails = createFakeSupabase({ alerts: { error: { message: 'permission denied' } } })
    expect(await reviewAlert(client(statusFails), 5, 'false_alarm', '')).toEqual({ ok: false, stage: 'status', message: 'permission denied' })

    const feedbackFails = createFakeSupabase({
      alerts: (call) => (isOp(call, 'update') ? { data: [{ id: 5 }] } : { data: [] }),
      feedback: { error: { message: 'new row violates row-level security policy' } },
    })
    expect(await reviewAlert(client(feedbackFails), 5, 'false_alarm', ''))
      .toEqual({ ok: false, stage: 'feedback', message: 'new row violates row-level security policy' })
  })
})
