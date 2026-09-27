/** Small shared presentational building blocks. */

import type { ReactNode } from 'react'

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`card ${className}`}>{children}</div>
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: ReactNode
  subtitle?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-4 py-3 sm:px-5">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-ink-primary">{title}</h2>
        {subtitle ? (
          <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

/**
 * A single headline number. Used where a one-value chart would be noise —
 * a stat tile is the right form when there is no comparison or trend to show.
 */
export function StatTile({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  accent?: string
}) {
  return (
    <div className="card card-pad">
      <div className="flex items-center gap-2">
        {accent ? (
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: accent }}
          />
        ) : null}
        <span className="label-muted">{label}</span>
      </div>
      <div className="tabular mt-2 text-2xl font-semibold text-ink-primary">{value}</div>
      {hint ? <div className="mt-1 text-xs text-ink-muted">{hint}</div> : null}
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 p-10 text-sm text-ink-muted">
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-series-1"
      />
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card card-pad text-center">
      <p className="text-sm text-status-bad">{message}</p>
      {onRetry ? (
        <button type="button" className="btn-ghost mt-3" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <div className="p-8 text-center text-sm text-ink-muted">{message}</div>
}

/**
 * The standing reminder that model output is an estimate.
 * Shown next to every probability in the product, not once in a footer.
 */
export function Disclaimer({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs leading-relaxed text-ink-secondary">
      <span className="font-semibold text-ink-primary">Estimate, not a forecast. </span>
      {children}
    </p>
  )
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
  const tones = {
    neutral: 'bg-surface-3 text-ink-secondary border-line',
    good: 'bg-status-good/15 text-status-good border-status-good/30',
    warn: 'bg-status-warn/15 text-status-warn border-status-warn/30',
    bad: 'bg-status-bad/15 text-status-bad border-status-bad/30',
  }
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  )
}

/** Team colour swatch — always paired with the team's name, never colour alone. */
export function TeamDot({ color, label }: { color: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 shrink-0 rounded-sm"
        style={{ backgroundColor: color }}
      />
      {label ? <span className="truncate">{label}</span> : null}
    </span>
  )
}

export function SectionTitle({
  children,
  hint,
}: {
  children: ReactNode
  hint?: ReactNode
}) {
  return (
    <div className="mb-3">
      <h1 className="text-lg font-semibold text-ink-primary sm:text-xl">{children}</h1>
      {hint ? <p className="mt-1 text-sm text-ink-secondary">{hint}</p> : null}
    </div>
  )
}
