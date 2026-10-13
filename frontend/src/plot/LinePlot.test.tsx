import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LinePlot } from './LinePlot'

function setup() {
  render(<LinePlot x={[0, 1, 2]} y={[10, 20, 15]} xLabel="E (meV)" yLabel="counts" title="Run 1" />)
  const svg = screen.getByRole('img', { name: 'Run 1: counts against E (meV)' })
  // jsdom has no layout, so give the SVG a size: 720 px wide, like its viewBox.
  svg.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 720, height: 320, right: 720, bottom: 320 }) as DOMRect
  return svg.querySelector('rect.hit')!
}

describe('LinePlot', () => {
  it('reads out the nearest point under the pointer', () => {
    const hit = setup()
    fireEvent.pointerMove(hit, { clientX: 700, clientY: 100 }) // right edge: x = 2
    expect(screen.getByText('E (meV): 2 · counts: 15')).toBeInTheDocument()

    fireEvent.pointerMove(hit, { clientX: 64, clientY: 100 }) // left edge: x = 0
    expect(screen.getByText('E (meV): 0 · counts: 10')).toBeInTheDocument()
  })

  it('clears the readout when the pointer leaves', () => {
    const hit = setup()
    fireEvent.pointerMove(hit, { clientX: 400, clientY: 100 })
    fireEvent.pointerLeave(hit)
    expect(screen.getByText('Move the pointer over the plot to read values.')).toBeInTheDocument()
  })

  it('explains when there is nothing to plot', () => {
    render(<LinePlot x={[0, 1]} y={[null, null]} xLabel="x" yLabel="y" title="Empty" />)
    expect(screen.getByText('The signal has no finite values to plot.')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('shows gaps as dashes in the data table', () => {
    render(<LinePlot x={[0, 1]} y={[5, null]} xLabel="x" yLabel="y" title="Gap" />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
