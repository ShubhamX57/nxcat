import type { FormEvent } from 'react'
import type { Facets } from '../api/types'
import type { FilterForm } from '../filters'

interface Props {
  form: FilterForm
  facets: Facets | null
  onChange: (form: FilterForm) => void
  onSubmit: () => void
  onReset: () => void
}

export function FilterPanel({ form, facets, onChange, onSubmit, onReset }: Props) {
  const set = (key: keyof FilterForm) => (value: string) => onChange({ ...form, [key]: value })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form className="filters" aria-label="Search filters" onSubmit={handleSubmit}>
      <label className="field field-wide">
        <span>Search</span>
        <input
          type="search"
          placeholder="title, sample or instrument"
          value={form.q}
          onChange={(e) => set('q')(e.target.value)}
        />
      </label>

      <label className="field">
        <span>Instrument</span>
        <select value={form.instrument} onChange={(e) => set('instrument')(e.target.value)}>
          <option value="">Any</option>
          {facets?.instrument.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.count})
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Technique</span>
        <select value={form.technique} onChange={(e) => set('technique')(e.target.value)}>
          <option value="">Any</option>
          {facets?.technique.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.count})
            </option>
          ))}
        </select>
      </label>

      <fieldset className="field range">
        <legend>Temperature (K)</legend>
        <input
          type="number"
          min={0}
          step="any"
          aria-label="Minimum temperature (K)"
          placeholder="min"
          value={form.tempMin}
          onChange={(e) => set('tempMin')(e.target.value)}
        />
        <span aria-hidden="true">–</span>
        <input
          type="number"
          min={0}
          step="any"
          aria-label="Maximum temperature (K)"
          placeholder="max"
          value={form.tempMax}
          onChange={(e) => set('tempMax')(e.target.value)}
        />
      </fieldset>

      <fieldset className="field range dates">
        <legend>Start date (UTC)</legend>
        <input
          type="date"
          aria-label="From date"
          value={form.dateFrom}
          onChange={(e) => set('dateFrom')(e.target.value)}
        />
        <span aria-hidden="true">–</span>
        <input
          type="date"
          aria-label="To date"
          value={form.dateTo}
          onChange={(e) => set('dateTo')(e.target.value)}
        />
      </fieldset>

      <div className="actions">
        <button type="submit" className="primary">
          Search
        </button>
        <button type="button" onClick={onReset}>
          Reset
        </button>
      </div>
    </form>
  )
}
