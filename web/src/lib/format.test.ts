import { describe, expect, it } from 'vitest'
import { formatCurrency, formatFeedTime, formatMs, formatPercent, formatProbability, reasonLabel } from './format'

describe('format', () => {
  it.each([
    [0, '0%'], [0.00001, '<0.01%'], [0.0012, '0.12%'], [0.05, '5.00%'], [0.429, '42.9%'], [1, '100.0%'], [NaN, '–'],
  ])('formatProbability(%s) = %s', (p, expected) => expect(formatProbability(p)).toBe(expected))

  it('formats money, percentages and latency', () => {
    expect(formatCurrency(1234.5)).toBe('$1,234.50')
    expect(formatPercent(12.345)).toBe('12.3%')
    expect(formatPercent(null)).toBe('–')
    expect(formatMs(6.63)).toBe('6.6 ms')
    expect(formatMs(123.4)).toBe('123 ms')
    expect(formatMs(null)).toBe('–')
  })

  it('shows only the clock for today and adds the date for older rows', () => {
    const now = new Date(2026, 9, 18, 15, 0, 0)
    expect(formatFeedTime(new Date(2026, 9, 18, 9, 5, 7).toISOString(), now)).not.toMatch(/Oct/)
    expect(formatFeedTime(new Date(2026, 9, 17, 9, 5, 7).toISOString(), now)).toMatch(/Oct/)
    expect(formatFeedTime('nope', now)).toBe('–')
  })

  it('labels known reason codes and humanises unknown ones', () => {
    expect(reasonLabel('TINY_AMOUNT')).toBe('Tiny amount')
    expect(reasonLabel('SOME_NEW_RULE')).toBe('Some new rule')
  })
})
