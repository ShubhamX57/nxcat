import { useEffect, useState } from 'react'
import { listAnalyses } from '../api/client'
import type { Analysis } from '../api/types'
import { formatNumber, formatTime, formatWithError } from '../format'

const POLL_MS = 2000

type Load = { key: string } & ({ state: 'done'; items: Analysis[] } | { state: 'error'; message: string })

/**
 * qens analyses of one dataset. Starting one needs a login, so it is done through
 * the API; this section shows the stored results and refreshes while one runs.
 */
export function AnalysesSection({ datasetId }: { datasetId: number }) {
  const [load, setLoad] = useState<Load | null>(null)
  const [tick, setTick] = useState(0)
  const key = `${datasetId}:${tick}`

  useEffect(() => {
    const controller = new AbortController()
    listAnalyses(datasetId, controller.signal)
      .then((items) => setLoad({ key, state: 'done', items }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoad({ key, state: 'error', message: error instanceof Error ? error.message : 'unknown error' })
      })
    return () => controller.abort()
  }, [datasetId, key])

  // While an analysis is queued or running, check again every two seconds.
  const pending =
    load?.state === 'done' && load.items.some((a) => a.status === 'queued' || a.status === 'running')
  useEffect(() => {
    if (!pending) return
    const timer = setTimeout(() => setTick((t) => t + 1), POLL_MS)
    return () => clearTimeout(timer)
  }, [pending, load])

  return (
    <section aria-labelledby="analyses">
      <h3 id="analyses">Analyses (qens)</h3>
      {load === null && <p className="status">Loading analyses…</p>}
      {load?.state === 'error' && (
        <p className="status error" role="alert">
          Could not load analyses: {load.message}
        </p>
      )}
      {load?.state === 'done' && load.items.length === 0 && (
        <p className="status">
          No analyses yet. A logged-in user can start one with{' '}
          <code>POST /api/v1/datasets/{datasetId}/analyses</code> (see the API docs).
        </p>
      )}
      {load?.state === 'done' && load.items.map((a) => <AnalysisCard key={a.id} analysis={a} />)}
    </section>
  )
}

function AnalysisCard({ analysis: a }: { analysis: Analysis }) {
  const r = a.result
  const commit = a.software.commit
  return (
    <article className="analysis" aria-label={`Analysis ${a.id}`}>
      <header className="analysis-head">
        <span className={`badge badge-${a.status}`}>{a.status}</span>
        <span>
          {a.method} · started {formatTime(a.created_at)} by {a.requested_by}
        </span>
      </header>

      {(a.status === 'queued' || a.status === 'running') && (
        <p className="status">Running… this page updates by itself.</p>
      )}
      {a.status === 'failed' && (
        <p className="status error" role="alert">
          Failed: {a.error}
        </p>
      )}

      {r && (
        <>
          <p className="headline">
            D = {formatWithError(r.diffusion_coefficient, r.diffusion_coefficient_error)}{' '}
            Å²/ps
          </p>
          {r.synthetic_truth !== null && (
            <p className="note">
              Synthetic data: generated with D = {formatNumber(r.synthetic_truth)} Å²/ps.
            </p>
          )}
          <dl className="meta compact">
            <Row term="Model">{r.model}</Row>
            <Row term="Reduced χ²">{formatNumber(r.reduced_chi_squared)}</Row>
            <Row term="Resolution">
              {formatNumber(r.resolution_fwhm_mev * 1000)} µeV FWHM ({r.resolution_source})
            </Row>
            <Row term="Q range">
              {String(a.parameters.q_min)}–{String(a.parameters.q_max)} Å⁻¹, {r.q_bins.length} bins
            </Row>
          </dl>
          {r.warnings.length > 0 && (
            <ul className="warnings">
              {r.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <details className="data-table">
            <summary>Show the fitted width in each Q-bin ({r.q_bins.length} rows)</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col" className="num">Q (Å⁻¹)</th>
                    <th scope="col" className="num">Γ (meV)</th>
                    <th scope="col" className="num">± (meV)</th>
                    <th scope="col" className="num">EISF</th>
                  </tr>
                </thead>
                <tbody>
                  {r.q_bins.map((b) => (
                    <tr key={b.q}>
                      <td className="num">{formatNumber(b.q)}</td>
                      <td className="num">{formatNumber(b.hwhm_mev)}</td>
                      <td className="num">{formatNumber(b.hwhm_error_mev)}</td>
                      <td className="num">{formatNumber(b.eisf)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}

      <p className="note provenance">
        Software: qens {a.software.version}
        {commit && a.software.source ? (
          <>
            {' '}
            at commit{' '}
            <a href={`${a.software.source}/commit/${commit}`} rel="noreferrer">
              {commit.slice(0, 7)}
            </a>
          </>
        ) : null}
        , nxcat {a.software.nxcat}
        {a.finished_at ? ` · finished ${formatTime(a.finished_at)}` : ''}
      </p>
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
