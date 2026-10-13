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
