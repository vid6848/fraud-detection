import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

function renderModal(onClose = vi.fn()) {
  render(
    <Modal title="Alert #1" onClose={onClose}>
      <button type="button">First action</button>
      <button type="button">Last action</button>
    </Modal>,
  )
  return onClose
}

describe('Modal', () => {
  it('is a labelled dialog that takes focus and locks page scroll', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: 'Alert #1' })).toBeInTheDocument()
    expect(document.activeElement).toHaveTextContent('Alert #1')
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('closes with Escape, the close button, or a backdrop click', async () => {
    const onClose = renderModal()
    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getAllByRole('button', { name: 'Close dialog' })[1]!)
    await userEvent.click(screen.getAllByRole('button', { name: 'Close dialog' })[0]!)
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('keeps Tab focus inside the dialog', async () => {
    renderModal()
    screen.getByRole('button', { name: 'Last action' }).focus()
    await userEvent.tab()
    expect(document.activeElement).toBe(screen.getAllByRole('button', { name: 'Close dialog' })[1])
    await userEvent.tab({ shift: true })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Last action' }))
  })
})
