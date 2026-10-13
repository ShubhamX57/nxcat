import type {
  Analysis,
  AskResponse,
  Dataset,
  DatasetPage,
  Facets,
  Preview,
  SearchParams,
} from './types'

const BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Build a query string, leaving out anything empty. */
export function toQuery(params: SearchParams): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (typeof value === 'number' && Number.isNaN(value)) continue
    query.set(key, String(value))
  }
  return query.toString()
}

/** Turn FastAPI's error body into one readable sentence. */
function describeError(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  const { detail } = body as { detail: unknown }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: unknown }) => String(item.msg ?? '').replace(/^Value error, /, ''))
      .filter(Boolean)
      .join('; ')
  }
  return null
}

async function getJson<T>(path: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    signal,
    headers: { Accept: 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, describeError(body) ?? `request failed (${response.status})`)
  }
  return (await response.json()) as T
}

export function searchDatasets(params: SearchParams, signal?: AbortSignal): Promise<DatasetPage> {
  const query = toQuery(params)
  return getJson<DatasetPage>(`/datasets${query ? `?${query}` : ''}`, signal)
}

export function getFacets(signal?: AbortSignal): Promise<Facets> {
  return getJson<Facets>('/facets', signal)
}

export function getDataset(id: number, signal?: AbortSignal): Promise<Dataset> {
  return getJson<Dataset>(`/datasets/${id}`, signal)
}

export function getPreview(id: number, signal?: AbortSignal): Promise<Preview> {
  return getJson<Preview>(`/datasets/${id}/preview`, signal)
}

export function askQuestion(question: string, signal?: AbortSignal): Promise<AskResponse> {
  return getJson<AskResponse>('/search/ask', signal, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export function listAnalyses(datasetId: number, signal?: AbortSignal): Promise<Analysis[]> {
  return getJson<Analysis[]>(`/datasets/${datasetId}/analyses`, signal)
}
