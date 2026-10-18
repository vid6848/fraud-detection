import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConfigMissing } from './ConfigMissing'

describe('ConfigMissing', () => {
  it('lists the missing variables with local instructions in development', () => {
    render(<ConfigMissing missing={['VITE_API_URL']} production={false} />)
    expect(screen.getByText('VITE_API_URL')).toBeInTheDocument()
    expect(screen.getByText('web/.env.example')).toBeInTheDocument()
  })

  it('points to the hosting settings and a redeploy in production', () => {
    render(<ConfigMissing missing={['VITE_SUPABASE_URL']} production />)
    expect(screen.getByText(/Settings → Environment\s+Variables/)).toBeInTheDocument()
    expect(screen.getByText('redeploy')).toBeInTheDocument()
    expect(screen.queryByText('web/.env.example')).not.toBeInTheDocument()
  })
})
