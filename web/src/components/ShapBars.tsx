import { featureLabel, type FeatureContribution } from '../lib/explain'

const fmt = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`

/**
 * SHAP contributions as horizontal bars from a zero line: red pushes the fraud score up,
 * blue pulls it down. Values and descriptions are printed as text, so nothing relies on colour.
 */
export function ShapBars({ features, baseValue, modelScore }: {
  features: FeatureContribution[]
  baseValue: number
  modelScore: number
}) {
  if (!features.length) return <p className="text-sm text-muted">The API returned no feature contributions.</p>
  const sorted = [...features].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
  const maxUp = Math.max(0, ...sorted.map((f) => f.shap_value))
  const maxDown = Math.max(0, ...sorted.map((f) => -f.shap_value))
  const span = maxUp + maxDown || 1
  // Zero sits at the left when everything raises risk, at the right when everything lowers it.
  const zero = (maxDown / span) * 100
  const shown = sorted.reduce((sum, f) => sum + f.shap_value, 0)
  const hasUp = maxUp > 0, hasDown = maxDown > 0

  return (
    <div>
      <p className="text-sm text-muted">
        The forest’s raw score starts at its average of <span className="font-medium text-fg tabular-nums">{baseValue.toFixed(2)}</span> and
        ends at <span className="font-medium text-fg tabular-nums">{modelScore.toFixed(2)}</span>.
        These {sorted.length} features account for <span className="font-medium text-fg tabular-nums">{fmt(shown)}</span> of that change.
      </p>

      <ul className="mt-4 space-y-3.5" aria-label="Feature contributions, largest first">
        {sorted.map((f) => {
          const up = f.shap_value >= 0
          const width = (Math.abs(f.shap_value) / span) * 100
          return (
            <li key={f.feature}>
              <div className="grid grid-cols-[4.5rem_1fr_4rem] items-center gap-3">
                <span className="text-sm font-medium">{featureLabel(f.feature)}</span>
                <span className="relative h-3.5" aria-hidden title={f.description}>
                  <span className="absolute inset-y-0 w-px bg-border" style={{ left: `${zero}%` }} />
                  <span
                    className={`absolute inset-y-0 ${up ? 'rounded-r bg-shap-up' : 'rounded-l bg-shap-down'}`}
                    style={up ? { left: `${zero}%`, width: `max(${width}%, 2px)` } : { right: `${100 - zero}%`, width: `max(${width}%, 2px)` }}
                  />
                </span>
                <span className="text-right text-sm tabular-nums">{fmt(f.shap_value)}</span>
              </div>
              <p className="mt-1 pl-[5.25rem] text-xs text-muted">
                <span className="sr-only">{up ? 'Raises risk: ' : 'Lowers risk: '}</span>{f.description}
              </p>
            </li>
          )
        })}
      </ul>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted" aria-hidden>
        {hasUp && <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-shap-up" />Raises risk</span>}
        {hasDown && <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-shap-down" />Lowers risk</span>}
      </div>
    </div>
  )
}
