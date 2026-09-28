/**
 * Chart primitives shared across pages.
 *
 * Conventions enforced here so every chart reads as one system:
 *  - recessive grid (horizontal only) and axis ink,
 *  - a hover tooltip on every plotted form,
 *  - a legend whenever there are two or more series,
 *  - a "Table" toggle, so no chart is the only way to read its numbers.
 */

import { useState, type ReactNode } from 'react'
import { axisProps, gridProps } from '../lib/palette'

export { axisProps, gridProps }

/** Styled container for a chart plus its legend, notes and table view. */
export function ChartFrame({
  title,
  subtitle,
  legend,
  children,
  table,
  note,
  height = 280,
}: {
  title: ReactNode
  subtitle?: ReactNode
  legend?: ReactNode
  children: ReactNode
  table?: ReactNode
  note?: ReactNode
  height?: number
}) {
  const [showTable, setShowTable] = useState(false)

  return (
    <section className="card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink-primary">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p> : null}
        </div>
        {table ? (
          <div className="flex shrink-0 gap-1 rounded-lg border border-line bg-surface-2 p-0.5">
            <ToggleButton active={!showTable} onClick={() => setShowTable(false)}>
              Chart
            </ToggleButton>
            <ToggleButton active={showTable} onClick={() => setShowTable(true)}>
              Table
            </ToggleButton>
          </div>
        ) : null}
      </div>

      {legend && !showTable ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 px-4 pt-3 sm:px-5">{legend}</div>
      ) : null}

      <div className="px-2 py-3 sm:px-3">
        {showTable && table ? (
          <div
            className="max-h-[420px] overflow-auto px-2"
            tabIndex={0}
            role="region"
            aria-label="Chart data as a table"
          >
            {table}
          </div>
        ) : (
          <div style={{ height }}>{children}</div>
        )}
      </div>

      {note ? (
        <p className="border-t border-line px-4 py-2.5 text-xs leading-relaxed text-ink-muted sm:px-5">
          {note}
        </p>
      ) : null}
    </section>
  )
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
        active
          ? 'bg-surface-3 text-ink-primary'
          : 'text-ink-muted hover:text-ink-secondary'
      }`}
    >
      {children}
    </button>
  )
}

/** Legend entry. The swatch never carries identity on its own — the label does. */
export function LegendItem({ color, label }: { color: string; label: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-secondary">
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 rounded-sm"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  )
}

/** Shared Recharts tooltip body. */
export function TooltipCard({
  title,
  rows,
  footer,
}: {
  title: ReactNode
  rows: Array<{ label: ReactNode; value: ReactNode; color?: string }>
  footer?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-line-strong bg-surface-2 px-3 py-2 shadow-xl">
      <div className="mb-1.5 text-xs font-semibold text-ink-primary">{title}</div>
      <div className="space-y-1">
        {rows.map((row, index) => (
          <div key={index} className="flex items-center justify-between gap-4 text-xs">
            <span className="inline-flex items-center gap-1.5 text-ink-secondary">
              {row.color ? (
                <span
                  aria-hidden="true"
                  className="h-2 w-2 rounded-sm"
                  style={{ backgroundColor: row.color }}
                />
              ) : null}
              {row.label}
            </span>
            <span className="tabular font-medium text-ink-primary">{row.value}</span>
          </div>
        ))}
      </div>
      {footer ? <div className="mt-1.5 text-[11px] text-ink-muted">{footer}</div> : null}
    </div>
  )
}

/**
 * Horizontal probability meter.
 *
 * Preferred over a bar chart when each row is an independent 0–100% value:
 * the shared 0–100% track makes the comparison read directly, and there is no
 * axis to mislead. Rounded data-end, anchored at the baseline.
 */
export function ProbabilityMeter({
  value,
  color,
  label,
  valueLabel,
}: {
  value: number
  color: string
  label?: ReactNode
  valueLabel?: ReactNode
}) {
  const width = Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="flex items-center gap-3">
      {label ? <div className="w-28 shrink-0 truncate text-xs">{label}</div> : null}
      <div
        className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-surface-3"
        role="img"
        aria-label={`${width.toFixed(0)} percent`}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </div>
      {valueLabel ? (
        <div className="tabular w-12 shrink-0 text-right text-xs font-medium text-ink-primary">
          {valueLabel}
        </div>
      ) : null}
    </div>
  )
}
