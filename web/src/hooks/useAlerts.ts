import { useCallback, useEffect, useRef, useState } from 'react'
import { ALERT_SELECT, sortAlerts, toAlert, type Alert, type AlertStatus, type StatusFilter } from '../lib/alerts'
import { channelName, toLiveStatus, type LiveStatus } from '../lib/realtime'
import { getSupabase } from '../lib/supabase'

const LIMIT = 500

interface State { key: string; alerts: Alert[]; error: string | null }

/**
 * Alerts for a status filter, kept current over Realtime: new alerts are added (with their
 * transaction), reviews update or remove rows, deletes remove them.
 */
export function useAlerts(status: StatusFilter, onNewAlert?: (alert: Alert) => void) {
  const [attempt, setAttempt] = useState(0)
  const key = `${status}#${attempt}`
  const [state, setState] = useState<State | null>(null)
  const [live, setLive] = useState<LiveStatus>('connecting')
  // Latest callback, without re-subscribing (which could drop events) when it changes.
  const onNewAlertRef = useRef(onNewAlert)
  useEffect(() => { onNewAlertRef.current = onNewAlert })

  useEffect(() => {
    const supabase = getSupabase()
    let cancelled = false
    const matches = (s: AlertStatus) => status === 'all' || s === status
    const update = (fn: (alerts: Alert[]) => Alert[]) =>
      setState((prev) => (prev && prev.key === key ? { ...prev, alerts: sortAlerts(fn(prev.alerts)) } : prev))

    const fetchOne = async (id: number) => {
      const { data } = await supabase.from('alerts').select(ALERT_SELECT).eq('id', id).maybeSingle()
      return data ? toAlert(data as Record<string, unknown>) : null
    }

    const channel = supabase
      .channel(channelName('alerts-queue'))
      .on('postgres_changes', { event: '*', schema: 'public', table: 'alerts' }, async (payload) => {
        if (cancelled) return
        if (payload.eventType === 'DELETE') {
          const id = Number((payload.old as { id?: number }).id)
          update((alerts) => alerts.filter((a) => a.id !== id))
          return
        }
        const row = payload.new as Record<string, unknown>
        const id = Number(row.id)
        if (payload.eventType === 'INSERT') {
          const alert = await fetchOne(id)
          if (!alert || cancelled) return
          onNewAlertRef.current?.(alert)
          if (matches(alert.status)) update((alerts) => [alert, ...alerts.filter((a) => a.id !== id)])
          return
        }
        // UPDATE: a review (or re-open). Re-read the row so the list entry is complete.
        if (!matches(row.status as AlertStatus)) {
          update((alerts) => alerts.filter((a) => a.id !== id))
          return
        }
        const alert = await fetchOne(id)
        if (alert && !cancelled) update((alerts) => [alert, ...alerts.filter((a) => a.id !== id)])
      })
      .subscribe((s) => { if (!cancelled) setLive(toLiveStatus(s)) })

    let query = supabase.from('alerts').select(ALERT_SELECT)
    if (status !== 'all') query = query.eq('status', status)
    query.order('created_at', { ascending: false }).limit(LIMIT).then(({ data, error }) => {
      if (cancelled) return
      setState({
        key,
        alerts: error ? [] : sortAlerts((data ?? []).map((r) => toAlert(r as Record<string, unknown>))),
        error: error ? error.message : null,
      })
    })

    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [key, status])

  const current = state?.key === key ? state : null
  return {
    loading: !current,
    alerts: current?.alerts ?? [],
    error: current?.error ?? null,
    live,
    retry: useCallback(() => setAttempt((n) => n + 1), []),
  }
}
