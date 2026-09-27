/**
 * Chart colour roles.
 *
 * Two palettes, used for two different jobs:
 *
 * 1. **Team colours** (from the API, per constructor) carry *entity identity*.
 *    Fans read them instantly, so they are worth keeping — but they are brand
 *    colours, not a validated categorical ramp, and several pairs are not
 *    distinguishable under colour-vision deficiency (the two reds, the several
 *    blues). Every team-coloured chart in this app therefore also carries a
 *    legend and direct labels, so identity is never conveyed by colour alone.
 *
 * 2. **SERIES** below is the validated categorical palette, used wherever the
 *    series are not teams (driver A vs driver B, model vs baseline). These are
 *    the dark-mode steps of the reference palette and pass the lightness,
 *    chroma, CVD-separation, normal-vision and contrast checks against the
 *    #15161c chart surface.
 */

/** Validated categorical slots — assign in order, never cycle. */
export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181'] as const

/** Single-hue ramp for ordinal magnitude. Lightest step still clears 2:1 on dark. */
export const SEQUENTIAL = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95']

export const SURFACE = '#15161c'
export const GRID_LINE = '#2a2e3a'
export const AXIS_TEXT = '#a8adba'

export const STATUS = {
  good: '#199e70',
  warn: '#c98500',
  bad: '#e66767',
} as const

const FALLBACK_TEAM = '#6f7686'

/** A constructor colour, with a neutral fallback for unknown teams. */
export const teamColor = (color: string | null | undefined): string => color || FALLBACK_TEAM

/**
 * Pick an ordinal step for a 0..1 value.
 * Used for probability heat cells, where magnitude is the message.
 */
export const sequentialStep = (value: number): string => {
  const clamped = Math.max(0, Math.min(1, value))
  const index = Math.min(SEQUENTIAL.length - 1, Math.floor(clamped * SEQUENTIAL.length))
  return SEQUENTIAL[index]
}

/** Shared Recharts axis/grid styling so every chart reads as one system. */
export const axisProps = {
  stroke: GRID_LINE,
  tick: { fill: AXIS_TEXT, fontSize: 11 },
  tickLine: false,
} as const

export const gridProps = {
  stroke: GRID_LINE,
  strokeDasharray: '3 3',
  vertical: false,
} as const
