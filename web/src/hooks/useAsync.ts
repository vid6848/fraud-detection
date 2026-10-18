import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Run `fn` whenever `key` changes (null = don't run). Stale results are dropped and
 * in-flight requests aborted. `reload` re-runs it; `refresh` re-runs it without
 * hiding the current data.
 */
export function useAsync<T>(fn: (signal: AbortSignal) => Promise<T>, key: string | null) {
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<{ key: string | null; data?: T; error?: unknown; base?: string | null }>({ key: null })
  const fullKey = key === null ? null : `${key}#${attempt}`

  useEffect(() => {
    if (fullKey === null) return
    const ac = new AbortController()
    fnRef.current(ac.signal).then(
      (data) => { if (!ac.signal.aborted) setState({ key: fullKey, data, base: key }) },
      (error) => { if (!ac.signal.aborted) setState({ key: fullKey, error, base: key }) },
    )
    return () => ac.abort()
  }, [fullKey, key])

  const current = state.key === fullKey
  // While a refresh of the same key is in flight, keep showing the previous data.
  const sameBase = state.base === key && key !== null
  return {
    loading: fullKey !== null && !current,
    data: current || sameBase ? state.data : undefined,
    error: current ? state.error : undefined,
    reload: useCallback(() => setAttempt((n) => n + 1), []),
  }
}
