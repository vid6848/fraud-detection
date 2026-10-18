import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light'

export interface ThemeState {
  theme: Theme
  toggle: () => void
}

export const ThemeContext = createContext<ThemeState | null>(null)

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}

export const THEME_KEY = 'theme'

/** Dark is the default; only an explicit saved "light" switches it. */
export function savedTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}
