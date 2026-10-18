import { env } from './env'

/** An API failure: `status` is 0 when the API couldn't be reached at all. */
export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export function apiUrl(): string {
  return env.ok ? env.config.apiUrl : ''
}

/** GET a JSON endpoint of the FastAPI service. Errors use its `{"error": {code, message}}` shape. */
export async function apiGet<T>(path: string, { token, signal }: { token?: string; signal?: AbortSignal } = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${apiUrl()}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'network error')
  }
  if (!res.ok) {
    let message = res.statusText
    let code: string | undefined
    try {
      const body = await res.json()
      message = body?.error?.message ?? message
      code = body?.error?.code
    } catch {
      // non-JSON error body: keep the status text
    }
    throw new ApiError(res.status, message, code)
  }
  return res.json() as Promise<T>
}

/** What to tell an analyst when an API call fails. */
export function apiErrorMessage(error: unknown): { title: string; message: string } {
  if (!(error instanceof ApiError)) {
    return { title: 'Something went wrong', message: error instanceof Error ? error.message : String(error) }
  }
  switch (error.status) {
    case 0:
      return { title: 'Can’t reach the API', message: `No response from ${apiUrl()}. Is uvicorn running? Start it with: uvicorn api.main:app` }
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
