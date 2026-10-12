import type { SearchParams } from './api/types'

/** What the filter form holds: everything is a string, as typed by the user. */
export interface FilterForm {
  q: string
  instrument: string
  technique: string
  tempMin: string
  tempMax: string
  dateFrom: string // YYYY-MM-DD
  dateTo: string // YYYY-MM-DD, inclusive
}

export const EMPTY_FORM: FilterForm = {
  q: '',
  instrument: '',
  technique: '',
  tempMin: '',
  tempMax: '',
  dateFrom: '',
  dateTo: '',
}

function number(value: string): number | undefined {
  return value.trim() === '' ? undefined : Number(value)
}

function nextDay(date: string): string {
  const d = new Date(`${date}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

/**
 * Convert the form to API parameters. Dates are whole days in UTC, and the
 * "to" date is inclusive, so it becomes "before the start of the next day".
 * Values are not checked here: the API validates them and explains any problem.
 */
export function toSearchParams(form: FilterForm): SearchParams {
  return {
    q: form.q.trim() || undefined,
    instrument: form.instrument || undefined,
    technique: form.technique || undefined,
    temp_min: number(form.tempMin),
    temp_max: number(form.tempMax),
    start_after: form.dateFrom ? `${form.dateFrom}T00:00:00Z` : undefined,
    start_before: form.dateTo ? `${nextDay(form.dateTo)}T00:00:00Z` : undefined,
  }
}
