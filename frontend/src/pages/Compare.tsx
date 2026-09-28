/**
 * Driver-versus-driver comparison.
 *
 * The head-to-head tally only counts races where both drivers were classified,
 * which is the only way the number means what people assume it means. DNFs are
 * still visible, as separate reliability figures.
 */

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import { useApi } from '../hooks/useApi'
import { num, pct, positionLabel, seasonRange } from '../lib/format'
import { axisProps, ChartFrame, gridProps, LegendItem, TooltipCard } from '../components/charts'
import { SERIES } from '../lib/palette'
import {
  Card,
  EmptyState,
  ErrorState,
  Loading,
  SectionTitle,
  StatTile,
} from '../components/ui'
import { FeedbackWidget } from '../components/FeedbackWidget'
import { DriverAvatar, PortraitCredit } from '../components/DriverAvatar'
import { Reveal } from '../lib/motion'
import { useAuth } from '../lib/auth'
import { validateLabel } from '../lib/validation'
import type { DriverSummary, HeadToHead } from '../lib/types'

// Driver A / driver B are not teams, so they use the validated categorical
// slots rather than constructor colours (both could be on the same team).
const COLOR_A = SERIES[0]
const COLOR_B = SERIES[1]

// Ergast driver refs are not always the surname (Verstappen is
// "max_verstappen"), so preferred defaults are resolved against the real list
// rather than hardcoded — otherwise the picker and the results disagree.
const PREFERRED_A = ['max_verstappen', 'verstappen', 'norris']
const PREFERRED_B = ['norris', 'leclerc', 'hamilton']

const pickDefault = (
  refs: string[],
  preferred: string[],
  fallbackIndex: number,
  exclude?: string,
): string => {
  const available = refs.filter((ref) => ref !== exclude)
  return (
    preferred.find((ref) => available.includes(ref)) ??
    available[fallbackIndex] ??
    available[0] ??
    ''
  )
}

export default function Compare() {
  const [driverA, setDriverA] = useState('')
  const [driverB, setDriverB] = useState('')
  const [query, setQuery] = useState<{ a: string; b: string } | null>(null)
  const [seasons, setSeasons] = useState<number[]>([])
  const [searchParams] = useSearchParams()

  const meta = useApi(() => api.meta(), [])
  const drivers = useApi(() => api.drivers(), [])
  const comparison = useApi(
    () =>
      api.compareDrivers(query!.a, query!.b, seasons.length ? seasons : undefined),
    [query?.a, query?.b, seasons.join(',')],
    { enabled: query !== null },
  )

  // Seed both pickers once the driver list arrives. URL parameters win, so a
  // saved comparison opens exactly as it was stored.
  useEffect(() => {
    if (!drivers.data || driverA) return
    const refs = drivers.data.map((driver) => driver.ref)
    const fromUrlA = searchParams.get('a')
    const fromUrlB = searchParams.get('b')
    const a =
      fromUrlA && refs.includes(fromUrlA) ? fromUrlA : pickDefault(refs, PREFERRED_A, 0)
    const b =
      fromUrlB && refs.includes(fromUrlB) ? fromUrlB : pickDefault(refs, PREFERRED_B, 1, a)
    setDriverA(a)
    setDriverB(b)
    setQuery({ a, b })
  }, [drivers.data, driverA, searchParams])

  const allSeasons = meta.data?.seasons ?? []

  return (
    <div className="space-y-5">
      <SectionTitle hint="Head-to-head records, qualifying pace and race-by-race finishing positions.">
        Driver comparison
      </SectionTitle>

      <Card className="card-pad">
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={(event) => {
            event.preventDefault()
            setQuery({ a: driverA, b: driverB })
          }}
        >
          <DriverPicker
            label="Driver A"
            value={driverA}
            onChange={setDriverA}
            options={drivers.data ?? []}
          />
          <DriverPicker
            label="Driver B"
            value={driverB}
            onChange={setDriverB}
            options={drivers.data ?? []}
          />
          <button type="submit" className="btn-primary h-[38px]">
            Compare
          </button>
        </form>

        {allSeasons.length > 0 ? (
          <div className="mt-4 border-t border-line pt-3">
            <div className="label-muted mb-2">Filter seasons</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setSeasons([])}
                className={`chip transition-colors hover:border-line-strong ${
                  seasons.length === 0 ? '!border-series-1 !text-series-1' : ''
                }`}
              >
                All
              </button>
              {allSeasons.map((season) => {
                const active = seasons.includes(season)
                return (
                  <button
                    key={season}
                    type="button"
                    onClick={() =>
                      setSeasons((current) =>
                        active ? current.filter((s) => s !== season) : [...current, season],
                      )
                    }
                    className={`chip transition-colors hover:border-line-strong ${
                      active ? '!border-series-1 !text-series-1' : ''
                    }`}
                  >
                    {season}
                  </button>
                )
              })}
            </div>
          </div>
        ) : null}
      </Card>

      {drivers.error ? (
        <ErrorState
          message={`Could not load the driver list. ${drivers.error}`}
          onRetry={drivers.reload}
        />
      ) : null}
      {drivers.loading || comparison.loading ? <Loading label="Comparing…" /> : null}
      {comparison.error ? (
        <ErrorState message={comparison.error} onRetry={comparison.reload} />
      ) : null}
      {comparison.data && query ? (
        <ComparisonBody data={comparison.data} refs={query} />
      ) : null}
    </div>
  )
}

function DriverPicker({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: Array<{ id: number; ref: string; name: string }>
}) {
  return (
    <label className="block">
      <span className="label-muted mb-1.5 block">{label}</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.length === 0 ? <option value={value}>{value}</option> : null}
        {options.map((option) => (
          <option key={option.id} value={option.ref}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  )
}

/* ------------------------------------------------------------------ */
function ComparisonBody({
  data,
  refs,
}: {
  data: HeadToHead
  refs: { a: string; b: string }
}) {
  const { driver_a: a, driver_b: b } = data

  if (data.shared_races === 0) {
    return (
      <Card>
        <EmptyState
          message={`${a.name} and ${b.name} have no races in common in this scope. Try widening the season filter.`}
        />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Race head-to-head"
          value={`${data.race_head_to_head.a} – ${data.race_head_to_head.b}`}
          hint={`${data.race_head_to_head.counted} races where both finished`}
        />
        <StatTile
          label="Qualifying head-to-head"
          value={`${data.qualifying_head_to_head.a} – ${data.qualifying_head_to_head.b}`}
          hint={`${data.qualifying_head_to_head.counted} sessions`}
        />
        <StatTile
          label="Shared races"
          value={data.shared_races}
          hint={seasonRange(a.seasons)}
        />
        <StatTile
          label="Points"
          value={`${num(a.total_points, 0)} – ${num(b.total_points, 0)}`}
          hint="In shared scope"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Reveal>
          <DriverCard summary={a} color={COLOR_A} />
        </Reveal>
        <Reveal delay={90}>
          <DriverCard summary={b} color={COLOR_B} />
        </Reveal>
      </div>

      <RecordChart a={a} b={b} />
      <PositionTimeline data={data} />

      <Card className="card-pad space-y-4">
        <SaveComparison
          refs={refs}
          defaultLabel={`${a.name} vs ${b.name}`}
        />
        <div className="border-t border-line pt-3">
          <FeedbackWidget
            surface="comparison"
            referenceId={`${a.ref}-vs-${b.ref}`}
            context={{ shared_races: data.shared_races, seasons: a.seasons }}
          />
        </div>
      </Card>
    </div>
  )
}

function DriverCard({ summary, color }: { summary: DriverSummary; color: string }) {
  const rows: Array<[string, string]> = [
    ['Races', String(summary.races)],
    ['Wins', String(summary.wins)],
    ['Podiums', String(summary.podiums)],
    ['Points finishes', String(summary.points_finishes)],
    ['Total points', num(summary.total_points, 1)],
    ['Average finish', num(summary.avg_finish)],
    ['Average grid', num(summary.avg_grid)],
    ['Positions gained/race', num(summary.avg_positions_gained)],
    ['Podium rate', pct(summary.podium_rate, 1)],
    ['DNF rate', pct(summary.dnf_rate, 1)],
  ]

  return (
    <Card className="overflow-hidden">
      <div
        aria-hidden="true"
        className="h-[3px] w-full"
        style={{ background: `linear-gradient(90deg, ${color}, transparent)` }}
      />
      <div className="flex items-center gap-4 border-b border-line px-4 py-4 sm:px-5">
        <DriverAvatar driver={summary} size="lg" />
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg font-bold">{summary.name}</h2>
          <p className="truncate text-sm" style={{ color }}>
            {summary.constructor ?? 'Unknown team'}
          </p>
          <p className="text-xs text-ink-muted">{seasonRange(summary.seasons)}</p>
          <PortraitCredit driver={summary} className="mt-1" />
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-px bg-line">
        {rows.map(([label, value]) => (
          <div key={label} className="bg-surface-1 px-4 py-2.5">
            <dt className="label-muted">{label}</dt>
            <dd className="tabular mt-0.5 text-sm font-medium text-ink-primary">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function RecordChart({ a, b }: { a: DriverSummary; b: DriverSummary }) {
  // Rates, not raw counts: the two drivers may have different race counts,
  // and comparing raw totals would then be misleading.
  const data = [
    { metric: 'Win rate', a: a.races ? a.wins / a.races : 0, b: b.races ? b.wins / b.races : 0 },
    { metric: 'Podium rate', a: a.podium_rate, b: b.podium_rate },
    { metric: 'Points rate', a: a.points_rate, b: b.points_rate },
    { metric: 'Finish rate', a: 1 - a.dnf_rate, b: 1 - b.dnf_rate },
  ]

  return (
    <ChartFrame
      title="Rates per race entered"
      subtitle="Normalised so different race counts compare fairly"
      height={260}
      legend={
        <>
          <LegendItem color={COLOR_A} label={a.name} />
          <LegendItem color={COLOR_B} label={b.name} />
        </>
      }
      note="Rates are computed over each driver's own races within the selected scope, not only their shared races."
      table={
        <table className="w-full text-xs">
          <thead className="text-ink-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Metric</th>
              <th className="px-2 py-1.5 text-right font-medium">{a.name}</th>
              <th className="px-2 py-1.5 text-right font-medium">{b.name}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.metric} className="border-t border-line">
                <td className="px-2 py-1">{row.metric}</td>
                <td className="tabular px-2 py-1 text-right">{pct(row.a, 1)}</td>
                <td className="tabular px-2 py-1 text-right">{pct(row.b, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}
          barGap={4}
          barCategoryGap="28%">
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="metric" {...axisProps} />
          <YAxis {...axisProps} tickFormatter={(v: number) => pct(v)} />
          <Tooltip
            cursor={{ fill: '#ffffff0a' }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipCard
                  title={String(label)}
                  rows={[
                    { label: a.name, value: pct(Number(payload[0]?.value), 1), color: COLOR_A },
                    { label: b.name, value: pct(Number(payload[1]?.value), 1), color: COLOR_B },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="a" fill={COLOR_A} radius={[4, 4, 0, 0]} maxBarSize={54} />
          <Bar dataKey="b" fill={COLOR_B} radius={[4, 4, 0, 0]} maxBarSize={54} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

function PositionTimeline({ data }: { data: HeadToHead }) {
  const recent = data.timeline.slice(-20)
  const chartData = recent.map((row) => ({
    label: `${String(row.season).slice(2)} R${row.round}`,
    race: row.race,
    season: row.season,
    a: row.a_position,
    b: row.b_position,
    aText: positionLabel(row.a_position, row.a_position_text),
    bText: positionLabel(row.b_position, row.b_position_text),
  }))

  return (
    <ChartFrame
      title="Finishing positions, race by race"
      subtitle={`Last ${recent.length} shared races · lower is better`}
      height={280}
      legend={
        <>
          <LegendItem color={COLOR_A} label={data.driver_a.name} />
          <LegendItem color={COLOR_B} label={data.driver_b.name} />
        </>
      }
      note="Gaps in a line are races the driver did not finish — a retirement has no finishing position, so plotting one would invent data."
      table={
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-1 text-ink-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Race</th>
              <th className="px-2 py-1.5 text-right font-medium">{data.driver_a.name}</th>
              <th className="px-2 py-1.5 text-right font-medium">{data.driver_b.name}</th>
            </tr>
          </thead>
          <tbody>
            {[...recent].reverse().map((row) => (
              <tr key={`${row.season}-${row.round}`} className="border-t border-line">
                <td className="px-2 py-1">
                  {row.season} {row.race}
                </td>
                <td className="tabular px-2 py-1 text-right">
                  {positionLabel(row.a_position, row.a_position_text)}
                </td>
                <td className="tabular px-2 py-1 text-right">
                  {positionLabel(row.b_position, row.b_position_text)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -22 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="label" {...axisProps} interval="preserveStartEnd" />
          <YAxis
            {...axisProps}
            reversed
            domain={[1, 20]}
            ticks={[1, 5, 10, 15, 20]}
            tickFormatter={(v: number) => `P${v}`}
          />
          <Tooltip
            cursor={{ stroke: '#3a3f4f', strokeWidth: 1 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipCard
                  title={`${payload[0].payload.season} ${payload[0].payload.race}`}
                  rows={[
                    { label: data.driver_a.name, value: payload[0].payload.aText, color: COLOR_A },
                    { label: data.driver_b.name, value: payload[0].payload.bText, color: COLOR_B },
                  ]}
                />
              ) : null
            }
          />
          <Line
            type="monotone"
            dataKey="a"
            stroke={COLOR_A}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 0, fill: COLOR_A }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: '#15161c' }}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="b"
            stroke={COLOR_B}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 0, fill: COLOR_B }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: '#15161c' }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

/* ------------------------------------------------------------------ */
/**
 * Save the current comparison. Requires an account, so anonymous visitors are
 * shown what the feature does and where to sign in rather than a dead button.
 */
function SaveComparison({
  refs,
  defaultLabel,
}: {
  refs: { a: string; b: string }
  defaultLabel: string
}) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState(defaultLabel)
  const [touched, setTouched] = useState(false)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLabel(defaultLabel)
    setStatus('idle')
  }, [defaultLabel])

  if (!user) {
    return (
      <p className="text-xs text-ink-muted">
        <Link to="/account" className="link">
          Sign in
        </Link>{' '}
        to save this comparison and revisit it later.
      </p>
    )
  }

  const labelError = validateLabel(label, 'Label')

  const save = async () => {
    setTouched(true)
    if (labelError) return
    setStatus('saving')
    setError(null)
    try {
      await api.saveComparison(label.trim(), 'driver', refs)
      setStatus('saved')
      setOpen(false)
    } catch (err) {
      setStatus('idle')
      setError(err instanceof Error ? err.message : 'Could not save')
    }
  }

  if (status === 'saved') {
    return (
      <p className="text-xs text-status-good">
        Saved.{' '}
        <Link to="/account" className="link">
          View your saved comparisons
        </Link>
        .
      </p>
    )
  }

  return (
    <div>
      {open ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <div className="flex-1">
            <input
              className={`input ${touched && labelError ? '!border-status-bad' : ''}`}
              value={label}
              maxLength={160}
              aria-label="Comparison label"
              aria-invalid={touched && labelError ? true : undefined}
              onChange={(event) => setLabel(event.target.value)}
              onBlur={() => setTouched(true)}
            />
            {touched && labelError ? (
              <p role="alert" className="mt-1.5 text-xs text-status-bad">
                {labelError}
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="mt-1.5 text-xs text-status-bad">
                {error}
              </p>
            ) : null}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-primary"
              onClick={save}
              disabled={status === 'saving'}
            >
              {status === 'saving' ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="btn-ghost" onClick={() => setOpen(true)}>
          Save comparison
        </button>
      )}
    </div>
  )
}
