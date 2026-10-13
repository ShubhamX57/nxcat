/** Small helpers for drawing a chart without a chart library. */

export interface Extent {
  min: number
  max: number
}

/** Smallest and largest finite value, or null if there are none. */
export function extent(values: (number | null)[]): Extent | null {
  let min = Infinity
  let max = -Infinity
  for (const v of values) {
    if (v === null || !Number.isFinite(v)) continue
    if (v < min) min = v
    if (v > max) max = v
  }
  if (min === Infinity) return null
  if (min === max) return { min: min - 1, max: max + 1 } // flat line: give it room
  return { min, max }
}

/**
 * "Nice" tick values covering [min, max]: steps of 1, 2 or 5 times a power of 10,
 * so axes read 0, 50, 100 rather than 0, 47.3, 94.6.
 */
export function niceTicks(min: number, max: number, target = 5): number[] {
  const span = max - min
  if (!(span > 0) || !Number.isFinite(span)) return [min]
  const rough = span / target
  const power = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough) ?? 10 * power
  const ticks: number[] = []
  for (let t = Math.ceil(min / step) * step; t <= max + step * 1e-9; t += step) {
    ticks.push(Math.abs(t) < step * 1e-9 ? 0 : Number(t.toPrecision(12)))
  }
  return ticks
}

/** A linear map from data values [d0, d1] to pixels [r0, r1]. */
export function linear(d0: number, d1: number, r0: number, r1: number) {
  return (v: number) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0)
}

/** SVG path for the points, with a gap wherever x or y is null. */
export function linePath(
  xs: (number | null)[],
  ys: (number | null)[],
  sx: (v: number) => number,
  sy: (v: number) => number,
): string {
  let d = ''
  let penDown = false
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i]
    const y = ys[i]
    if (x === null || y === null) {
      penDown = false
      continue
    }
    d += `${penDown ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`
    penDown = true
  }
  return d
}

/** Index of the point whose x is closest to `target` (ignoring gaps), or -1. */
export function nearestIndex(xs: (number | null)[], ys: (number | null)[], target: number): number {
  let best = -1
  let bestDistance = Infinity
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i]
    if (x === null || ys[i] === null) continue
    const distance = Math.abs(x - target)
    if (distance < bestDistance) {
      best = i
      bestDistance = distance
    }
  }
  return best
}
