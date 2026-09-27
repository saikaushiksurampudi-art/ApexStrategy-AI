/**
 * Form-validation rules.
 *
 * These mirror the server's Pydantic constraints. If a rule changes here it
 * must change in `backend/app/schemas.py` too, or the client will accept input
 * the API rejects.
 */

import { describe, expect, it } from 'vitest'
import {
  MIN_PASSWORD_LENGTH,
  passwordStrength,
  validateDisplayName,
  validateEmail,
  validateLabel,
  validatePassword,
  validatePasswordConfirmation,
  validateQuestion,
} from '../validation'

describe('validateEmail', () => {
  it.each(['fan@example.com', 'a.b+tag@sub.domain.co.uk', ' spaced@example.com '])(
    'accepts %s',
    (value) => {
      expect(validateEmail(value)).toBeNull()
    },
  )

  it.each([
    ['', 'Email is required'],
    ['   ', 'Email is required'],
    ['not-an-email', 'Enter a valid email address'],
    ['missing@domain', 'Enter a valid email address'],
    ['@example.com', 'Enter a valid email address'],
    ['two spaces@example.com', 'Enter a valid email address'],
  ])('rejects %s', (value, expected) => {
    expect(validateEmail(value)).toBe(expected)
  })
})

describe('validatePassword', () => {
  it('requires a value', () => {
    expect(validatePassword('')).toBe('Password is required')
  })

  it(`requires at least ${MIN_PASSWORD_LENGTH} characters`, () => {
    expect(validatePassword('short')).toContain('at least 8 characters')
    expect(validatePassword('a'.repeat(MIN_PASSWORD_LENGTH))).toBeNull()
  })

  it('rejects absurdly long values', () => {
    expect(validatePassword('a'.repeat(129))).toContain('128 characters or fewer')
  })

  it('does not trim -- spaces are legitimate password characters', () => {
    expect(validatePassword('  pass  ')).toBeNull()
  })
})

describe('validatePasswordConfirmation', () => {
  it('requires a confirmation', () => {
    expect(validatePasswordConfirmation('secret123', '')).toBe('Confirm your password')
  })

  it('rejects a mismatch', () => {
    expect(validatePasswordConfirmation('secret123', 'secret124')).toBe(
      'Passwords do not match',
    )
  })

  it('accepts a match', () => {
    expect(validatePasswordConfirmation('secret123', 'secret123')).toBeNull()
  })
})

describe('validateDisplayName', () => {
  it('is optional', () => {
    expect(validateDisplayName('')).toBeNull()
  })

  it('caps the length', () => {
    expect(validateDisplayName('x'.repeat(121))).toContain('120 characters or fewer')
    expect(validateDisplayName('x'.repeat(120))).toBeNull()
  })
})

describe('validateQuestion', () => {
  it('requires something to ask', () => {
    expect(validateQuestion('   ')).toBe('Type a question first')
  })

  it('rejects a question below the API minimum', () => {
    // The server enforces min_length=3; the client must not send less.
    expect(validateQuestion('hi')).toBe('That question is too short')
  })

  it('caps at the API maximum', () => {
    expect(validateQuestion('a'.repeat(1001))).toContain('1000 characters or fewer')
    expect(validateQuestion('a'.repeat(1000))).toBeNull()
  })

  it('accepts an ordinary question', () => {
    expect(validateQuestion('Compare Verstappen and Norris at Monza')).toBeNull()
  })
})

describe('validateLabel', () => {
  it('requires a value and names the field', () => {
    expect(validateLabel('', 'Label')).toBe('Label is required')
  })

  it('caps at 160 characters', () => {
    expect(validateLabel('x'.repeat(161))).toContain('160 characters or fewer')
  })
})

describe('passwordStrength', () => {
  it('reports too short below the minimum', () => {
    expect(passwordStrength('abc')).toEqual({ score: 0, label: 'Too short' })
  })

  it('rises with length and character variety', () => {
    const weak = passwordStrength('abcdefgh')
    const longer = passwordStrength('abcdefghijkl')
    const complex = passwordStrength('abcdefghijkl1!')
    expect(weak.score).toBe(1)
    expect(longer.score).toBeGreaterThan(weak.score)
    expect(complex.score).toBe(3)
    expect(complex.label).toBe('Strong')
  })

  it('never exceeds the top score', () => {
    expect(passwordStrength('a'.repeat(60) + '1!@#$').score).toBe(3)
  })
})
