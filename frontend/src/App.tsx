import { Link, Route, Routes } from 'react-router'
import { DatasetPage } from './DatasetPage'
import { SearchPage } from './SearchPage'

export default function App() {
  return (
    <div className="app">
      <header className="masthead">
        <h1>
          <Link to="/">nxcat</Link>
        </h1>
        <p>Find neutron datasets by their metadata.</p>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/datasets/:id" element={<DatasetPage />} />
          <Route path="*" element={<p className="status">Page not found.</p>} />
        </Routes>
      </main>
      <footer className="footer">
        Personal portfolio project, not production software. All data is synthetic.
      </footer>
    </div>
  )
}
