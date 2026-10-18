import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

/** A terminal command with a copy button. */
export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard blocked: the command is still selectable
    }
  }
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 py-1.5 pl-3 pr-1.5 text-left">
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs text-fg">{command}</code>
      <button type="button" onClick={copy} aria-label={copied ? 'Copied' : `Copy command: ${command}`}
        className="grid size-7 shrink-0 place-items-center rounded-md text-muted hover:bg-surface hover:text-fg">
        {copied ? <Check aria-hidden className="size-4 text-low" /> : <Copy aria-hidden className="size-4" />}
      </button>
    </div>
  )
}
