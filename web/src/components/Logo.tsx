/**
 * Brand mark: a payment card with a signal trace running through it —
 * every card payment is read as it happens.
 */
export function LogoMark({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden focusable="false">
      <rect width="32" height="32" rx="9" className="fill-accent" />
      <rect x="6.5" y="9" width="19" height="14" rx="3" fill="none" className="stroke-accent-fg" strokeWidth="1.8" />
      <path d="M6.5 16.5h5l2-4 3.2 7.5 2.3-5 1.2 1.5h5.3" fill="none" className="stroke-accent-fg"
        strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark />
      <span className="text-[1.05rem] font-semibold tracking-[-0.01em]">Fraud Watch</span>
    </span>
  )
}
