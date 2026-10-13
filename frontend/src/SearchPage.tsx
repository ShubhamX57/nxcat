import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { getFacets, searchDatasets } from './api/client'
import type { DatasetPage, Facets, SearchParams } from './api/types'
import { FilterPanel } from './components/FilterPanel'
import { Pagination } from './components/Pagination'
import { ResultsTable } from './components/ResultsTable'
import { EMPTY_FORM, formFromUrl, formToUrl, pageFromUrl, toSearchParams } from './filters'

export const PAGE_SIZE = 20

type Result = { key: string } & (
  | { state: 'error'; message: string }
  | { state: 'done'; data: DatasetPage }
)

export function SearchPage() {
  // The URL is the single source of truth for the applied filters and the page.
  const [url, setUrl] = useSearchParams()
  const applied = formFromUrl(url)
  const page = pageFromUrl(url)
  const appliedKey = formToUrl(applied).toString()

  // The form holds what the user is typing, which may differ from what is applied.
  // When the applied filters change from outside (Back button, a shared link), the
  // form is reset to match them. This is React's "adjust state during render" pattern.
  const [form, setForm] = useState(applied)
  const [formSource, setFormSource] = useState(appliedKey)
  if (formSource !== appliedKey) {
    setFormSource(appliedKey)
    setForm(applied)
  }

  const [result, setResult] = useState<Result | null>(null)
  const [facets, setFacets] = useState<Facets | null>(null)

  // Facets only load once; if they fail, the filters still work with "Any".
  useEffect(() => {
    const controller = new AbortController()
    getFacets(controller.signal)
      .then(setFacets)
      .catch(() => setFacets(null))
    return () => controller.abort()
  }, [])

  // Search again whenever the applied filters or the page change. Aborting the
  // previous request means a slow old response can never overwrite a newer one.
  const request: SearchParams = { ...toSearchParams(applied), page, size: PAGE_SIZE }
  const key = JSON.stringify(request)
  useEffect(() => {
    const controller = new AbortController()
    searchDatasets(JSON.parse(key) as SearchParams, controller.signal)
      .then((data) => setResult({ key, state: 'done', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : 'unknown error'
        setResult({ key, state: 'error', message })
      })
    return () => controller.abort()
  }, [key])

  // A result for an older request means the new one is still loading.
  const current = result?.key === key ? result : null

  return (
    <>
      <FilterPanel
        form={form}
        facets={facets}
        onChange={setForm}
        onSubmit={() => setUrl(formToUrl(form))}
        onReset={() => {
          setForm(EMPTY_FORM)
          setUrl(new URLSearchParams())
        }}
      />
      <section className="results" aria-live="polite" aria-busy={current === null}>
        {current === null && <p className="status">Loading…</p>}
        {current?.state === 'error' && (
          <p className="status error" role="alert">
            Could not load datasets: {current.message}
          </p>
        )}
        {current?.state === 'done' && current.data.total === 0 && (
          <p className="status">No datasets match these filters.</p>
        )}
        {current?.state === 'done' && current.data.total > 0 && (
          <>
            <p className="status">
              Showing {(current.data.page - 1) * current.data.size + 1}–
              {(current.data.page - 1) * current.data.size + current.data.items.length} of{' '}
              {current.data.total} datasets
            </p>
            <ResultsTable items={current.data.items} />
            <Pagination
              page={current.data.page}
              size={current.data.size}
              total={current.data.total}
              onPage={(next) => setUrl(formToUrl(applied, next))}
            />
          </>
        )}
      </section>
    </>
  )
}
