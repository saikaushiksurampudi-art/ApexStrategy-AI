/** Shared number, date and label formatting. */

export const pct = (value: number | null | undefined, digits = 0): string =>
  value === null || value === undefined || Number.isNaN(value)
    ? '—'
    : `${(value * 100).toFixed(digits)}%`

export const num = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(digits)

export const int = (value: number | null | undefined): string =>
  value === null || value === undefined || Number.isNaN(value) ? '—' : String(Math.round(value))

export const ordinal = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `P${Math.round(value)}`
}

export const signed = (value: number | null | undefined, digits = 1): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

export const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return '—'
  const date = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/** "2021, 2022, 2023" -> "2021–2023" */
export const seasonRange = (seasons: number[] | undefined): string => {
  if (!seasons || seasons.length === 0) return '—'
  const sorted = [...seasons].sort((a, b) => a - b)
  const first = sorted[0]
  const last = sorted[sorted.length - 1]
  return first === last ? String(first) : `${first}–${last}`
}

export const titleCase = (value: string | null | undefined): string =>
  !value ? '—' : value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ')

/** Display a classified position, or the reason the driver isn't classified. */
export const positionLabel = (
  position: number | null,
  positionText: string | null,
): string => {
  // Check the status code first: a disqualified driver still carries a
  // classified position in the source data, and showing "P19" for a DSQ
  // would misreport the result.
  const codes: Record<string, string> = {
    R: 'DNF',
    D: 'DSQ',
    W: 'WD',
    E: 'EX',
    F: 'DNQ',
    N: 'NC',
  }
  if (positionText && codes[positionText]) return codes[positionText]
  if (position) return `P${position}`
  return positionText ?? '—'
}
