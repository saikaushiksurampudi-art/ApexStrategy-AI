/**
 * Landing hero.
 *
 * Carries real numbers rather than stock phrases: the season in focus, the
 * championship leader with their portrait, and live counts pulled from the API.
 * The ambient motion (drifting glow, sweeping speed line) is decorative and is
 * switched off entirely under `prefers-reduced-motion`.
 */

import { Link } from 'react-router-dom'
import { CountUp, Reveal, usePrefersReducedMotion } from '../lib/motion'
import { DriverAvatar, PortraitCredit } from './DriverAvatar'
import { teamColor } from '../lib/palette'
import { num } from '../lib/format'
import type { Meta, Standings } from '../lib/types'

export function Hero({
  meta,
  standings,
  raceCount,
  resultCount,
}: {
  meta: Meta | null
  standings: Standings | null
  raceCount: number
  resultCount: number
}) {
  const reduced = usePrefersReducedMotion()
  const leader = standings?.drivers[0]
  const accent = teamColor(leader?.color)

  return (
    <section className="relative -mx-4 -mt-5 mb-6 overflow-hidden border-b border-line sm:-mx-6 sm:-mt-6">
      {/* Ambient background layers, all decorative. */}
      <div aria-hidden="true" className="absolute inset-0">
        <div
          className={`absolute -left-1/4 -top-1/2 h-[140%] w-[80%] rounded-full blur-3xl ${
            reduced ? '' : 'animate-slow-drift'
          }`}
          style={{ background: `radial-gradient(circle, ${accent}22, transparent 65%)` }}
        />
        <div
          className={`absolute -right-1/4 -top-1/3 h-[120%] w-[70%] rounded-full blur-3xl ${
            reduced ? '' : 'animate-slow-drift'
          }`}
          style={{
            background: 'radial-gradient(circle, rgba(57,135,229,0.18), transparent 65%)',
            animationDelay: '-9s',
          }}
        />
        <div className="stripes absolute inset-0 opacity-60" />
        {!reduced ? (
          <div className="absolute inset-x-0 top-1/3 h-px overflow-hidden">
            <div
              className="animate-speed-sweep h-px w-1/3"
              style={{
                background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
              }}
            />
          </div>
        ) : null}
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-line-strong to-transparent" />
      </div>

      <div className="relative mx-auto max-w-[1400px] px-4 py-12 sm:px-6 sm:py-16 lg:py-20">
        <div className="grid items-center gap-10 lg:grid-cols-[1.15fr_0.85fr]">
          {/* ---- Copy ---- */}
          <div>
            <Reveal>
              <span className="chip !border-accent/30 !bg-accent/10 !text-accent">
                <span className="relative flex h-1.5 w-1.5">
                  {!reduced ? (
                    <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-accent" />
                  ) : null}
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                </span>
                {meta ? `${meta.first_season}–${meta.last_season} · ${raceCount} races analysed` : 'Loading data'}
              </span>
            </Reveal>

            <Reveal delay={80}>
              <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
                <span className="text-gradient">Understand the race,</span>
                <br />
                <span style={{ color: accent }}>not just the result.</span>
              </h1>
            </Reveal>

            <Reveal delay={160}>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-secondary sm:text-lg">
                Evidence-based Formula 1 strategy analytics. Compare drivers, read a
                circuit&rsquo;s character, and see calibrated podium probabilities —
                each one showing the data behind it.
              </p>
            </Reveal>

            <Reveal delay={240}>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link to="/predictions" className="btn-accent">
                  See podium probabilities
                  <span aria-hidden="true">→</span>
                </Link>
                <Link to="/analyst" className="btn-ghost">
                  Ask the Race Analyst
                </Link>
              </div>
            </Reveal>

            <Reveal delay={320}>
              <dl className="mt-10 grid max-w-lg grid-cols-3 gap-4 border-t border-line pt-6">
                <HeroStat label="Races" value={raceCount} />
                <HeroStat label="Race results" value={resultCount} />
                <HeroStat label="Seasons" value={meta?.seasons.length ?? 0} />
              </dl>
            </Reveal>
          </div>

          {/* ---- Championship leader card ---- */}
          {leader ? (
            <Reveal delay={200} y={26}>
              <div
                className="card relative overflow-hidden p-5 sm:p-6"
                style={{ boxShadow: `0 24px 60px -30px ${accent}80` }}
              >
                <div
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-[3px]"
                  style={{ background: `linear-gradient(90deg, ${accent}, transparent)` }}
                />
                <div
                  aria-hidden="true"
                  className="checkers absolute -right-6 -top-6 h-24 w-24 rotate-12 opacity-30"
                />

                <p className="label-muted">
                  {standings?.season} championship leader
                </p>

                <div className="mt-4 flex items-center gap-4">
                  <DriverAvatar driver={leader} size="xl" />
                  <div className="min-w-0">
                    <p className="truncate font-display text-2xl font-bold leading-tight">
                      {leader.name}
                    </p>
                    <p className="mt-0.5 truncate text-sm" style={{ color: accent }}>
                      {leader.constructor}
                    </p>
                    <p className="mt-2 text-xs text-ink-muted">
                      {leader.wins} wins this season
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
                    <p className="label-muted">Points</p>
                    <p className="mt-0.5 font-display text-xl font-bold">
                      <CountUp to={leader.points} />
                    </p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
                    <p className="label-muted">Lead</p>
                    <p className="mt-0.5 font-display text-xl font-bold">
                      {standings && standings.drivers[1]
                        ? `+${num(leader.points - standings.drivers[1].points, 0)}`
                        : '—'}
                    </p>
                  </div>
                </div>

                <PortraitCredit driver={leader} className="mt-3" />
              </div>
            </Reveal>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function HeroStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="label-muted">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-bold sm:text-3xl">
        <CountUp to={value} />
      </dd>
    </div>
  )
}
