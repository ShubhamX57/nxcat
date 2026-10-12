/** "2025-03-01T10:00:00Z" -> "2025-03-01 10:00 UTC" */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

export function formatTemperature(kelvin: number | null): string {
  return kelvin === null ? '—' : `${Number(kelvin.toFixed(1))} K`
}
