import { useCallback, useEffect, useRef, useState } from 'react'
import { useApiStatus } from '../apiStatus/context'
import { useAuth } from '../auth/context'
import { ApiError } from '../lib/api'
import { demoErrorMessage, fetchDemoStatus, startDemoStream, type DemoRun, type DemoStatus } from '../lib/demo'
import { useToast } from '../toast/context'

export const DEMO_POLL_MS = 1000

export interface DemoStream {
  status: DemoStatus | null
  /** False when the API has no demo stream (503: no storage); null until known. */
  available: boolean | null
  running: boolean
  starting: boolean
  apiReady: boolean
  canStart: boolean
  error: string | null
  start: () => Promise<void>
}

/** POST /demo/stream for the signed-in analyst, plus its progress while it runs. */
export function useDemoStream(): DemoStream {
  const { session } = useAuth()
  const { phase } = useApiStatus()
  const toast = useToast()
  const apiReady = phase === 'ready'
  const [status, setStatus] = useState<DemoStatus | null>(null)
  const [available, setAvailable] = useState<boolean | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const running = status?.running ?? false

  // Once the API is up: is the demo stream offered, and is one already running?
  useEffect(() => {
    if (!apiReady) return
    const ac = new AbortController()
    fetchDemoStatus(ac.signal).then(
      (s) => { setStatus(s); setAvailable(true) },
      (e) => { if (!ac.signal.aborted && e instanceof ApiError && e.status === 503) setAvailable(false) },
    )
    return () => ac.abort()
  }, [apiReady])

  // Progress while a stream runs.
  useEffect(() => {
    if (!running) return
    const ac = new AbortController()
    const id = setInterval(() => { fetchDemoStatus(ac.signal).then(setStatus, () => {}) }, DEMO_POLL_MS)
    return () => { clearInterval(id); ac.abort() }
  }, [running])

  // Tell the analyst when it ends.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && status && !status.running && status.run) {
      toast(finishedToast(status.run))
      setError(null)
    }
    wasRunning.current = status?.running ?? false
  }, [status, toast])

  const start = useCallback(async () => {
    if (!session) return
    setStarting(true)
    setError(null)
    try {
      setStatus(await startDemoStream(session.access_token))
    } catch (e) {
      setError(demoErrorMessage(e))
      if (e instanceof ApiError && e.status === 409) fetchDemoStatus().then(setStatus, () => {})
      if (e instanceof ApiError && e.status === 503) setAvailable(false)
    } finally {
      setStarting(false)
    }
  }, [session])

  const canStart = Boolean(session) && apiReady && available !== false && !running && !starting
  return { status, available, running, starting, apiReady, canStart, error, start }
}

function finishedToast(run: DemoRun) {
  if (run.state === 'completed') {
    return { title: 'Demo stream finished', body: `${run.sent} transactions scored and saved.`, tone: 'success' as const }
  }
  return {
    title: 'Demo stream stopped early',
    body: `${run.sent} of ${run.total} transactions sent${run.failed ? `, ${run.failed} failed` : ''}.`,
    tone: 'error' as const,
  }
}
