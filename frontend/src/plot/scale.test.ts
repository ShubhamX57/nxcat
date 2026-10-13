import { describe, expect, it } from 'vitest'
import { extent, linePath, linear, nearestIndex, niceTicks } from './scale'

describe('extent', () => {
  it('ignores gaps and non-finite values', () => {
    expect(extent([3, null, -2, Infinity, 7])).toEqual({ min: -2, max: 7 })
  })

  it('returns null when nothing can be plotted', () => {
    expect(extent([null, NaN])).toBeNull()
  })

  it('widens a flat line so it can be drawn', () => {
    expect(extent([5, 5])).toEqual({ min: 4, max: 6 })
  })
})

describe('niceTicks', () => {
  it.each([
    [0, 100, [0, 20, 40, 60, 80, 100]],
    [0, 437, [0, 100, 200, 300, 400]],
    [-1, 1, [-1, -0.5, 0, 0.5, 1]],
    [0.001, 0.0042, [0.001, 0.002, 0.003, 0.004]],
  ])('covers %s to %s with round steps', (min, max, ticks) => {
    expect(niceTicks(min, max)).toEqual(ticks)
  })

  it('never returns a "negative zero" or rounding noise', () => {
    const ticks = niceTicks(-0.3, 0.3)
    expect(ticks).toContain(0)
    expect(ticks.every((t) => String(t).length < 6)).toBe(true)
  })

  it('handles an empty range', () => {
    expect(niceTicks(4, 4)).toEqual([4])
  })
})

describe('linePath', () => {
  const same = (v: number) => v

  it('draws one stroke through the points', () => {
    expect(linePath([0, 1, 2], [5, 6, 7], same, same)).toBe('M0.0,5.0L1.0,6.0L2.0,7.0')
  })

  it('lifts the pen at a gap', () => {
    expect(linePath([0, 1, 2, 3], [5, null, 7, 8], same, same)).toBe('M0.0,5.0M2.0,7.0L3.0,8.0')
  })
})

describe('linear and nearestIndex', () => {
  it('maps data to pixels, including flipped ranges', () => {
    const sy = linear(0, 100, 300, 0)
    expect(sy(0)).toBe(300)
    expect(sy(25)).toBe(225)
  })

  it('finds the closest point and skips gaps', () => {
    expect(nearestIndex([0, 1, 2, 3], [1, null, 1, 1], 1.1)).toBe(2) // x = 1 is a gap; 2 is closer than 0
    expect(nearestIndex([0, 1, 2, 3], [1, 1, 1, 1], 2.6)).toBe(3)
    expect(nearestIndex([0, 1], [null, null], 0)).toBe(-1)
  })
})
