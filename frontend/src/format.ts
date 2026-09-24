// Money + date formatting helpers. Amounts live as integer cents; inputs are
// dollar strings converted with rounding to avoid float drift.

export function centsToStr(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

export function strToCents(value: string): number | null {
  const n = Number.parseFloat(value)
  if (!Number.isFinite(n) || n < 0) return null
  return Math.round(n * 100)
}

export function currentMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function monthLabel(month: string): string {
  const [y, m] = month.split('-').map(Number)
  return `${MONTH_NAMES[m - 1]} ${y}`
}

/** Split total cents evenly across n members; earlier members absorb the remainder. */
export function evenSplit(totalCents: number, n: number): number[] {
  const base = Math.floor(totalCents / n)
  return Array.from({ length: n }, (_, i) => base + (i < totalCents - base * n ? 1 : 0))
}
