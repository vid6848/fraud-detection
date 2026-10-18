import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiStatusContext, type ApiPhase } from '../apiStatus/context'
import { useDemoStream } from '../hooks/useDemoStream'
import { fakeApi, idleDemo, json, runningDemo } from '../test/fakeApi'
import { fakeSession, renderWithProviders } from '../test/render'
import { ToastProvider } from '../toast/ToastProvider'
import { DemoStreamControl } from './DemoStreamControl'

function Harness() {
  return <DemoStreamControl demo={useDemoStream()} />
}

function renderControl({ phase = 'ready', session = fakeSession }: { phase?: ApiPhase; session?: typeof fakeSession | null } = {}) {
  return renderWithProviders(
    <ApiStatusContext.Provider value={{ phase, since: null, retry: () => {} }}>
      <ToastProvider><Harness /></ToastProvider>
    </ApiStatusContext.Provider>,
    { auth: { session } },
  )
}

const button = () => screen.getByRole('button', { name: /demo stream|streaming|starting|waiting/i })

describe('DemoStreamControl', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('starts a stream with the analyst’s token, shows progress, then a finished toast', async () => {
    let gets = 0
    const fetchMock = fakeApi({
      'GET /demo/stream': () => {
        gets += 1
        if (gets === 1) return json(200, idleDemo)
        if (gets === 2) return json(200, runningDemo({ sent: 120 }))
        return json(200, { running: false, max_rows: 200, run: { ...runningDemo().run, state: 'completed', sent: 200 } })
      },
      'POST /demo/stream': () => json(202, runningDemo({ sent: 0 })),
    })
    vi.stubGlobal('fetch', fetchMock)
    renderControl()
    await waitFor(() => expect(button()).toBeEnabled())
    expect(button()).toHaveTextContent('Start demo stream')

    await userEvent.click(button())
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect((post[1]!.headers as Record<string, string>).Authorization).toBe('Bearer test-token')
    expect(await screen.findByText('Streaming 0 / 200')).toBeInTheDocument()
    expect(button()).toBeDisabled()

    expect(await screen.findByText('Streaming 120 / 200', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Demo stream progress' })).toHaveAttribute('aria-valuenow', '120')

    expect(await screen.findByText('Demo stream finished', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByText('200 transactions scored and saved.')).toBeInTheDocument()
    expect(button()).toHaveTextContent('Start demo stream')
  })

  it('shows progress for a stream that was already running', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /demo/stream': () => json(200, runningDemo({ sent: 40 })) }))
    renderControl()
    expect(await screen.findByText('Streaming 40 / 200')).toBeInTheDocument()
    expect(button()).toBeDisabled()
  })

  it('explains a rate limit using Retry-After', async () => {
    vi.stubGlobal('fetch', fakeApi({
      'GET /demo/stream': () => json(200, idleDemo),
      'POST /demo/stream': () => json(429, { error: { code: 'rate_limited', message: 'Try again later' } }, { 'Retry-After': '42' }),
    }))
    renderControl()
    await waitFor(() => expect(button()).toBeEnabled())
    await userEvent.click(button())
    expect(await screen.findByRole('alert')).toHaveTextContent('Demo streams are rate-limited. Try again in 42 s.')
    expect(button()).toBeEnabled()
  })

  it('on 409 picks up the stream someone else started', async () => {
    let gets = 0
    vi.stubGlobal('fetch', fakeApi({
      'GET /demo/stream': () => json(200, ++gets === 1 ? idleDemo : runningDemo({ sent: 7 })),
      'POST /demo/stream': () => json(409, { error: { code: 'conflict', message: 'A demo stream is already running' } }),
    }))
    renderControl()
    await waitFor(() => expect(button()).toBeEnabled())
    await userEvent.click(button())
    expect(await screen.findByRole('alert')).toHaveTextContent(/already running/)
    expect(await screen.findByText('Streaming 7 / 200')).toBeInTheDocument()
  })

  it('tells the analyst to sign in again on 401', async () => {
    vi.stubGlobal('fetch', fakeApi({
      'GET /demo/stream': () => json(200, idleDemo),
      'POST /demo/stream': () => json(401, { error: { code: 'unauthorized', message: 'Invalid or expired analyst token' } }),
    }))
    renderControl()
    await waitFor(() => expect(button()).toBeEnabled())
    await userEvent.click(button())
    expect(await screen.findByRole('alert')).toHaveTextContent(/session has expired/)
  })

  it('hides itself when the API has no demo stream (503)', async () => {
    const fetchMock = fakeApi({ 'GET /demo/stream': () => json(503, { error: { code: 'service_unavailable', message: 'x' } }) })
    vi.stubGlobal('fetch', fetchMock)
    renderControl()
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument())
  })

  it('waits for the API before asking about the demo stream', () => {
    const fetchMock = fakeApi({})
    vi.stubGlobal('fetch', fetchMock)
    renderControl({ phase: 'waking' })
    expect(button()).toHaveTextContent('Waiting for the API…')
    expect(button()).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('is disabled without a session', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /demo/stream': () => json(200, idleDemo) }))
    renderControl({ session: null })
    await waitFor(() => expect(button()).toHaveTextContent('Start demo stream'))
    expect(button()).toBeDisabled()
  })

  it('reports a stream that stopped early', async () => {
    let gets = 0
    vi.stubGlobal('fetch', fakeApi({
      'GET /demo/stream': () => json(200, ++gets === 1 ? runningDemo({ sent: 3 })
        : { running: false, max_rows: 200, run: { ...runningDemo().run, state: 'failed', sent: 3, failed: 5 } }),
    }))
    renderControl()
    expect(await screen.findByText('Demo stream stopped early', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByText('3 of 200 transactions sent, 5 failed.')).toBeInTheDocument()
  })
})
