import { screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { renderAt } from './test/render'

it('shows the title and the personal-project notice', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))) // requests never finish
  renderAt('/')
  expect(screen.getByRole('heading', { name: 'nxcat' })).toBeInTheDocument()
  expect(screen.getByText(/not production software/)).toBeInTheDocument()
})

it('shows "Page not found" for an unknown address', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  renderAt('/nowhere')
  expect(screen.getByText('Page not found.')).toBeInTheDocument()
})
