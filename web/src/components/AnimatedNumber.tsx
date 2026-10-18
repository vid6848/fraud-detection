import { useCountUp } from '../hooks/useCountUp'

/** A number that counts smoothly to its new value. Screen readers get the final value. */
export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const shown = useCountUp(value)
  return (
    <>
      <span aria-hidden>{format(shown)}</span>
      <span className="sr-only">{format(value)}</span>
    </>
  )
}
