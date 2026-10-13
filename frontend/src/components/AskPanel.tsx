import { useState, type FormEvent } from 'react'
import { ApiError, askQuestion } from '../api/client'
import type { Filters } from '../api/types'

type State =
  | { step: 'idle' }
  | { step: 'asking' }
  | { step: 'proposed'; filter: Filters; description: string[] }
  | { step: 'rejected'; reason: string }
  | { step: 'error'; message: string }

interface Props {
  /** Called only when the user confirms the proposal by pressing Run. */
  onRun: (filter: Filters) => void
}

/**
 * Plain-English search. The language model only *proposes* a filter; this panel
 * shows it in plain words, and nothing is searched until the user presses Run.
 */
export function AskPanel({ onRun }: Props) {
  const [question, setQuestion] = useState('')
  const [state, setState] = useState<State>({ step: 'idle' })

  async function handleAsk(event: FormEvent) {
    event.preventDefault()
    if (!question.trim()) return
    setState({ step: 'asking' })
    try {
      const reply = await askQuestion(question.trim())
      if (reply.status === 'proposed') {
        setState({ step: 'proposed', filter: reply.filter, description: reply.description })
      } else {
        setState({ step: 'rejected', reason: reply.reason })
      }
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 503
          ? `${error.message}. You can still use the filters below.`
          : error instanceof Error
            ? error.message
            : 'unknown error'
      setState({ step: 'error', message })
    }
  }

  return (
    <section className="ask" aria-labelledby="ask-title">
      <form onSubmit={handleAsk}>
        <label htmlFor="ask-input" id="ask-title" className="ask-label">
          Ask in plain English
        </label>
        <div className="ask-row">
          <input
            id="ask-input"
            type="text"
            maxLength={300}
            placeholder='e.g. "LET runs on benzene above 250 K from 2025"'
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="submit" disabled={state.step === 'asking' || !question.trim()}>
            {state.step === 'asking' ? 'Thinking…' : 'Propose a search'}
          </button>
        </div>
      </form>

      {state.step === 'proposed' && (
        <div className="proposal" role="region" aria-label="Proposed search">
          <p className="proposal-title">This search will run:</p>
          <ul>
            {state.description.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={() => {
                onRun(state.filter)
                setState({ step: 'idle' })
              }}
            >
              Run this search
            </button>
            <button type="button" onClick={() => setState({ step: 'idle' })}>
              Discard
            </button>
          </div>
          <p className="note">Proposed by a language model. Check it before running.</p>
        </div>
      )}
      {state.step === 'rejected' && (
        <p className="status" role="status">
          {state.reason} Please rephrase, or use the filters below.
        </p>
      )}
      {state.step === 'error' && (
        <p className="status error" role="alert">
          Plain-English search failed: {state.message}
        </p>
      )}
    </section>
  )
}
