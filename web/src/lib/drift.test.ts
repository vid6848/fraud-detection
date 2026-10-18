import { describe, expect, it } from 'vitest'
import { DRIFT } from '../test/modelRun'
import { bandLabel, scorePct, sharePct } from './drift'

describe('drift labels', () => {
  it('formats score bounds as short percentages', () => {
    expect(scorePct(0.0005)).toBe('0.05%')
    expect(scorePct(0.005)).toBe('0.5%')
    expect(scorePct(0.05)).toBe('5%')
    expect(scorePct(0.42857142857142855)).toBe('42.9%')
  })

  it('names the bins, with the Medium and High bands last', () => {
    expect(DRIFT.bins.map((_, i) => bandLabel(DRIFT.bins, i))).toEqual([
      '< 0.05%', '0.05%–0.1%', '0.1%–0.5%', '0.5%–5%', '5%–42.9% (Medium)', '≥ 42.9% (High)',
    ])
  })

  it('formats shares, keeping tiny ones visible', () => {
    expect(sharePct(0)).toBe('0%')
    expect(sharePct(0.00017)).toBe('<0.1%')
    expect(sharePct(0.93295)).toBe('93.3%')
  })
})
