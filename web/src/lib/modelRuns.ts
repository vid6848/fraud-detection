/** Shapes of model_runs.metrics (written by scripts/load_model_runs.py from ml/artifacts/metadata.json). */
export interface Interval { low: number; high: number }
export interface Confusion { tn: number; fp: number; fn: number; tp: number }

export interface SplitMetrics {
  pr_auc: number
  recall_at_90_precision: number
  threshold: number
  precision: number
  recall: number
  f1: number
  alerts: number
  confusion_matrix: Confusion
  total_fraud_amount: number
  fraud_amount_caught: number
  fraud_amount_missed: number
  pct_fraud_dollars_caught: number
  review_cost_total: number
  cost_no_model: number
  cost_with_model: number
  cost_saved: number
}

export interface TestMetrics extends SplitMetrics {
  n_bootstrap?: number
  ci95?: Partial<Record<'pr_auc' | 'precision' | 'recall' | 'f1' | 'recall_at_90_precision' | 'pct_fraud_dollars_caught' | 'cost_saved', Interval>>
}

export interface SplitPart { rows: number; frauds: number; fraud_pct: number; start_time: number; end_time: number }

export interface RunMetrics {
  model: { name: string; label: string; imbalance_strategy: string; params: Record<string, unknown>; selected_by?: string }
  threshold: number
  threshold_90_precision?: number
  threshold_selection?: string
  review_cost_per_alert?: number
  calibration?: {
    method: string
    val_brier_uncalibrated: number
    val_brier_calibrated: number
    val_pr_auc_uncalibrated: number
    val_pr_auc_calibrated: number
  }
  validation_metrics?: SplitMetrics
  test_metrics: TestMetrics
  model_comparison_best_per_model?: Record<string, { strategy: string; params: Record<string, unknown>; val_pr_auc: number }>
  split?: { train: SplitPart; validation: SplitPart; test: SplitPart }
}

export interface ModelRun {
  id: number
  version: string
  trained_at: string
  metrics: RunMetrics
}

export const MODEL_LABELS: Record<string, string> = {
  logistic_regression: 'Logistic Regression',
  decision_tree: 'Decision Tree',
  random_forest: 'Random Forest',
  xgboost: 'XGBoost',
}

export const STRATEGY_LABELS: Record<string, string> = {
  class_weight: 'Class weights',
  none: 'No resampling',
  smote: 'SMOTE',
  undersample: 'Undersampling',
}

export const label = (map: Record<string, string>, key: string) =>
  map[key] ?? key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

/** Sorted best first, with a flag for the deployed model. */
export function comparisonRows(metrics: RunMetrics) {
  return Object.entries(metrics.model_comparison_best_per_model ?? {})
    .map(([key, v]) => ({ key, name: label(MODEL_LABELS, key), strategy: label(STRATEGY_LABELS, v.strategy), params: v.params, prAuc: v.val_pr_auc, selected: key === metrics.model.name }))
    .sort((a, b) => b.prAuc - a.prAuc)
}

export const formatParams = (params: Record<string, unknown>) =>
  Object.entries(params).map(([k, v]) => `${k}=${String(v)}`).join(', ') || 'defaults'
