import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { FACETS, calls, dataset, fakeApi, json } from '../test/fakeApi'
import { renderAt } from '../test/render'

const PROPOSAL = {
  status: 'proposed',
  filter: {
    instrument: 'LET',
    q: 'benzene',
    temp_min: 250,
    start_after: '2025-01-01T00:00:00Z',
    start_before: '2026-01-01T00:00:00Z',
  },
  description: [
    'Instrument is LET',
    'Title, sample or instrument contains "benzene"',
    'Temperature at least 250 K',
    'Started on or after 2025-01-01',
    'Started before 2026-01-01',
  ],
}

function api(askReply: () => Response) {
  return fakeApi((url) => {
    if (url.pathname === '/api/v1/search/ask') return askReply()
    if (url.pathname === '/api/v1/facets') return json(FACETS)
    return json({ items: [dataset(1)], total: 1, page: 1, size: 20 })
  })
}

async function askFor(question: string) {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox', { name: 'Ask in plain English' }), question)
  await user.click(screen.getByRole('button', { name: 'Propose a search' }))
  return user
}

describe('plain-English search', () => {
  it('shows the proposed filter in plain words and does not search yet', async () => {
    const fetch = api(() => json(PROPOSAL))
    renderAt('/')
    await screen.findByRole('table')
    const searchesBefore = calls(fetch, '/api/v1/datasets').length

    await askFor('LET runs on benzene above 250 K from 2025')

    const proposal = await screen.findByRole('region', { name: 'Proposed search' })
    for (const line of PROPOSAL.description) {
      expect(within(proposal).getByText(line)).toBeInTheDocument()
    }
    expect(calls(fetch, '/api/v1/datasets')).toHaveLength(searchesBefore) // nothing ran
    expect(screen.getByTestId('address')).toHaveTextContent(/^\/$/)
  })

  it('runs the proposed search only after the user presses Run', async () => {
    const fetch = api(() => json(PROPOSAL))
    renderAt('/')
    await screen.findByRole('table')
    const user = await askFor('LET benzene')
    await screen.findByRole('region', { name: 'Proposed search' })

    await user.click(screen.getByRole('button', { name: 'Run this search' }))

    expect(screen.getByTestId('address')).toHaveTextContent(
      '/?q=benzene&instrument=LET&temp_min=250&from=2025-01-01&to=2025-12-31',
    )
    await screen.findByRole('table')
    const sent = calls(fetch, '/api/v1/datasets').at(-1)!.searchParams
    expect(sent.get('instrument')).toBe('LET')
    expect(sent.get('start_before')).toBe('2026-01-01T00:00:00Z') // same filter as proposed
    // The proposal is now in the normal filters, where the user can still edit it.
    expect(screen.getByRole('searchbox', { name: 'Search' })).toHaveValue('benzene')
    expect(screen.queryByRole('region', { name: 'Proposed search' })).not.toBeInTheDocument()
  })

  it('Discard throws the proposal away without searching', async () => {
    const fetch = api(() => json(PROPOSAL))
    renderAt('/')
    await screen.findByRole('table')
    const searchesBefore = calls(fetch, '/api/v1/datasets').length
    const user = await askFor('LET benzene')
    await screen.findByRole('region', { name: 'Proposed search' })

    await user.click(screen.getByRole('button', { name: 'Discard' }))
    expect(screen.queryByRole('region', { name: 'Proposed search' })).not.toBeInTheDocument()
    expect(calls(fetch, '/api/v1/datasets')).toHaveLength(searchesBefore)
  })

  it('asks the user to rephrase when the question is rejected', async () => {
    api(() =>
      json({
        status: 'rejected',
        kind: 'out_of_scope',
        reason: 'That is a science question, not a search.',
        description: [],
      }),
    )
    renderAt('/')
    await askFor('What is the diffusion coefficient of water?')
    expect(
      await screen.findByText(
        'That is a science question, not a search. Please rephrase, or use the filters below.',
      ),
    ).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('button', { name: 'Run this search' })).not.toBeInTheDocument()
  })

  it('explains when plain-English search is switched off', async () => {
    api(() => json({ detail: 'plain-English search is not configured on this server' }, 503))
    renderAt('/')
    await askFor('LET runs')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'not configured on this server. You can still use the filters below.',
    )
  })

  it('cannot be submitted empty', () => {
    api(() => json(PROPOSAL))
    renderAt('/')
    expect(screen.getByRole('button', { name: 'Propose a search' })).toBeDisabled()
  })
})
