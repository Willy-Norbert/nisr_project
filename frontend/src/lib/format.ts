export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function compact(v: number | null | undefined): string {
  if (v === null || v === undefined) return '–'
  return Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(v)
}

export function signed(v: number | null | undefined, digits = 1, suffix = '%'): string {
  if (v === null || v === undefined) return '–'
  return `${v > 0 ? '+' : ''}${v.toFixed(digits)}${suffix}`
}

export function valueWithUnit(v: number | null | undefined, unit: string): string {
  if (unit.startsWith('%')) return `${num(v, 1)}%`
  if (unit === 'kg/ha') return `${num(v)} kg/ha`
  if (unit === 'tonnes') return `${compact(v)} t`
  return `${num(v, 1)} ${unit}`
}

export function decimals(unit: string): number {
  return unit.startsWith('%') ? 1 : 0
}

export const INPUT_LABELS: Record<string, string> = {
  improved_seed: 'Improved seed',
  inorganic_fertilizer: 'Inorganic fertilizer',
  organic_fertilizer: 'Organic fertilizer',
  irrigated: 'Irrigation',
}
