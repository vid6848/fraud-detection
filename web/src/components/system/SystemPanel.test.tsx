import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HEALTH, METRICS, systemFetch } from '../../test/modelRun'
import { POLL_MS, SystemPanel } from './SystemPanel'

describe('SystemPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('shows health, uptime, requests, errors, /predict latency, risk counts and endpoints', async () => {
    vi.stubGlobal('fetch', vi.fn(systemFetch()))
    render(<SystemPanel />)
    expect(await screen.findByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText('1h 02m')).toBeInTheDocument()
    expect(screen.getByText('1,210')).toBeInTheDocument()
    expect(screen.getByText('3× 422')).toBeInTheDocument()
    expect(screen.getByText(/p95 13 ms, p99 31 ms \(POST \/predict\)/)).toBeInTheDocument()
    expect(screen.getByText('1,190')).toBeInTheDocument() // LOW
    expect(screen.getByRole('cell', { name: 'POST /predict' })).toBeInTheDocument()
    expect(screen.getByText(/collecting samples/i)).toBeInTheDocument() // one sample so far
  })

  it('says when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<SystemPanel />)
    expect(await screen.findByText('API unreachable')).toBeInTheDocument()
    expect(screen.getByText('Can’t reach the API')).toBeInTheDocument()
    expect(screen.getByText('uvicorn api.main:app --no-access-log')).toBeInTheDocument()
  })

  it('says when the model is not loaded (503)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'unavailable', model_loaded: false }), { status: 503 })))
    render(<SystemPanel />)
    expect(await screen.findByText('Model not loaded')).toBeInTheDocument()
  })

  it('keeps the last values, greyed out, when the API goes down', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetchMock = vi.fn(systemFetch(HEALTH, METRICS))
    vi.stubGlobal('fetch', fetchMock)
    render(<SystemPanel />)
    expect(await screen.findByText('Healthy')).toBeInTheDocument()
    fetchMock.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')))
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS + 10) })
    expect(await screen.findByText('Lost contact with the API')).toBeInTheDocument()
    expect(screen.getByText('1,210')).toBeInTheDocument()
    expect(screen.getByText('1,210').closest('[aria-busy]')).toHaveAttribute('aria-busy', 'true')
  })
})
