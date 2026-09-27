/**
 * Model transparency.
 *
 * The product shows users probabilities, so it owes them the evidence that the
 * model is worth listening to: how it was trained, what it was tested on, and
 * whether it actually beats the obvious baselines. If it ever stops beating
 * them, this page says so.
 */

import { api } from '../lib/api'
import { useApi } from '../hooks/useApi'
import { num, pct } from '../lib/format'
import { Badge, Card, CardHeader, EmptyState, ErrorState, Loading, SectionTitle, StatTile } from '../components/ui'
import type { ModelInfo } from '../lib/types'

const METRIC_HELP: Record<string, string> = {
  log_loss: 'Penalises confident mistakes. Lower is better.',
  brier: 'Mean squared error of the probabilities. Lower is better.',
  roc_auc: 'Ranking quality: can it order drivers correctly? Higher is better.',
  accuracy: 'Share of correct calls at a 50% threshold.',
  precision: 'Of the drivers it flagged, how many were right.',
  recall: 'Of the drivers who qualified, how many it caught.',
}

const BASELINE_HELP: Record<string, string> = {
  grid_base_rate:
    'The historical conversion rate for each grid slot — a genuinely strong baseline in a sport where starting position dominates.',
  grid_rule: 'A hard rule: the front rows convert, everyone else does not.',
  class_prior: 'Always predict the overall base rate, ignoring the driver entirely.',
}

export default function ModelPage() {
  const model = useApi(() => api.modelInfo(), [])
  const feedback = useApi(() => api.feedbackStats(), [])

  if (model.loading) return <Loading label="Loading model details…" />
  if (model.error) return <ErrorState message={model.error} onRetry={model.reload} />
  if (!model.data) return null

  const info = model.data

  if (!info.available) {
    return (
      <Card className="card-pad">
        <EmptyState message={info.message ?? 'No trained model is available.'} />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <SectionTitle hint="How the podium model was built, and how it performs against simple baselines on seasons it never saw during training.">
        Model transparency
      </SectionTitle>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Version" value={info.version ?? '—'} hint={info.trained_at?.slice(0, 10)} />
        <StatTile
          label="Trained on"
          value={info.train_seasons?.join(', ') ?? '—'}
          hint={`${info.n_train_rows ?? 0} race entries`}
        />
        <StatTile
          label="Tested on"
          value={info.test_seasons?.join(', ') ?? '—'}
          hint="Held out entirely from training"
        />
        <StatTile label="Features" value={info.features?.length ?? 0} hint="All computable pre-race" />
      </div>

      <Card className="card-pad">
        <h2 className="text-sm font-semibold text-ink-primary">How it works</h2>
        <div className="mt-2 space-y-2 text-sm leading-relaxed text-ink-secondary">
          <p>
            Two binary classifiers estimate the probability of a podium (top 3) and a points finish
            (top 10). Each one blends a calibrated logistic regression over the features below with
            the historical conversion rate for the driver&rsquo;s grid slot.
          </p>
          <p>
            That second component matters. Starting position is so dominant in Formula 1 that a
            lookup table of &ldquo;how often does P4 reach the podium&rdquo; is a hard baseline to
            beat, so the model keeps it as an explicit term and learns how far to lean on it. The
            blend weight is chosen on a validation season carved out of the training range — never
            on the test seasons — so the scores below stay honest.
          </p>
          <p>
            Every feature is strictly backward-looking: rolling form is shifted by one race within
            each driver and team, so a race can never contribute to its own prediction.
          </p>
        </div>
      </Card>

      {info.evaluation
        ? Object.entries(info.evaluation).map(([target, block]) => (
            <EvaluationCard key={target} target={target} block={block} />
          ))
        : null}

      <Card>
        <CardHeader title="Features used" subtitle="All computable before the lights go out" />
        <div className="flex flex-wrap gap-1.5 p-4 sm:p-5">
          {(info.features ?? []).map((feature) => (
            <span key={feature} className="chip font-mono text-[11px]">
              {feature}
            </span>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="User feedback"
          subtitle="Ratings across the product — the signal for which explanations need work"
        />
        {feedback.loading ? (
          <Loading />
        ) : feedback.data && feedback.data.total > 0 ? (
          <div className="card-pad space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <MiniStat label="Total ratings" value={String(feedback.data.total)} />
              <MiniStat
                label="Helpful"
                value={pct(feedback.data.helpful_rate ?? 0)}
                tone="good"
              />
              <MiniStat label="Unhelpful" value={String(feedback.data.unhelpful)} tone="bad" />
            </div>

            {feedback.data.top_reasons.length > 0 ? (
              <div>
                <div className="label-muted mb-2">Most common complaints</div>
                <ul className="space-y-1">
                  {feedback.data.top_reasons.map((reason) => (
                    <li
                      key={reason.reason}
                      className="flex justify-between border-b border-line/60 py-1 text-xs last:border-0"
                    >
                      <span className="text-ink-secondary">
                        {reason.reason.replace(/_/g, ' ')}
                      </span>
                      <span className="tabular text-ink-primary">{reason.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState message="No feedback submitted yet." />
        )}
      </Card>
    </div>
  )
}

function EvaluationCard({
  target,
  block,
}: {
  target: string
  block: NonNullable<ModelInfo['evaluation']>[string]
}) {
  const metrics = ['log_loss', 'brier', 'roc_auc', 'accuracy', 'precision', 'recall']

  return (
    <Card>
      <CardHeader
        title={`Target: ${target === 'podium' ? 'podium finish (top 3)' : 'points finish (top 10)'}`}
        subtitle={`Measured on held-out seasons, against the strongest baseline (${block.best_baseline})`}
        action={
          <Badge tone={block.beats_baseline ? 'good' : 'bad'}>
            {block.beats_baseline ? 'Beats baseline' : 'Does not beat baseline'}
          </Badge>
        }
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-xs text-ink-muted">
            <tr className="border-b border-line">
              <th className="px-4 py-2 text-left font-medium">Metric</th>
              <th className="px-4 py-2 text-right font-medium">Model</th>
              <th className="px-4 py-2 text-right font-medium">Baseline</th>
              <th className="px-4 py-2 text-left font-medium">What it means</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => {
              const modelValue = block.model[metric]
              const baselineValue = block.baseline_scores[metric]
              // Lower is better for the two loss metrics, higher for the rest.
              const lowerIsBetter = metric === 'log_loss' || metric === 'brier'
              const better = lowerIsBetter
                ? modelValue < baselineValue
                : modelValue > baselineValue
              return (
                <tr key={metric} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{metric}</td>
                  <td
                    className={`tabular px-4 py-2 text-right font-medium ${
                      better ? 'text-status-good' : 'text-ink-primary'
                    }`}
                  >
                    {num(modelValue, 4)}
                  </td>
                  <td className="tabular px-4 py-2 text-right text-ink-secondary">
                    {num(baselineValue, 4)}
                  </td>
                  <td className="px-4 py-2 text-xs text-ink-muted">{METRIC_HELP[metric]}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-3 text-xs leading-relaxed text-ink-muted sm:px-5">
        <span className="font-medium text-ink-secondary">
          Baseline &ldquo;{block.best_baseline}&rdquo;:{' '}
        </span>
        {BASELINE_HELP[block.best_baseline] ?? 'A simple reference method.'} The model improves on it
        by {num(block.log_loss_improvement, 4)} log loss.
      </p>
    </Card>
  )
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'good' | 'bad'
}) {
  const color =
    tone === 'good' ? 'text-status-good' : tone === 'bad' ? 'text-status-bad' : 'text-ink-primary'
  return (
    <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
      <div className="label-muted">{label}</div>
      <div className={`tabular mt-0.5 text-lg font-semibold ${color}`}>{value}</div>
    </div>
  )
}
