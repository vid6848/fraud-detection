// Guard: the browser bundle may only ever hold the Supabase PUBLISHABLE key.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const WEB = resolve(import.meta.dirname, '..')
const FORBIDDEN = [/service[_-]?role/i, /sb_secret_/, /SUPABASE_SECRET/i]

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path]
  })
}

describe('no secret keys in web/', () => {
  const targets = [...files(join(WEB, 'src')), join(WEB, '.env.example')]

  it.each(targets.map((f) => [f.slice(WEB.length + 1), f]))('%s', (_name, path) => {
    const text = readFileSync(path, 'utf8')
      // Comments that warn *about* the secret key are fine; strip them before checking.
      .split('\n').filter((line) => !/^\s*(#|\/\/|\*)/.test(line)).join('\n')
    for (const pattern of FORBIDDEN) expect(text).not.toMatch(pattern)
  })

  it('only VITE_SUPABASE_PUBLISHABLE_KEY is used for Supabase', () => {
    const example = readFileSync(join(WEB, '.env.example'), 'utf8')
    const vars = [...example.matchAll(/^(VITE_\w+)=/gm)].map((m) => m[1])
    expect(vars).toEqual(['VITE_SUPABASE_URL', 'VITE_SUPABASE_PUBLISHABLE_KEY', 'VITE_API_URL'])
  })
})
