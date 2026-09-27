/**
 * Form validation rules, shared between the UI and its tests.
 *
 * These mirror the server's Pydantic schemas. The server remains the authority
 * -- client validation exists to give immediate feedback, not to be trusted --
 * so any rule here must also hold in `backend/app/schemas.py`.
 */

export type ValidationResult = string | null

/** Deliberately permissive: the real check is whether the address receives mail. */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_LENGTH = 128
export const MAX_DISPLAY_NAME_LENGTH = 120
export const MAX_QUESTION_LENGTH = 1000
export const MIN_QUESTION_LENGTH = 3

export function validateEmail(value: string): ValidationResult {
  const trimmed = value.trim()
  if (!trimmed) return 'Email is required'
  if (!EMAIL_PATTERN.test(trimmed)) return 'Enter a valid email address'
  return null
}

export function validatePassword(value: string): ValidationResult {
  if (!value) return 'Password is required'
  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`
  }
  if (value.length > MAX_PASSWORD_LENGTH) {
    return `Password must be ${MAX_PASSWORD_LENGTH} characters or fewer`
  }
  return null
}

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): ValidationResult {
  if (!confirmation) return 'Confirm your password'
  if (password !== confirmation) return 'Passwords do not match'
  return null
}

export function validateDisplayName(value: string): ValidationResult {
  if (value.length > MAX_DISPLAY_NAME_LENGTH) {
    return `Name must be ${MAX_DISPLAY_NAME_LENGTH} characters or fewer`
  }
  return null
}

export function validateQuestion(value: string): ValidationResult {
  const trimmed = value.trim()
  if (!trimmed) return 'Type a question first'
  if (trimmed.length < MIN_QUESTION_LENGTH) return 'That question is too short'
  if (trimmed.length > MAX_QUESTION_LENGTH) {
    return `Questions must be ${MAX_QUESTION_LENGTH} characters or fewer`
  }
  return null
}

export function validateLabel(value: string, field = 'Name'): ValidationResult {
  const trimmed = value.trim()
  if (!trimmed) return `${field} is required`
  if (trimmed.length > 160) return `${field} must be 160 characters or fewer`
  return null
}

/** A coarse strength hint. Never blocks submission -- length is the real rule. */
export function passwordStrength(value: string): {
  score: 0 | 1 | 2 | 3
  label: string
} {
  if (value.length < MIN_PASSWORD_LENGTH) return { score: 0, label: 'Too short' }
  let score = 1
  if (value.length >= 12) score += 1
  if (/[^a-zA-Z0-9]/.test(value) && /\d/.test(value)) score += 1
  const labels = ['Too short', 'Weak', 'Reasonable', 'Strong'] as const
  const clamped = Math.min(score, 3) as 0 | 1 | 2 | 3
  return { score: clamped, label: labels[clamped] }
}
