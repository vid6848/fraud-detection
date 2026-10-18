import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiGet, isLocalApi } from '../lib/api'
import type { Health } from '../lib/system'
import { ApiStatusContext, type ApiPhase } from './context'

/** A first answer slower than this is treated as a cold start. */
export const SLOW_MS = 3000
/** Abandon a single /health call after this long and try again. */
export const TIMEOUT_MS = 15_000
export const RETRY_MS = 3000
/** While healthy, check again this often (only while the tab is visible). */
export const RECHECK_MS = 60_000
/** A free Render instance takes ~30-60 s to wake; after this long, report it as down. */
export const GIVE_UP_MS = 120_000

/**
 * Watches GET /health for the whole dashboard. The API runs on a free plan that sleeps when
 * idle, so a slow or failing first call means "waking up", not "broken": keep retrying and
 * say so. A local API (development) has no cold start, so failures show as down at once.
 */
export function ApiStatusProvider({ children, giveUpMs = isLocalApi() ? 0 : GIVE_UP_MS }: {
  children: ReactNode
  giveUpMs?: number
}) {
  const [phase, setPhase] = useState<ApiPhase>('checking')
  const [since, setSince] = useState<number | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let ac: AbortController | undefined
    let spellStart: number | null = null

    const startSpell = () => {
      if (spellStart === null) {
        spellStart = Date.now()
        setSince(spellStart)
      }
    }
    const schedule = (ms: number) => { clearTimeout(timer); if (!stopped) timer = setTimeout(check, ms) }

    async function check() {
      if (document.hidden) return // resumed by the visibility listener
      const controller = new AbortController()
      ac = controller
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS)
      const slow = setTimeout(() => {
        startSpell()
        setPhase((p) => (p === 'down' ? p : 'waking'))
      }, SLOW_MS)
      let loaded = false
      try {
        loaded = (await apiGet<Health>('/health', { signal: controller.signal })).model_loaded
      } catch {
        // unreachable, 5xx while starting, or timed out: all count as "not up yet"
      }
      clearTimeout(timeout)
      clearTimeout(slow)
      if (stopped) return
      if (loaded) {
        spellStart = null
        setSince(null)
        setPhase('ready')
        schedule(RECHECK_MS)
        return
      }
      startSpell()
      setPhase(Date.now() - spellStart! >= giveUpMs ? 'down' : 'waking')
      schedule(RETRY_MS)
    }

    const onVisible = () => { if (!document.hidden) { clearTimeout(timer); check() } }
    document.addEventListener('visibilitychange', onVisible)
    check()
    return () => {
      stopped = true
      clearTimeout(timer)
      ac?.abort()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [attempt, giveUpMs])

  const retry = useCallback(() => {
    setPhase('checking')
    setSince(null)
    setAttempt((n) => n + 1)
  }, [])
  const value = useMemo(() => ({ phase, since, retry }), [phase, since, retry])
  return <ApiStatusContext.Provider value={value}>{children}</ApiStatusContext.Provider>
}
