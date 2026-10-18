import type { Reason, RiskLevel } from './types'

/**
 * Made-up transactions for the landing page animation only (no real data, no network).
 * The shape mirrors what the API returns; the mix is roughly realistic: almost
 * everything is low risk, with an occasional medium or high score.
 */
export interface SampleTx {
  id: string
  amount: number
  probability: number
  risk: RiskLevel
  reasons: Reason[]
  latencyMs: number
}

/** Small seeded PRNG so the preview (and its tests) are reproducible. */
export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function makeSampleStream(seed = 7) {
  const rand = mulberry32(seed)
  let n = 0
  return function next(): SampleTx {
    n += 1
    const roll = rand()
    // Every 11th row is a high-risk one so the preview reliably shows an alert.
    const risk: RiskLevel = n % 11 === 0 ? 'HIGH' : roll < 0.08 ? 'MEDIUM' : 'LOW'
    const tiny = risk !== 'LOW' && rand() < 0.4
    const amount = Math.round((tiny ? rand() : Math.exp(2.6 + rand() * 3.2)) * 100) / 100
    const probability =
      risk === 'HIGH' ? 0.62 + rand() * 0.35 : risk === 'MEDIUM' ? 0.05 + rand() * 0.3 : rand() * 0.004
    const reasons: Reason[] = []
    if (risk === 'HIGH') reasons.push({ code: 'MODEL_HIGH_RISK', message: 'Model score above the alert threshold' })
    if (risk === 'MEDIUM') reasons.push({ code: 'MODEL_MEDIUM_RISK', message: 'Model score above the review threshold' })
    if (tiny) reasons.push({ code: 'TINY_AMOUNT', message: 'Charge under $1.00, a common card-testing pattern' })
    return {
      id: `s${n}`,
      amount,
      probability,
      risk,
      reasons,
      latencyMs: 4.5 + rand() * 5,
    }
  }
}
