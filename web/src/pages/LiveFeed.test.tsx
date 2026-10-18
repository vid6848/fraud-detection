import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeApi, idleDemo, json } from '../test/fakeApi'
import { createFakeSupabase, makeTx } from '../test/fakeSupabase'
import { fakeSession, renderWithProviders } from '../test/render'
import { LiveFeed } from './LiveFeed'

let fake = createFakeSupabase()
vi.mock('../lib/supabase', () => ({ getSupabase: () => fake.client }))

const renderFeed = () => renderWithProviders(<LiveFeed />, { auth: { session: fakeSession }, route: '/app' })
// The table is the desktop view; jsdom renders both views, so scope queries to it.
const table = () => screen.getByRole('table')

describe('LiveFeed', () => {
  beforeEach(() => {
    fake = createFakeSupabase({ transactions: { data: [] }, alerts: { count: 0 } })
    vi.stubGlobal('fetch', fakeApi({ 'GET /demo/stream': () => json(200, idleDemo) }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the waiting state pointing to the demo stream, with local instructions folded away', async () => {
    renderFeed()
    expect(await screen.findByText('Waiting for transactions')).toBeInTheDocument()
    expect(screen.getByText(/Click/)).toHaveTextContent('Click Start demo stream above')
    expect(screen.getByText('Running the project locally?')).toBeInTheDocument()
    expect(screen.getByText('python -m simulator --rate 20')).toBeInTheDocument()
    expect(screen.getByText('Live')).toBeInTheDocument()
  })

  it('has a Start demo stream button in the header', async () => {
    renderFeed()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start demo stream' })).toBeEnabled())
  })

  it('shows an error with a retry button when loading fails', async () => {
    let fail = true
    fake = createFakeSupabase({
      transactions: () => (fail ? { error: { message: 'permission denied' } } : { data: [makeTx()] }),
      alerts: { count: 0 },
    })
    renderFeed()
    expect(await screen.findByText('Couldn’t load transactions')).toBeInTheDocument()
    expect(screen.getByText('permission denied')).toBeInTheDocument()
    fail = false
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('renders rows with amount, probability, risk and reasons, plus the KPIs', async () => {
    fake = createFakeSupabase({
      transactions: { data: [
        makeTx({ id: 'a', amount: 0.5, probability: 0.93, risk_level: 'HIGH', latency_ms: 10,
          reasons: [{ code: 'TINY_AMOUNT', message: 'Charge under $1.00' }] }),
        makeTx({ id: 'b', amount: 120, latency_ms: 20 }),
      ] },
      alerts: { count: 3 },
    })
    renderFeed()
    const rows = within(await screen.findByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]!).getByText('$0.50')).toBeInTheDocument()
    expect(within(rows[0]!).getByText('93.0%')).toBeInTheDocument()
    expect(within(rows[0]!).getByText('High')).toBeInTheDocument()
    expect(within(rows[0]!).getByText('Tiny amount')).toHaveAttribute('title', 'Charge under $1.00')
    // Animated numbers render a visual copy and a screen-reader copy; check the latter.
    const srText = (t: string) => screen.getAllByText(t).find((el) => el.classList.contains('sr-only'))
    expect(srText('50.0%')).toBeTruthy() // flagged
    expect(srText('15 ms')).toBeTruthy() // average latency
    await waitFor(() => expect(srText('3')).toBeTruthy()) // open alerts
  })

  it('adds Realtime inserts to the top, and holds them while paused', async () => {
    fake = createFakeSupabase({ transactions: { data: [makeTx({ id: 'a', amount: 1 })] }, alerts: { count: 0 } })
    renderFeed()
    await screen.findByRole('table')

    act(() => fake.emit('transactions', 'INSERT', makeTx({ id: 'b', amount: 2 })))
    expect(within(table()).getAllByRole('row')[1]).toHaveTextContent('$2.00')

    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    act(() => fake.emit('transactions', 'INSERT', makeTx({ id: 'c', amount: 3 })))
    expect(within(table()).queryByText('$3.00')).not.toBeInTheDocument()
    expect(screen.getByText('1 new')).toBeInTheDocument()
    expect(screen.getByText('Paused')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /resume/i }))
    expect(within(table()).getAllByRole('row')[1]).toHaveTextContent('$3.00')
  })

  it('warns when the Realtime connection drops', async () => {
    fake = createFakeSupabase({ transactions: { data: [makeTx()] }, alerts: { count: 0 } })
    renderFeed()
    await screen.findByRole('table')
    act(() => fake.setChannelStatus('CHANNEL_ERROR'))
    expect(screen.getByText('Live updates disconnected')).toBeInTheDocument()
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
  })

  it('subscribes to transaction inserts and cleans up on unmount', async () => {
    const { unmount } = renderFeed()
    await screen.findByText(/waiting for transactions/i)
    const ch = fake.client.channel.mock.results[0]!.value
    expect(ch.on).toHaveBeenCalledWith('postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'transactions' }, expect.any(Function))
    unmount()
    expect(fake.client.removeChannel).toHaveBeenCalled()
  })
})
