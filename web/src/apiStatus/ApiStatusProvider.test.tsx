import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeApi, HEALTHY, json } from '../test/fakeApi'
import { ApiStatusProvider, GIVE_UP_MS, RECHECK_MS, RETRY_MS, SLOW_MS, TIMEOUT_MS } from './ApiStatusProvider'
import { useApiStatus } from './context'

function Probe() {
  const { phase, since, retry } = useApiStatus()
  return (
    <>
      <p>phase: {phase}</p>
      <p>since: {since === null ? 'none' : 'set'}</p>
      <button type="button" onClick={retry}>retry</button>
    </>
  )
}

const renderProvider = (giveUpMs = GIVE_UP_MS) =>
  render(<ApiStatusProvider giveUpMs={giveUpMs}><Probe /></ApiStatusProvider>)
const phase = () => screen.getByText(/^phase:/).textContent

/** Let pending fetch promises settle under fake timers. */
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0) })
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

describe('ApiStatusProvider', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('is ready when /health answers quickly with the model loaded', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': () => json(200, HEALTHY) }))
    renderProvider()
    expect(phase()).toBe('phase: checking')
    await flush()
    expect(phase()).toBe('phase: ready')
    expect(screen.getByText('since: none')).toBeInTheDocument()
  })

  it('shows waking while a slow first call is still in flight, then ready', async () => {
    let answer: (r: Response) => void = () => {}
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { answer = resolve })))
    renderProvider()
    await advance(SLOW_MS - 1)
    expect(phase()).toBe('phase: checking')
    await advance(1)
    expect(phase()).toBe('phase: waking')
    expect(screen.getByText('since: set')).toBeInTheDocument()
    await act(async () => { answer(json(200, HEALTHY)) })
    expect(phase()).toBe('phase: ready')
    expect(screen.getByText('since: none')).toBeInTheDocument()
  })

  it('keeps retrying while the API fails, and gives up after the give-up time', async () => {
    const fetchMock = fakeApi({}) // every call fails like a sleeping server
    vi.stubGlobal('fetch', fetchMock)
    renderProvider(10_000)
    await flush()
    expect(phase()).toBe('phase: waking')
    await advance(RETRY_MS)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(phase()).toBe('phase: waking')
    await advance(10_000)
    expect(phase()).toBe('phase: down')
  })

  it('abandons a hung call after the timeout and tries again', async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    vi.stubGlobal('fetch', fetchMock)
    renderProvider()
    await advance(TIMEOUT_MS)
    expect(phase()).toBe('phase: waking')
    await advance(RETRY_MS)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('treats a 503 (model still loading) as not up yet', async () => {
    let calls = 0
    vi.stubGlobal('fetch', fakeApi({
      'GET /health': () => (++calls === 1 ? json(503, { status: 'unavailable', model_loaded: false }) : json(200, HEALTHY)),
    }))
    renderProvider()
    await flush()
    expect(phase()).toBe('phase: waking')
    await advance(RETRY_MS)
    expect(phase()).toBe('phase: ready')
  })

  it('reports a local API as down at once (no cold start to wait for)', async () => {
    vi.stubGlobal('fetch', fakeApi({}))
    renderProvider(0)
    await flush()
    expect(phase()).toBe('phase: down')
  })

  it('re-checks while healthy and notices when the API goes to sleep', async () => {
    let up = true
    const fetchMock = fakeApi({ 'GET /health': () => (up ? json(200, HEALTHY) : json(502, {})) })
    vi.stubGlobal('fetch', fetchMock)
    renderProvider()
    await flush()
    expect(phase()).toBe('phase: ready')
    up = false
    await advance(RECHECK_MS)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(phase()).toBe('phase: waking')
  })

  it('retry starts over from checking', async () => {
    vi.stubGlobal('fetch', fakeApi({}))
    renderProvider(0)
    await flush()
    expect(phase()).toBe('phase: down')
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': () => json(200, HEALTHY) }))
    act(() => screen.getByRole('button', { name: 'retry' }).click())
    expect(phase()).toBe('phase: checking')
    await flush()
    expect(phase()).toBe('phase: ready')
  })

  it('pauses while the tab is hidden and checks again when it is shown', async () => {
    const fetchMock = fakeApi({ 'GET /health': () => json(200, HEALTHY) })
    vi.stubGlobal('fetch', fetchMock)
    renderProvider()
    await flush()
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    await advance(RECHECK_MS * 3)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    hidden.mockReturnValue(false)
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    await flush()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('stops checking after unmount', async () => {
    const fetchMock = fakeApi({ 'GET /health': () => json(200, HEALTHY) })
    vi.stubGlobal('fetch', fetchMock)
    const { unmount } = renderProvider()
    await flush()
    unmount()
    await advance(RECHECK_MS * 2)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('useApiStatus outside a provider', () => {
  it('assumes the API is ready', () => {
    render(<Probe />)
    expect(phase()).toBe('phase: ready')
    act(() => screen.getByRole('button', { name: 'retry' }).click()) // no-op, no crash
  })
})
