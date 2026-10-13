import { describe, expect, it } from 'vitest'
import {
  formatBytes,
  formatDuration,
  formatNumber,
  formatTemperature,
  formatTime,
  formatWithError,
} from './format'

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

describe('formatNumber', () => {
  it.each([
    [0, '0'],
    [1234.5678, '1,235'],
    [0.12345, '0.1235'],
    [-2.5, '-2.5'],
    [12345678, '1.235e+7'],
    [0.0001234, '1.234e-4'],
    [2e6, '2e+6'],
  ])('%s -> %s', (value, text) => {
    expect(formatNumber(value)).toBe(text)
  })
})

describe('formatWithError', () => {
  it.each([
    [0.210804, 0.00089, '0.21080 ± 0.00089'],
    [0.1491, 0.0012, '0.1491 ± 0.0012'],
    [123.456, 12.3, '123 ± 12'],
    [5, 0, '5 ± 0'],
    [5, Number.NaN, '5 ± NaN'],
  ])('%s, %s -> %s', (value, error, text) => {
    expect(formatWithError(value, error)).toBe(text)
  })
})

describe('formatBytes', () => {
  it.each([
    [512, '512 B'],
    [16904, '16.5 KB'],
    [5 * 1024 ** 3, '5.0 GB'],
  ])('%s -> %s', (bytes, text) => {
    expect(formatBytes(bytes)).toBe(text)
  })
})

describe('formatDuration', () => {
  it('shows hours and minutes', () => {
    expect(formatDuration('2025-03-01T10:00:00Z', '2025-03-01T12:15:00Z')).toBe('2 h 15 min')
    expect(formatDuration('2025-03-01T10:00:00Z', '2025-03-01T10:40:00Z')).toBe('40 min')
  })

  it('is empty when the end is missing or before the start', () => {
    expect(formatDuration('2025-03-01T10:00:00Z', null)).toBeNull()
    expect(formatDuration('2025-03-01T10:00:00Z', '2025-03-01T09:00:00Z')).toBeNull()
  })
})
