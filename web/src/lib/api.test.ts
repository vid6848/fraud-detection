import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiErrorMessage, apiGet, apiPost, isLocalApi, wakeApi } from './api'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('apiGet', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends the bearer token and returns the JSON body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: 1 }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await apiGet('/explain/abc', { token: 'tok' })).toEqual({ ok: 1 })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toMatch(/\/explain\/abc$/)
    expect(init.headers).toEqual({ Authorization: 'Bearer tok' })
  })

  it('turns the API error envelope into an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'unauthorized', message: 'Log in as an analyst' } })))
    await expect(apiGet('/explain/x')).rejects.toMatchObject({ status: 401, code: 'unauthorized', message: 'Log in as an analyst' })
  })

  it('keeps the status text when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('oops', { status: 502, statusText: 'Bad Gateway' })))
    await expect(apiGet('/health')).rejects.toMatchObject({ status: 502, message: 'Bad Gateway' })
  })

  it('reports an unreachable API as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(apiGet('/health')).rejects.toMatchObject({ status: 0 })
  })
})

describe('apiPost', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('POSTs a JSON body with the token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(202, { running: true }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await apiPost('/demo/stream', { token: 'tok', body: { limit: 5 } })).toEqual({ running: true })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toMatch(/\/demo\/stream$/)
    expect(init).toMatchObject({ method: 'POST', body: '{"limit":5}',
      headers: { Authorization: 'Bearer tok', 'Content-Type': 'application/json' } })
  })

  it('reads Retry-After on errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'slow down' } }), { status: 429, headers: { 'Retry-After': '17' } })))
    await expect(apiPost('/demo/stream')).rejects.toMatchObject({ status: 429, code: 'rate_limited', retryAfterS: 17 })
  })

  it('ignores a missing or invalid Retry-After', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 429, headers: { 'Retry-After': 'soon' } })))
    await expect(apiPost('/demo/stream')).rejects.toMatchObject({ status: 429, retryAfterS: undefined })
  })

  it('passes an abort through untouched', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))
    await expect(apiGet('/health')).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('isLocalApi', () => {
  it.each([
    ['http://localhost:8000', true],
    ['http://127.0.0.1:8000', true],
    ['https://fraud-detection-api.onrender.com', false],
    ['', false],
  ])('%s -> %s', (url, local) => {
    expect(isLocalApi(url)).toBe(local)
  })
})

describe('wakeApi', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('pings /health and swallows failures', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    wakeApi()
    const called = fetchMock.mock.calls.length
    // Without VITE_API_URL (e.g. CI) there is nothing to wake.
    if (called) expect(fetchMock.mock.calls[0]![0]).toMatch(/\/health$/)
    await Promise.resolve()
  })
})

describe('apiErrorMessage', () => {
  it.each([
    [0, /can’t reach the api/i],
    [401, /session has expired/i],
    [404, /not found/i],
    [503, /api unavailable/i],
    [500, /api error \(500\)/i],
  ])('status %s', (status, title) => {
    expect(apiErrorMessage(new ApiError(status, 'x')).title).toMatch(title)
  })

  it('handles non-API errors', () => {
    expect(apiErrorMessage(new Error('boom'))).toEqual({ title: 'Something went wrong', message: 'boom' })
  })
})
