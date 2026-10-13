import { describe, expect, it } from 'vitest'
import {
  EMPTY_FORM,
  formFromFilters,
  formFromUrl,
  formToUrl,
  pageFromUrl,
  toSearchParams,
} from './filters'

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

describe('filters in the address', () => {
  it('round-trips through the URL, leaving out empty fields', () => {
    const form = { ...EMPTY_FORM, q: 'benzene', tempMin: '200', dateTo: '2025-02-28' }
    const url = formToUrl(form, 3)
    expect(url.toString()).toBe('q=benzene&temp_min=200&to=2025-02-28&page=3')
    expect(formFromUrl(url)).toEqual(form)
  })

  it('does not write page 1', () => {
    expect(formToUrl(EMPTY_FORM, 1).toString()).toBe('')
  })

  it.each([
    ['page=4', 4],
    ['', 1],
    ['page=0', 1],
    ['page=-2', 1],
    ['page=2.5', 1],
    ['page=abc', 1],
  ])('reads "%s" as page %s', (query, page) => {
    expect(pageFromUrl(new URLSearchParams(query))).toBe(page)
  })
})

describe('formFromFilters', () => {
  it('turns an API filter into the form, with an inclusive "to" date', () => {
    expect(
      formFromFilters({
        q: 'water',
        technique: 'QENS',
        temp_max: 100,
        start_after: '2025-03-01T00:00:00Z',
        start_before: '2025-04-01T00:00:00Z',
      }),
    ).toEqual({
      ...EMPTY_FORM,
      q: 'water',
      technique: 'QENS',
      tempMax: '100',
      dateFrom: '2025-03-01',
      dateTo: '2025-03-31',
    })
  })

  it('round-trips through toSearchParams', () => {
    const filters = { instrument: 'LET', start_after: '2025-01-01T00:00:00Z', start_before: '2026-01-01T00:00:00Z' }
    const params = toSearchParams(formFromFilters(filters))
    expect(params.instrument).toBe('LET')
    expect(params.start_after).toBe(filters.start_after)
    expect(params.start_before).toBe(filters.start_before)
  })
})
