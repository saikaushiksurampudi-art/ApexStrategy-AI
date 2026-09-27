/**
 * Podium probabilities, the factors behind them, and the "what if" explorer.
 *
 * Every probability on this page carries its reasoning: the factor breakdown
 * comes from re-running the real model with one feature held at its training
 * median, so the numbers shown are measured, not narrated.
 */

import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../hooks/useApi'
import { formatDate, num, pct, signed } from '../lib/format'
import { DriverAvatar } from '../components/DriverAvatar'
import { CountUp, GrowBar, Reveal, stagger } from '../lib/motion'
import { teamColor } from '../lib/palette'
import {
  Badge,
  Card,
  CardHeader,
  Disclaimer,
  EmptyState,
  ErrorState,
  Loading,
  SectionTitle,
  StatTile,
} from '../components/ui'
import { FeedbackWidget } from '../components/FeedbackWidget'
import type { DriverPrediction, RacePrediction, ScenarioResult } from '../lib/types'

export default function Predictions() {
  const prediction = useApi(() => api.nextPredictions(), [])

  if (prediction.loading) return <Loading label="Scoring the field…" />
  if (prediction.error) {
    return <ErrorState message={prediction.error} onRetry={prediction.reload} />
  }
  if (!prediction.data) return null

  const data = prediction.data

  if (!data.available) {
    return (
      <Card className="card-pad">
        <EmptyState
          message={
            data.message ??
            'No trained model is available. Run the training script after ingesting data.'
          }
        />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <SectionTitle
        hint={`Model ${data.model_version} · ${data.race} (${data.season}, round ${data.round}) at ${data.circuit}`}
      >
        Podium probabilities
      </SectionTitle>

      <Disclaimer>
        {data.disclaimer}
        {data.grid_source === 'projected'
          ? ' Qualifying has not run for this race, so the starting grid is projected from recent qualifying form.'
          : ''}
      </Disclaimer>

      <HeaderStats data={data} />
      <PodiumSpotlight predictions={data.predictions} />
      <FieldList predictions={data.predictions} />
      <ScenarioExplorer raceId={data.race_id} predictions={data.predictions} />

      <Card className="card-pad">
        <FeedbackWidget
          surface="prediction"
          referenceId={`${data.race_id}-${data.model_version}`}
          context={{ race: data.race, model_version: data.model_version }}
        />
      </Card>
    </div>
  )
}

function HeaderStats({ data }: { data: RacePrediction }) {
  const favourite = data.predictions[0]
  const podiumSum = data.predictions.reduce((sum, p) => sum + p.podium_probability, 0)

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label="Most likely podium"
        value={favourite?.driver ?? '—'}
        hint={favourite ? `${pct(favourite.podium_probability, 1)} podium estimate` : undefined}
        accent={teamColor(favourite?.color)}
      />
      <StatTile
        label="Grid source"
        value={data.grid_source === 'qualifying' ? 'Actual qualifying' : 'Projected'}
        hint={formatDate(data.date)}
      />
      <StatTile
        label="Drivers scored"
        value={data.predictions.length}
        hint={`Model ${data.model_version}`}
      />
      <StatTile
        label="Podium probabilities sum"
        value={num(podiumSum, 2)}
        hint="Should be near 3.00 — one podium has three places"
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
function FieldList({ predictions }: { predictions: DriverPrediction[] }) {
  const [expanded, setExpanded] = useState<number | null>(
    predictions[0]?.driver_id ?? null,
  )

  return (
    <Card>
      <CardHeader
        title="The field"
        subtitle="Ranked by podium probability. Select a driver to see what drives the estimate."
      />
      <ul className="divide-y divide-line">
        {predictions.map((entry, index) => {
          const open = expanded === entry.driver_id
          return (
            <li key={entry.driver_id}>
              <button
                type="button"
                onClick={() => setExpanded(open ? null : entry.driver_id)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2 sm:px-5"
              >
                <span className="tabular w-8 shrink-0 text-xs text-ink-muted">
                  P{entry.grid ?? '—'}
                </span>
                <DriverAvatar driver={entry} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink-primary">
                    {entry.driver}
                  </span>
                  <span
                    className="block truncate text-xs"
                    style={{ color: teamColor(entry.color) }}
                  >
                    {entry.constructor}
                  </span>
                </span>
                <span className="hidden w-40 shrink-0 items-center gap-3 sm:flex">
                  <GrowBar
                    value={entry.podium_probability}
                    color={teamColor(entry.color)}
                    className="h-2 flex-1"
                    delay={stagger(index, 40, 300)}
                  />
                  <span className="tabular w-10 text-right text-xs font-semibold">
                    {pct(entry.podium_probability)}
                  </span>
                </span>
                <span className="tabular w-14 shrink-0 text-right text-sm font-semibold sm:hidden">
                  {pct(entry.podium_probability)}
                </span>
                <span
                  aria-hidden="true"
                  className={`shrink-0 text-ink-muted transition-transform ${open ? 'rotate-90' : ''}`}
                >
                  ›
                </span>
              </button>

              {open ? <FactorPanel entry={entry} /> : null}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function FactorPanel({ entry }: { entry: DriverPrediction }) {
  return (
    <div className="border-t border-line bg-surface-2/60 px-4 py-4 sm:px-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <MiniStat label="Podium" value={pct(entry.podium_probability, 1)} />
        <MiniStat label="Points finish" value={pct(entry.points_probability, 1)} />
        <MiniStat
          label="Win (normalised)"
          value={pct(entry.win_probability, 1)}
          hint="Podium scores rescaled so the field sums to one winner"
        />
      </div>

      <div className="mt-4">
        <div className="label-muted mb-2">What moves this estimate</div>
        {entry.top_factors.length === 0 ? (
          <p className="text-xs text-ink-muted">
            No single feature moved this estimate by more than half a percentage point.
          </p>
        ) : (
          <ul className="space-y-2">
            {entry.top_factors.map((factor) => (
              <li key={factor.feature} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-1 h-2 w-2 shrink-0 rounded-full"
                  style={{
                    backgroundColor:
                      factor.direction === 'increases' ? '#199e70' : '#e66767',
                  }}
                />
                <span className="min-w-0 flex-1 text-xs leading-relaxed text-ink-secondary">
                  <span className="font-medium text-ink-primary">
                    {factor.direction === 'increases' ? 'Raises' : 'Lowers'} the estimate by{' '}
                    {pct(Math.abs(factor.impact), 1)}
                  </span>{' '}
                  — {factor.label}:{' '}
                  <span className="tabular text-ink-primary">{num(factor.value)}</span> versus a
                  typical <span className="tabular">{num(factor.baseline)}</span>.
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-[11px] leading-relaxed text-ink-muted">
          Each figure is measured by re-running the model with that one feature reset to its
          training median and recording how far the probability moves. Features are varied one at
          a time, so interactions between them are not separated out.
        </p>
      </div>
    </div>
  )
}

function MiniStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface-1 px-3 py-2">
      <div className="label-muted">{label}</div>
      <div className="tabular mt-0.5 text-lg font-semibold text-ink-primary">{value}</div>
      {hint ? <div className="mt-0.5 text-[11px] text-ink-muted">{hint}</div> : null}
    </div>
  )
}

/* ------------------------------------------------------------------ */
function ScenarioExplorer({
  raceId,
  predictions,
}: {
  raceId: number
  predictions: DriverPrediction[]
}) {
  const [driverId, setDriverId] = useState<number>(predictions[0]?.driver_id ?? 0)
  const [grid, setGrid] = useState(10)
  const [result, setResult] = useState<ScenarioResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      setResult(await api.scenario(raceId, driverId, grid))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Scenario explorer"
        subtitle="Move a driver to a different starting position and re-score the race"
        action={<Badge tone="warn">Simulation</Badge>}
      />
      <div className="card-pad space-y-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <label className="block">
            <span className="label-muted mb-1.5 block">Driver</span>
            <select
              className="input"
              value={driverId}
              onChange={(event) => setDriverId(Number(event.target.value))}
            >
              {predictions.map((entry) => (
                <option key={entry.driver_id} value={entry.driver_id}>
                  {entry.driver} — currently P{entry.grid}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="label-muted mb-1.5 block">Starts from</span>
            <select
              className="input sm:w-28"
              value={grid}
              onChange={(event) => setGrid(Number(event.target.value))}
            >
              {Array.from({ length: 20 }, (_, index) => index + 1).map((slot) => (
                <option key={slot} value={slot}>
                  P{slot}
                </option>
              ))}
            </select>
          </label>

          <button type="button" className="btn-primary h-[38px]" onClick={run} disabled={loading}>
            {loading ? 'Simulating…' : 'Simulate'}
          </button>
        </div>

        {error ? <p className="text-sm text-status-bad">{error}</p> : null}

        {result?.available ? (
          <div className="space-y-4 border-t border-line pt-4">
            <div className="text-sm">
              <span className="font-medium text-ink-primary">{result.driver}</span>
              <span className="text-ink-secondary">
                {' '}
                moved from P{result.original_grid} to P{result.scenario_grid}
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <DeltaCard
                label="Podium probability"
                before={result.before.podium_probability}
                after={result.after.podium_probability}
                delta={result.delta.podium_probability}
              />
              <DeltaCard
                label="Points probability"
                before={result.before.points_probability}
                after={result.after.points_probability}
                delta={result.delta.points_probability}
              />
              <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
                <div className="label-muted">Expected finish</div>
                <div className="tabular mt-1 text-lg font-semibold text-ink-primary">
                  P{result.before.expected_position} → P{result.after.expected_position}
                </div>
                <div className="mt-0.5 text-[11px] text-ink-muted">
                  Ranking within the simulated field
                </div>
              </div>
            </div>

            <Disclaimer>{result.disclaimer}</Disclaimer>

            <FeedbackWidget
              surface="scenario"
              referenceId={`${raceId}-${result.driver_id}-${grid}`}
              context={{ driver: result.driver, grid }}
            />
          </div>
        ) : null}
      </div>
    </Card>
  )
}

function DeltaCard({
  label,
  before,
  after,
  delta,
}: {
  label: string
  before: number
  after: number
  delta: number
}) {
  const tone = delta > 0 ? '#199e70' : delta < 0 ? '#e66767' : '#a8adba'
  return (
    <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
      <div className="label-muted">{label}</div>
      <div className="tabular mt-1 text-lg font-semibold text-ink-primary">
        {pct(before, 1)} → {pct(after, 1)}
      </div>
      <div className="tabular mt-0.5 text-xs font-medium" style={{ color: tone }}>
        {signed(delta * 100, 1)} pts
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/**
 * The three most likely podium finishers, given the room they deserve.
 *
 * Ordered visually as a podium (2nd, 1st, 3rd) with the favourite raised, so
 * the ranking reads before any number does.
 */
function PodiumSpotlight({ predictions }: { predictions: DriverPrediction[] }) {
  const top = predictions.slice(0, 3)
  if (top.length < 3) return null

  // Visual podium order: silver, gold, bronze.
  const arranged = [
    { entry: top[1], place: 2, lift: 'sm:mt-8' },
    { entry: top[0], place: 1, lift: '' },
    { entry: top[2], place: 3, lift: 'sm:mt-12' },
  ]

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-ink-primary">Most likely podium</h2>
        <span className="text-xs text-ink-muted">Model estimate, not a forecast</span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:items-start">
        {arranged.map(({ entry, place, lift }, index) => {
          const accent = teamColor(entry.color)
          return (
            <Reveal key={entry.driver_id} delay={stagger(index, 90)} className={lift}>
              <article
                className="card-interactive group relative overflow-hidden p-5 text-center"
                style={{
                  boxShadow: place === 1 ? `0 20px 50px -28px ${accent}` : undefined,
                }}
              >
                <div
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-[3px]"
                  style={{ background: accent }}
                />
                {place === 1 ? (
                  <div
                    aria-hidden="true"
                    className="checkers absolute -right-5 -top-5 h-20 w-20 rotate-12 opacity-25"
                  />
                ) : null}

                <p className="label-muted">
                  {place === 1 ? 'Favourite' : `${place}${place === 2 ? 'nd' : 'rd'} most likely`}
                </p>

                <DriverAvatar
                  driver={entry}
                  size={place === 1 ? 'xl' : 'lg'}
                  className="mx-auto mt-3"
                />

                <p className="mt-3 truncate font-display text-base font-bold">
                  {entry.driver}
                </p>
                <p className="truncate text-xs" style={{ color: accent }}>
                  {entry.constructor}
                </p>

                <p className="mt-3 font-display text-3xl font-extrabold">
                  <CountUp to={entry.podium_probability * 100} decimals={1} suffix="%" />
                </p>
                <p className="text-[11px] text-ink-muted">podium probability</p>

                <p className="mt-3 text-xs text-ink-secondary">
                  Starts P{entry.grid ?? '—'}
                </p>
              </article>
            </Reveal>
          )
        })}
      </div>
    </section>
  )
}
