export type LiveStatus = 'connecting' | 'live' | 'offline' | 'error'

/** Map a Supabase channel status to what the UI shows. */
export function toLiveStatus(status: string): LiveStatus {
  switch (status) {
    case 'SUBSCRIBED': return 'live'
    case 'CHANNEL_ERROR':
    case 'TIMED_OUT': return 'error'
    case 'CLOSED': return 'offline'
    default: return 'connecting'
  }
}

/** Unique channel names so StrictMode's double mount doesn't reuse a closing channel. */
export const channelName = (base: string) => `${base}-${Math.random().toString(36).slice(2, 10)}`
