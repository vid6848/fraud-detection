import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function PageHeader({ title, description, actions, icon: Icon }: {
  title: string
  description?: string
  actions?: ReactNode
  icon?: LucideIcon
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3.5">
        {Icon && (
          <span className="bg-brand mt-0.5 grid size-11 shrink-0 place-items-center rounded-xl text-accent-fg shadow-[0_8px_24px_-8px_var(--accent)]">
            <Icon aria-hidden className="size-5" />
          </span>
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
