/**
 * Circuit intelligence: who goes well here, whether track position decides the
 * race, and what the pit-stop history says about strategy.
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import { useApi } from '../hooks/useApi'
import { num, pct, seasonRange, titleCase } from '../lib/format'
import { axisProps, ChartFrame, gridProps, TooltipCard } from '../components/charts'
import { SERIES } from '../lib/palette'
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Loading,
  SectionTitle,
  StatTile,
} from '../components/ui'
import { FeedbackWidget } from '../components/FeedbackWidget'
import { DriverAvatar } from '../components/DriverAvatar'
import { Reveal } from '../lib/motion'
import type { CircuitHistory } from '../lib/types'

export default function Circuits() {
  const params = useParams<{ ref?: string }>()
  const circuits = useApi(() => api.circuits(), [])
  const [selected, setSelected] = useState<string>(params.ref ?? 'monza')

  useEffect(() => {
    if (params.ref) setSelected(params.ref)
  }, [params.ref])

  const detail = useApi(() => api.circuit(selected), [selected])

  return (
    <div className="space-y-5">
      <SectionTitle hint="Historical performance, grid-position conversion and observed pit-stop patterns.">
        Circuit analysis
      </SectionTitle>

      <Card className="card-pad">
        <label className="block max-w-md">
          <span className="label-muted mb-1.5 block">Circuit</span>
          <select
            className="input"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            {(circuits.data ?? []).map((circuit) => (
              <option key={circuit.id} value={circuit.ref}>
                {circuit.name}
                {circuit.country ? ` — ${circuit.country}` : ''}
              </option>
            ))}
          </select>
        </label>
      </Card>

      {detail.loading ? <Loading /> : null}
      {detail.error ? <ErrorState message={detail.error} onRetry={detail.reload} /> : null}
      {detail.data ? (
        <Reveal>
          <CircuitBody data={detail.data} />
        </Reveal>
      ) : null}
    </div>
  )
}

function CircuitBody({ data }: { data: CircuitHistory }) {
  const { circuit } = data

  if (data.top_drivers.length === 0) {
    return (
      <Card>
        <EmptyState message={`No race results are held for ${circuit.name}.`} />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={circuit.name}
          subtitle={`${circuit.locality ?? ''}${circuit.locality ? ', ' : ''}${circuit.country ?? ''} · ${data.races_counted} races (${seasonRange(data.seasons_covered)})`}
          action={
            circuit.tyre_degradation ? (
              <Badge
                tone={
                  circuit.tyre_degradation === 'high'
                    ? 'bad'
                    : circuit.tyre_degradation === 'medium'
                      ? 'warn'
                      : 'good'
                }
              >
                {titleCase(circuit.tyre_degradation)} degradation
              </Badge>
            ) : null
          }
        />
        <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Circuit type" value={titleCase(circuit.circuit_type)} />
          <Fact label="Overtaking" value={titleCase(circuit.overtaking_difficulty)} />
          <Fact
            label="Pit-lane loss"
            value={circuit.pit_loss_seconds ? `~${num(circuit.pit_loss_seconds, 1)}s` : '—'}
          />
          <Fact label="DRS zones" value={circuit.drs_zones ? String(circuit.drs_zones) : '—'} />
        </div>
        {circuit.notes ? (
          <p className="border-t border-line px-4 py-3 text-xs leading-relaxed text-ink-secondary sm:px-5">
            {circuit.notes}{' '}
            <span className="text-ink-muted">
              (Track character is an editorial judgement, not a measurement.)
            </span>
          </p>
        ) : null}
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Pole converts to a win"
          value={pct(data.pole_to_win_rate.win_rate)}
          hint={`${data.pole_to_win_rate.poles_counted} races in sample`}
        />
        <StatTile
          label="Pole converts to a podium"
          value={pct(data.pole_to_win_rate.podium_rate)}
          hint="From the same sample"
        />
        <StatTile
          label="Average stops"
          value={data.pit_strategy?.avg_stops ? num(data.pit_strategy.avg_stops) : '—'}
          hint={
            data.pit_strategy?.sample_size
              ? `${data.pit_strategy.sample_size} driver-races`
              : 'No pit data'
          }
        />
        <StatTile
          label="Median stop time"
          value={
            data.pit_strategy?.median_stop_duration_s
              ? `${num(data.pit_strategy.median_stop_duration_s)}s`
              : '—'
          }
          hint="Stationary time in the box"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GridConversionChart data={data} />
        {data.pit_strategy && data.pit_strategy.sample_size > 0 ? (
          <StopDistributionChart strategy={data.pit_strategy} circuitName={circuit.name} />
        ) : null}
      </div>

      <TopDriversTable data={data} />
      <WinnersList data={data} />

      <Card className="card-pad">
        <FeedbackWidget
          surface="circuit"
          referenceId={circuit.ref}
          context={{ circuit: circuit.name }}
        />
      </Card>
    </div>
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

function GridConversionChart({ data }: { data: CircuitHistory }) {
  return (
    <ChartFrame
      title="Grid position vs. podium conversion"
      subtitle="How often each starting bucket reaches the podium here"
      height={260}
      note="A steep drop after the front rows means track position decides the race; a flatter shape means places can still be gained."
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
            {data.grid_analysis.map((row) => (
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
        <BarChart data={data.grid_analysis} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
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
                    { label: 'Win rate', value: pct(payload[0].payload.win_rate, 1) },
                    { label: 'Podium rate', value: pct(payload[0].payload.podium_rate, 1) },
                    { label: 'Points rate', value: pct(payload[0].payload.points_rate, 1) },
                    { label: 'Starts', value: payload[0].payload.starts },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="podium_rate" radius={[4, 4, 0, 0]} maxBarSize={56}>
            {data.grid_analysis.map((row) => (
              <Cell key={row.bucket} fill={SERIES[0]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

function StopDistributionChart({
  strategy,
  circuitName,
}: {
  strategy: NonNullable<CircuitHistory['pit_strategy']>
  circuitName: string
}) {
  const dominant = strategy.stop_distribution.reduce(
    (best, row) => (row.driver_races > (best?.driver_races ?? 0) ? row : best),
    strategy.stop_distribution[0],
  )

  return (
    <ChartFrame
      title="Observed pit-stop counts"
      subtitle={`${strategy.sample_size} driver-races at ${circuitName}`}
      height={260}
      note={
        dominant
          ? `Most common: ${dominant.stops} stop${dominant.stops === 1 ? '' : 's'} (${pct(dominant.share)} of the sample). Going against the field's usual choice is the strategic gamble.`
          : undefined
      }
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
            ...row,
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
                    { label: 'Driver-races', value: payload[0].payload.driver_races },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="share" fill={SERIES[2]} radius={[4, 4, 0, 0]} maxBarSize={56} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

function TopDriversTable({ data }: { data: CircuitHistory }) {
  return (
    <Card>
      <CardHeader
        title="Strongest records at this circuit"
        subtitle={`Ranked by podiums, then points · ${seasonRange(data.seasons_covered)}`}
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-xs text-ink-muted">
            <tr className="border-b border-line">
              <th className="px-4 py-2 text-left font-medium">Driver</th>
              <th className="px-4 py-2 text-left font-medium">Team</th>
              <th className="px-4 py-2 text-right font-medium">Starts</th>
              <th className="px-4 py-2 text-right font-medium">Wins</th>
              <th className="px-4 py-2 text-right font-medium">Podiums</th>
              <th className="px-4 py-2 text-right font-medium">Avg finish</th>
              <th className="px-4 py-2 text-right font-medium">Avg grid</th>
              <th className="px-4 py-2 text-right font-medium">Points</th>
            </tr>
          </thead>
          <tbody>
            {data.top_drivers.map((driver) => (
              <tr key={driver.driver_id} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2">
                  <span className="flex items-center gap-2.5">
                    <DriverAvatar driver={driver} size="sm" />
                    <span className="truncate">{driver.name}</span>
                  </span>
                </td>
                <td className="px-4 py-2 text-ink-secondary">{driver.constructor}</td>
                <td className="tabular px-4 py-2 text-right">{driver.starts}</td>
                <td className="tabular px-4 py-2 text-right">{driver.wins}</td>
                <td className="tabular px-4 py-2 text-right">{driver.podiums}</td>
                <td className="tabular px-4 py-2 text-right">{num(driver.avg_finish)}</td>
                <td className="tabular px-4 py-2 text-right text-ink-secondary">
                  {num(driver.avg_grid)}
                </td>
                <td className="tabular px-4 py-2 text-right">{num(driver.points, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-2.5 text-xs text-ink-muted sm:px-5">
        Small samples are common at circuit level — a driver with two starts here has a record, not
        a trend. Check the starts column before reading much into an average.
      </p>
    </Card>
  )
}

function WinnersList({ data }: { data: CircuitHistory }) {
  if (data.winners.length === 0) return null
  return (
    <Card>
      <CardHeader title="Past winners" subtitle="Most recent first" />
      <ul className="divide-y divide-line">
        {data.winners.map((winner) => (
          <li
            key={`${winner.season}-${winner.driver}`}
            className="flex items-center gap-3 px-4 py-2.5 text-sm sm:px-5"
          >
            <span className="tabular w-12 shrink-0 text-ink-muted">{winner.season}</span>
            <span className="flex min-w-0 flex-1 items-center gap-2.5">
              <DriverAvatar driver={{ ...winner, name: winner.driver }} size="sm" />
              <span className="truncate">{winner.driver}</span>
            </span>
            <span className="hidden shrink-0 text-xs text-ink-secondary sm:block">
              {winner.constructor}
            </span>
            <span className="tabular w-20 shrink-0 text-right text-xs text-ink-muted">
              from P{winner.grid ?? '—'}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
