/** A model_runs row shaped like the real one (values from ml/artifacts/metadata.json). */
export const MODEL_RUN = {
  id: 1,
  version: '1.0.0',
  trained_at: '2026-10-11T09:02:03+00:00',
  metrics: {
    model: { name: 'random_forest', label: 'Random Forest', imbalance_strategy: 'class_weight', params: { max_depth: 16 } },
    threshold: 0.42857,
    review_cost_per_alert: 5,
    calibration: { method: 'isotonic', val_brier_uncalibrated: 0.000335, val_brier_calibrated: 0.000299, val_pr_auc_uncalibrated: 0.8805, val_pr_auc_calibrated: 0.8662 },
    test_metrics: {
      pr_auc: 0.7438, recall_at_90_precision: 0.7115, threshold: 0.42857, precision: 0.8125, recall: 0.75, f1: 0.78, alerts: 48,
      confusion_matrix: { tn: 42660, fp: 9, fn: 13, tp: 39 },
      total_fraud_amount: 6168.88, fraud_amount_caught: 3796.5, fraud_amount_missed: 2372.4, pct_fraud_dollars_caught: 61.54,
      review_cost_total: 240, cost_no_model: 6168.88, cost_with_model: 2612.4, cost_saved: 3556.48,
      ci95: { pr_auc: { low: 0.6222, high: 0.8559 }, cost_saved: { low: 1111.95, high: 7204.12 } },
    },
    model_comparison_best_per_model: {
      logistic_regression: { strategy: 'class_weight', params: { C: 1 }, val_pr_auc: 0.8153 },
      random_forest: { strategy: 'class_weight', params: { max_depth: 16 }, val_pr_auc: 0.8805 },
      xgboost: { strategy: 'none', params: { max_depth: 3 }, val_pr_auc: 0.8642 },
    },
    split: {
      train: { rows: 199364, frauds: 384, fraud_pct: 0.1926, start_time: 0, end_time: 1 },
      validation: { rows: 42722, frauds: 56, fraud_pct: 0.1311, start_time: 1, end_time: 2 },
      test: { rows: 42721, frauds: 52, fraud_pct: 0.1217, start_time: 2, end_time: 3 },
    },
  },
}

export const HEALTH = { status: 'ok', model_loaded: true, model_version: '1.0.0', model_name: 'random_forest', trained_at: '2026-10-11T09:02:03+00:00' }

export const METRICS = {
  uptime_seconds: 3725,
  started_at: '2026-10-18T07:00:00+00:00',
  requests: { total: 1210, by_endpoint: { 'POST /predict': 1200, 'GET /health': 10 } },
  errors: { total: 3, by_status: { '422': 3 } },
  latency_ms: {
    count: 1210, p50: 6.1, p95: 12.4, p99: 30.2, window: 10000,
    by_endpoint: { 'POST /predict': { count: 1200, p50: 6.6, p95: 13.1, p99: 31 }, 'GET /health': { count: 10, p50: 0.6, p95: 1, p99: 1 } },
  },
  risk_levels: { LOW: 1190, MEDIUM: 6, HIGH: 4 },
  storage: { enabled: true, writes_ok: 1200, writes_failed: 0, rows_written: 1200, rows_failed: 0 },
  scope: 'in-memory, per worker process, reset on restart',
}

/** fetch mock answering /health and /metrics. */
export function systemFetch(health: unknown = HEALTH, metrics: unknown = METRICS) {
  return (url: RequestInfo | URL) => {
    const u = String(url)
    const body = u.endsWith('/health') ? health : u.endsWith('/metrics') ? metrics : null
    return Promise.resolve(new Response(JSON.stringify(body), { status: body ? 200 : 404 }))
  }
}
