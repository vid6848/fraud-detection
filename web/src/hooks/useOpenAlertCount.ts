import { useEffect, useState } from 'react'
import { channelName } from '../lib/realtime'
import { getSupabase } from '../lib/supabase'

/** Number of alerts with status "open", refreshed whenever an alert is created or reviewed. */
export function useOpenAlertCount() {
  const [count, setCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const supabase = getSupabase()
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const load = () => {
      supabase.from('alerts').select('id', { count: 'exact', head: true }).eq('status', 'open')
        .then(({ count: n, error: e }) => {
          if (cancelled) return
          setError(e ? e.message : null)
          if (!e) setCount(n ?? 0)
        })
    }
    // A burst of alerts (simulator at 20/s) triggers one recount, not dozens.
    const reload = () => { clearTimeout(timer); timer = setTimeout(load, 400) }

    const channel = supabase
      .channel(channelName('alerts-count'))
      .on('postgres_changes', { event: '*', schema: 'public', table: 'alerts' }, reload)
      .subscribe()
    load()

    return () => {
      cancelled = true
      clearTimeout(timer)
      supabase.removeChannel(channel)
    }
  }, [])

  return { count, error }
}
