import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * Centred dialog: blurred backdrop, scale-in, Esc / backdrop click to close,
 * focus moves inside on open and Tab stays inside while it's open.
 */
export function Modal({ title, titleExtra, onClose, children, size = 'lg', labelledBy = 'modal-title' }: {
  title: ReactNode
  titleExtra?: ReactNode
  onClose: () => void
  children: ReactNode
  size?: 'md' | 'lg' | 'xl'
  labelledBy?: string
}) {
  const panel = useRef<HTMLDivElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose })

  useEffect(() => {
    heading.current?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current()
      if (e.key !== 'Tab' || !panel.current) return
      const items = panel.current.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], textarea:not([disabled]), input:not([disabled]), [tabindex="0"]')
      if (!items.length) return
      const first = items[0]!, last = items[items.length - 1]!
      if (e.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [])

  const width = { md: 'max-w-lg', lg: 'max-w-3xl', xl: 'max-w-5xl' }[size]

  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center p-3 sm:p-6">
      <button type="button" aria-label="Close dialog" tabIndex={-1} onClick={onClose}
        className="absolute inset-0 animate-fade-in bg-[#020617]/60 backdrop-blur-sm" />
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        className={`relative flex max-h-[calc(100dvh-1.5rem)] w-full ${width} animate-modal-in flex-col overflow-hidden rounded-2xl border border-border bg-bg shadow-[0_30px_80px_-20px_rgba(2,6,23,0.6)] sm:max-h-[calc(100dvh-3rem)]`}>
        <div aria-hidden className="bg-brand h-1 shrink-0" />
        <div className="flex items-center justify-between gap-3 border-b border-border bg-surface px-5 py-4">
          <div className="flex min-w-0 flex-wrap items-center gap-2.5">
            <h2 id={labelledBy} ref={heading} tabIndex={-1} className="text-lg font-semibold">{title}</h2>
            {titleExtra}
          </div>
          <button type="button" onClick={onClose} aria-label="Close dialog"
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-border text-muted transition-colors hover:bg-surface-2 hover:text-fg">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        {/* Focusable so keyboard users can scroll long content (WCAG 2.1.1). */}
        <div className="flex-1 overflow-y-auto" tabIndex={0} role="region" aria-labelledby={labelledBy}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
