/**
 * Was this useful?
 *
 * Ratings are the product's main quality signal: they are what surfaces weak
 * explanations, unclear charts and gaps in the dataset. An "unhelpful" rating
 * asks one follow-up question, because a bare thumbs-down says something is
 * wrong but not what.
 */

import { useState } from 'react'
import { api } from '../lib/api'

const REASONS = [
  { id: 'not_grounded', label: 'Not backed by the data' },
  { id: 'unclear_explanation', label: 'Explanation was unclear' },
  { id: 'wrong_numbers', label: 'Numbers look wrong' },
  { id: 'missing_context', label: 'Missing context I needed' },
  { id: 'too_vague', label: 'Too vague to act on' },
]

export function FeedbackWidget({
  surface,
  referenceId,
  context,
  className = '',
}: {
  surface: string
  referenceId?: string
  context?: Record<string, unknown>
  className?: string
}) {
  const [rating, setRating] = useState<'helpful' | 'unhelpful' | null>(null)
  const [reason, setReason] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = async (value: 'helpful' | 'unhelpful', pickedReason?: string) => {
    setError(null)
    try {
      await api.feedback({
        surface,
        rating: value,
        reference_id: referenceId,
        reason: pickedReason,
        context,
      })
      if (value === 'helpful' || pickedReason) setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send feedback')
    }
  }

  if (done) {
    return (
      <p className={`text-xs text-ink-muted ${className}`}>
        Thanks — this helps us find weak explanations.
      </p>
    )
  }

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">Was this useful?</span>
        <button
          type="button"
          className={`btn-ghost !px-2.5 !py-1 !text-xs ${
            rating === 'helpful' ? '!border-status-good !text-status-good' : ''
          }`}
          onClick={() => {
            setRating('helpful')
            void send('helpful')
          }}
        >
          Yes
        </button>
        <button
          type="button"
          className={`btn-ghost !px-2.5 !py-1 !text-xs ${
            rating === 'unhelpful' ? '!border-status-bad !text-status-bad' : ''
          }`}
          onClick={() => {
            setRating('unhelpful')
            void send('unhelpful')
          }}
        >
          No
        </button>
      </div>

      {rating === 'unhelpful' ? (
        <div className="mt-2">
          <p className="mb-1.5 text-xs text-ink-muted">What was wrong?</p>
          <div className="flex flex-wrap gap-1.5">
            {REASONS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`chip transition-colors hover:border-line-strong hover:text-ink-primary ${
                  reason === item.id ? '!border-status-bad !text-status-bad' : ''
                }`}
                onClick={() => {
                  setReason(item.id)
                  void send('unhelpful', item.id)
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-1.5 text-xs text-status-bad">{error}</p> : null}
    </div>
  )
}
