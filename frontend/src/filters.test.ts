import { describe, expect, it } from 'vitest'
import { EMPTY_FORM, toSearchParams } from './filters'

describe('toSearchParams', () => {
  it('turns an empty form into no filters', () => {
    expect(Object.values(toSearchParams(EMPTY_FORM)).every((v) => v === undefined)).toBe(true)
  })

  it('trims text and converts numbers', () => {
    const params = toSearchParams({ ...EMPTY_FORM, q: '  benzene ', tempMin: '250', tempMax: '0' })
    expect(params.q).toBe('benzene')
    expect(params.temp_min).toBe(250)
    expect(params.temp_max).toBe(0)
  })

  it('makes the "to" date inclusive, in UTC', () => {
    const params = toSearchParams({ ...EMPTY_FORM, dateFrom: '2025-01-31', dateTo: '2025-02-28' })
    expect(params.start_after).toBe('2025-01-31T00:00:00Z')
    expect(params.start_before).toBe('2025-03-01T00:00:00Z')
  })

  it('handles the end of a year', () => {
    expect(toSearchParams({ ...EMPTY_FORM, dateTo: '2025-12-31' }).start_before).toBe(
      '2026-01-01T00:00:00Z',
    )
  })
})
