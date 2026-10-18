import { env } from './env'

/** An API failure: `status` is 0 when the API couldn't be reached at all. */
export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string, public retryAfterS?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export function apiUrl(): string {
  return env.ok ? env.config.apiUrl : ''
}

/** True when the dashboard talks to an API on this machine (development), not a deployed one. */
export function isLocalApi(url = apiUrl()): boolean {
  try {
    return ['localhost', '127.0.0.1', '[::1]'].includes(new URL(url).hostname)
  } catch {
    return false
  }
}

/**
 * Fire-and-forget GET /health at start-up: a sleeping free-tier API starts waking while the
 * visitor reads the landing page or logs in, instead of after they reach the dashboard.
 */
export function wakeApi(): void {
  if (!apiUrl()) return
  fetch(`${apiUrl()}/health`).catch(() => {})
}

interface RequestOptions { token?: string; signal?: AbortSignal; body?: unknown }

/** Call the FastAPI service. Errors use its `{"error": {code, message}}` shape. */
async function apiRequest<T>(method: 'GET' | 'POST', path: string, { token, signal, body }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(`${apiUrl()}${path}`, {
      ...(method === 'GET' ? {} : { method }),
      headers,
      signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'network error')
  }
  if (!res.ok) {
    let message = res.statusText
    let code: string | undefined
    try {
      const errorBody = await res.json()
      message = errorBody?.error?.message ?? message
      code = errorBody?.error?.code
    } catch {
      // non-JSON error body: keep the status text
    }
    const retryAfter = Number(res.headers.get('Retry-After'))
    throw new ApiError(res.status, message, code, retryAfter > 0 ? retryAfter : undefined)
  }
  return res.json() as Promise<T>
}

export function apiGet<T>(path: string, options: Omit<RequestOptions, 'body'> = {}): Promise<T> {
  return apiRequest<T>('GET', path, options)
}

export function apiPost<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return apiRequest<T>('POST', path, options)
}

/** What to tell an analyst when the API can't be reached at all. */
export function unreachableMessage(): string {
  return isLocalApi()
    ? `No response from ${apiUrl()}. Is uvicorn running? Start it with: uvicorn api.main:app`
    : 'The API runs on a free plan and sleeps when idle; it can take about a minute to wake up. Try again shortly.'
}

/** What to tell an analyst when an API call fails. */
export function apiErrorMessage(error: unknown): { title: string; message: string } {
  if (!(error instanceof ApiError)) {
    return { title: 'Something went wrong', message: error instanceof Error ? error.message : String(error) }
  }
  switch (error.status) {
    case 0:
      return { title: 'Can’t reach the API', message: unreachableMessage() }
    case 401:
      return { title: 'Your session has expired', message: 'Sign out and sign in again to load explanations.' }
    case 404:
      return { title: 'Transaction not found', message: 'The API has no stored transaction with this id. It may have been deleted.' }
    case 503:
      return { title: 'API unavailable', message: `The API is running but not ready: ${error.message}` }
    default:
      return { title: `API error (${error.status})`, message: error.message }
  }
}
