/**
 * A labelled input with inline validation.
 *
 * Errors appear only after the field has been touched or a submit attempted,
 * so the form does not shout at someone who has simply not finished typing.
 * The error is wired to the input with aria-describedby and aria-invalid.
 */

import { useId, type InputHTMLAttributes } from 'react'

interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string
  error?: string | null
  hint?: string
  showError?: boolean
}

export function Field({
  label,
  error,
  hint,
  showError = true,
  className = '',
  ...inputProps
}: FieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const visibleError = showError ? error : null

  return (
    <div className={className}>
      <label htmlFor={id} className="label-muted mb-1.5 block">
        {label}
      </label>
      <input
        id={id}
        className={`input ${visibleError ? '!border-status-bad' : ''}`}
        aria-invalid={visibleError ? true : undefined}
        aria-describedby={visibleError ? errorId : hint ? hintId : undefined}
        {...inputProps}
      />
      {visibleError ? (
        <p id={errorId} role="alert" className="mt-1.5 text-xs text-status-bad">
          {visibleError}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-1.5 text-xs text-ink-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

/** Coarse password-strength indicator. Never gates submission. */
export function StrengthMeter({ score, label }: { score: number; label: string }) {
  const colors = ['#e66767', '#e66767', '#c98500', '#199e70']
  return (
    <div className="mt-2">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="h-1 flex-1 rounded-full transition-colors"
            style={{
              backgroundColor: index < score ? colors[score] : '#252833',
            }}
          />
        ))}
      </div>
      <p className="mt-1 text-xs text-ink-muted">Password strength: {label}</p>
    </div>
  )
}
