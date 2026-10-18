/** A labelled group of radio buttons styled as a segmented control (keyboard: arrow keys). */
export function Segmented<T extends string>({ legend, name, options, value, onChange }: {
  legend: string
  name: string
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-xs font-medium text-muted">{legend}</legend>
      <div className="inline-flex max-w-full overflow-x-auto rounded-xl border border-border bg-surface p-1">
        {options.map((o) => (
          <label key={o.value}
            className={`cursor-pointer whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--focus)] ${
              value === o.value ? 'bg-brand text-accent-fg shadow-sm' : 'text-muted hover:text-fg'}`}>
            <input type="radio" name={name} value={o.value} checked={value === o.value}
              onChange={() => onChange(o.value)} className="sr-only" />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
