import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProbabilityBar } from './ProbabilityBar'
import { ReasonChips } from './ReasonChips'
import { RiskBadge } from './RiskBadge'
import { StatusBadge } from './StatusBadge'

describe('badges', () => {
  it.each([['LOW', 'Low'], ['MEDIUM', 'Medium'], ['HIGH', 'High']] as const)('risk %s shows the word, not just a colour', (level, text) => {
    render(<RiskBadge level={level} />)
    expect(screen.getByText(text)).toBeInTheDocument()
  })

  it.each([['open', 'Open'], ['confirmed_fraud', 'Confirmed fraud'], ['false_alarm', 'False alarm']] as const)('status %s', (status, text) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(text)).toBeInTheDocument()
  })

  it('prints the probability next to its (decorative) bar', () => {
    const { container } = render(<ProbabilityBar probability={0.4286} level="MEDIUM" />)
    expect(screen.getByText('42.9%')).toBeInTheDocument()
    expect(container.querySelector('[aria-hidden]')).not.toBeNull()
  })

  it('gives reason chips their full message for screen readers and on hover', () => {
    render(<ReasonChips reasons={[{ code: 'NIGHT_HOURS', message: 'Between 01:00 and 07:00' }]} />)
    const chip = screen.getByRole('listitem')
    expect(chip).toHaveAttribute('title', 'Between 01:00 and 07:00')
    expect(chip).toHaveTextContent('Night hours: Between 01:00 and 07:00')
  })

  it('says None when there are no reasons', () => {
    render(<ReasonChips reasons={[]} />)
    expect(screen.getByText('None')).toBeInTheDocument()
  })
})
