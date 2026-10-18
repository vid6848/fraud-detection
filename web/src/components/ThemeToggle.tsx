import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../theme/context'

export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button type="button" onClick={toggle} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}
      className="grid size-9 place-items-center rounded-xl border border-border bg-surface/70 text-muted backdrop-blur transition-colors hover:bg-surface-2 hover:text-fg">
      {theme === 'dark'
        ? <Sun aria-hidden className="size-4 text-amber" />
        : <Moon aria-hidden className="size-4 text-violet" />}
    </button>
  )
}
