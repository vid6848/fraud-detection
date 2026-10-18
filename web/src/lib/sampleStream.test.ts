import { describe, expect, it } from 'vitest'
import { makeSampleStream } from './sampleStream'

describe('sample stream (landing preview)', () => {
  it('is reproducible for a seed', () => {
    const a = makeSampleStream(3), b = makeSampleStream(3)
    expect(Array.from({ length: 20 }, a)).toEqual(Array.from({ length: 20 }, b))
  })

  it('is mostly low risk, with a high-risk row every 11th and matching probabilities', () => {
    const rows = Array.from({ length: 110 }, makeSampleStream())
    expect(rows.filter((r) => r.risk === 'HIGH')).toHaveLength(10)
    expect(rows.filter((r) => r.risk === 'LOW').length).toBeGreaterThan(80)
    for (const r of rows) {
      expect(r.amount).toBeGreaterThanOrEqual(0)
      if (r.risk === 'LOW') expect(r.probability).toBeLessThan(0.05)
      if (r.risk === 'HIGH') expect(r.probability).toBeGreaterThan(0.43)
    }
  })
})
