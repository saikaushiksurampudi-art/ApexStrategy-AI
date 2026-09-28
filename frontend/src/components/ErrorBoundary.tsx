/**
 * Top-level error boundary.
 *
 * Without one, a single render-time throw anywhere in the tree unmounts the
 * whole application and leaves a blank white page with no explanation and no
 * way back. This catches that case and offers a recovery path.
 *
 * It deliberately does not try to be clever: it shows what failed, offers a
 * retry that remounts the subtree, and a link home. Anything more elaborate
 * risks throwing inside the handler for a throw.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Changing this value resets the boundary — used to clear on navigation. */
  resetKey?: string
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidUpdate(prev: Props) {
    // A new route should get a clean slate rather than inheriting the error.
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In a deployed app this is where a reporter (Sentry, CloudWatch RUM)
    // would receive the error. Logging keeps it visible in development.
    console.error('Unhandled render error:', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="mx-auto mt-10 max-w-lg">
        <div className="card card-pad text-center">
          <div
            aria-hidden="true"
            className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-status-bad/15 text-lg text-status-bad"
          >
            !
          </div>
          <h1 className="mt-4 font-display text-lg font-bold">
            Something went wrong on this page
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
            The rest of the app is still working. You can retry this page, or head
            back to the dashboard.
          </p>

          <div className="mt-5 flex justify-center gap-2">
            <button
              type="button"
              className="btn-primary"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
            <a href="/" className="btn-ghost">
              Back to dashboard
            </a>
          </div>

          <details className="mt-5 text-left">
            <summary className="cursor-pointer text-xs text-ink-muted hover:text-ink-secondary">
              Technical details
            </summary>
            <pre className="mt-2 overflow-auto rounded-lg border border-line bg-surface-2 p-3 text-[11px] leading-relaxed text-ink-muted">
              {error.message || String(error)}
            </pre>
          </details>
        </div>
      </div>
    )
  }
}
