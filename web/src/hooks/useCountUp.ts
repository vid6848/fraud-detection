import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from './useReducedMotion'

/** Animate a number from its previous value to `target` (instant with reduced motion). */
export function useCountUp(target: number, durationMs = 700): number {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(target)
  const from = useRef(target)

  useEffect(() => {
    if (reduced || !Number.isFinite(target)) {
      from.current = target
      return
    }
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(begin + (target - begin) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else from.current = target
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); from.current = target }
  }, [target, durationMs, reduced])

  return reduced || !Number.isFinite(target) ? target : value
}
