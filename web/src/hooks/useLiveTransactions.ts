import { useCallback, useEffect, useReducer, useState } from 'react'
import { FEED_CAP, feedReducer, initialFeed } from '../lib/feed'
import { channelName, toLiveStatus, type LiveStatus } from '../lib/realtime'
import { getSupabase } from '../lib/supabase'
import { toTransaction, TRANSACTION_COLUMNS } from '../lib/types'

/**
 * Newest scored transactions, kept live over Supabase Realtime.
 * Subscribes first, then loads the latest rows, so nothing inserted in between is lost
 * (duplicates are dropped by id).
 */
export function useLiveTransactions() {
  const [state, dispatch] = useReducer(feedReducer, initialFeed)
  const [live, setLive] = useState<LiveStatus>('connecting')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const supabase = getSupabase()
    let cancelled = false
    const channel = supabase
      .channel(channelName('transactions-feed'))
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'transactions' },
        (payload) => dispatch({ type: 'received', row: toTransaction(payload.new as Record<string, unknown>) }))
      .subscribe((status) => { if (!cancelled) setLive(toLiveStatus(status)) })

    supabase.from('transactions').select(TRANSACTION_COLUMNS)
      .order('created_at', { ascending: false }).limit(FEED_CAP)
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) dispatch({ type: 'failed', error: error.message })
        else dispatch({ type: 'loaded', rows: (data ?? []).map((r) => toTransaction(r as Record<string, unknown>)) })
      })

    return () => {
      cancelled = true
      supabase.removeChannel(channel)
    }
  }, [attempt])

  const retry = useCallback(() => {
    dispatch({ type: 'loading' })
    setLive('connecting')
    setAttempt((n) => n + 1)
  }, [])

  return {
    state,
    live,
    retry,
    pause: useCallback(() => dispatch({ type: 'pause' }), []),
    resume: useCallback(() => dispatch({ type: 'resume' }), []),
  }
}
