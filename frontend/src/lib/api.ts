const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api/v1`

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(body.detail ?? `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export function qs(params: Record<string, string | number | boolean | null | undefined | string[]>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x))
    else sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

const cache = new Map<string, Promise<unknown>>()

export const api = {
  get: <T>(path: string): Promise<T> => {
    if (!cache.has(path)) cache.set(path, request<T>(path).catch((e) => { cache.delete(path); throw e }))
    return cache.get(path) as Promise<T>
  },
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  url: (path: string) => BASE + path,
}

export type Season = 'A' | 'B' | 'C'

export interface IndicatorDef {
  id: string
  name: string
  unit: string
  topic: string
  source: string
  description: string
  higher_is_better: boolean
  crop_specific: boolean
}

export interface Filters {
  years: number[]
  seasons: Season[]
  crops: string[]
  provinces: string[]
  districts: string[]
  latest: { year: number; season: Season }
}

export interface Kpi {
  indicator_id: string
  name: string
  unit: string
  value: number | null
  previous_value: number | null
  change: number | null
  period: string
}

export interface Overview {
  year: number
  season: Season
  coverage: { plot_crop_records: number; households: number; districts: number; crops: number }
  kpis: Kpi[]
  crops: { crop: string; yield_kg_ha: number; previous_yield_kg_ha: number | null; yield_change_pct: number | null; production_t: number | null }[]
}

export interface Insight {
  id: string
  topic: string
  title: string
  summary: string
  chart: 'bar' | 'map' | 'scatter'
  evidence: Record<string, unknown>[]
  action: string
  period: string
}

export interface DistrictValue {
  area: string
  province: string
  value: number
  n: number
  low_reliability: boolean
  rank: number
}

export interface DistrictComparison {
  indicator: IndicatorDef
  year: number | null
  season: Season | null
  crop: string
  national_value: number | null
  districts: DistrictValue[]
}

export interface SeasonSeries {
  indicator: IndicatorDef
  crop: string
  area: string
  series: { period: string; year: number; season: Season; value: number; n: number; low_reliability: boolean }[]
}

export interface InputEffect {
  input: string
  input_label: string
  yield_with: number
  yield_without: number
  premium_pct: number
  n_with: number
  n_without: number
}

export interface DistrictProfile {
  district: string
  province: string
  year: number
  season: Season
  indicators: {
    indicator_id: string; name: string; unit: string; crop: string | null; value: number; national_value: number | null
    difference: number | null; rank: number | null; of: number; higher_is_better: boolean
  }[]
  crop_yields: { crop: string; value: number; national_value: number; vs_national_pct: number; n: number }[]
}

export interface PriorityDistrict {
  district: string
  province: string
  rank: number
  score: number
  yield_kg_ha: number
  production_t: number | null
  improved_seed_pct: number | null
  inorganic_fertilizer_pct: number | null
  extension_access_pct: number | null
  potential_gain_pct: number | null
  additional_production_t: number | null
  yield_gap: number | null
}

export interface Priorities {
  year: number
  season: Season
  crop: string
  benchmark_yield_kg_ha: number | null
  weights: Record<string, number>
  components: { id: string; label: string; weight: number }[]
  method: string
  districts: PriorityDistrict[]
}

export interface ScenarioOptions {
  year: number
  seasons: Season[]
  crops: string[]
  districts: string[]
  inputs: { id: string; label: string }[]
  model: { r2_log_yield: number; mape_yield: number; train_rows: number; test_rows: number; model: string; features: string[] }
}

export interface ScenarioResult {
  crop: string
  district: string
  season: Season
  year: number
  inputs: string[]
  current_yield: number
  scenario_yield: number
  change_pct: number
  current_adoption_pct: Record<string, number>
  single_input_effects: { input: string; predicted_yield: number; change_pct: number }[]
  n_plots: number
  note: string
}

export interface AskResponse {
  question: string
  answer: string
  parsed: { intent: string; indicator_id: string; crop: string | null; district: string | null; year: number; season: Season }
  data: unknown
  ai: boolean
}

export interface AskStatus {
  ai_enabled: boolean
  model: string | null
}

export interface GeoFeatureProps {
  district: string
  province: string
  value: number | null
  n: number | null
  low_reliability: boolean | null
}
