import { vi } from 'vitest'
import type { Dataset, Facets } from '../api/types'

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export const FACETS: Facets = {
  instrument: [
    { value: 'LET', count: 2 },
    { value: 'MARI', count: 1 },
  ],
  technique: [
    { value: 'QENS', count: 2 },
    { value: 'INS', count: 1 },
  ],
}

export function dataset(id: number, overrides: Partial<Dataset> = {}): Dataset {
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

/** Replace fetch with a router: `routes` maps a path to a reply (URL lets you read the query). */
export function fakeApi(route: (url: URL) => Response | Promise<Response>) {
  const fetch = vi.fn(async (input: string) => route(new URL(input, 'http://test')))
  vi.stubGlobal('fetch', fetch)
  return fetch
}

export function calls(fetch: ReturnType<typeof fakeApi>, path: string): URL[] {
  return fetch.mock.calls
    .map(([input]) => new URL(input, 'http://test'))
    .filter((url) => url.pathname === path)
}
