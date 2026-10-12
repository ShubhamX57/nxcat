import { SearchPage } from './SearchPage'

export default function App() {
  return (
    <div className="app">
      <header className="masthead">
        <h1>nxcat</h1>
        <p>Find neutron datasets by their metadata.</p>
      </header>
      <main>
        <SearchPage />
      </main>
      <footer className="footer">
        Personal portfolio project, not production software. All data is synthetic.
      </footer>
    </div>
  )
}
