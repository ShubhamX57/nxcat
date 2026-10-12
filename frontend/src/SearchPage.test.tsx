import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Dataset, DatasetPage, Facets } from './api/types'
import { PAGE_SIZE, SearchPage } from './SearchPage'

const FACETS: Facets = {
  instrument: [
    { value: 'LET', count: 2 },
    { value: 'MARI', count: 1 },
  ],
  technique: [
    { value: 'QENS', count: 2 },
    { value: 'INS', count: 1 },
  ],
}

function dataset(id: number, overrides: Partial<Dataset> = {}): Dataset {
  return {
    id,
    title: `Run ${id}`,
    instrument: 'LET',
    technique: 'QENS',
    run_number: 1000 + id,
    sample_name: 'water',
    sample_temperature_k: 300,
    start_time: '2025-03-01T10:00:00Z',
    end_time: null,
    facility: 'ISIS',
    proposal_id: null,
    file_path: `/data/${id}.nxs`,
    file_size_bytes: 1000,
    checksum: '0'.repeat(64),
    schema_version: '1',
    ingested_at: '2025-03-02T00:00:00Z',
    ...overrides,
  }
}

function page(items: Dataset[], total = items.length, pageNumber = 1): DatasetPage {
  return { items, total, page: pageNumber, size: PAGE_SIZE }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** A fake API: facets always succeed; search answers with `searchReply(url)`. */
function fakeApi(searchReply: (url: URL) => Response) {
  const fetch = vi.fn(async (input: string) => {
    const url = new URL(input, 'http://test')
    if (url.pathname === '/api/v1/facets') return json(FACETS)
    return searchReply(url)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function searchCalls(fetch: ReturnType<typeof fakeApi>): URL[] {
  return fetch.mock.calls
    .map(([input]) => new URL(input, 'http://test'))
    .filter((url) => url.pathname === '/api/v1/datasets')
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads and shows datasets', async () => {
    fakeApi(() => json(page([dataset(1, { title: 'Benzene QENS 260 K', sample_temperature_k: 260 })])))
    render(<SearchPage />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
    const table = await screen.findByRole('table')
    const row = within(table).getAllByRole('row')[1]
    expect(row).toHaveTextContent('Benzene QENS 260 K')
    expect(row).toHaveTextContent('260 K')
    expect(row).toHaveTextContent('2025-03-01 10:00 UTC')
    expect(screen.getByText('Showing 1–1 of 1 datasets')).toBeInTheDocument()
  })

  it('fills the filter menus from the facets, with counts', async () => {
    fakeApi(() => json(page([])))
    render(<SearchPage />)
    expect(await screen.findByRole('option', { name: 'LET (2)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'INS (1)' })).toBeInTheDocument()
  })

  it('sends the chosen filters when Search is pressed', async () => {
    const user = userEvent.setup()
    const fetch = fakeApi(() => json(page([dataset(1)])))
    render(<SearchPage />)
    await screen.findByRole('option', { name: 'MARI (1)' })

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'benzene')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Instrument' }), 'MARI')
    await user.type(screen.getByRole('spinbutton', { name: 'Minimum temperature (K)' }), '250')
    expect(searchCalls(fetch)).toHaveLength(1) // nothing sent until Search is pressed

    await user.click(screen.getByRole('button', { name: 'Search' }))

    const last = searchCalls(fetch).at(-1)!
    expect(last.searchParams.get('q')).toBe('benzene')
    expect(last.searchParams.get('instrument')).toBe('MARI')
    expect(last.searchParams.get('temp_min')).toBe('250')
    expect(last.searchParams.get('page')).toBe('1')
  })

  it('shows a message when nothing matches', async () => {
    fakeApi(() => json(page([])))
    render(<SearchPage />)
    expect(await screen.findByText('No datasets match these filters.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows the API reason when the filters are invalid', async () => {
    const user = userEvent.setup()
    fakeApi((url) =>
      url.searchParams.has('temp_min')
        ? json({ detail: [{ msg: 'Value error, temp_min must not be greater than temp_max' }] }, 422)
        : json(page([dataset(1)])),
    )
    render(<SearchPage />)
    await screen.findByRole('table')

    await user.type(screen.getByRole('spinbutton', { name: 'Minimum temperature (K)' }), '300')
    await user.type(screen.getByRole('spinbutton', { name: 'Maximum temperature (K)' }), '10')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load datasets: temp_min must not be greater than temp_max',
    )
  })

  it('shows an error when the API cannot be reached', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string) =>
        input.endsWith('/facets') ? json(FACETS) : Promise.reject(new TypeError('Failed to fetch')),
      ),
    )
    render(<SearchPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch')
  })

  it('moves between pages', async () => {
    const user = userEvent.setup()
    const fetch = fakeApi((url) => {
      const n = Number(url.searchParams.get('page') ?? 1)
      return json(page([dataset(n)], 45, n))
    })
    render(<SearchPage />)
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getByText('Showing 21–21 of 45 datasets')).toBeInTheDocument()
    expect(searchCalls(fetch).at(-1)!.searchParams.get('page')).toBe('2')

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 3 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('Reset clears the filters and searches again', async () => {
    const user = userEvent.setup()
    const fetch = fakeApi(() => json(page([dataset(1)])))
    render(<SearchPage />)
    await screen.findByRole('table')

    const search = screen.getByRole('searchbox', { name: 'Search' })
    await user.type(search, 'water')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.click(screen.getByRole('button', { name: 'Reset' }))

    expect(search).toHaveValue('')
    await screen.findByRole('table')
    expect(searchCalls(fetch).at(-1)!.searchParams.has('q')).toBe(false)
  })

  it('still works when facets fail to load', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string) =>
        input.endsWith('/facets') ? json({ detail: 'down' }, 503) : json(page([dataset(1)])),
      ),
    )
    render(<SearchPage />)
    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Instrument' })).toHaveTextContent('Any')
  })
})
