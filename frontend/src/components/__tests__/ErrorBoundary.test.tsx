/**
 * Error boundary behaviour.
 *
 * Without a boundary, one render-time throw blanks the entire application.
 * These tests pin the recovery path.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { ErrorBoundary } from '../ErrorBoundary'

function Boom({ explode = true }: { explode?: boolean }) {
  if (explode) throw new Error('Simulated render failure')
  return <p>Recovered content</p>
}

beforeEach(() => {
  // React logs caught errors to console.error; silence the expected noise.
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('ErrorBoundary', () => {
  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('All good')).toBeInTheDocument()
  })

  it('catches a render error instead of unmounting the tree', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText(/something went wrong on this page/i)).toBeInTheDocument()
  })

  it('offers both a retry and a way back', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument()
  })

  it('exposes the message for debugging without dumping a stack at the user', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Simulated render failure')).toBeInTheDocument()
    expect(screen.getByText(/technical details/i)).toBeInTheDocument()
  })

  it('retry clears the error so a transient failure can recover', async () => {
    const user = userEvent.setup()

    function Harness() {
      const [explode, setExplode] = useState(true)
      return (
        <>
          <button onClick={() => setExplode(false)}>Fix it</button>
          <ErrorBoundary>
            <Boom explode={explode} />
          </ErrorBoundary>
        </>
      )
    }

    render(<Harness />)
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()

    await user.click(screen.getByText('Fix it'))
    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(screen.getByText('Recovered content')).toBeInTheDocument()
  })

  it('resets when the route changes', () => {
    const { rerender } = render(
      <ErrorBoundary resetKey="/model">
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()

    rerender(
      <ErrorBoundary resetKey="/compare">
        <Boom explode={false} />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Recovered content')).toBeInTheDocument()
  })
})
