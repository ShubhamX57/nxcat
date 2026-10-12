import { describe, expect, it, vi } from 'vitest'
import { ApiError, getFacets, searchDatasets, toQuery } from './client'

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

describe('toQuery', () => {
  it('leaves out empty values', () => {
    expect(toQuery({ q: '', instrument: undefined, temp_min: Number.NaN, page: 2 })).toBe('page=2')
  })

  it('encodes text safely', () => {
    expect(toQuery({ q: 'benzene & toluene' })).toBe('q=benzene+%26+toluene')
  })

  it('keeps zero', () => {
    expect(toQuery({ temp_min: 0 })).toBe('temp_min=0')
  })
})

describe('searchDatasets', () => {
  it('calls the search endpoint with the filters', async () => {
    const fetch = respond(200, { items: [], total: 0, page: 1, size: 20 })
    vi.stubGlobal('fetch', fetch)
    await searchDatasets({ instrument: 'LET', page: 1 })
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/datasets?instrument=LET&page=1')
  })

  it('has no "?" when there are no filters', async () => {
    const fetch = respond(200, { items: [], total: 0, page: 1, size: 20 })
    vi.stubGlobal('fetch', fetch)
    await searchDatasets({})
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/datasets')
  })

  it('turns a validation error into a readable message', async () => {
    vi.stubGlobal(
      'fetch',
      respond(422, {
        detail: [{ msg: 'Value error, temp_min must not be greater than temp_max' }],
      }),
    )
    const error = await searchDatasets({ temp_min: 300, temp_max: 1 }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).message).toBe('temp_min must not be greater than temp_max')
  })

  it('handles an error without a JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502 })))
    await expect(searchDatasets({})).rejects.toThrow('request failed (502)')
  })
})

describe('getFacets', () => {
  it('returns facet counts', async () => {
    const facets = { instrument: [{ value: 'LET', count: 3 }], technique: [] }
    vi.stubGlobal('fetch', respond(200, facets))
    await expect(getFacets()).resolves.toEqual(facets)
  })

  it('passes a string detail through', async () => {
    vi.stubGlobal('fetch', respond(404, { detail: 'not found' }))
    await expect(getFacets()).rejects.toThrow('not found')
  })
})
