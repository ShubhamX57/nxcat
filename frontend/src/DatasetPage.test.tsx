import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Preview } from './api/types'
import { FACETS, calls, dataset, fakeApi, json } from './test/fakeApi'
import { renderAt } from './test/render'

const PREVIEW: Preview = {
  dataset_id: 5,
  x: [-1, 0, 1],
  y: [10, 250, 12],
  x_label: 'energy_transfer (meV)',
  y_label: 'counts',
  original_points: 3,
  downsampled: false,
}

const DETAIL = dataset(5, {
  title: 'Benzene QENS 260 K',
  sample_name: 'benzene',
  sample_temperature_k: 260,
  start_time: '2025-03-01T10:00:00Z',
  end_time: '2025-03-01T12:15:00Z',
  proposal_id: '2512345',
  file_size_bytes: 16904,
  checksum: 'ab'.repeat(32),
})

function api(overrides: Record<string, () => Response> = {}) {
  return fakeApi((url) => {
    const reply = overrides[url.pathname]
    if (reply) return reply()
    if (url.pathname === '/api/v1/datasets/5') return json(DETAIL)
    if (url.pathname === '/api/v1/datasets/5/preview') return json(PREVIEW)
    if (url.pathname === '/api/v1/facets') return json(FACETS)
    if (url.pathname === '/api/v1/datasets') {
      return json({ items: [DETAIL], total: 1, page: 1, size: 20 })
    }
    return json({ detail: `dataset ${url.pathname.split('/').pop()} not found` }, 404)
  })
}

describe('DatasetPage', () => {
  it('shows the metadata', async () => {
    api()
    renderAt('/datasets/5')
    expect(await screen.findByRole('heading', { name: 'Benzene QENS 260 K' })).toBeInTheDocument()

    const meta = screen.getByRole('heading', { name: 'Metadata' }).parentElement!
    expect(within(meta).getByText('benzene')).toBeInTheDocument()
    expect(within(meta).getByText('260 K')).toBeInTheDocument()
    expect(within(meta).getByText('2025-03-01 12:15 UTC')).toBeInTheDocument()
    expect(within(meta).getByText('2 h 15 min')).toBeInTheDocument()
    expect(within(meta).getByText('16.5 KB')).toBeInTheDocument()
    expect(within(meta).getByText('ab'.repeat(32))).toBeInTheDocument()
  })

  it('draws the quick-look plot with labelled axes', async () => {
    api()
    renderAt('/datasets/5')
    const plot = await screen.findByRole('img', {
      name: 'Benzene QENS 260 K: counts against energy_transfer (meV)',
    })
    expect(within(plot).getByText('energy_transfer (meV)')).toBeInTheDocument()
    expect(plot.querySelector('path.series')?.getAttribute('d')).toMatch(/^M.+L.+L/)
  })

  it('offers the plotted values as a table', async () => {
    api()
    renderAt('/datasets/5')
    await screen.findByRole('img', { name: /counts against/ })
    const table = screen.getByText('Show data as a table (3 rows)').closest('details')!
    expect(within(table).getAllByRole('row')).toHaveLength(4) // header + 3
    expect(within(table).getByText('250')).toBeInTheDocument()
  })

  it('says when the plot shows averaged points', async () => {
    api({
      '/api/v1/datasets/5/preview': () =>
        json({ ...PREVIEW, original_points: 30000, downsampled: true }),
    })
    renderAt('/datasets/5')
    expect(await screen.findByText('Showing 3 averaged points of 30000.')).toBeInTheDocument()
  })

  it('still shows the metadata when the plot fails', async () => {
    api({
      '/api/v1/datasets/5/preview': () =>
        json({ detail: 'no preview: no NXdata group to plot' }, 422),
    })
    renderAt('/datasets/5')
    expect(await screen.findByRole('alert')).toHaveTextContent('no preview: no NXdata group to plot')
    expect(screen.getByText('benzene')).toBeInTheDocument()
  })

  it('reports a dataset that does not exist', async () => {
    api()
    renderAt('/datasets/999')
    expect(await screen.findByText('Dataset 999 does not exist.')).toBeInTheDocument()
  })

  it('rejects an address that is not a dataset id', () => {
    const fetch = api()
    renderAt('/datasets/abc')
    expect(screen.getByText('This is not a valid dataset address.')).toBeInTheDocument()
    expect(calls(fetch, '/api/v1/datasets/abc')).toHaveLength(0)
  })

  it('reports other errors', async () => {
    api({ '/api/v1/datasets/5': () => json({ detail: 'the database is unavailable' }, 503) })
    renderAt('/datasets/5')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load dataset 5: the database is unavailable',
    )
  })

  it('goes from a search result to the dataset and back to the same search', async () => {
    const user = userEvent.setup()
    api()
    renderAt('/?q=benzene')
    await user.click(await screen.findByRole('link', { name: 'Benzene QENS 260 K' }))
    expect(screen.getByTestId('address')).toHaveTextContent('/datasets/5')
    await screen.findByRole('heading', { name: 'Metadata' })

    await user.click(screen.getByRole('link', { name: '← Back to search' }))
    expect(screen.getByTestId('address')).toHaveTextContent('/?q=benzene')
    expect(await screen.findByRole('searchbox', { name: 'Search' })).toHaveValue('benzene')
  })
})
