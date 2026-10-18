import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { env } from './env'

let client: SupabaseClient | null = null

/**
 * The browser Supabase client. It only ever holds the PUBLISHABLE key; what an
 * analyst can read or change is decided by Row Level Security using their login token.
 * main.tsx shows a "configuration missing" screen before anything calls this.
 */
export function getSupabase(): SupabaseClient {
  if (!env.ok) throw new Error(`Missing configuration: ${env.missing.join(', ')}`)
  client ??= createClient(env.config.supabaseUrl, env.config.supabasePublishableKey)
  return client
}
