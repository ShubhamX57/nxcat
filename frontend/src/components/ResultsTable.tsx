import { Link, useLocation } from 'react-router'
import type { Dataset } from '../api/types'
import { formatTemperature, formatTime } from '../format'

export function ResultsTable({ items }: { items: Dataset[] }) {
  const { search } = useLocation()
  return (
    <div className="table-wrap">
      <table>
        <caption className="visually-hidden">Matching datasets</caption>
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Instrument</th>
            <th scope="col">Technique</th>
            <th scope="col">Sample</th>
            <th scope="col" className="num">
              Temperature
            </th>
            <th scope="col">Start</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id}>
              <td>
                <Link to={`/datasets/${d.id}`} state={{ search }}>
                  {d.title}
                </Link>
                <span className="run">run {d.run_number}</span>
              </td>
              <td>{d.instrument}</td>
              <td>
                <span className="tag">{d.technique}</span>
              </td>
              <td>{d.sample_name}</td>
              <td className="num">{formatTemperature(d.sample_temperature_k)}</td>
              <td className="nowrap">{formatTime(d.start_time)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
