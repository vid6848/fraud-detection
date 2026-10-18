import { ExternalLink, Maximize2 } from 'lucide-react'
import { useState } from 'react'
import { Modal } from '../Modal'

const FIGURES = [
  { file: 'pr_curve_test.png', title: 'Precision–recall curve (test)', caption: 'How precision trades off against recall on the held-out test period.' },
  { file: 'pr_curves_validation.png', title: 'All models compared (validation)', caption: 'Precision–recall curves of every model family on the validation period.' },
  { file: 'cost_vs_threshold.png', title: 'Cost vs. threshold (validation)', caption: 'Missed fraud plus review cost at each threshold; the alert threshold sits at the minimum.' },
  { file: 'calibration_curve.png', title: 'Calibration', caption: 'Predicted probability against the observed fraud rate, before and after isotonic calibration.' },
  { file: 'confusion_matrix_test.png', title: 'Confusion matrix (test)', caption: 'Outcomes on the test period at the chosen threshold.' },
  { file: 'shap_importance.png', title: 'Feature importance (SHAP)', caption: 'Average absolute SHAP value per feature: which inputs move the score most overall.' },
] as const

/** Training charts from Phase 2 (static PNGs); click one to see it large. */
export function FigureGallery() {
  const [open, setOpen] = useState<(typeof FIGURES)[number] | null>(null)
  return (
    <>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {FIGURES.map((f, i) => (
          <li key={f.file} className="animate-rise-in" style={{ animationDelay: `${i * 60}ms` }}>
            <figure className="group h-full overflow-hidden rounded-2xl border border-border bg-surface">
              <button type="button" onClick={() => setOpen(f)} aria-label={`Enlarge: ${f.title}`}
                className="relative block w-full overflow-hidden bg-white">
                <img src={`/figures/${f.file}`} alt={f.title} loading="lazy"
                  className="aspect-[4/3] w-full object-contain p-2 transition-transform duration-500 group-hover:scale-[1.03]" />
                <span aria-hidden className="absolute right-2 top-2 grid size-8 place-items-center rounded-lg bg-black/55 text-white opacity-0 transition-opacity group-hover:opacity-100">
                  <Maximize2 className="size-4" />
                </span>
              </button>
              <figcaption className="p-4">
                <p className="font-medium">{f.title}</p>
                <p className="mt-1 text-sm text-muted">{f.caption}</p>
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
      {open && (
        <Modal title={open.title} labelledBy="figure-title" size="xl" onClose={() => setOpen(null)}>
          <div className="space-y-3 p-5">
            <div className="rounded-xl bg-white p-3">
              <img src={`/figures/${open.file}`} alt={open.title} className="mx-auto max-h-[70dvh] w-auto object-contain" />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-muted">{open.caption}</p>
              <a href={`/figures/${open.file}`} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
                <ExternalLink aria-hidden className="size-4" /> Open full size
              </a>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
