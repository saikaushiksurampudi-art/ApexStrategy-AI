/**
 * Driver portrait with a monogram fallback.
 *
 * Portraits come from Wikimedia Commons and not every driver has one, so the
 * fallback is a first-class path rather than a broken-image box: initials on a
 * gradient derived from the driver's team colour. A remote image can also fail
 * at load time, so `onError` falls back too.
 */

import { useState } from 'react'
import { teamColor } from '../lib/palette'

export interface DriverLike {
  driver?: string
  name?: string
  code?: string | null
  color?: string | null
  constructor_color?: string | null
  image_url?: string | null
  image_author?: string | null
  image_license?: string | null
}

const SIZES = {
  sm: { box: 'h-9 w-9', text: 'text-[10px]', ring: 2 },
  md: { box: 'h-12 w-12', text: 'text-xs', ring: 2 },
  lg: { box: 'h-20 w-20', text: 'text-lg', ring: 3 },
  xl: { box: 'h-28 w-28', text: 'text-2xl', ring: 3 },
} as const

export type AvatarSize = keyof typeof SIZES

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function DriverAvatar({
  driver,
  size = 'md',
  className = '',
}: {
  driver: DriverLike
  size?: AvatarSize
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  const spec = SIZES[size]
  const name = driver.driver ?? driver.name ?? ''
  const accent = teamColor(driver.color ?? driver.constructor_color)
  const showImage = Boolean(driver.image_url) && !failed

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-full bg-surface-3 ${spec.box} ${className}`}
      style={{ boxShadow: `inset 0 0 0 ${spec.ring}px ${accent}` }}
    >
      {showImage ? (
        <img
          src={driver.image_url as string}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover object-top"
        />
      ) : (
        <div
          className={`flex h-full w-full items-center justify-center font-semibold tracking-wide text-white ${spec.text}`}
          style={{
            background: `linear-gradient(140deg, ${accent}cc, ${accent}55)`,
          }}
          aria-hidden="true"
        >
          {driver.code || initials(name)}
        </div>
      )}
    </div>
  )
}

/**
 * Attribution line for a portrait.
 *
 * The Commons images are freely licensed but almost all require credit, so
 * this is rendered wherever a portrait is shown at a prominent size.
 */
export function PortraitCredit({
  driver,
  className = '',
}: {
  driver: DriverLike
  className?: string
}) {
  if (!driver.image_url || !driver.image_license) return null
  return (
    <p className={`text-[10px] leading-tight text-ink-muted ${className}`}>
      Photo: {driver.image_author ?? 'Wikimedia Commons'} · {driver.image_license}
    </p>
  )
}
