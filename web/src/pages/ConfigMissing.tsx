import { Logo } from '../components/Logo'

/** Shown instead of the app when web/.env is missing values (no blank page). */
export function ConfigMissing({ missing }: { missing: string[] }) {
  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <Logo />
        <h1 className="mt-6 text-xl font-semibold">Configuration missing</h1>
        <p className="mt-2 text-sm text-muted">
          Copy <code className="font-mono">web/.env.example</code> to <code className="font-mono">web/.env</code>,
          fill in these values, then restart <code className="font-mono">npm run dev</code>:
        </p>
        <ul className="mt-4 space-y-1 font-mono text-sm">
          {missing.map((name) => <li key={name} className="rounded bg-surface-2 px-2 py-1">{name}</li>)}
        </ul>
        <p className="mt-4 text-xs text-muted">
          Use the Supabase <strong>publishable</strong> key only. Never put the secret key in the browser.
        </p>
      </div>
    </div>
  )
}
