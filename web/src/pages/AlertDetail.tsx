import { BrainCircuit, ClipboardCheck, Loader2, RotateCw, ShieldCheck, ShieldX } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useAuth } from '../auth/context'
import { RiskBadge } from '../components/RiskBadge'
import { ShapBars } from '../components/ShapBars'
import { Modal } from '../components/Modal'
import { ErrorState, Skeleton } from '../components/StateViews'
import { StatusBadge } from '../components/StatusBadge'
import { useAsync } from '../hooks/useAsync'
import { ALERT_DETAIL_SELECT, NOTE_MAX, reviewAlert, saveFeedback, STATUS_LABELS, toAlert, type Alert, type ReviewLabel } from '../lib/alerts'
import { apiErrorMessage } from '../lib/api'
import { fetchExplanation } from '../lib/explain'
import { formatCurrency, formatDateTime, formatMs, formatProbability, reasonLabel } from '../lib/format'
import { getSupabase } from '../lib/supabase'
import { useToast } from '../toast/context'

/** Centred dialog with the transaction, its SHAP explanation and the review form. */
export function AlertDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const detail = useAsync(async () => {
    const { data, error } = await getSupabase().from('alerts').select(ALERT_DETAIL_SELECT).eq('id', id).maybeSingle()
    if (error) throw new Error(error.message)
    return data ? toAlert(data as Record<string, unknown>) : null
  }, `alert-${id}`)
  const alert = detail.data

  return (
    <Modal title={`Alert #${id}`} labelledBy="alert-detail-title" onClose={onClose} size="xl"
      titleExtra={alert && <><RiskBadge level={alert.severity} /><StatusBadge status={alert.status} /></>}>
      <div className="p-5">
        {detail.loading && !alert ? <Skeleton rows={6} label="Loading alert" />
          : detail.error ? <ErrorState title="Couldn’t load this alert" message={String((detail.error as Error).message ?? detail.error)} onRetry={detail.reload} />
          : !alert ? <ErrorState title="Alert not found" message="It may have been deleted. Close this window to go back to the queue." />
          : <DetailBody alert={alert} onReviewed={detail.reload} />}
      </div>
    </Modal>
  )
}

function DetailBody({ alert, onReviewed }: { alert: Alert; onReviewed: () => void }) {
  const tx = alert.transaction
  return (
    // DOM order = phone order (facts, explanation, review); on wide screens the
    // explanation moves to its own column on the right.
    <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:grid-rows-[auto_1fr]">
      <div className="lg:col-start-1 lg:row-start-1">
      {tx ? (
        <section aria-labelledby="tx-title" className="animate-rise-in rounded-2xl border border-border bg-surface p-4">
          <h3 id="tx-title" className="text-sm text-muted">Transaction</h3>
          <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{formatCurrency(tx.amount)}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Fact label="Fraud probability" value={<span className="tabular-nums">{formatProbability(tx.probability)}</span>} />
            <Fact label="Risk level" value={<RiskBadge level={tx.risk_level} />} />
            <Fact label="Scored at" value={formatDateTime(tx.created_at)} />
            <Fact label="Hour of day (dataset)" value={`${String(tx.hour_of_day).padStart(2, '0')}:00`} />
            <Fact label="Scoring latency" value={formatMs(tx.latency_ms)} />
            <Fact label="Model version" value={tx.model_version} />
            <div className="col-span-2">
              <dt className="text-muted">Transaction id</dt>
              <dd className="mt-0.5 break-all font-mono text-xs">{tx.id}</dd>
            </div>
          </dl>
          {tx.reasons.length > 0 && (
            <div className="mt-4 border-t border-border pt-4">
              <h4 className="text-sm text-muted">Reasons</h4>
              <ul className="mt-2 space-y-1.5 text-sm">
                {tx.reasons.map((r) => (
                  <li key={r.code}><span className="font-medium">{reasonLabel(r.code)}.</span> <span className="text-muted">{r.message}</span></li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ) : (
        <ErrorState title="Transaction missing" message="This alert’s transaction couldn’t be loaded." />
      )}

      </div>
      <div className="lg:col-start-2 lg:row-span-2 lg:row-start-1">{tx && <Explanation transactionId={tx.id} />}</div>
      <div className="lg:col-start-1 lg:row-start-2">
        <section aria-labelledby="review-title" className="animate-rise-in rounded-2xl border border-border bg-surface p-4" style={{ animationDelay: '120ms' }}>
          <h3 id="review-title" className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-lg bg-emerald/15 text-emerald"><ClipboardCheck aria-hidden className="size-4" /></span>
            Review
          </h3>
          {alert.status === 'open' ? <ReviewForm alertId={alert.id} onReviewed={onReviewed} /> : <ReviewHistory alert={alert} />}
        </section>
      </div>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  )
}

function Explanation({ transactionId }: { transactionId: string }) {
  const { session } = useAuth()
  const token = session?.access_token ?? ''
  const result = useAsync((signal) => fetchExplanation(transactionId, token, signal), token ? `explain-${transactionId}` : null)

  return (
    <section aria-labelledby="explain-title" className="animate-rise-in rounded-2xl border border-border bg-surface p-4" style={{ animationDelay: '60ms' }}>
      <h3 id="explain-title" className="flex items-center gap-2 font-semibold">
        <span className="grid size-7 place-items-center rounded-lg bg-violet/15 text-violet"><BrainCircuit aria-hidden className="size-4" /></span>
        Why the model flagged it
      </h3>
      <div className="mt-3">
        {result.loading ? <Skeleton rows={5} label="Loading explanation" />
          : result.error ? <ErrorState {...apiErrorMessage(result.error)} onRetry={result.reload} />
          : result.data ? (
            <>
              <ShapBars features={result.data.top_features} baseValue={result.data.base_value} modelScore={result.data.model_score} />
              {result.data.stored_model_version !== result.data.model_version && (
                <p className="mt-3 text-xs text-muted">
                  Scored by model {result.data.stored_model_version}; explained with the current model {result.data.model_version}.
                </p>
              )}
            </>
          ) : null}
      </div>
    </section>
  )
}

const ACTION_TEXT: Record<ReviewLabel, { done: string }> = {
  confirmed_fraud: { done: 'Confirmed as fraud' },
  false_alarm: { done: 'Marked as a false alarm' },
}

function ReviewForm({ alertId, onReviewed }: { alertId: number; onReviewed: () => void }) {
  const notify = useToast()
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState<ReviewLabel | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Set when the status was saved but the feedback row wasn't: retry saves only the feedback.
  const [pendingFeedback, setPendingFeedback] = useState<ReviewLabel | null>(null)

  async function submit(label: ReviewLabel) {
    setSaving(label)
    setError(null)
    const supabase = getSupabase()
    const result = pendingFeedback
      ? await saveFeedback(supabase, alertId, pendingFeedback, note)
      : await reviewAlert(supabase, alertId, label, note)
    setSaving(null)
    if (result.ok) {
      setPendingFeedback(null)
      notify({ tone: 'success', title: ACTION_TEXT[pendingFeedback ?? label].done, body: `Alert #${alertId}` })
      onReviewed()
    } else if (result.stage === 'feedback') {
      setPendingFeedback(pendingFeedback ?? label)
      setError(`The alert is marked “${STATUS_LABELS[pendingFeedback ?? label]}”, but your verdict wasn’t saved to feedback: ${result.message}`)
    } else if (result.stage === 'conflict') {
      setError(result.message)
      onReviewed()
    } else {
      setError(`Couldn’t save your review: ${result.message}`)
    }
  }

  const busy = saving !== null
  return (
    <div className="mt-3 space-y-3">
      <div>
        <label htmlFor="review-note" className="text-sm font-medium">Note <span className="font-normal text-muted">(optional)</span></label>
        <textarea id="review-note" rows={3} maxLength={NOTE_MAX} value={note} disabled={busy || pendingFeedback !== null}
          onChange={(e) => setNote(e.target.value)} aria-describedby="review-note-count"
          placeholder="What made you decide? e.g. customer confirmed the purchase."
          className="mt-1.5 block w-full resize-y rounded-lg border border-border bg-bg px-3 py-2 text-sm placeholder:text-muted/70 disabled:opacity-60" />
        <p id="review-note-count" className="mt-1 text-right text-xs text-muted tabular-nums">{note.length} / {NOTE_MAX}</p>
      </div>

      {error && <p role="alert" className="rounded-lg border border-high/40 bg-high-soft px-3 py-2 text-sm">{error}</p>}

      {pendingFeedback ? (
        <button type="button" disabled={busy} onClick={() => submit(pendingFeedback)}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-surface-2 disabled:opacity-60">
          {busy ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RotateCw aria-hidden className="size-4" />} Retry saving the verdict
        </button>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          <button type="button" disabled={busy} onClick={() => submit('confirmed_fraud')}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-high px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 dark:text-bg">
            {saving === 'confirmed_fraud' ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <ShieldX aria-hidden className="size-4" />}
            {saving === 'confirmed_fraud' ? 'Saving…' : 'Confirm fraud'}
          </button>
          <button type="button" disabled={busy} onClick={() => submit('false_alarm')}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-semibold hover:bg-surface-2 disabled:opacity-60">
            {saving === 'false_alarm' ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <ShieldCheck aria-hidden className="size-4" />}
            {saving === 'false_alarm' ? 'Saving…' : 'False alarm'}
          </button>
        </div>
      )}
    </div>
  )
}

function ReviewHistory({ alert }: { alert: Alert }) {
  const { session } = useAuth()
  const who = alert.reviewed_by && alert.reviewed_by === session?.user.id ? 'you' : 'another analyst'
  return (
    <div className="mt-3 space-y-3 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <StatusBadge status={alert.status} />
        {alert.reviewed_at && <span className="text-muted">by {who}, {formatDateTime(alert.reviewed_at)}</span>}
      </p>
      {alert.feedback?.length ? (
        <ul className="space-y-2">
          {alert.feedback.map((f) => (
            <li key={f.id} className="rounded-lg bg-surface-2 px-3 py-2">
              <p className="text-xs text-muted">{STATUS_LABELS[f.label]}, {formatDateTime(f.created_at)}</p>
              <p className="mt-0.5">{f.note ?? <span className="text-muted">No note</span>}</p>
            </li>
          ))}
        </ul>
      ) : <p className="text-muted">No feedback was recorded for this alert.</p>}
    </div>
  )
}
