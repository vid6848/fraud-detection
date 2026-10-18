import { BarChart3, Cpu, FlaskConical, Images, Scale, Server, Sparkles, Waves } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { CopyCommand } from '../components/CopyCommand'
import { ConfusionMatrix } from '../components/model/ConfusionMatrix'
import { FigureGallery } from '../components/model/FigureGallery'
import { MetricCard } from '../components/model/MetricCard'
import { ModelComparison } from '../components/model/ModelComparison'
import { SplitBar } from '../components/model/SplitBar'
import { PageHeader } from '../components/PageHeader'
import { EmptyState, ErrorState, Skeleton } from '../components/StateViews'
import { DriftPanel } from '../components/system/DriftPanel'
import { SystemPanel } from '../components/system/SystemPanel'
import { useAsync } from '../hooks/useAsync'
import { formatCurrencyWhole, formatDateTime } from '../lib/format'
import { label, STRATEGY_LABELS, type ModelRun } from '../lib/modelRuns'
import { getSupabase } from '../lib/supabase'

const pct = (n: number) => `${(n * 100).toFixed(1)}%`
const pct2 = (n: number) => `${(n * 100).toFixed(2)}%`
const dec3 = (n: number) => n.toFixed(3)

async function loadRuns(): Promise<ModelRun[]> {
  const { data, error } = await getSupabase().from('model_runs')
    .select('id, version, trained_at, metrics').order('trained_at', { ascending: false })
  if (error) throw new Error(error.message)
  return (data ?? []) as ModelRun[]
}

function Section({ id, icon: Icon, title, description, children }: {
  id: string; icon: typeof Cpu; title: string; description?: string; children: ReactNode
}) {
  return (
    <section aria-labelledby={`${id}-title`} id={id} className="scroll-mt-28">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent"><Icon aria-hidden className="size-4.5" /></span>
        <div>
          <h2 id={`${id}-title`} className="text-lg font-semibold tracking-tight">{title}</h2>
          {description && <p className="text-sm text-muted">{description}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function Card({ title, icon: Icon, children, className = '' }: { title: string; icon?: typeof Cpu; children: ReactNode; className?: string }) {
  return (
    <div className={`animate-rise-in rounded-2xl border border-border bg-surface p-4 ${className}`}>
      <h3 className="mb-3 flex items-center gap-2 font-semibold">
        {Icon && <Icon aria-hidden className="size-4 text-accent" />}{title}
      </h3>
      {children}
    </div>
  )
}

export function ModelSystem() {
  const runs = useAsync(loadRuns, 'model-runs')
  const [version, setVersion] = useState<string | null>(null)
  const list = runs.data ?? []
  const run = list.find((r) => r.version === version) ?? list[0]

  return (
    <>
      <PageHeader title="Model & system" icon={Cpu}
        description="How well the model performs on unseen data, and how the API is doing right now."
        actions={
          <nav aria-label="On this page" className="flex flex-wrap gap-2 text-sm">
            {[['#model', 'Model'], ['#charts', 'Charts'], ['#drift', 'Drift'], ['#system', 'System']].map(([href, text]) => (
              <a key={href} href={href} className="rounded-xl border border-border bg-surface px-3 py-1.5 font-medium text-muted transition-colors hover:text-fg">{text}</a>
            ))}
          </nav>
        } />

      <div className="space-y-10">
        <Section id="model" icon={FlaskConical} title="Model quality"
          description="Measured once on the final, unseen test period. Bands show 95% bootstrap confidence intervals.">
          {runs.loading ? <Skeleton rows={4} label="Loading model results" />
            : runs.error ? <ErrorState title="Couldn’t load model results" message={(runs.error as Error).message} onRetry={runs.reload} />
            : !run ? (
              <EmptyState title="No model results yet" icon={<BarChart3 className="size-8" />}>
                <p>Load the trained model’s metrics into Supabase from the project folder:</p>
                <div className="mt-3"><CopyCommand command="python scripts/load_model_runs.py" /></div>
              </EmptyState>
            ) : <ModelResults run={run} runs={list} onVersion={setVersion} />}
        </Section>

        <Section id="charts" icon={Images} title="Training charts" description="Generated in Phase 2 by the training pipeline. Click a chart to enlarge it.">
          <FigureGallery />
        </Section>

        <Section id="drift" icon={Waves} title="Score drift"
          description="Are live fraud scores still distributed like the training scores? Checked with the Population Stability Index (PSI).">
          <DriftPanel />
        </Section>

        <Section id="system" icon={Server} title="System health" description="Live from the API’s /health and /metrics endpoints.">
          <SystemPanel />
        </Section>
      </div>
    </>
  )
}

function ModelResults({ run, runs, onVersion }: { run: ModelRun; runs: ModelRun[]; onVersion: (v: string) => void }) {
  const m = run.metrics
  const t = m.test_metrics
  const ci = t.ci95 ?? {}
  const cm = t.confusion_matrix
  const fraudRate = m.split ? m.split.test.fraud_pct / 100 : null
  // Accuracy from the confusion matrix, next to the "flag nothing" baseline for context.
  const total = cm.tn + cm.fp + cm.fn + cm.tp
  const accuracy = total ? (cm.tn + cm.tp) / total : 0
  const baseline = total ? (cm.tn + cm.fp) / total : 0

  return (
    <div className="space-y-4">
      {/* Model identity */}
      <div className="relative animate-rise-in overflow-hidden rounded-2xl border border-border bg-surface p-5">
        <div aria-hidden className="bg-brand pointer-events-none absolute -right-16 -top-20 size-56 rounded-full opacity-20 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="bg-brand grid size-12 place-items-center rounded-xl text-accent-fg"><Sparkles aria-hidden className="size-6" /></span>
            <div>
              <p className="text-xl font-semibold tracking-tight">{m.model.label}</p>
              <p className="text-sm text-muted">{label(STRATEGY_LABELS, m.model.imbalance_strategy)}, trained {formatDateTime(run.trained_at)}</p>
            </div>
          </div>
          {runs.length > 1 ? (
            <label className="text-sm">
              <span className="mr-2 text-muted">Version</span>
              <select value={run.version} onChange={(e) => onVersion(e.target.value)}
                className="rounded-lg border border-border bg-surface px-2 py-1.5 font-medium">
                {runs.map((r) => <option key={r.id} value={r.version}>{r.version}</option>)}
              </select>
            </label>
          ) : <span className="rounded-full border border-border px-3 py-1 text-sm">Version <span className="font-semibold">{run.version}</span></span>}
        </div>
        <dl className="relative mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div><dt className="text-muted">High-risk threshold</dt><dd className="mt-0.5 font-semibold tabular-nums">{m.threshold.toFixed(3)}</dd></div>
          <div><dt className="text-muted">Chosen by</dt><dd className="mt-0.5 font-semibold">Lowest validation cost</dd></div>
          <div><dt className="text-muted">Review cost per alert</dt><dd className="mt-0.5 font-semibold tabular-nums">{m.review_cost_per_alert !== undefined ? `$${m.review_cost_per_alert.toFixed(2)}` : '–'}</dd></div>
          <div><dt className="text-muted">Test transactions</dt><dd className="mt-0.5 font-semibold tabular-nums">{m.split ? `${m.split.test.rows.toLocaleString()} (${m.split.test.frauds} fraud)` : '–'}</dd></div>
        </dl>
      </div>

      {/* Headline metrics */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="PR-AUC" value={t.pr_auc} interval={ci.pr_auc} scale={[0, 1]} format={dec3} tone="violet"
          note={fraudRate !== null ? `Area under the precision–recall curve. Guessing would score about ${fraudRate.toFixed(4)}, the fraud rate.` : undefined} />
        <MetricCard label="Recall at 90% precision" value={t.recall_at_90_precision} interval={ci.recall_at_90_precision} scale={[0, 1]} format={pct} tone="cyan" delay={60}
          note="Share of fraud caught while 9 in 10 alerts are real fraud." />
        <MetricCard label="Cost saved" value={t.cost_saved} interval={ci.cost_saved} format={formatCurrencyWhole} tone="emerald" delay={120}
          scale={[0, Math.max(t.cost_no_model, ci.cost_saved?.high ?? 0)]}
          note={`Out of ${formatCurrencyWhole(t.cost_no_model)} lost with no model (missed fraud plus review costs).`} />
        <MetricCard label="Precision" value={t.precision} interval={ci.precision} scale={[0, 1]} format={pct} tone="amber" delay={180}
          note={`${cm.tp} of ${t.alerts} alerts were fraud.`} />
        <MetricCard label="Recall" value={t.recall} interval={ci.recall} scale={[0, 1]} format={pct} tone="rose" delay={240}
          note={`${cm.tp} of ${cm.tp + cm.fn} frauds were caught.`} />
        <MetricCard label="Fraud dollars caught" value={t.pct_fraud_dollars_caught / 100}
          interval={ci.pct_fraud_dollars_caught && { low: ci.pct_fraud_dollars_caught.low / 100, high: ci.pct_fraud_dollars_caught.high / 100 }}
          scale={[0, 1]} format={pct} tone="violet" delay={300}
          note={`${formatCurrencyWhole(t.fraud_amount_caught)} of ${formatCurrencyWhole(t.total_fraud_amount)} in fraudulent charges.`} />
        <MetricCard label="F1 score" value={t.f1} interval={ci.f1} scale={[0, 1]} format={dec3} tone="cyan" delay={360}
          note="Balance of precision and recall (1 is perfect)." />
        <MetricCard label="Accuracy" value={accuracy} scale={[0, 1]} format={pct2} tone="emerald" delay={420}
          note={`${(cm.tn + cm.tp).toLocaleString()} of ${total.toLocaleString()} transactions classified correctly. Flagging nothing would already score ${pct2(baseline)}, because fraud is so rare, so PR-AUC and recall are the better guides.`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card title="Outcomes on the test period" icon={Scale}>
          <ConfusionMatrix cm={cm} />
          <p className="mt-2 text-xs text-muted">At threshold {t.threshold.toFixed(3)}. Accuracy {pct2(accuracy)} (flagging nothing: {pct2(baseline)}).</p>
        </Card>
        <Card title="Model comparison" icon={BarChart3}>
          <ModelComparison metrics={m} />
          <p className="mt-3 text-xs text-muted">Best setting per model on the validation period. Only the deployed model was evaluated on test.</p>
        </Card>
        <Card title="Data and calibration" icon={FlaskConical} className="lg:col-span-2 xl:col-span-1">
          {m.split && <SplitBar split={m.split} />}
          {m.calibration && (
            <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm">
              <div>
                <dt className="text-muted">Calibration</dt>
                <dd className="mt-0.5 font-semibold capitalize">{m.calibration.method}</dd>
              </div>
              <div>
                <dt className="text-muted">Validation Brier score</dt>
                <dd className="mt-0.5 font-semibold tabular-nums">
                  {m.calibration.val_brier_uncalibrated.toFixed(6)} → <span className="text-emerald">{m.calibration.val_brier_calibrated.toFixed(6)}</span>
                </dd>
              </div>
            </dl>
          )}
        </Card>
      </div>
    </div>
  )
}
