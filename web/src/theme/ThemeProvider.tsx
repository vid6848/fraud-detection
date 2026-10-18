import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { savedTheme, THEME_KEY, ThemeContext, type Theme } from './context'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(savedTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // storage blocked (private mode): the theme just won't be remembered
    }
  }, [theme])

  const value = useMemo(() => ({
    theme,
    toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
  }), [theme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
