import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import App from './App'

it('shows the title and the personal-project notice', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))) // requests never finish
  render(<App />)
  expect(screen.getByRole('heading', { name: 'nxcat' })).toBeInTheDocument()
  expect(screen.getByText(/not production software/)).toBeInTheDocument()
})
