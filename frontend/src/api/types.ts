// Mirrors the response models in backend/src/nxcat/api/schemas.py.

export type Technique =
  | 'QENS'
  | 'INS'
  | 'SANS'
  | 'DIFFRACTION'
  | 'REFLECTOMETRY'
  | 'IMAGING'

export interface Dataset {
  id: number
  title: string
  instrument: string
  technique: Technique
  run_number: number
  sample_name: string
  sample_temperature_k: number | null
  start_time: string
  end_time: string | null
  facility: string | null
  proposal_id: string | null
  file_path: string
  file_size_bytes: number
  checksum: string
  schema_version: string
  ingested_at: string
}

export interface DatasetPage {
  items: Dataset[]
  total: number
  page: number
  size: number
}

export interface Preview {
  dataset_id: number
  x: (number | null)[]
  y: (number | null)[]
  x_label: string
  y_label: string
  original_points: number
  downsampled: boolean
}

export interface FacetCount {
  value: string
  count: number
}

export interface Facets {
  instrument: FacetCount[]
  technique: FacetCount[]
}

/** Query parameters accepted by GET /api/v1/datasets. */
export interface SearchParams {
  q?: string
  instrument?: string
  technique?: string
  temp_min?: number
  temp_max?: number
  start_after?: string
  start_before?: string
  page?: number
  size?: number
}

/** Filters as the API returns them (the same fields as SearchParams, minus paging). */
export type Filters = Omit<SearchParams, 'page' | 'size'>

/** Reply of POST /api/v1/search/ask. It proposes a filter; it never contains results. */
export type AskResponse =
  | { status: 'proposed'; filter: Filters; description: string[] }
  | {
      status: 'rejected'
      kind: 'out_of_scope' | 'unclear' | 'invalid'
      reason: string
      description: string[]
    }

export interface QBin {
  q: number
  hwhm_mev: number
  hwhm_error_mev: number
  eisf: number
}

export interface FickianResult {
  model: string
  diffusion_coefficient: number
  diffusion_coefficient_error: number
  units: string
  reduced_chi_squared: number
  resolution_fwhm_mev: number
  resolution_source: string
  q_bins: QBin[]
  synthetic_truth: number | null
  warnings: string[]
}

/** One qens analysis run, with the settings and software it used. */
export interface Analysis {
  id: number
  dataset_id: number
  method: string
  status: 'queued' | 'running' | 'done' | 'failed'
  parameters: Record<string, number | string | null>
  result: FickianResult | null
  error: string | null
  software: { nxcat?: string; package?: string; version?: string; commit?: string | null; source?: string | null }
  requested_by: string
  created_at: string
  finished_at: string | null
}
