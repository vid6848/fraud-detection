import { BrainCircuit, Database, FolderGit2, Radio, ShieldCheck, UserCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { ScoringPreview } from '../components/landing/ScoringPreview'
import { Logo } from '../components/Logo'
import { ThemeToggle } from '../components/ThemeToggle'

const REPO_URL = 'https://github.com/vid6848/Fraud_Detection'

// The real pipeline, in order (so the numbering means something).
const STEPS = [
  { icon: Radio, title: 'Stream', body: 'A simulator replays held-out card transactions at 20 per second, like a payment network would.' },
  { icon: BrainCircuit, title: 'Score', body: 'The API runs each one through a calibrated Random Forest and two simple rules. Median time: 6.6 ms.' },
  { icon: Database, title: 'Store', body: 'Every result is saved in Supabase. Medium and High scores open an alert automatically.' },
  { icon: UserCheck, title: 'Review', body: 'An analyst sees why the model scored it, then confirms fraud or marks a false alarm.' },
]

// Test-set results from ml/artifacts/metadata.json (evaluated once; see docs/model_results.md).
const RESULTS = [
  { value: '0.744', label: 'PR-AUC', note: '95% CI 0.62–0.86. The headline metric for rare events.' },
  { value: '81%', label: 'Precision', note: '39 of 48 alerts were real fraud.' },
  { value: '75%', label: 'Recall', note: 'Three in four fraud cases caught.' },
  { value: '$3,556', label: 'Cost saved', note: 'Out of $6,169 lost with no model, after paying for reviews.' },
]

const primaryBtn =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-accent-fg hover:opacity-90'
const secondaryBtn =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-5 py-3 text-sm font-semibold hover:bg-surface-2'

export function Landing() {
  const { session } = useAuth()
  const dashboard = session ? { to: '/app', label: 'Open the dashboard' } : { to: '/login', label: 'Sign in to the dashboard' }

  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav aria-label="Site" className="flex items-center gap-2">
          <a href="#how" className="hidden rounded-lg px-3 py-2 text-sm text-muted hover:text-fg sm:inline">How it works</a>
          <a href="#results" className="hidden rounded-lg px-3 py-2 text-sm text-muted hover:text-fg sm:inline">Results</a>
          <ThemeToggle />
          <Link to={dashboard.to} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2">
            {session ? 'Dashboard' : 'Sign in'}
          </Link>
        </nav>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-8 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:pt-16">
          <div className="max-w-xl">
            <h1 className="text-[2.6rem] font-semibold leading-[1.05] tracking-[-0.035em] [font-stretch:88%] sm:text-6xl">
              Every card payment, scored before it settles.
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-muted">
              Fraud Watch scores each transaction in a few milliseconds, flags the risky ones,
              and puts them in front of an analyst with the reasons behind every score.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to={dashboard.to} className={primaryBtn}>
                <ShieldCheck aria-hidden className="size-4" /> {dashboard.label}
              </Link>
              <a href="#how" className={secondaryBtn}>See how it works</a>
            </div>
            <p className="mt-6 text-sm text-muted">
              Trained on 284,807 real card transactions, of which 492 are fraud.
            </p>
          </div>
          <ScoringPreview />
        </section>

        {/* Pipeline */}
        <section id="how" aria-labelledby="how-title" className="scroll-mt-8 border-y border-border bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <h2 id="how-title" className="text-2xl font-semibold tracking-tight sm:text-3xl">How a transaction moves through the system</h2>
            <p className="mt-2 max-w-2xl text-muted">Four steps, from the moment a payment arrives to an analyst’s decision.</p>
            <ol className="relative mt-10 grid gap-8 md:grid-cols-4 md:gap-6">
              <span aria-hidden className="absolute left-5 top-5 hidden h-px w-[calc(100%-2.5rem)] bg-border md:block" />
              {STEPS.map(({ icon: Icon, title, body }, i) => (
                <li key={title} className="relative flex gap-4 md:block">
                  <span className="relative z-10 grid size-10 shrink-0 place-items-center rounded-full border border-border bg-bg text-accent">
                    <Icon aria-hidden className="size-5" />
                  </span>
                  <div className="md:mt-5">
                    <h3 className="font-semibold"><span className="mr-2 text-muted tabular-nums">{i + 1}</span>{title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Results */}
        <section id="results" aria-labelledby="results-title" className="scroll-mt-8">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
              <div>
                <h2 id="results-title" className="text-2xl font-semibold tracking-tight sm:text-3xl">Measured once, on unseen data</h2>
                <p className="mt-3 leading-relaxed text-muted">
                  The model was tuned on earlier transactions, then tested a single time on the final period it had never seen.
                  Accuracy isn’t reported: calling everything “not fraud” would already score 99.83%.
                </p>
              </div>
              <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-2">
                {RESULTS.map((r) => (
                  <div key={r.label} className="bg-surface p-6">
                    <dt className="text-sm text-muted">{r.label}</dt>
                    <dd className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{r.value}</dd>
                    <dd className="mt-2 text-sm text-muted">{r.note}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Logo />
          <p>A portfolio project built with Python, FastAPI, Supabase and React.</p>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-fg">
            <FolderGit2 aria-hidden className="size-4" /> Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
