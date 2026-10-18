import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiErrorMessage, apiGet } from './api'

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
