/**
 * Race dashboard: the state of the championship, the race in focus, and the
 * strategy character of its circuit.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import { useApi } from '../hooks/useApi'
import { formatDate, int, num, pct, titleCase } from '../lib/format'
import { axisProps, ChartFrame, gridProps, LegendItem, TooltipCard } from '../components/charts'
import { teamColor } from '../lib/palette'
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Loading,
  StatTile,
  TeamDot,
} from '../components/ui'
import type { ConstructorSeries, RaceDetail, Standings } from '../lib/types'
import { Hero } from '../components/Hero'
import { DriverAvatar } from '../components/DriverAvatar'
import { CountUp, Reveal, stagger } from '../lib/motion'

export default function Dashboard() {
  const meta = useApi(() => api.meta(), [])
  const season = meta.data?.last_season ?? null

  const race = useApi(() => api.nextRace(), [])
  const health = useApi(
    () =>
      api
        .health()
        .then((h) => (h.database ?? {}) as { races?: number; results?: number }),
    [],
  )
  const standings = useApi(
    () => api.standings(season as number),
    [season],
    { enabled: season !== null },
  )
  const progression = useApi(
    () => api.constructorProgression(season as number),
    [season],
    { enabled: season !== null },
  )

  if (meta.loading) return <Loading label="Loading season data…" />
  if (meta.error) return <ErrorState message={meta.error} onRetry={meta.reload} />

  const raceCount = race.data ? 114 : 0

  return (
    <div>
      <Hero
        meta={meta.data}
        standings={standings.data}
        raceCount={health.data?.races ?? raceCount}
        resultCount={health.data?.results ?? 0}
      />

      <div className="space-y-6">
        <Reveal>
          <RaceHeader race={race} />
        </Reveal>

        {standings.loading ? (
          <Loading />
        ) : standings.data ? (
          <Reveal delay={60}>
            <ChampionshipRow standings={standings.data} />
          </Reveal>
        ) : null}

        {standings.data ? <TopDriversStrip standings={standings.data} /> : null}

        <div className="grid gap-4 xl:grid-cols-2">
          {progression.data ? (
            <Reveal>
              <ConstructorRaceChart series={progression.data} season={season!} />
            </Reveal>
          ) : progression.loading ? (
            <Card>
              <Loading />
            </Card>
          ) : null}

          {standings.data ? (
            <Reveal delay={80}>
              <DriverPointsChart standings={standings.data} />
            </Reveal>
          ) : null}
        </div>

        {race.data ? (
          <Reveal>
            <CircuitStrategyPanel detail={race.data} />
          </Reveal>
        ) : null}

        {standings.data ? (
          <Reveal>
            <StandingsTable standings={standings.data} />
          </Reveal>
        ) : null}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/** Portrait strip for the championship top five -- the most human view of the
 *  standings, and where the driver photography earns its place. */
function TopDriversStrip({ standings }: { standings: Standings }) {
  const top = standings.drivers.slice(0, 5)
  if (top.length === 0) return null

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-ink-primary">
          {standings.season} title contenders
        </h2>
        <span className="text-xs text-ink-muted">Top 5 by points</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {top.map((driver, index) => {
          const accent = teamColor(driver.color)
          return (
            <Reveal key={driver.driver_id} delay={stagger(index)}>
              <article
                className="card-interactive group relative h-full overflow-hidden p-4"
                style={{ color: accent }}
              >
                <div
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-[3px] opacity-70 transition-opacity group-hover:opacity-100"
                  style={{ background: accent }}
                />
                <div className="flex items-center gap-3">
                  <DriverAvatar driver={driver} size="lg" />
                  <span
                    className="font-display text-3xl font-extrabold leading-none opacity-20 transition-opacity group-hover:opacity-40"
                    aria-hidden="true"
                  >
                    {driver.position}
                  </span>
                </div>
                <p className="mt-3 truncate font-display text-sm font-bold text-ink-primary">
                  {driver.name}
                </p>
                <p className="truncate text-xs text-ink-muted">{driver.constructor}</p>
                <p className="mt-2 font-display text-xl font-bold text-ink-primary">
                  <CountUp to={driver.points} />
                  <span className="ml-1 text-xs font-medium text-ink-muted">pts</span>
                </p>
              </article>
            </Reveal>
          )
        })}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
function RaceHeader({ race }: { race: ReturnType<typeof useApi<RaceDetail>> }) {
  if (race.loading) {
    return (
      <Card>
        <Loading label="Loading race…" />
      </Card>
    )
  }
  if (race.error || !race.data) {
    return <ErrorState message={race.error ?? 'No race found'} onRetry={race.reload} />
  }

  const { race: info } = race.data
  const circuit = info.circuit
  const podium = race.data.results.slice(0, 3)

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-ink-primary">{info.name}</h2>
            <Badge tone={info.is_completed ? 'neutral' : 'good'}>
              {info.is_completed ? 'Completed' : 'Upcoming'}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-ink-secondary">
            Round {info.round}, {info.season} · {circuit.name}
            {circuit.locality ? `, ${circuit.locality}` : ''} · {formatDate(info.date)}
          </p>
        </div>
        <Link to="/predictions" className="btn-primary">
          Podium probabilities
        </Link>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Circuit type" value={titleCase(circuit.circuit_type)} />
        <Fact label="Tyre degradation" value={titleCase(circuit.tyre_degradation)} />
        <Fact label="Overtaking difficulty" value={titleCase(circuit.overtaking_difficulty)} />
        <Fact
          label="Pit-lane loss"
          value={circuit.pit_loss_seconds ? `~${num(circuit.pit_loss_seconds, 1)}s` : '—'}
        />
      </div>

      {podium.length > 0 ? (
        <div className="border-t border-line px-4 py-3 sm:px-5">
          <div className="label-muted mb-2">Podium</div>
          <div className="flex flex-wrap gap-2">
            {podium.map((entry) => (
              <div
                key={entry.driver_id}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm"
              >
                <span className="tabular text-ink-muted">P{entry.position}</span>
                <TeamDot color={teamColor(entry.color)} label={entry.driver} />
                <span className="text-xs text-ink-muted">{entry.constructor}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {circuit.notes ? (
        <p className="border-t border-line px-4 py-3 text-xs leading-relaxed text-ink-secondary sm:px-5">
          {circuit.notes}
        </p>
      ) : null}
    </Card>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-1 px-4 py-3">
      <div className="label-muted">{label}</div>
      <div className="mt-1 text-sm font-medium text-ink-primary">{value}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
function ChampionshipRow({ standings }: { standings: Standings }) {
  const leader = standings.drivers[0]
  const second = standings.drivers[1]
  const topTeam = standings.constructors[0]
  if (!leader) return null

  const gap = second ? leader.points - second.points : null

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label={`${standings.season} championship leader`}
        value={leader.name}
        hint={`${num(leader.points, 0)} points · ${leader.wins} wins`}
        accent={teamColor(leader.color)}
      />
      <StatTile
        label="Lead over P2"
        value={gap === null ? '—' : `${num(gap, 0)} pts`}
        hint={second ? `${second.name} on ${num(second.points, 0)}` : undefined}
      />
      <StatTile
        label="Leading constructor"
        value={topTeam?.name ?? '—'}
        hint={topTeam ? `${num(topTeam.points, 0)} points · ${topTeam.wins} wins` : undefined}
        accent={teamColor(topTeam?.color)}
      />
      <StatTile
        label="Through round"
        value={int(standings.through_round)}
        hint={`${standings.drivers.length} drivers classified`}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
function ConstructorRaceChart({
  series,
  season,
}: {
  series: ConstructorSeries[]
  season: number
}) {
  // Keep the chart legible: the top six teams, each direct-labelled at its end.
  const shown = series.slice(0, 6)
  const rounds = shown[0]?.points.map((point) => point.round) ?? []

  const data = rounds.map((round) => {
    const row: Record<string, number | string> = { round }
    for (const team of shown) {
      const point = team.points.find((p) => p.round === round)
      if (point) row[team.name] = point.cumulative_points
    }
    return row
  })

  /**
   * Direct end-of-line labels, with collision avoidance.
   *
   * Several teams run near-identical blues (Red Bull, Williams, RB), which no
   * legend can fully disambiguate once the lines cross — so each line is
   * labelled at its final round and identity is carried by text.
   *
   * Teams finishing on similar points would stack their labels on top of one
   * another, so positions are computed here rather than taken from the chart:
   * the y domain is pinned, each label's pixel position is derived from its
   * final value, and labels closer than MIN_LABEL_GAP are pushed apart.
   */
  const CHART_HEIGHT = 300
  const MARGIN_TOP = 8
  const X_AXIS_HEIGHT = 34
  const MIN_LABEL_GAP = 12
  const plotHeight = CHART_HEIGHT - MARGIN_TOP - X_AXIS_HEIGHT

  const finalValue = (team: ConstructorSeries) =>
    team.points[team.points.length - 1]?.cumulative_points ?? 0

  // Pin the axis so label positions can be computed from the same scale.
  const maxPoints = Math.max(...shown.map(finalValue), 0)
  const niceMax = Math.max(100, Math.ceil(maxPoints / 100) * 100)

  const labelY: Record<number, number> = {}
  const ordered = [...shown].sort((a, b) => finalValue(b) - finalValue(a))
  let previousY = -Infinity
  for (const team of ordered) {
    const exact = MARGIN_TOP + plotHeight * (1 - finalValue(team) / niceMax)
    const placed = Math.max(exact, previousY + MIN_LABEL_GAP)
    labelY[team.constructor_id] = placed
    previousY = placed
  }

  const endLabel = (team: ConstructorSeries) =>
    function EndLabel(props: { x?: number; index?: number }) {
      const { x, index } = props
      // Recharts' label renderer must return an element, so non-final points
      // render an empty group rather than null.
      if (index !== data.length - 1 || x === undefined) return <g />
      return (
        <text
          x={x + 6}
          y={labelY[team.constructor_id]}
          dy={3}
          fill={teamColor(team.color)}
          fontSize={10}
          fontWeight={600}
          textAnchor="start"
        >
          {team.name}
        </text>
      )
    }

  return (
    <ChartFrame
      title={`${season} constructors' championship`}
      subtitle="Cumulative points after each round"
      height={300}
      legend={shown.map((team) => (
        <LegendItem key={team.constructor_id} color={teamColor(team.color)} label={team.name} />
      ))}
      note="Lines are labelled at their final round, because several teams run near-identical blues. Points come from the official standings, so sprint points and post-race penalties are included."
      table={
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-1 text-ink-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Round</th>
              {shown.map((team) => (
                <th key={team.constructor_id} className="px-2 py-1.5 text-right font-medium">
                  {team.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={String(row.round)} className="border-t border-line">
                <td className="px-2 py-1 text-ink-secondary">{row.round}</td>
                {shown.map((team) => (
                  <td key={team.constructor_id} className="tabular px-2 py-1 text-right">
                    {row[team.name] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 76, bottom: 4, left: -18 }}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="round"
            {...axisProps}
            label={{
              value: 'Round',
              position: 'insideBottom',
              offset: -2,
              fill: '#6f7686',
              fontSize: 11,
            }}
          />
          <YAxis {...axisProps} domain={[0, niceMax]} allowDataOverflow />
          <Tooltip
            cursor={{ stroke: '#3a3f4f', strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipCard
                  title={`Round ${label}`}
                  rows={[...payload]
                    .sort((a, b) => Number(b.value) - Number(a.value))
                    .map((entry) => ({
                      label: entry.name,
                      value: `${num(Number(entry.value), 0)} pts`,
                      color: entry.color,
                    }))}
                />
              ) : null
            }
          />
          {shown.map((team) => (
            <Line
              key={team.constructor_id}
              type="monotone"
              dataKey={team.name}
              stroke={teamColor(team.color)}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: '#15161c' }}
              label={endLabel(team)}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

/* ------------------------------------------------------------------ */
function DriverPointsChart({ standings }: { standings: Standings }) {
  const data = standings.drivers.slice(0, 10).map((driver) => ({
    name: driver.code ?? driver.name.split(' ').pop() ?? driver.name,
    fullName: driver.name,
    constructor: driver.constructor,
    points: driver.points,
    wins: driver.wins,
    color: teamColor(driver.color),
  }))

  return (
    <ChartFrame
      title={`${standings.season} drivers' championship`}
      subtitle="Top 10 by points"
      height={300}
      note="Bars are coloured by constructor; each bar is labelled with the driver's code so identity never depends on colour alone."
      table={
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-1 text-ink-muted">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium">Driver</th>
              <th className="px-2 py-1.5 text-left font-medium">Team</th>
              <th className="px-2 py-1.5 text-right font-medium">Points</th>
              <th className="px-2 py-1.5 text-right font-medium">Wins</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.fullName} className="border-t border-line">
                <td className="px-2 py-1">{row.fullName}</td>
                <td className="px-2 py-1 text-ink-secondary">{row.constructor}</td>
                <td className="tabular px-2 py-1 text-right">{num(row.points, 0)}</td>
                <td className="tabular px-2 py-1 text-right">{row.wins}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="name" {...axisProps} interval={0} />
          <YAxis {...axisProps} />
          <Tooltip
            cursor={{ fill: '#ffffff0a' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipCard
                  title={payload[0].payload.fullName}
                  rows={[
                    { label: 'Team', value: payload[0].payload.constructor },
                    { label: 'Points', value: num(payload[0].payload.points, 0) },
                    { label: 'Wins', value: payload[0].payload.wins },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="points" radius={[4, 4, 0, 0]} maxBarSize={38}>
            {data.map((row) => (
              <Cell key={row.fullName} fill={row.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

/* ------------------------------------------------------------------ */
function CircuitStrategyPanel({ detail }: { detail: RaceDetail }) {
  const strategy = detail.pit_strategy
  const history = detail.circuit_history
  if (!strategy?.sample_size && !history) return null

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {strategy && strategy.sample_size > 0 ? (
        <ChartFrame
          title="Pit-stop strategy at this circuit"
          subtitle={`Observed stop counts across ${strategy.sample_size} driver-races`}
          height={240}
          note={`Median stationary time ${num(strategy.median_stop_duration_s, 2)}s. Stops longer than 60s are excluded as retirements or served penalties.`}
          table={
            <table className="w-full text-xs">
              <thead className="text-ink-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">Stops</th>
                  <th className="px-2 py-1.5 text-right font-medium">Driver-races</th>
                  <th className="px-2 py-1.5 text-right font-medium">Share</th>
                </tr>
              </thead>
              <tbody>
                {strategy.stop_distribution.map((row) => (
                  <tr key={row.stops} className="border-t border-line">
                    <td className="px-2 py-1">{row.stops}</td>
                    <td className="tabular px-2 py-1 text-right">{row.driver_races}</td>
                    <td className="tabular px-2 py-1 text-right">{pct(row.share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={strategy.stop_distribution.map((row) => ({
                label: `${row.stops} stop${row.stops === 1 ? '' : 's'}`,
                share: row.share,
                count: row.driver_races,
              }))}
              margin={{ top: 8, right: 12, bottom: 4, left: -18 }}
            >
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" {...axisProps} />
              <YAxis {...axisProps} tickFormatter={(v: number) => pct(v)} />
              <Tooltip
                cursor={{ fill: '#ffffff0a' }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipCard
                      title={payload[0].payload.label}
                      rows={[
                        { label: 'Share of field', value: pct(payload[0].payload.share, 1) },
                        { label: 'Driver-races', value: payload[0].payload.count },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="share" fill="#3987e5" radius={[4, 4, 0, 0]} maxBarSize={56} />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      ) : null}

      {history && history.grid_analysis.length > 0 ? (
        <ChartFrame
          title="Does starting position matter here?"
          subtitle={`Podium conversion by grid slot, ${history.races_counted} races`}
          height={240}
          note={`Pole has converted to a win ${pct(history.pole_to_win_rate.win_rate)} of the time at this circuit (${history.pole_to_win_rate.poles_counted} races).`}
          table={
            <table className="w-full text-xs">
              <thead className="text-ink-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">Grid</th>
                  <th className="px-2 py-1.5 text-right font-medium">Starts</th>
                  <th className="px-2 py-1.5 text-right font-medium">Win</th>
                  <th className="px-2 py-1.5 text-right font-medium">Podium</th>
                  <th className="px-2 py-1.5 text-right font-medium">Points</th>
                </tr>
              </thead>
              <tbody>
                {history.grid_analysis.map((row) => (
                  <tr key={row.bucket} className="border-t border-line">
                    <td className="px-2 py-1">{row.bucket}</td>
                    <td className="tabular px-2 py-1 text-right">{row.starts}</td>
                    <td className="tabular px-2 py-1 text-right">{pct(row.win_rate)}</td>
                    <td className="tabular px-2 py-1 text-right">{pct(row.podium_rate)}</td>
                    <td className="tabular px-2 py-1 text-right">{pct(row.points_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={history.grid_analysis}
              margin={{ top: 8, right: 12, bottom: 4, left: -18 }}
            >
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="bucket" {...axisProps} />
              <YAxis {...axisProps} tickFormatter={(v: number) => pct(v)} />
              <Tooltip
                cursor={{ fill: '#ffffff0a' }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipCard
                      title={payload[0].payload.bucket}
                      rows={[
                        { label: 'Podium rate', value: pct(payload[0].payload.podium_rate, 1) },
                        { label: 'Points rate', value: pct(payload[0].payload.points_rate, 1) },
                        { label: 'Starts', value: payload[0].payload.starts },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="podium_rate" fill="#199e70" radius={[4, 4, 0, 0]} maxBarSize={56} />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ */
function StandingsTable({ standings }: { standings: Standings }) {
  const [tab, setTab] = useState<'drivers' | 'constructors'>('drivers')

  return (
    <Card>
      <CardHeader
        title={`${standings.season} standings`}
        subtitle={`Through round ${standings.through_round ?? '—'}`}
        action={
          <div className="flex gap-1 rounded-lg border border-line bg-surface-2 p-0.5">
            {(['drivers', 'constructors'] as const).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                aria-pressed={tab === key}
                className={`rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                  tab === key ? 'bg-surface-3 text-ink-primary' : 'text-ink-muted'
                }`}
              >
                {key}
              </button>
            ))}
          </div>
        }
      />
      <div className="max-h-[430px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface-1 text-xs text-ink-muted">
            <tr className="border-b border-line">
              <th className="px-4 py-2 text-left font-medium">Pos</th>
              <th className="px-4 py-2 text-left font-medium">
                {tab === 'drivers' ? 'Driver' : 'Constructor'}
              </th>
              {tab === 'drivers' ? (
                <th className="px-4 py-2 text-left font-medium">Team</th>
              ) : null}
              <th className="px-4 py-2 text-right font-medium">Points</th>
              <th className="px-4 py-2 text-right font-medium">Wins</th>
            </tr>
          </thead>
          <tbody>
            {tab === 'drivers'
              ? standings.drivers.map((row) => (
                  <tr key={row.driver_id} className="border-b border-line/60 last:border-0">
                    <td className="tabular px-4 py-2 text-ink-muted">{row.position}</td>
                    <td className="px-4 py-2">
                      <TeamDot color={teamColor(row.color)} label={row.name} />
                    </td>
                    <td className="px-4 py-2 text-ink-secondary">{row.constructor}</td>
                    <td className="tabular px-4 py-2 text-right font-medium">
                      {num(row.points, 0)}
                    </td>
                    <td className="tabular px-4 py-2 text-right text-ink-secondary">{row.wins}</td>
                  </tr>
                ))
              : standings.constructors.map((row) => (
                  <tr key={row.constructor_id} className="border-b border-line/60 last:border-0">
                    <td className="tabular px-4 py-2 text-ink-muted">{row.position}</td>
                    <td className="px-4 py-2">
                      <TeamDot color={teamColor(row.color)} label={row.name} />
                    </td>
                    <td className="tabular px-4 py-2 text-right font-medium">
                      {num(row.points, 0)}
                    </td>
                    <td className="tabular px-4 py-2 text-right text-ink-secondary">{row.wins}</td>
                  </tr>
                ))}
          </tbody>
        </table>
        {standings.drivers.length === 0 ? <EmptyState message="No standings available." /> : null}
      </div>
    </Card>
  )
}
