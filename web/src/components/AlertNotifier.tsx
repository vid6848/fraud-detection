import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { formatCurrency, formatProbability } from '../lib/format'
import { channelName } from '../lib/realtime'
import { getSupabase } from '../lib/supabase'
import { useToast } from '../toast/context'

/** Pops a notification for every new alert, on any dashboard page. */
export function AlertNotifier() {
  const notify = useToast()
  const { pathname } = useLocation()
  const onAlertsPage = pathname.startsWith('/app/alerts')

  useEffect(() => {
    const supabase = getSupabase()
    let cancelled = false
    const channel = supabase
      .channel(channelName('alerts-notify'))
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alerts' }, async (payload) => {
        const alert = payload.new as { id: number; severity: string; transaction_id: string }
        const { data } = await supabase.from('transactions').select('amount, probability')
          .eq('id', alert.transaction_id).maybeSingle()
        if (cancelled) return
        const severity = alert.severity === 'HIGH' ? 'High' : 'Medium'
        notify({
          tone: 'alert',
          title: `New ${severity.toLowerCase()}-risk alert`,
          body: data ? `${formatCurrency(Number(data.amount))}, fraud probability ${formatProbability(Number(data.probability))}` : undefined,
          action: { label: onAlertsPage ? 'Open alert' : 'Review in the alert queue', to: `/app/alerts?id=${alert.id}` },
        })
      })
      .subscribe()
    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [notify, onAlertsPage])

  return null
}
