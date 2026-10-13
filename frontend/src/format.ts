/** "2025-03-01T10:00:00Z" -> "2025-03-01 10:00 UTC" */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

export function formatTemperature(kelvin: number | null): string {
  return kelvin === null ? '—' : `${Number(kelvin.toFixed(1))} K`
}

const significant = new Intl.NumberFormat('en-GB', { maximumSignificantDigits: 4 })

/** Short, readable numbers for axes and tooltips: 0.1235, 1,234, 1.235e+7 */
export function formatNumber(value: number): string {
  if (value !== 0 && (Math.abs(value) >= 1e6 || Math.abs(value) < 1e-3)) {
    return value.toExponential(3).replace(/\.?0+e/, 'e')
  }
  return significant.format(value)
}

/**
 * A measured value and its uncertainty, rounded together: the error to two
 * significant figures, and the value to the same decimal place.
 * (0.210804, 0.00089) -> "0.21080 ± 0.00089"
 */
export function formatWithError(value: number, error: number): string {
  if (!Number.isFinite(error) || error <= 0) {
    return `${formatNumber(value)} ± ${formatNumber(error)}`
  }
  const decimals = Math.min(12, Math.max(0, 1 - Math.floor(Math.log10(error))))
  return `${value.toFixed(decimals)} ± ${error.toFixed(decimals)}`
}

export function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`
}

/** "2 h 15 min" between two ISO times, or null if either is missing. */
export function formatDuration(startIso: string, endIso: string | null): string | null {
  if (endIso === null) return null
  const minutes = Math.round((Date.parse(endIso) - Date.parse(startIso)) / 60000)
  if (!Number.isFinite(minutes) || minutes < 0) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}
