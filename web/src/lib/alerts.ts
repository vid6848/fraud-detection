import type { SupabaseClient } from '@supabase/supabase-js'
import { toTransaction, TRANSACTION_COLUMNS, type Transaction } from './types'

export type Severity = 'HIGH' | 'MEDIUM'
export type AlertStatus = 'open' | 'confirmed_fraud' | 'false_alarm'
export type ReviewLabel = Exclude<AlertStatus, 'open'>
export type SeverityFilter = Severity | 'all'
export type StatusFilter = AlertStatus | 'all'

export interface Feedback {
  id: number
  label: ReviewLabel
  note: string | null
  analyst: string
  created_at: string
}

export interface Alert {
  id: number
  transaction_id: string
  severity: Severity
  status: AlertStatus
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
  transaction: Transaction | null
  feedback?: Feedback[]
}

export const ALERT_COLUMNS = 'id, transaction_id, severity, status, reviewed_by, reviewed_at, created_at'
export const ALERT_SELECT = `${ALERT_COLUMNS}, transactions(${TRANSACTION_COLUMNS})`
export const ALERT_DETAIL_SELECT = `${ALERT_SELECT}, feedback(id, label, note, analyst, created_at)`

export const STATUS_LABELS: Record<AlertStatus, string> = {
  open: 'Open',
  confirmed_fraud: 'Confirmed fraud',
  false_alarm: 'False alarm',
}

export function toAlert(raw: Record<string, unknown>): Alert {
  const tx = raw.transactions as Record<string, unknown> | null | undefined
  const fb = raw.feedback as Feedback[] | undefined
  return {
    id: Number(raw.id),
    transaction_id: String(raw.transaction_id),
    severity: raw.severity as Severity,
    status: raw.status as AlertStatus,
    reviewed_by: (raw.reviewed_by as string | null) ?? null,
    reviewed_at: (raw.reviewed_at as string | null) ?? null,
    created_at: String(raw.created_at),
    transaction: tx ? toTransaction(tx) : null,
    ...(fb ? { feedback: [...fb].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)) } : {}),
  }
}

const SEVERITY_RANK: Record<Severity, number> = { HIGH: 0, MEDIUM: 1 }

/** The queue order: HIGH before MEDIUM, then newest first. */
export function sortAlerts(alerts: Alert[]): Alert[] {
  return [...alerts].sort((a, b) =>
    SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id)
}

export function matchesFilters(alert: Pick<Alert, 'severity' | 'status'>, severity: SeverityFilter, status: StatusFilter) {
  return (severity === 'all' || alert.severity === severity) && (status === 'all' || alert.status === status)
}

export type ReviewResult =
  | { ok: true }
  | { ok: false; stage: 'status' | 'conflict' | 'feedback'; message: string }

/**
 * Record an analyst's verdict. Row Level Security decides what is allowed: analysts may
 * change only alerts.status and insert their own feedback (the trigger stamps reviewer + time).
 *
 * 1. Set the status, but only if the alert is still open, so two analysts can't both review it.
 * 2. Save the verdict (+ optional note) in `feedback`. If only this step fails, retry it with
 *    `saveFeedback` alone.
 */
export async function reviewAlert(client: SupabaseClient, alertId: number, label: ReviewLabel, note: string): Promise<ReviewResult> {
  const { data, error } = await client.from('alerts').update({ status: label })
    .eq('id', alertId).eq('status', 'open').select('id')
  if (error) return { ok: false, stage: 'status', message: error.message }
  if (!data?.length) return { ok: false, stage: 'conflict', message: 'This alert was already reviewed by another analyst.' }
  return saveFeedback(client, alertId, label, note)
}

export async function saveFeedback(client: SupabaseClient, alertId: number, label: ReviewLabel, note: string): Promise<ReviewResult> {
  const { error } = await client.from('feedback').insert({ alert_id: alertId, label, note: note.trim() || null })
  return error ? { ok: false, stage: 'feedback', message: error.message } : { ok: true }
}

export const NOTE_MAX = 2000
