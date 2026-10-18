import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiStatusContext, type ApiPhase } from '../../apiStatus/context'
import { fakeApi, json } from '../../test/fakeApi'
import { DRIFT } from '../../test/modelRun'
import { fakeSession, renderWithProviders } from '../../test/render'
import { DriftPanel } from './DriftPanel'

function renderPanel(phase: ApiPhase = 'ready') {
  return renderWithProviders(
    <ApiStatusContext.Provider value={{ phase, since: null, retry: () => {} }}><DriftPanel /></ApiStatusContext.Provider>,
    { auth: { session: fakeSession } },
  )
}

describe('DriftPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the PSI, its label and the per-band table, using the analyst’s token', async () => {
    const fetchMock = fakeApi({ 'GET /drift': () => json(200, DRIFT) })
    vi.stubGlobal('fetch', fetchMock)
    renderPanel()
    expect(await screen.findByText('0.140')).toBeInTheDocument()
    expect(screen.getByText('Watch')).toBeInTheDocument()
    expect(screen.getByText('A moderate shift: keep an eye on it.')).toBeInTheDocument()
    expect(screen.getByText(/vs 199,364 training scores, model 1\.0\.0/)).toBeInTheDocument()
    expect((fetchMock.mock.calls[0]![1]!.headers as Record<string, string>).Authorization).toBe('Bearer test-token')

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(6)
    expect(rows[0]).toHaveTextContent('< 0.05%93.3%82.0%10%')
    expect(rows[1]).toHaveTextContent('0.05%–0.1%5.2%12.0%41%') // biggest part of the PSI
    expect(rows[4]).toHaveTextContent('5%–42.9% (Medium)<0.1%0.4%')
  })

  it.each([
    ['OK', 0.02, 'Live scores look like the training scores.'],
    ['Alert', 0.4, 'A large shift: the model may need retraining.'],
  ] as const)('labels %s', async (status, psi, meaning) => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /drift': () => json(200, { ...DRIFT, status, psi }) }))
    renderPanel()
    expect(await screen.findByText(meaning)).toBeInTheDocument()
    expect(screen.getByText(status)).toBeInTheDocument()
  })

  it('explains when there are too few live scores', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /drift': () => json(200, { ...DRIFT, status: 'Not enough data', live_rows: 300 }) }))
    renderPanel()
    expect(await screen.findByText('Not enough data')).toBeInTheDocument()
    expect(screen.getByText(/at least 500 live scores \(300 so far\)/)).toBeInTheDocument()
  })

  it('handles no live scores at all', async () => {
    const bins = DRIFT.bins.map((b) => ({ ...b, live: 0, contribution: 0 }))
    vi.stubGlobal('fetch', fakeApi({ 'GET /drift': () => json(200, {
      ...DRIFT, status: 'Not enough data', psi: null, live_rows: 0, live_from: null, live_to: null, bins }) }))
    renderPanel()
    expect(await screen.findByText('No live scores from this model yet.')).toBeInTheDocument()
    expect(screen.getByText('–', { selector: 'p' })).toBeInTheDocument()
  })

  it('refreshes on demand', async () => {
    let psi = 0.1395
    const fetchMock = fakeApi({ 'GET /drift': () => json(200, { ...DRIFT, psi }) })
    vi.stubGlobal('fetch', fetchMock)
    renderPanel()
    await screen.findByText('0.140')
    psi = 0.2
    await userEvent.click(screen.getByRole('button', { name: /refresh/i }))
    expect(await screen.findByText('0.200')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('says what to do when the API has no drift check (503)', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /drift': () => json(503, { error: { code: 'service_unavailable',
      message: 'No training score distribution for this model (run scripts/make_score_distribution.py)' } }) }))
    renderPanel()
    expect(await screen.findByText('Drift check not available')).toBeInTheDocument()
    expect(screen.getByText('python scripts/make_score_distribution.py')).toBeInTheDocument()
  })

  it('shows other errors with a retry', async () => {
    vi.stubGlobal('fetch', fakeApi({ 'GET /drift': () => json(401, { error: { code: 'unauthorized', message: 'x' } }) }))
    renderPanel()
    expect(await screen.findByRole('alert')).toHaveTextContent('Your session has expired')
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('waits for the API before asking', () => {
    const fetchMock = fakeApi({})
    vi.stubGlobal('fetch', fetchMock)
    renderPanel('waking')
    expect(screen.getByText('Waiting for the API…')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
