import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { ThemeToggle } from '../components/ThemeToggle'
import { ThemeProvider } from './ThemeProvider'

describe('ThemeProvider', () => {
  afterEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('starts in dark mode by default', () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(document.documentElement).toHaveClass('dark')
    expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeInTheDocument()
  })

  it('toggles the theme and remembers the choice', async () => {
    const { unmount } = render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem('theme')).toBe('light')
    unmount()

    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument()
  })
})
