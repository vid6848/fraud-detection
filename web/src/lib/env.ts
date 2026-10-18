/** Public, browser-safe configuration (VITE_* variables are bundled into the page). */
export interface AppConfig {
  supabaseUrl: string
  supabasePublishableKey: string
  apiUrl: string
}

export const ENV_VARS = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_API_URL'] as const

export type EnvResult = { ok: true; config: AppConfig } | { ok: false; missing: string[] }

/** Treat empty values and `.env.example` placeholders as missing. */
function clean(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const v = value.trim()
  return v && !v.includes('your-') ? v : null
}

export function readEnv(raw: Record<string, unknown>): EnvResult {
  const values = ENV_VARS.map((name) => clean(raw[name]))
  const missing = ENV_VARS.filter((_, i) => values[i] === null)
  if (missing.length) return { ok: false, missing: [...missing] }
  const [supabaseUrl, supabasePublishableKey, apiUrl] = values as string[]
  return {
    ok: true,
    config: {
      supabaseUrl: supabaseUrl!,
      supabasePublishableKey: supabasePublishableKey!,
      // Trailing slashes, dots or spaces (easy to paste into a hosting dashboard) would break
      // every API call: `https://x.onrender.com.` answers 404 on Render.
      apiUrl: apiUrl!.replace(/[\s/.]+$/, ''),
    },
  }
}

export const env = readEnv(import.meta.env)
