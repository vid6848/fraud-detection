import { describe, expect, it } from 'vitest'
import { MODEL_RUN } from '../test/modelRun'
import { formatDuration } from './format'
import { comparisonRows, formatParams, type RunMetrics } from './modelRuns'

describe('comparisonRows', () => {
  it('sorts best first, labels models and strategies, and flags the deployed model', () => {
    const rows = comparisonRows(MODEL_RUN.metrics as unknown as RunMetrics)
    expect(rows.map((r) => [r.name, r.strategy, r.selected])).toEqual([
      ['Random Forest', 'Class weights', true],
      ['XGBoost', 'No resampling', false],
      ['Logistic Regression', 'Class weights', false],
    ])
  })

  it('handles a run without a comparison', () => {
    expect(comparisonRows({ ...MODEL_RUN.metrics, model_comparison_best_per_model: undefined } as unknown as RunMetrics)).toEqual([])
  })

  it('formats hyperparameters', () => {
    expect(formatParams({ max_depth: 3, learning_rate: 0.05 })).toBe('max_depth=3, learning_rate=0.05')
    expect(formatParams({})).toBe('defaults')
  })
})

describe('formatDuration', () => {
  it.each([[37, '37s'], [249, '4m 09s'], [7500, '2h 05m'], [90000, '1d 1h'], [null, '–']])('%s -> %s', (s, out) => {
    expect(formatDuration(s)).toBe(out)
  })
})
