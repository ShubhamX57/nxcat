import { useId, useState, type PointerEvent } from 'react'
import { formatNumber } from '../format'
import { extent, linear, linePath, nearestIndex, niceTicks } from './scale'

interface Props {
  x: (number | null)[]
  y: (number | null)[]
  xLabel: string
  yLabel: string
  title: string
}

// Drawing area in SVG units; the SVG scales to the width of its container.
const WIDTH = 720
const HEIGHT = 320
const M = { top: 16, right: 20, bottom: 48, left: 64 }

export function LinePlot({ x, y, xLabel, yLabel, title }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const titleId = useId()
  const xe = extent(x)
  const ye = extent(y)

  if (xe === null || ye === null) {
    return <p className="status">The signal has no finite values to plot.</p>
  }

  const yMin = Math.min(0, ye.min) // counts start at zero; negative data still fits
  const xTicks = niceTicks(xe.min, xe.max)
  const yTicks = niceTicks(yMin, ye.max)
  const yTop = Math.max(ye.max, yTicks.at(-1) ?? ye.max)
  const sx = linear(xe.min, xe.max, M.left, WIDTH - M.right)
  const sy = linear(yMin, yTop, HEIGHT - M.bottom, M.top)
  const invertX = linear(M.left, WIDTH - M.right, xe.min, xe.max)

  function handleMove(event: PointerEvent<SVGRectElement>) {
    const box = event.currentTarget.ownerSVGElement?.getBoundingClientRect()
    if (!box || box.width === 0) return
    const svgX = ((event.clientX - box.left) / box.width) * WIDTH
    const index = nearestIndex(x, y, invertX(svgX))
    setHover(index >= 0 ? index : null)
  }

  const hx = hover === null ? null : x[hover]
  const hy = hover === null ? null : y[hover]

  return (
    <figure className="plot">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby={titleId}
        className="plot-svg"
      >
        <title id={titleId}>{`${title}: ${yLabel} against ${xLabel}`}</title>

        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line className="grid" x1={M.left} x2={WIDTH - M.right} y1={sy(t)} y2={sy(t)} />
            <text className="tick" x={M.left - 8} y={sy(t)} textAnchor="end" dominantBaseline="middle">
              {formatNumber(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={`x${t}`} className="tick" x={sx(t)} y={HEIGHT - M.bottom + 18} textAnchor="middle">
            {formatNumber(t)}
          </text>
        ))}
        <line className="axis" x1={M.left} x2={WIDTH - M.right} y1={HEIGHT - M.bottom} y2={HEIGHT - M.bottom} />

        <text className="axis-label" x={(M.left + WIDTH - M.right) / 2} y={HEIGHT - 8} textAnchor="middle">
          {xLabel}
        </text>
        <text
          className="axis-label"
          transform={`translate(16 ${(M.top + HEIGHT - M.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>

        <path className="series" d={linePath(x, y, sx, sy)} />

        {hx !== null && hy !== null && (
          <g className="hover" aria-hidden="true">
            <line className="crosshair" x1={sx(hx)} x2={sx(hx)} y1={M.top} y2={HEIGHT - M.bottom} />
            <circle cx={sx(hx)} cy={sy(hy)} r={4.5} />
          </g>
        )}

        {/* Invisible layer larger than the line, so the pointer is easy to track. */}
        <rect
          className="hit"
          x={M.left}
          y={M.top}
          width={WIDTH - M.left - M.right}
          height={HEIGHT - M.top - M.bottom}
          onPointerMove={handleMove}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      <figcaption className="readout" aria-live="polite">
        {hx !== null && hy !== null
          ? `${xLabel}: ${formatNumber(hx)} · ${yLabel}: ${formatNumber(hy)}`
          : 'Move the pointer over the plot to read values.'}
      </figcaption>

      <details className="data-table">
        <summary>Show data as a table ({x.length} rows)</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col" className="num">
                  {xLabel}
                </th>
                <th scope="col" className="num">
                  {yLabel}
                </th>
              </tr>
            </thead>
            <tbody>
              {x.map((xv, i) => (
                <tr key={i}>
                  <td className="num">{xv === null ? '—' : formatNumber(xv)}</td>
                  <td className="num">{y[i] === null ? '—' : formatNumber(y[i] as number)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}
