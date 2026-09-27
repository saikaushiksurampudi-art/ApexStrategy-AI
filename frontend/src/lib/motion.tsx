/**
 * Motion primitives.
 *
 * Every animation here checks `prefers-reduced-motion` and collapses to its
 * final state when the viewer has asked for less movement. That is not a
 * courtesy -- vestibular disorders make large parallax and sliding motion
 * genuinely unpleasant -- so the reduced path renders the same information,
 * just immediately.
 */

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'

/** True when the viewer has asked for reduced motion. Reacts to live changes. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return reduced
}

/**
 * Fires once when the element first scrolls into view.
 *
 * Fails open. Anything gated on this sits at `opacity: 0` until it fires, so a
 * missing IntersectionObserver, an `overflow: hidden` ancestor that never
 * reports intersection, or a print/screenshot context would otherwise hide
 * real content permanently. `fallbackMs` guarantees it appears regardless;
 * content is never sacrificed to an effect.
 */
export function useInView<T extends HTMLElement>(
  options: { threshold?: number; rootMargin?: string; fallbackMs?: number } = {},
) {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)
  const { threshold = 0.12, rootMargin = '0px', fallbackMs = 2500 } = options

  useEffect(() => {
    const element = ref.current
    if (!element) return

    if (typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold, rootMargin },
    )
    observer.observe(element)

    // Safety net: reveal even if the observer never reports an intersection.
    const timer = window.setTimeout(() => {
      setInView(true)
      observer.disconnect()
    }, fallbackMs)

    return () => {
      observer.disconnect()
      window.clearTimeout(timer)
    }
  }, [threshold, rootMargin, fallbackMs])

  return { ref, inView }
}

/** Fades and lifts its children into view on scroll. */
export function Reveal({
  children,
  delay = 0,
  y = 16,
  className = '',
}: {
  children: ReactNode
  delay?: number
  y?: number
  className?: string
}) {
  const reduced = usePrefersReducedMotion()
  const { ref, inView } = useInView<HTMLDivElement>()
  const visible = reduced || inView

  const style: CSSProperties = reduced
    ? {}
    : {
        opacity: visible ? 1 : 0,
        transform: visible ? 'none' : `translateY(${y}px)`,
        transition: `opacity 620ms cubic-bezier(.22,.61,.36,1) ${delay}ms,
                     transform 620ms cubic-bezier(.22,.61,.36,1) ${delay}ms`,
      }

  return (
    <div ref={ref} style={style} className={className}>
      {children}
    </div>
  )
}

/**
 * Counts up to a target number once visible.
 *
 * Uses requestAnimationFrame with an ease-out curve so the number decelerates
 * into place rather than stopping dead.
 */
export function CountUp({
  to,
  duration = 1400,
  decimals = 0,
  prefix = '',
  suffix = '',
}: {
  to: number
  duration?: number
  decimals?: number
  prefix?: string
  suffix?: string
}) {
  const reduced = usePrefersReducedMotion()
  const { ref, inView } = useInView<HTMLSpanElement>({ threshold: 0.3 })
  const [value, setValue] = useState(reduced ? to : 0)

  useEffect(() => {
    if (reduced) {
      setValue(to)
      return
    }
    if (!inView) return

    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(to * eased)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [inView, to, duration, reduced])

  return (
    <span ref={ref} className="tabular">
      {prefix}
      {value.toFixed(decimals)}
      {suffix}
    </span>
  )
}

/** A bar that grows from zero to `value` (0..1) when it scrolls into view. */
export function GrowBar({
  value,
  color,
  className = '',
  delay = 0,
}: {
  value: number
  color: string
  className?: string
  delay?: number
}) {
  const reduced = usePrefersReducedMotion()
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.2 })
  const target = Math.max(0, Math.min(1, value)) * 100
  const width = reduced || inView ? target : 0

  return (
    <div
      ref={ref}
      className={`relative overflow-hidden rounded-full bg-surface-3 ${className}`}
    >
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{
          width: `${width}%`,
          backgroundColor: color,
          transition: reduced
            ? undefined
            : `width 900ms cubic-bezier(.22,.61,.36,1) ${delay}ms`,
        }}
      />
    </div>
  )
}

/** Staggered delay helper, capped so long lists do not crawl. */
export const stagger = (index: number, step = 60, max = 420): number =>
  Math.min(index * step, max)
