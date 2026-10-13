import { act, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Analysis } from '../api/types'
import { calls, dataset, fakeApi, json } from '../test/fakeApi'
import { renderAt } from '../test/render'

const PREVIEW = {
  dataset_id: 7,
  x: [-1, 0, 1],
  y: [1, 9, 1],
  x_label: 'energy (meV)',
  y_label: 'data',
  original_points: 3,
  downsampled: false,
}

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    id: 1,
    dataset_id: 7,
    method: 'qens-fickian',
    status: 'done',
    parameters: { method: 'qens-fickian', q_min: 0.3, q_max: 2.5, n_q_bins: 12 },
    result: {
      model: 'Fickian diffusion, Γ = ħ D Q²',
      diffusion_coefficient: 0.1491,
      diffusion_coefficient_error: 0.0012,
      units: 'angstrom^2/ps',
      reduced_chi_squared: 11.5,
      resolution_fwhm_mev: 0.041209,
      resolution_source: 'instrument resolution recorded in the file',
      q_bins: [
        { q: 0.42, hwhm_mev: 0.0172, hwhm_error_mev: 0.0004, eisf: 0.31 },
        { q: 2.31, hwhm_mev: 0.5231, hwhm_error_mev: 0.0081, eisf: 0.29 },
      ],
      synthetic_truth: 0.15,
      warnings: [],
    },
    error: null,
    software: {
      nxcat: '0.0.1',
      package: 'qens',
      version: '0.1.0',
      commit: 'a7fddd80093e45deb5e46a22611df258ed153533',
      source: 'https://github.com/ShubhamX57/qens',
    },
    requested_by: 'admin',
    created_at: '2026-10-13T10:00:00Z',
    finished_at: '2026-10-13T10:00:01Z',
    ...overrides,
  }
}

function api(technique: string, replies: Analysis[][]) {
  let call = 0
  return fakeApi((url) => {
    if (url.pathname === '/api/v1/datasets/7') return json(dataset(7, { technique: technique as never }))
    if (url.pathname === '/api/v1/datasets/7/preview') return json(PREVIEW)
    if (url.pathname === '/api/v1/datasets/7/analyses') {
      const reply = replies[Math.min(call, replies.length - 1)]
      call += 1
      return json(reply)
    }
    return json({ detail: 'not found' }, 404)
  })
}

afterEach(() => {
  vi.useRealTimers()
})

describe('analyses on the dataset page', () => {
  it('explains how to start one when there are none', async () => {
    api('QENS', [[]])
    renderAt('/datasets/7')
    expect(await screen.findByText(/No analyses yet/)).toHaveTextContent(
      'POST /api/v1/datasets/7/analyses',
    )
  })

  it('shows the result, how it was obtained and the exact software', async () => {
    api('QENS', [[analysis()]])
    renderAt('/datasets/7')
    const card = await screen.findByRole('article', { name: 'Analysis 1' })
    expect(within(card).getByText('D = 0.1491 ± 0.0012 Å²/ps')).toBeInTheDocument()
    expect(within(card).getByText('Synthetic data: generated with D = 0.15 Å²/ps.')).toBeInTheDocument()
    expect(within(card).getByText(/41.21 µeV FWHM \(instrument resolution recorded in the file\)/)).toBeInTheDocument()
    expect(within(card).getByText('0.3–2.5 Å⁻¹, 2 bins')).toBeInTheDocument()
    const commit = within(card).getByRole('link', { name: 'a7fddd8' })
    expect(commit).toHaveAttribute(
      'href',
      'https://github.com/ShubhamX57/qens/commit/a7fddd80093e45deb5e46a22611df258ed153533',
    )
    expect(within(card).getAllByRole('row')).toHaveLength(3) // header + 2 Q-bins
  })

  it('shows warnings and failures plainly', async () => {
    api('QENS', [
      [
        analysis({ id: 2, status: 'failed', result: null, error: 'only 2 Q-bins could be fitted' }),
        analysis({
          id: 1,
          result: { ...analysis().result!, warnings: ['D is likely overestimated'] },
        }),
      ],
    ])
    renderAt('/datasets/7')
    const failed = await screen.findByRole('article', { name: 'Analysis 2' })
    expect(within(failed).getByRole('alert')).toHaveTextContent('Failed: only 2 Q-bins could be fitted')
    expect(
      within(screen.getByRole('article', { name: 'Analysis 1' })).getByText('D is likely overestimated'),
    ).toBeInTheDocument()
  })

  it('refreshes by itself until a running analysis finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetch = api('QENS', [[analysis({ status: 'running', result: null, finished_at: null })], [analysis()]])
    renderAt('/datasets/7')
    expect(await screen.findByText('Running… this page updates by itself.')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100)
    })
    expect(await screen.findByText('D = 0.1491 ± 0.0012 Å²/ps')).toBeInTheDocument()
    const polls = calls(fetch, '/api/v1/datasets/7/analyses').length

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(calls(fetch, '/api/v1/datasets/7/analyses')).toHaveLength(polls) // stopped polling
  })

  it('is not shown for other techniques', async () => {
    const fetch = api('SANS', [[]])
    renderAt('/datasets/7')
    await screen.findByRole('heading', { name: 'Metadata' })
    expect(screen.queryByRole('heading', { name: 'Analyses (qens)' })).not.toBeInTheDocument()
    expect(calls(fetch, '/api/v1/datasets/7/analyses')).toHaveLength(0)
  })
})
