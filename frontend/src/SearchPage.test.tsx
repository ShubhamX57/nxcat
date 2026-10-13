import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Dataset, DatasetPage } from './api/types'
import { PAGE_SIZE } from './SearchPage'
import { FACETS, calls, dataset, fakeApi as fakeRoutes, json } from './test/fakeApi'
import { renderAt } from './test/render'

function page(items: Dataset[], total = items.length, pageNumber = 1): DatasetPage {
  return { items, total, page: pageNumber, size: PAGE_SIZE }
}

/** Facets always succeed; search answers with `searchReply(url)`. */
function fakeApi(searchReply: (url: URL) => Response) {
  return fakeRoutes((url) => (url.pathname === '/api/v1/facets' ? json(FACETS) : searchReply(url)))
}

function searchCalls(fetch: ReturnType<typeof fakeApi>): URL[] {
  return calls(fetch, '/api/v1/datasets')
}

function renderSearch(path = '/') {
  return renderAt(path)
}

describe('SearchPage', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads and shows datasets', async () => {
    fakeApi(() => json(page([dataset(1, { title: 'Benzene QENS 260 K', sample_temperature_k: 260 })])))
    renderSearch()

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
    renderSearch()
    expect(await screen.findByRole('option', { name: 'LET (2)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'INS (1)' })).toBeInTheDocument()
  })

  it('sends the chosen filters when Search is pressed', async () => {
    const user = userEvent.setup()
    const fetch = fakeApi(() => json(page([dataset(1)])))
    renderSearch()
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
    renderSearch()
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
    renderSearch()
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
    renderSearch()
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch')
  })

  it('moves between pages', async () => {
    const user = userEvent.setup()
    const fetch = fakeApi((url) => {
      const n = Number(url.searchParams.get('page') ?? 1)
      return json(page([dataset(n)], 45, n))
    })
    renderSearch()
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
    renderSearch()
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
    renderSearch()
    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Instrument' })).toHaveTextContent('Any')
  })

  it('reads the filters and page from the address', async () => {
    const fetch = fakeApi(() => json(page([dataset(1)], 45, 2)))
    renderSearch('/?q=benzene&instrument=LET&temp_min=200&page=2')

    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Search' })).toHaveValue('benzene')
    const sent = searchCalls(fetch).at(-1)!.searchParams
    expect(sent.get('q')).toBe('benzene')
    expect(sent.get('instrument')).toBe('LET')
    expect(sent.get('temp_min')).toBe('200')
    expect(sent.get('page')).toBe('2')
  })

  it('puts applied filters and the page in the address', async () => {
    const user = userEvent.setup()
    fakeApi((url) => {
      const n = Number(url.searchParams.get('page') ?? 1)
      return json(page([dataset(n)], 45, n))
    })
    renderSearch()
    await screen.findByRole('table')

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'water')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(screen.getByTestId('address')).toHaveTextContent('/?q=water')

    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(screen.getByTestId('address')).toHaveTextContent('/?q=water&page=2')
  })

  it('a new search starts again at page 1', async () => {
    const user = userEvent.setup()
    fakeApi((url) => json(page([dataset(1)], 45, Number(url.searchParams.get('page') ?? 1))))
    renderSearch('/?page=3')
    await screen.findByText('Page 3 of 3')

    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByTestId('address')).toHaveTextContent(/^\/$/)
  })

  it('ignores a nonsense page number in the address', async () => {
    const fetch = fakeApi(() => json(page([dataset(1)])))
    renderSearch('/?page=banana')
    await screen.findByRole('table')
    expect(searchCalls(fetch).at(-1)!.searchParams.get('page')).toBe('1')
  })

  it('links each title to its dataset page', async () => {
    fakeApi(() => json(page([dataset(7, { title: 'Benzene QENS 260 K' })])))
    renderSearch()
    const link = await screen.findByRole('link', { name: 'Benzene QENS 260 K' })
    expect(link).toHaveAttribute('href', '/datasets/7')
  })
})
