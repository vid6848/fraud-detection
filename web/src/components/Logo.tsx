/**
 * Brand mark: a payment card with a signal trace running through it —
 * every card payment is read as it happens.
 */
export function LogoMark({ className = 'size-8' }: { className?: string }) {
  return (
    <span className={`bg-brand grid shrink-0 place-items-center rounded-[9px] shadow-[0_6px_20px_-6px_var(--accent)] ${className}`}>
      <svg viewBox="0 0 32 32" className="size-full" aria-hidden focusable="false">
        <rect x="6.5" y="9" width="19" height="14" rx="3" fill="none" className="stroke-accent-fg" strokeWidth="1.8" />
        <path d="M6.5 16.5h5l2-4 3.2 7.5 2.3-5 1.2 1.5h5.3" fill="none" className="stroke-accent-fg"
          strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
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
