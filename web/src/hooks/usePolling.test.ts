import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePolling } from './usePolling'

const flush = () => act(async () => { await Promise.resolve() })

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
  })

  it('calls immediately, then every interval, keeping a capped history', async () => {
    let n = 0
    const fn = vi.fn(async () => ++n)
    const { result } = renderHook(() => usePolling(fn, 1000, 2))
    await flush()
    expect(result.current.data).toBe(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.data).toBe(3)
    expect(result.current.history.map((h) => h.data)).toEqual([2, 3])
  })

  it('keeps the last good data when a call fails, and clears the error on recovery', async () => {
    let fail = false
    const fn = vi.fn(async () => { if (fail) throw new Error('down'); return 'ok' })
    const { result } = renderHook(() => usePolling(fn, 1000))
    await flush()
    fail = true
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.data).toBe('ok')
    expect((result.current.error as Error).message).toBe('down')
    fail = false
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(result.current.error).toBeUndefined()
  })

  it('pauses while the tab is hidden and polls again when it becomes visible', async () => {
    const fn = vi.fn(async () => 'x')
    renderHook(() => usePolling(fn, 1000))
    await flush()
    expect(fn).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(fn).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); await Promise.resolve() })
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('stops polling on unmount', async () => {
    const fn = vi.fn(async () => 'x')
    const { unmount } = renderHook(() => usePolling(fn, 1000))
    await flush()
    unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
