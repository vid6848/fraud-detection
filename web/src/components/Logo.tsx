import { ShieldCheck } from 'lucide-react'

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-fg">
        <ShieldCheck aria-hidden className="size-5" />
      </span>
      <span>Fraud Watch</span>
    </span>
  )
}
