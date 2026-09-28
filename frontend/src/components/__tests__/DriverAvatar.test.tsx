/**
 * Driver portrait fallback behaviour.
 *
 * 34 of 35 drivers have a Commons portrait, so the missing case is real and
 * must look deliberate rather than broken.
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DriverAvatar, PortraitCredit } from '../DriverAvatar'

describe('DriverAvatar', () => {
  it('renders the portrait when one exists', () => {
    const { container } = render(
      <DriverAvatar
        driver={{ name: 'Max Verstappen', code: 'VER', image_url: 'https://x/y.jpg' }}
      />,
    )
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', 'https://x/y.jpg')
    // Decorative: the name is always rendered beside it, so alt is empty.
    expect(img).toHaveAttribute('alt', '')
  })

  it('falls back to the driver code when there is no portrait', () => {
    render(<DriverAvatar driver={{ name: 'Yuki Tsunoda', code: 'TSU' }} />)
    expect(screen.getByText('TSU')).toBeInTheDocument()
  })

  it('falls back to initials when there is no code either', () => {
    render(<DriverAvatar driver={{ name: 'Ada Apex' }} />)
    expect(screen.getByText('AA')).toBeInTheDocument()
  })

  it('falls back when a remote image fails to load', () => {
    const { container } = render(
      <DriverAvatar
        driver={{ name: 'Broken Link', code: 'BRK', image_url: 'https://x/404.jpg' }}
      />,
    )
    fireEvent.error(container.querySelector('img')!)
    expect(screen.getByText('BRK')).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
  })

  it('handles an empty name without throwing', () => {
    render(<DriverAvatar driver={{}} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})

describe('PortraitCredit', () => {
  it('credits the author and licence', () => {
    render(
      <PortraitCredit
        driver={{
          image_url: 'https://x/y.jpg',
          image_author: 'Jane Photographer',
          image_license: 'CC BY-SA 4.0',
        }}
      />,
    )
    expect(screen.getByText(/Jane Photographer/)).toBeInTheDocument()
    expect(screen.getByText(/CC BY-SA 4.0/)).toBeInTheDocument()
  })

  it('renders nothing when there is no portrait to credit', () => {
    const { container } = render(<PortraitCredit driver={{ name: 'No Photo' }} />)
    expect(container).toBeEmptyDOMElement()
  })
})
