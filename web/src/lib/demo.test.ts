import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { demoErrorMessage, formatWait } from './demo'

describe('demoErrorMessage', () => {
  it.each([
    [new ApiError(401, 'x'), /session has expired/],
    [new ApiError(409, 'x'), /already running/],
    [new ApiError(429, 'x', 'rate_limited', 30), /Try again in 30 s/],
    [new ApiError(429, 'x', 'rate_limited', 1800), /Try again in 30 min/],
    [new ApiError(429, 'x'), /Try again in a minute/],
    [new ApiError(503, 'x'), /isn’t available on this API/],
    [new ApiError(0, 'network error'), /./],
    [new ApiError(500, 'boom'), /answered 500: boom/],
    [new Error('plain'), /^plain$/],
    ['text', /^text$/],
  ])('%s', (error, expected) => {
    expect(demoErrorMessage(error)).toMatch(expected)
  })
})

describe('formatWait', () => {
  it('uses seconds under 90 s, minutes above', () => {
    expect(formatWait(0.4)).toBe('1 s')
    expect(formatWait(89)).toBe('89 s')
    expect(formatWait(91)).toBe('2 min')
  })
})
