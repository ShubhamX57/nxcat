import { describe, expect, it } from 'vitest'
import { EMPTY_FORM, formFromUrl, formToUrl, pageFromUrl, toSearchParams } from './filters'

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
