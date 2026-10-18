import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FeatureContribution } from '../lib/explain'
import { ShapBars } from './ShapBars'

const f = (feature: string, shap_value: number): FeatureContribution => ({
  feature, value: 1, shap_value, direction: shap_value >= 0 ? 'raises_risk' : 'lowers_risk',
  description: `${feature} description`,
})

describe('ShapBars', () => {
  it('lists features largest first with signed values and descriptions', () => {
    render(<ShapBars features={[f('V4', 0.05), f('V14', 0.13), f('Amount', -0.08)]} baseValue={0.5} modelScore={0.6} />)
    const items = within(screen.getByRole('list', { name: /feature contributions/i })).getAllByRole('listitem')
    expect(items.map((li) => li.textContent)).toEqual([
      'V14+0.130Raises risk: V14 description',
      'Amount−0.080Lowers risk: Amount description',
      'V4+0.050Raises risk: V4 description',
    ])
  })

  it('summarises the score change the features explain', () => {
    render(<ShapBars features={[f('V14', 0.3), f('V10', 0.1)]} baseValue={0.5} modelScore={0.95} />)
    expect(screen.getByText(/starts at its average of/)).toHaveTextContent('0.50 and ends at 0.95. These 2 features account for +0.400')
  })

  it('labels time_of_day readably and handles an empty list', () => {
    const { rerender } = render(<ShapBars features={[f('time_of_day', 0.01)]} baseValue={0} modelScore={0} />)
    expect(screen.getByText('Time of day')).toBeInTheDocument()
    rerender(<ShapBars features={[]} baseValue={0} modelScore={0} />)
    expect(screen.getByText(/no feature contributions/i)).toBeInTheDocument()
  })
})
