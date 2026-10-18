import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createFakeSupabase, isOp, makeTx, type QueryCall } from '../test/fakeSupabase'
import { fakeSession, renderWithProviders } from '../test/render'
import { ToastProvider } from '../toast/ToastProvider'
import { Alerts } from './Alerts'

let fake = createFakeSupabase()
vi.mock('../lib/supabase', () => ({ getSupabase: () => fake.client }))

const at = (min: number) => new Date(Date.UTC(2026, 9, 18, 12, min)).toISOString()
const alertRow = (id: number, severity: string, min: number, extra: Record<string, unknown> = {}) => ({
  id, transaction_id: `tx-${id}`, severity, status: 'open', reviewed_by: null, reviewed_at: null, created_at: at(min),
  transactions: makeTx({ id: `tx-${id}`, amount: id * 10, probability: severity === 'HIGH' ? 0.93 : 0.12, risk_level: severity }),
  ...extra,
})

const EXPLANATION = {
  transaction_id: 'tx-1', probability: 0.93, risk_level: 'HIGH', model_version: '1.0.0', model_score: 0.96, base_value: 0.5,
  stored_probability: 0.93, stored_model_version: '1.0.0',
  top_features: [{ feature: 'V14', value: -8.5, shap_value: 0.124, direction: 'raises_risk', description: 'V14 = -8.56 (much lower than typical) pushed fraud risk up' }],
}

/** Alerts table: list query returns `rows` (filtered by an eq('status') if present); single-row reads by id. */
function alertsTable(rows: ReturnType<typeof alertRow>[], overrides: (call: QueryCall) => object | undefined = () => undefined) {
  return (call: QueryCall) => {
    const custom = overrides(call)
    if (custom) return custom
    const idEq = call.ops.find(([m, a]) => m === 'eq' && a[0] === 'id')
    if (idEq) return { data: { ...rows.find((r) => r.id === idEq[1][1]), feedback: [] } }
    const statusEq = call.ops.find(([m, a]) => m === 'eq' && a[0] === 'status')
    return { data: statusEq ? rows.filter((r) => r.status === statusEq[1][1]) : rows }
  }
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status })

function renderAlerts(route = '/app/alerts') {
  return renderWithProviders(
    <ToastProvider><Routes><Route path="/app/alerts" element={<Alerts />} /></Routes></ToastProvider>,
    { auth: { session: fakeSession }, route },
  )
}

const rowsInList = () => within(screen.getByRole('list', { name: 'Alerts' })).getAllByRole('button')

describe('Alerts', () => {
  beforeEach(() => {
    fake = createFakeSupabase({ alerts: alertsTable([alertRow(1, 'MEDIUM', 5), alertRow(2, 'HIGH', 1), alertRow(3, 'HIGH', 3)]) })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, EXPLANATION)))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('lists open alerts, HIGH first then newest', async () => {
    renderAlerts()
    await screen.findByRole('list', { name: 'Alerts' })
    expect(rowsInList().map((b) => b.id)).toEqual(['alert-row-3', 'alert-row-2', 'alert-row-1'])
    expect(screen.getByText('3 alerts')).toBeInTheDocument()
    const listQuery = fake.calls.find((c) => c.table === 'alerts')!
    expect(listQuery.ops).toContainEqual(['eq', ['status', 'open']])
  })

  it('filters by severity, and re-queries when the status filter changes', async () => {
    renderAlerts()
    await screen.findByRole('list', { name: 'Alerts' })
    await userEvent.click(screen.getByRole('radio', { name: 'Medium' }))
    expect(rowsInList().map((b) => b.id)).toEqual(['alert-row-1'])

    await userEvent.click(screen.getByRole('radio', { name: 'Confirmed fraud' }))
    expect(await screen.findByText('No alerts match these filters')).toBeInTheDocument()
    expect(fake.calls.some((c) => c.ops.some(([m, a]) => m === 'eq' && a[1] === 'confirmed_fraud'))).toBe(true)

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByText('3 alerts')).toBeInTheDocument()
  })

  it('shows a calm empty state when nothing is open, and an error with retry', async () => {
    fake = createFakeSupabase({ alerts: { data: [] } })
    const { unmount } = renderAlerts()
    expect(await screen.findByText('No open alerts')).toBeInTheDocument()
    unmount()

    fake = createFakeSupabase({ alerts: { error: { message: 'permission denied for table alerts' } } })
    renderAlerts()
    expect(await screen.findByText('Couldn’t load alerts')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('opens the detail panel with transaction facts and SHAP bars from /explain (with the analyst token)', async () => {
    renderAlerts()
    await screen.findByRole('list', { name: 'Alerts' })
    await userEvent.click(document.getElementById('alert-row-2')!)
    const dialog = await screen.findByRole('dialog', { name: 'Alert #2' })
    expect(await within(dialog).findByText('V14 = -8.56 (much lower than typical) pushed fraud risk up', { exact: false })).toBeInTheDocument()
    expect(within(dialog).getByText('$20.00')).toBeInTheDocument()
    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(String(url)).toMatch(/\/explain\/tx-2$/)
    expect((init as RequestInit).headers).toEqual({ Authorization: 'Bearer test-token' })
  })

  it('closes on Escape and returns focus to the alert row', async () => {
    renderAlerts('/app/alerts')
    await screen.findByRole('list', { name: 'Alerts' })
    await userEvent.click(document.getElementById('alert-row-3')!)
    await screen.findByRole('dialog')
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await waitFor(() => expect(document.activeElement?.id).toBe('alert-row-3'))
  })

  it.each([
    [401, 'Your session has expired'],
    [503, 'API unavailable'],
  ])('explains an /explain %s error', async (status, title) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(status, { error: { code: 'x', message: 'nope' } })))
    renderAlerts('/app/alerts?id=2')
    expect(await screen.findByText(title)).toBeInTheDocument()
  })

  it('records a verdict: guarded status update, then feedback with the note', async () => {
    fake = createFakeSupabase({
      alerts: alertsTable([alertRow(2, 'HIGH', 1)], (call) => (isOp(call, 'update') ? { data: [{ id: 2 }] } : undefined)),
      feedback: {},
    })
    renderAlerts('/app/alerts?id=2')
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/note/i), 'Customer denied it')
    expect(within(dialog).getByText('18 / 2000')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm fraud' }))

    expect(await screen.findByText('Confirmed as fraud')).toBeInTheDocument() // toast
    const update = fake.calls.find((c) => isOp(c, 'update'))!
    expect(update.ops).toEqual([['update', [{ status: 'confirmed_fraud' }]], ['eq', ['id', 2]], ['eq', ['status', 'open']], ['select', ['id']]])
    const insert = fake.calls.find((c) => c.table === 'feedback')!
    expect(insert.ops).toEqual([['insert', [{ alert_id: 2, label: 'confirmed_fraud', note: 'Customer denied it' }]]])
  })

  it('offers to retry only the feedback when the status saved but feedback failed', async () => {
    let feedbackFails = true
    fake = createFakeSupabase({
      alerts: alertsTable([alertRow(2, 'HIGH', 1)], (call) => (isOp(call, 'update') ? { data: [{ id: 2 }] } : undefined)),
      feedback: () => (feedbackFails ? { error: { message: 'network down' } } : {}),
    })
    renderAlerts('/app/alerts?id=2')
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'False alarm' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('wasn’t saved to feedback: network down')

    feedbackFails = false
    await userEvent.click(within(dialog).getByRole('button', { name: /retry saving the verdict/i }))
    expect(await screen.findByText('Marked as a false alarm')).toBeInTheDocument()
    expect(fake.calls.filter((c) => isOp(c, 'update'))).toHaveLength(1) // status not re-sent
    expect(fake.calls.filter((c) => c.table === 'feedback')).toHaveLength(2)
  })

  it('shows the review history instead of buttons for a reviewed alert', async () => {
    fake = createFakeSupabase({
      alerts: alertsTable([alertRow(2, 'HIGH', 1, { status: 'false_alarm', reviewed_by: 'user-1', reviewed_at: at(30) })],
        (call) => (call.ops.some(([m, a]) => m === 'eq' && a[0] === 'id')
          ? { data: { ...alertRow(2, 'HIGH', 1, { status: 'false_alarm', reviewed_by: 'user-1', reviewed_at: at(30) }),
              feedback: [{ id: 9, label: 'false_alarm', note: 'Known customer', analyst: 'user-1', created_at: at(30) }] } }
          : undefined)),
    })
    renderAlerts('/app/alerts?id=2&status=all')
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText('Known customer')).toBeInTheDocument()
    expect(within(dialog).getByText(/by you/)).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Confirm fraud' })).not.toBeInTheDocument()
  })

  it('adds new alerts live, and drops reviewed ones from the open view', async () => {
    const rows = [alertRow(1, 'MEDIUM', 5)]
    fake = createFakeSupabase({ alerts: alertsTable(rows) })
    renderAlerts()
    await screen.findByRole('list', { name: 'Alerts' })

    rows.push(alertRow(4, 'HIGH', 9))
    await act(async () => fake.emit('alerts', 'INSERT', { id: 4, status: 'open' }))
    await waitFor(() => expect(rowsInList().map((b) => b.id)).toEqual(['alert-row-4', 'alert-row-1']))

    await act(async () => fake.emit('alerts', 'UPDATE', { id: 1, status: 'false_alarm' }))
    expect(rowsInList().map((b) => b.id)).toEqual(['alert-row-4'])
  })
})
