// Guard: Vercel must serve index.html for client-side routes (deep links, refreshes).
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const config = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', 'vercel.json'), 'utf8'))

describe('vercel.json', () => {
  it('rewrites every path to the SPA entry point', () => {
    expect(config.rewrites).toEqual([{ source: '/(.*)', destination: '/index.html' }])
  })

  it('builds with Vite into dist/', () => {
    expect(config).toMatchObject({ framework: 'vite', buildCommand: 'npm run build', outputDirectory: 'dist' })
  })

  it('caches hashed assets for a year', () => {
    const assets = config.headers.find((h: { source: string }) => h.source === '/assets/(.*)')
    expect(assets.headers[0].value).toContain('immutable')
  })
})
