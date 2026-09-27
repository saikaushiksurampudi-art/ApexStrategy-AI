/**
 * Typed fetch wrapper for the ApexStrategy API.
 *
 * The auth token lives in localStorage: this is a read-mostly analytics product
 * where the only protected resources are a user's own saved comparisons, so the
 * tradeoff is acceptable and keeps the SPA free of a session backend.
 */

import type {
  ChatResponse,
  CircuitHistory,
  ConstructorSeries,
  HeadToHead,
  Meta,
  ModelInfo,
  RaceDetail,
  RacePrediction,
  RaceSummary,
  ScenarioResult,
  Standings,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'
const TOKEN_KEY = 'apex.token'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const auth = {
  get token(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* private browsing: stay signed out rather than crash */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* no-op */
    }
  },
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = auth.token
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Could not reach the API. Is the backend running?', 0)
  }

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const payload = text ? safeParse(text) : null

  if (!response.ok) {
    const detail =
      (payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : null) ?? `Request failed (${response.status})`
    throw new ApiError(detail, response.status)
  }
  return payload as T
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

const qs = (params: Record<string, unknown>): string => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)))
    else search.append(key, String(value))
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

export const api = {
  meta: () => request<Meta>('/meta'),
  health: () => request<Record<string, unknown>>('/health'),

  races: (params: { season?: number; completed_only?: boolean } = {}) =>
    request<RaceSummary[]>(`/races${qs(params)}`),
  nextRace: () => request<RaceDetail>('/races/next'),
  race: (id: number) => request<RaceDetail>(`/races/${id}`),

  standings: (season: number) => request<Standings>(`/seasons/${season}/standings`),
  constructorProgression: (season: number) =>
    request<ConstructorSeries[]>(`/seasons/${season}/constructor-progression`),

  drivers: (season?: number) =>
    request<Array<{ id: number; ref: string; name: string; code: string | null }>>(
      `/drivers${qs({ season })}`,
    ),
  compareDrivers: (a: string, b: string, seasons?: number[], circuitId?: number) =>
    request<HeadToHead>(`/drivers/compare${qs({ a, b, seasons, circuit_id: circuitId })}`),
  driverCircuits: (ref: string) =>
    request<
      Array<{
        circuit_id: number
        circuit: string
        country: string | null
        starts: number
        wins: number
        podiums: number
        avg_finish: number | null
        avg_grid: number | null
        podium_rate: number
        points: number
      }>
    >(`/drivers/${encodeURIComponent(ref)}/circuits`),

  constructors: () =>
    request<Array<{ id: number; ref: string; name: string; color: string }>>('/constructors'),

  circuits: () =>
    request<
      Array<{
        id: number
        ref: string
        name: string
        country: string | null
        locality: string | null
        circuit_type: string | null
        tyre_degradation: string | null
        overtaking_difficulty: string | null
      }>
    >('/circuits'),
  circuit: (ref: string, seasons?: number[]) =>
    request<CircuitHistory>(`/circuits/${encodeURIComponent(ref)}${qs({ seasons })}`),

  modelInfo: () => request<ModelInfo>('/predictions/model'),
  nextPredictions: () => request<RacePrediction>('/predictions/next'),
  racePredictions: (raceId: number) => request<RacePrediction>(`/predictions/race/${raceId}`),
  scenario: (raceId: number, driverId: number, grid: number) =>
    request<ScenarioResult>('/predictions/scenario', {
      method: 'POST',
      body: JSON.stringify({ race_id: raceId, driver_id: driverId, grid }),
    }),

  chatSuggestions: () => request<{ questions: string[] }>('/chat/suggestions'),
  ask: (question: string, sessionId?: string, raceId?: number) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ question, session_id: sessionId, race_id: raceId }),
    }),

  feedback: (body: {
    surface: string
    rating: 'helpful' | 'unhelpful'
    reference_id?: string
    reason?: string
    comment?: string
    context?: Record<string, unknown>
  }) => request<{ id: number }>('/feedback', { method: 'POST', body: JSON.stringify(body) }),
  feedbackStats: () =>
    request<{
      total: number
      helpful: number
      unhelpful: number
      helpful_rate: number | null
      by_surface: Record<string, Record<string, number>>
      top_reasons: Array<{ reason: string; count: number }>
    }>('/feedback/stats'),

  register: (email: string, password: string, displayName?: string) =>
    request<{ access_token: string; user: { id: number; email: string; display_name: string } }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, display_name: displayName }) },
    ),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: { id: number; email: string; display_name: string } }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    ),
  me: () => request<{ id: number; email: string; display_name: string }>('/auth/me'),

  savedComparisons: () =>
    request<
      Array<{
        id: number
        label: string
        kind: string
        payload: Record<string, unknown>
        created_at: string
      }>
    >('/saved'),
  saveComparison: (label: string, kind: 'driver' | 'constructor', payload: Record<string, unknown>) =>
    request<{ id: number }>('/saved', {
      method: 'POST',
      body: JSON.stringify({ label, kind, payload }),
    }),
  deleteSavedComparison: (id: number) =>
    request<void>(`/saved/${id}`, { method: 'DELETE' }),
}
