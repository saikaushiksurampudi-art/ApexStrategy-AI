/**
 * Sign in / create account, and the signed-in user's saved comparisons.
 *
 * An account is optional throughout the product -- it exists so comparisons can
 * be saved and revisited. Nothing else is gated behind it.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import {
  validateDisplayName,
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
  passwordStrength,
  MAX_DISPLAY_NAME_LENGTH,
  MAX_PASSWORD_LENGTH,
} from '../lib/validation'
import { Field, StrengthMeter } from '../components/Field'
import { Card, CardHeader, EmptyState, Loading, SectionTitle } from '../components/ui'
import { formatDate } from '../lib/format'

type Mode = 'signin' | 'signup'

export default function Account() {
  const { user, loading } = useAuth()
  if (loading) return <Loading label="Checking your session…" />
  return user ? <SignedIn /> : <AuthForm />
}

/* ------------------------------------------------------------------ */
function AuthForm() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [submitted, setSubmitted] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const isSignUp = mode === 'signup'

  const errors = {
    email: validateEmail(email),
    password: validatePassword(password),
    confirmation: isSignUp ? validatePasswordConfirmation(password, confirmation) : null,
    displayName: isSignUp ? validateDisplayName(displayName) : null,
  }
  const hasErrors = Object.values(errors).some(Boolean)
  const shows = (field: string) => submitted || touched[field]

  const switchMode = (next: Mode) => {
    setMode(next)
    setSubmitted(false)
    setServerError(null)
    setTouched({})
    setConfirmation('')
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(true)
    setServerError(null)
    if (hasErrors) return

    setPending(true)
    try {
      if (isSignUp) {
        await signUp(email.trim(), password, displayName.trim() || undefined)
      } else {
        await signIn(email.trim(), password)
      }
    } catch (error) {
      // Map the server's codes onto something a person can act on.
      if (error instanceof ApiError && error.status === 409) {
        setServerError('An account with that email already exists. Try signing in instead.')
      } else if (error instanceof ApiError && error.status === 401) {
        setServerError('Incorrect email or password.')
      } else if (error instanceof ApiError && error.status === 0) {
        setServerError('Could not reach the server. Is the backend running?')
      } else {
        setServerError(error instanceof Error ? error.message : 'Something went wrong')
      }
    } finally {
      setPending(false)
    }
  }

  const strength = passwordStrength(password)

  return (
    <div className="mx-auto max-w-md">
      <SectionTitle hint="An account is optional — it lets you save driver and team comparisons to revisit later.">
        {isSignUp ? 'Create an account' : 'Sign in'}
      </SectionTitle>

      <Card className="card-pad">
        <div
          className="mb-5 flex gap-1 rounded-lg border border-line bg-surface-2 p-0.5"
          role="tablist"
        >
          {(['signin', 'signup'] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => switchMode(value)}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === value
                  ? 'bg-surface-3 text-ink-primary'
                  : 'text-ink-muted hover:text-ink-secondary'
              }`}
            >
              {value === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            error={errors.email}
            showError={shows('email')}
            onChange={(event) => setEmail(event.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          />

          {isSignUp ? (
            <Field
              label="Display name (optional)"
              type="text"
              autoComplete="nickname"
              placeholder="How you want to be addressed"
              maxLength={MAX_DISPLAY_NAME_LENGTH}
              value={displayName}
              error={errors.displayName}
              showError={shows('displayName')}
              onChange={(event) => setDisplayName(event.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, displayName: true }))}
            />
          ) : null}

          <div>
            <Field
              label="Password"
              type="password"
              autoComplete={isSignUp ? 'new-password' : 'current-password'}
              maxLength={MAX_PASSWORD_LENGTH}
              value={password}
              error={errors.password}
              showError={shows('password')}
              hint={isSignUp ? 'At least 8 characters.' : undefined}
              onChange={(event) => setPassword(event.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            />
            {isSignUp && password ? (
              <StrengthMeter score={strength.score} label={strength.label} />
            ) : null}
          </div>

          {isSignUp ? (
            <Field
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              error={errors.confirmation}
              showError={shows('confirmation')}
              onChange={(event) => setConfirmation(event.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, confirmation: true }))}
            />
          ) : null}

          {serverError ? (
            <p role="alert" className="rounded-lg border border-status-bad/30 bg-status-bad/10 px-3 py-2 text-sm text-status-bad">
              {serverError}
            </p>
          ) : null}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={pending || (submitted && hasErrors)}
          >
            {pending ? 'Working…' : isSignUp ? 'Create account' : 'Sign in'}
          </button>
        </form>
      </Card>

      <p className="mt-4 text-center text-xs text-ink-muted">
        Dashboards, comparisons, predictions and the AI analyst all work without an
        account. <Link to="/" className="link">Back to the dashboard</Link>.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
function SignedIn() {
  const { user, signOut } = useAuth()
  const [saved, setSaved] = useState<
    Array<{ id: number; label: string; kind: string; payload: Record<string, unknown>; created_at: string }>
  >([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api
      .savedComparisons()
      .then(setSaved)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const remove = async (id: number) => {
    try {
      await api.deleteSavedComparison(id)
      setSaved((current) => current.filter((item) => item.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete')
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <SectionTitle hint={user?.email}>
        {user?.display_name ? `Hello, ${user.display_name}` : 'Your account'}
      </SectionTitle>

      <Card>
        <CardHeader
          title="Saved comparisons"
          subtitle="Comparisons you've saved from the Compare page"
          action={
            <button type="button" className="btn-ghost !px-2.5 !py-1 !text-xs" onClick={signOut}>
              Sign out
            </button>
          }
        />
        {loading ? (
          <Loading />
        ) : error ? (
          <p className="px-4 py-3 text-sm text-status-bad">{error}</p>
        ) : saved.length === 0 ? (
          <EmptyState message="Nothing saved yet. Build a comparison and use “Save comparison”." />
        ) : (
          <ul className="divide-y divide-line">
            {saved.map((item) => {
              const a = String(item.payload.a ?? '')
              const b = String(item.payload.b ?? '')
              return (
                <li key={item.id} className="flex items-center gap-3 px-4 py-3 sm:px-5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-primary">{item.label}</p>
                    <p className="text-xs text-ink-muted">
                      {item.kind} · saved {formatDate(item.created_at.slice(0, 10))}
                    </p>
                  </div>
                  {a && b ? (
                    <Link
                      to={`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`}
                      className="btn-ghost !px-2.5 !py-1 !text-xs"
                    >
                      Open
                    </Link>
                  ) : null}
                  <button
                    type="button"
                    className="btn-ghost !px-2.5 !py-1 !text-xs hover:!text-status-bad"
                    onClick={() => remove(item.id)}
                    aria-label={`Delete ${item.label}`}
                  >
                    Delete
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
