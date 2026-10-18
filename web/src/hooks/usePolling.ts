import { useCallback, useEffect, useRef, useState } from 'react'

export interface PollState<T> {
  data?: T
  error?: unknown
  /** When the last successful response arrived (ms). */
  updatedAt?: number
  /** Successful responses, oldest first (capped). */
  history: { t: number; data: T }[]
}

/**
 * Call `fn` now and then every `intervalMs` (waiting for each call to finish). Polling pauses
 * while the tab is hidden and resumes immediately when it's visible again. On failure the
 * last good data is kept, so the UI can show it as stale.
 */
export function usePolling<T>(fn: (signal: AbortSignal) => Promise<T>, intervalMs: number, keep = 60) {
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })
  const [state, setState] = useState<PollState<T>>({ history: [] })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let ac: AbortController | undefined

    const schedule = () => { clearTimeout(timer); if (!stopped) timer = setTimeout(run, intervalMs) }
    async function run() {
      if (document.hidden) return // resumed by the visibility listener
      ac = new AbortController()
      try {
        const data = await fnRef.current(ac.signal)
        if (stopped) return
        const t = Date.now()
        setState((s) => ({ data, error: undefined, updatedAt: t, history: [...s.history, { t, data }].slice(-keep) }))
      } catch (error) {
        if (stopped || ac.signal.aborted) return
        setState((s) => ({ ...s, error }))
      }
      schedule()
    }
    const onVisible = () => {
      if (!document.hidden) { clearTimeout(timer); run() }
    }
    document.addEventListener('visibilitychange', onVisible)
    run()
    return () => {
      stopped = true
      clearTimeout(timer)
      ac?.abort()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [intervalMs, keep, attempt])

  return { ...state, loading: state.data === undefined && state.error === undefined, retry: useCallback(() => setAttempt((n) => n + 1), []) }
}
