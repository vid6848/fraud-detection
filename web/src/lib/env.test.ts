import { describe, expect, it } from 'vitest'
import { readEnv } from './env'

const full = {
  VITE_SUPABASE_URL: 'https://abc.supabase.co',
  VITE_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_123',
  VITE_API_URL: 'http://localhost:8000/',
}

describe('readEnv', () => {
  it('reads all values and strips the trailing slash from the API URL', () => {
    expect(readEnv(full)).toEqual({
      ok: true,
      config: { supabaseUrl: full.VITE_SUPABASE_URL, supabasePublishableKey: 'sb_publishable_123', apiUrl: 'http://localhost:8000' },
    })
  })

  it.each(['https://api.onrender.com.', 'https://api.onrender.com/', 'https://api.onrender.com. ', 'https://api.onrender.com./ '])(
    'strips stray trailing characters from the API URL: %j', (url) => {
      const result = readEnv({ ...full, VITE_API_URL: url })
      expect(result.ok && result.config.apiUrl).toBe('https://api.onrender.com')
    })

  it('lists missing, empty and placeholder values', () => {
    const result = readEnv({ VITE_SUPABASE_URL: 'https://your-project-ref.supabase.co', VITE_API_URL: '  ' })
    expect(result).toEqual({ ok: false, missing: ['VITE_SUPABASE_URL', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_API_URL'] })
  })
})
