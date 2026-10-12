import { describe, expect, it } from 'vitest'
import { formatTemperature, formatTime } from './format'

describe('formatTime', () => {
  it('shows UTC to the minute', () => {
    expect(formatTime('2025-03-01T10:05:59Z')).toBe('2025-03-01 10:05 UTC')
  })

  it('converts other time zones to UTC', () => {
    expect(formatTime('2025-03-01T10:00:00+01:00')).toBe('2025-03-01 09:00 UTC')
  })

  it('returns unparseable input unchanged', () => {
    expect(formatTime('not a date')).toBe('not a date')
  })
})

describe('formatTemperature', () => {
  it('rounds to one decimal place', () => {
    expect(formatTemperature(260.04)).toBe('260 K')
    expect(formatTemperature(1.55)).toBe('1.6 K')
  })

  it('shows a dash when unknown', () => {
    expect(formatTemperature(null)).toBe('—')
  })
})
