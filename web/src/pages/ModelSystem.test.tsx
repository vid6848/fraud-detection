import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createFakeSupabase } from '../test/fakeSupabase'
import { MODEL_RUN, systemFetch } from '../test/modelRun'
import { fakeSession, renderWithProviders } from '../test/render'
import { ModelSystem } from './ModelSystem'

let fake = createFakeSupabase()
vi.mock('../lib/supabase', () => ({ getSupabase: () => fake.client }))

const renderPage = () => renderWithProviders(<ModelSystem />, { auth: { session: fakeSession }, route: '/app/model' })

describe('ModelSystem', () => {
  beforeEach(() => {
    fake = createFakeSupabase({ model_runs: { data: [MODEL_RUN] } })
    vi.stubGlobal('fetch', vi.fn(systemFetch()))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the deployed model with test metrics and confidence intervals', async () => {
    renderPage()
    expect(await screen.findByText('Random Forest', { selector: 'p.text-xl' })).toBeInTheDocument()
    expect(screen.getByText('0.744')).toBeInTheDocument()
    expect(screen.getByText('95% CI 0.622–0.856')).toBeInTheDocument()
    expect(screen.getByText('$3,556')).toBeInTheDocument()
    expect(screen.getByText('95% CI $1,112–$7,204')).toBeInTheDocument()
    expect(screen.getByText('39 of 48 alerts were fraud.')).toBeInTheDocument()
    expect(screen.getByText('0.429')).toBeInTheDocument()
  })

  it('shows accuracy computed from the confusion matrix, with the flag-nothing baseline', async () => {
    renderPage()
    await screen.findByText('0.744')
    expect(screen.getByText('99.95%')).toBeInTheDocument() // (42,660 + 39) / 42,721
    expect(screen.getByText(/42,699 of 42,721 transactions classified correctly\. Flagging nothing would already score 99\.88%/)).toBeInTheDocument()
    expect(screen.getByText('0.780')).toBeInTheDocument() // F1
  })

  it('shows outcomes, the model comparison and the data split', async () => {
    renderPage()
    await screen.findByText('0.744')
    expect(screen.getByText('Fraud missed').closest('td')).toHaveTextContent('13Fraud missed')
    const comparison = screen.getByRole('list', { name: /models compared/i })
    const rows = within(comparison).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Random Forest Deployed')
    expect(rows[0]).toHaveTextContent('0.880')
    expect(screen.getByText(/199,364 rows/)).toBeInTheDocument()
    expect(screen.getByText('isotonic')).toBeInTheDocument()
  })

  it('explains how to load results when model_runs is empty, and shows load errors', async () => {
    fake = createFakeSupabase({ model_runs: { data: [] } })
    const { unmount } = renderPage()
    expect(await screen.findByText('No model results yet')).toBeInTheDocument()
    expect(screen.getByText('python scripts/load_model_runs.py')).toBeInTheDocument()
    unmount()

    fake = createFakeSupabase({ model_runs: { error: { message: 'permission denied' } } })
    renderPage()
    expect(await screen.findByText('Couldn’t load model results')).toBeInTheDocument()
  })

  it('shows the six training charts with alt text and enlarges one on click', async () => {
    renderPage()
    const charts = screen.getAllByRole('button', { name: /^enlarge:/i })
    expect(charts).toHaveLength(6)
    await userEvent.click(screen.getByRole('button', { name: 'Enlarge: Calibration' }))
    const dialog = await screen.findByRole('dialog', { name: 'Calibration' })
    expect(within(dialog).getByRole('img', { name: 'Calibration' })).toHaveAttribute('src', '/figures/calibration_curve.png')
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('includes the live system panel', async () => {
    renderPage()
    expect(await screen.findByText('Healthy')).toBeInTheDocument()
  })
})
