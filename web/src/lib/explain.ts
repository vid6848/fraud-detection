import { apiGet } from './api'

export interface FeatureContribution {
  feature: string
  value: number
  shap_value: number
  direction: 'raises_risk' | 'lowers_risk'
  description: string
}

/** GET /explain/{id} (StoredExplainResponse in api/schemas.py). */
export interface Explanation {
  transaction_id: string
  probability: number
  risk_level: string
  model_version: string
  model_score: number
  base_value: number
  top_features: FeatureContribution[]
  stored_probability: number
  stored_model_version: string
}

export function fetchExplanation(transactionId: string, token: string, signal?: AbortSignal) {
  return apiGet<Explanation>(`/explain/${encodeURIComponent(transactionId)}`, { token, signal })
}

export function featureLabel(feature: string): string {
  return feature === 'time_of_day' ? 'Time of day' : feature
}
