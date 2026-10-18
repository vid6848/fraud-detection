import { createContext, useContext } from 'react'

/**
 * - checking: first /health call in flight (not slow yet)
 * - ready: the model is loaded and answering
 * - waking: slow or failing, probably a free-tier cold start; still retrying
 * - down: still failing after the give-up time (or at once for a local API)
 */
export type ApiPhase = 'checking' | 'ready' | 'waking' | 'down'

export interface ApiStatus {
  phase: ApiPhase
  /** When the current slow/failing spell started (ms), or null while healthy. */
  since: number | null
  retry: () => void
}

export const ApiStatusContext = createContext<ApiStatus | null>(null)

const ASSUME_READY: ApiStatus = { phase: 'ready', since: null, retry: () => {} }

/** API reachability. Outside an ApiStatusProvider (public pages, unit tests) it is assumed ready. */
export function useApiStatus(): ApiStatus {
  return useContext(ApiStatusContext) ?? ASSUME_READY
}
