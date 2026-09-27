/** Shapes returned by the ApexStrategy API. */

export interface DriverSummary {
  driver_id: number
  ref: string
  name: string
  code: string | null
  nationality: string | null
  constructor: string | null
  constructor_color: string | null
  races: number
  wins: number
  podiums: number
  points_finishes: number
  total_points: number
  dnfs: number
  avg_finish: number | null
  avg_grid: number | null
  best_finish: number | null
  podium_rate: number
  points_rate: number
  dnf_rate: number
  avg_positions_gained: number | null
  seasons: number[]
}

export interface HeadToHead {
  driver_a: DriverSummary
  driver_b: DriverSummary
  shared_races: number
  race_head_to_head: { a: number; b: number; counted: number }
  qualifying_head_to_head: { a: number; b: number; counted: number }
  timeline: Array<{
    season: number
    round: number
    race: string
    circuit: string
    a_position: number | null
    a_position_text: string | null
    a_points: number
    a_grid: number | null
    b_position: number | null
    b_position_text: string | null
    b_points: number
    b_grid: number | null
    race_winner: string | null
    quali_winner: string | null
  }>
}

export interface CircuitProfile {
  id: number
  ref: string
  name: string
  locality: string | null
  country: string | null
  circuit_type: string | null
  overtaking_difficulty: string | null
  tyre_degradation: string | null
  pit_loss_seconds: number | null
  drs_zones: number | null
  notes: string | null
}

export interface PitStrategy {
  sample_size: number
  stop_distribution: Array<{ stops: number; driver_races: number; share: number }>
  avg_stops: number | null
  median_stop_duration_s: number | null
  pit_loss_seconds?: number | null
  note?: string
}

export interface CircuitHistory {
  circuit: CircuitProfile
  seasons_covered: number[]
  races_counted: number
  top_drivers: Array<{
    driver_id: number
    ref: string
    name: string
    code: string | null
    constructor: string
    color: string
    starts: number
    wins: number
    podiums: number
    points_finishes: number
    dnfs: number
    points: number
    avg_finish: number | null
    best_finish: number | null
    avg_grid: number | null
    podium_rate: number
  }>
  grid_analysis: Array<{
    bucket: string
    starts: number
    win_rate: number
    podium_rate: number
    points_rate: number
  }>
  winners: Array<{
    season: number
    driver: string
    code: string | null
    constructor: string
    color: string
    grid: number | null
  }>
  pole_to_win_rate: { poles_counted: number; win_rate: number; podium_rate: number }
  pit_strategy?: PitStrategy
}

export interface PredictionFactor {
  feature: string
  label: string
  value: number
  baseline: number
  impact: number
  direction: 'increases' | 'decreases'
}

export interface DriverPrediction {
  driver_id: number
  ref: string
  driver: string
  code: string | null
  constructor: string | null
  color: string
  grid: number | null
  grid_source: string
  podium_probability: number
  points_probability: number
  win_probability: number
  expected_position: number
  top_factors: PredictionFactor[]
  features: Record<string, number | null>
}

export interface RacePrediction {
  available: boolean
  message?: string
  race_id: number
  race?: string
  season?: number
  round?: number
  circuit?: string
  date?: string | null
  is_completed?: boolean
  is_simulation?: boolean
  model_version?: string
  grid_source?: string
  predictions: DriverPrediction[]
  disclaimer?: string
}

export interface ScenarioResult {
  available: boolean
  message?: string
  race: string
  race_id: number
  driver: string
  driver_id: number
  original_grid: number | null
  scenario_grid: number
  before: ProbabilitySet
  after: ProbabilitySet
  delta: { podium_probability: number; points_probability: number; expected_position: number }
  top_factors: PredictionFactor[]
  field: DriverPrediction[]
  disclaimer: string
}

export interface ProbabilitySet {
  podium_probability: number
  points_probability: number
  win_probability: number
  expected_position: number
}

export interface Citation {
  source: string
  detail: string
}

export interface ChatResponse {
  session_id: string
  message_id: number | null
  question: string
  answer: string
  intent: string
  citations: Citation[]
  entities: Record<string, Array<{ id: number; ref: string; name: string }> | number[]>
  notes: string[]
  grounded: boolean
  context: Record<string, unknown>
  generator: string | null
  model_id?: string | null
  latency_ms?: number | null
  fallback_reason?: string | null
}

export interface RaceSummary {
  id: number
  season: number
  round: number
  name: string
  date: string | null
  is_completed: boolean
  weather?: string | null
  circuit: { id: number; ref: string; name: string; country: string | null; locality: string | null }
}

export interface RaceDetail {
  race: {
    id: number
    season: number
    round: number
    name: string
    date: string | null
    url: string | null
    is_completed: boolean
    weather: string | null
    total_laps: number | null
    circuit: CircuitProfile
  }
  results: Array<{
    position: number | null
    position_text: string | null
    driver_id: number
    ref: string
    driver: string
    code: string | null
    constructor: string
    color: string
    grid: number | null
    positions_gained: number | null
    laps: number | null
    points: number
    status: string | null
    finished: boolean
    fastest_lap: string | null
    fastest_lap_rank: number | null
  }>
  qualifying: Array<{
    position: number
    driver_id: number
    ref: string
    driver: string
    code: string | null
    constructor: string
    color: string
    q1: string | null
    q2: string | null
    q3: string | null
    best: string | null
    gap_to_pole_s: number | null
  }>
  pit_strategy?: PitStrategy
  circuit_history?: CircuitHistory
}

export interface Standings {
  season: number
  through_round: number | null
  drivers: Array<{
    position: number | null
    driver_id: number
    ref: string
    name: string
    code: string | null
    constructor: string | null
    color: string | null
    points: number
    wins: number
  }>
  constructors: Array<{
    position: number | null
    constructor_id: number
    ref: string
    name: string
    color: string | null
    points: number
    wins: number
  }>
}

export interface ConstructorSeries {
  constructor_id: number
  name: string
  color: string
  points: Array<{ round: number; race: string; round_points: number; cumulative_points: number }>
}

export interface Meta {
  app_name: string
  version: string
  seasons: number[]
  first_season: number | null
  last_season: number | null
  next_race: {
    id: number
    season: number
    round: number
    name: string
    date: string | null
    circuit: string
    circuit_id: number
    is_completed: boolean
  } | null
  latest_race: Meta['next_race']
  ai_generator: string
}

export interface ModelInfo {
  available: boolean
  message?: string
  version?: string
  trained_at?: string
  train_seasons?: number[]
  test_seasons?: number[]
  n_train_rows?: number
  features?: string[]
  evaluation?: Record<
    string,
    {
      model: Record<string, number>
      best_baseline: string
      baseline_scores: Record<string, number>
      beats_baseline: boolean
      log_loss_improvement: number
    }
  >
}
