import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError, getDataset, getPreview } from './api/client'
import type { Dataset, Preview } from './api/types'
import { formatBytes, formatDuration, formatTemperature, formatTime } from './format'
import { AnalysesSection } from './components/AnalysesSection'
import { LinePlot } from './plot/LinePlot'

type Load<T> = { id: number } & ({ state: 'done'; data: T } | { state: 'error'; error: unknown })

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'unknown error'
}

export function DatasetPage() {
  const id = Number(useParams().id)
  const location = useLocation()
  // The search page passes its query string, so "Back" returns to the same results.
  const backTo = `/${(location.state as { search?: string } | null)?.search ?? ''}`
  const [dataset, setDataset] = useState<Load<Dataset> | null>(null)
  const [preview, setPreview] = useState<Load<Preview> | null>(null)

  useEffect(() => {
    if (!Number.isInteger(id) || id < 1) return
    const controller = new AbortController()
    const settle =
      <T,>(set: (value: Load<T>) => void) =>
      (promise: Promise<T>) =>
        promise
          .then((data) => set({ id, state: 'done', data }))
          .catch((error: unknown) => {
            if (!controller.signal.aborted) set({ id, state: 'error', error })
          })
    // Both requests start together; the metadata does not wait for the plot.
    settle(setDataset)(getDataset(id, controller.signal))
    settle(setPreview)(getPreview(id, controller.signal))
    return () => controller.abort()
  }, [id])

  if (!Number.isInteger(id) || id < 1) {
    return <NotFound backTo={backTo} text="This is not a valid dataset address." />
  }

  // Results for an older id mean the new ones are still loading.
  const ds = dataset?.id === id ? dataset : null
  const pv = preview?.id === id ? preview : null

  if (ds === null) return <p className="status">Loading…</p>
  if (ds.state === 'error') {
    if (ds.error instanceof ApiError && ds.error.status === 404) {
      return <NotFound backTo={backTo} text={`Dataset ${id} does not exist.`} />
    }
    return (
      <>
        <BackLink to={backTo} />
        <p className="status error" role="alert">
          Could not load dataset {id}: {message(ds.error)}
        </p>
      </>
    )
  }

  const d = ds.data
  const duration = formatDuration(d.start_time, d.end_time)
  return (
    <article className="dataset">
      <BackLink to={backTo} />
      <header className="dataset-head">
        <h2>{d.title}</h2>
        <p className="subtitle">
          <span className="tag">{d.technique}</span> {d.instrument}
          {d.facility ? ` · ${d.facility}` : ''} · run {d.run_number}
        </p>
      </header>

      <section aria-labelledby="quick-look">
        <h3 id="quick-look">Quick look</h3>
        {pv === null && <p className="status">Loading plot…</p>}
        {pv?.state === 'error' && (
          <p className="status error" role="alert">
            {message(pv.error)}
          </p>
        )}
        {pv?.state === 'done' && (
          <>
            <LinePlot
              x={pv.data.x}
              y={pv.data.y}
              xLabel={pv.data.x_label}
              yLabel={pv.data.y_label}
              title={d.title}
            />
            {pv.data.downsampled && (
              <p className="note">
                Showing {pv.data.x.length} averaged points of {pv.data.original_points}.
              </p>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="metadata">
        <h3 id="metadata">Metadata</h3>
        <dl className="meta">
          <Row term="Sample">{d.sample_name}</Row>
          <Row term="Temperature">{formatTemperature(d.sample_temperature_k)}</Row>
          <Row term="Start">{formatTime(d.start_time)}</Row>
          <Row term="End">{d.end_time ? formatTime(d.end_time) : 'not recorded'}</Row>
          {duration && <Row term="Duration">{duration}</Row>}
          <Row term="Proposal">{d.proposal_id ?? '—'}</Row>
          <Row term="File">
            <code className="break">{d.file_path}</code>
          </Row>
          <Row term="Size">{formatBytes(d.file_size_bytes)}</Row>
          <Row term="SHA-256">
            <code className="break">{d.checksum}</code>
          </Row>
          <Row term="Catalogued">
            {formatTime(d.ingested_at)} (schema v{d.schema_version})
          </Row>
        </dl>
      </section>

      {d.technique === 'QENS' && <AnalysesSection datasetId={d.id} />}
    </article>
  )
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function BackLink({ to }: { to: string }) {
  return (
    <p>
      <Link to={to} className="back">
        ← Back to search
      </Link>
    </p>
  )
}

function NotFound({ backTo, text }: { backTo: string; text: string }) {
  return (
    <>
      <BackLink to={backTo} />
      <p className="status" role="alert">
        {text}
      </p>
    </>
  )
}
